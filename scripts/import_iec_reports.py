"""Import DIRECT official IEC LGE public-report CSVs, without using ESP.

2026: requires the verified IEC election-report ID (IEC_2026_EVENT_ID).
2021: official IEC LGE report ID is 1091.
The public report URL is results.elections.org.za/home/LGEPublicReports/{ID}/
Downloadable%20Party%20Results/{PROVINCE}/{MUNICIPALITY}.csv

This importer deliberately never substitutes an ESP page, browser scrape,
ballot-type guess, percentage estimate or unverified partial municipality.
A missing 2026 report leaves the existing live site untouched.
"""
from __future__ import annotations
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPORT_HOST = "https://results.elections.org.za/home/LGEPublicReports"
CITIES = {
    "Cape Town": ("WP", "CPT", 118, ("cpt", "city of cape town", "cape town")),
    "Tshwane": ("GP", "TSH", 107, ("tsh", "city of tshwane", "tshwane")),
    "Johannesburg": ("GP", "JHB", 135, ("jhb", "city of johannesburg", "johannesburg")),
    "Hermanus": ("WP", "WC032", 15, ("wc032", "overstrand", "overstrand local municipality")),
}
PARTY_NAMES = {
    "DEMOCRATIC ALLIANCE": "DA",
    "AFRICAN NATIONAL CONGRESS": "ANC",
    "ECONOMIC FREEDOM FIGHTERS": "EFF",
    "PATRIOTIC ALLIANCE": "PA",
    "ACTIONSA": "ActionSA",
    "VRYHEIDSFRONT PLUS": "FF+",
    "FREEDOM FRONT PLUS": "FF+",
    "VF PLUS": "FF+",
    "INKATHA FREEDOM PARTY": "IFP",
    "UMKHONTO WESIZWE": "MK",
    "UMKHONTO WESIZWE PARTY": "MK",
    "AFRICAN CHRISTIAN DEMOCRATIC PARTY": "ACDP",
    "GOOD": "GOOD",
    "AL JAMA-AH": "Al Jama-ah",
    "AL JAMA AH": "Al Jama-ah",
    "LAND PARTY": "LAND",
    "HOME OF INDEPENDENCE": "H.O.I.",
    "RISE MZANSI": "RISE",
    "NATIONAL COLOURED CONGRESS": "CCC",
    "UNITED DEMOCRATIC MOVEMENT": "UDM",
}
COLUMN_KEYS = ("PROVINCE", "MUNICIPALITY", "WARD", "VOTINGDISTRICT",
               "BALLOTTYPE", "PARTYNAME", "TOTALVALIDVOTES")
MAX_DOWNLOAD = 22_000_000  # each municipality report should be well under this
MIN_ROWS = 1


class ImportErrorIEC(ValueError):
    """IEC source data did not pass strict source/shape checks."""


def report_url(year: int, event_id: int, city: str) -> str:
    if year not in (2021, 2026) or int(event_id) <= 0:
        raise ImportErrorIEC("Unexpected election year or IEC report ID")
    prov, muni, _, _ = CITIES[city]
    return (f"{REPORT_HOST}/{event_id}/Downloadable%20Party%20Results/"
            f"{prov}/{muni}.csv")


def download_report(url: str) -> bytes:
    if not url.startswith(REPORT_HOST + "/") or not url.endswith(".csv"):
        raise ImportErrorIEC("Not a direct official IEC CSV report")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; municipal-results/1.0)",
        "Accept": "text/csv,text/plain,*/*",
    })
    with urllib.request.urlopen(req, timeout=45) as response:
        if response.status != 200:
            raise ImportErrorIEC(f"IEC report HTTP {response.status}")
        payload = response.read(MAX_DOWNLOAD + 1)
    if len(payload) > MAX_DOWNLOAD:
        raise ImportErrorIEC("IEC report exceeded the permitted data size")
    if payload.lstrip()[:40].lower().startswith((b"<!doctype", b"<html", b"<?xml")):
        raise ImportErrorIEC("IEC returned HTML/XML instead of report CSV")
    return payload


def normalized(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def read_int(v: str) -> int:
    val = str(v).strip().replace(" ", "").replace("\u00a0", "").replace(",", "")
    if not re.fullmatch(r"\d+", val):
        raise ImportErrorIEC("Invalid source vote count")
    number = int(val)
    if number > 100_000_000:
        raise ImportErrorIEC("Vote count outside reasonable bounds")
    return number


def ward_number(raw: str, maximum: int) -> int:
    text = str(raw).strip()
    found = re.search(r"(\d{1,3})$", text)
    if not found:
        raise ImportErrorIEC("IEC row has no recognised ward identifier")
    number = int(found.group(1))
    if not 1 <= number <= maximum:
        raise ImportErrorIEC("Ward number outside published 2026 municipality")
    return number


def decode(payload: bytes) -> str:
    if not isinstance(payload, bytes):
        raise ImportErrorIEC("IEC report was not received as bytes")
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        return payload.decode("utf-16")
    return payload.decode("utf-8-sig")


def party_label(name: str) -> str:
    label = " ".join(str(name).strip().split())
    if not 2 <= len(label) <= 160 or any(c in label for c in "<>"):
        raise ImportErrorIEC("Invalid IEC party name")
    return PARTY_NAMES.get(label.upper(), label)


def parse_csv(payload: bytes, city: str, year: int) -> dict:
    """Read only *Ward* ballot party-vote rows, not PR/seat figures."""
    if year not in (2021, 2026) or city not in CITIES:
        raise ImportErrorIEC("Unsupported election or municipality")
    prov, muni, nwards, aliases = CITIES[city]
    raw = decode(payload)
    reader = csv.DictReader(io.StringIO(raw, newline=""))
    if not reader.fieldnames:
        raise ImportErrorIEC("No IEC party report CSV header")
    columns = {normalized(col): col for col in reader.fieldnames if col}
    if not set(COLUMN_KEYS).issubset(columns):
        raise ImportErrorIEC("Official IEC report columns not recognised; no source guessing")
    totals = defaultdict(int)
    wards = defaultdict(lambda: defaultdict(int))
    vd_by_ward = defaultdict(set)
    observed = set()
    seen_rows = set()
    count = 0
    for line in reader:
        if not any(line.values()):
            continue
        get = lambda k: str(line.get(columns[k]) or "").strip()
        if normalized(get("BALLOTTYPE")) != "WARD":
            continue  # never mix PR ballot with ward ballot
        raw_muni = " ".join(get("MUNICIPALITY").lower().split())
        # IEC's public CSV identifies a municipality as "JHB - City of
        # Johannesburg" rather than just "JHB" or its formal name.
        if " - " in raw_muni:
            code, name = raw_muni.split(" - ", 1)
            valid_municipality = code == muni.lower() and name in aliases
        else:
            valid_municipality = raw_muni in aliases
        if not valid_municipality:
            raise ImportErrorIEC("Downloaded report is for a different municipality: " + repr(raw_muni[:80]))
        ward = ward_number(get("WARD"), nwards)
        district = get("VOTINGDISTRICT")
        if not re.fullmatch(r"\d{6,12}", district):
            raise ImportErrorIEC("Missing or invalid IEC voting-district number")
        name = party_label(get("PARTYNAME"))
        votes = read_int(get("TOTALVALIDVOTES"))
        ident = (ward, district, name)
        if ident in seen_rows:
            raise ImportErrorIEC("Duplicate IEC vote row; would double-count votes")
        seen_rows.add(ident)
        totals[name] += votes
        wards[ward][name] += votes
        if votes > 0:
            vd_by_ward[ward].add(district)
        count += 1
    if count < MIN_ROWS or not totals or sum(totals.values()) <= 0:
        raise ImportErrorIEC("No valid IEC Ward-ballot party vote results")
    total = sum(totals.values())
    if total > 100_000_000:
        raise ImportErrorIEC("Unexpected overall vote total")
    party_rows = [{"name": name, "share": round(100 * votes / total, 1), "votes": votes}
                  for name, votes in sorted(totals.items(), key=lambda p: (-p[1], p[0]))
                  if votes > 0]
    total_vds = set().union(*vd_by_ward.values()) if vd_by_ward else set()
    return {
        "total_votes": total,
        "party_rows": party_rows,
        "wards": {
            i: {
                "valid_votes": sum(wards[i].values()),
                "parties": [{"name": name, "share": round(100 * v / sum(wards[i].values()), 1), "votes": v}
                            for name, v in sorted(wards[i].items(), key=lambda p: (-p[1], p[0]))
                            if v > 0] if sum(wards[i].values()) else [],
                "vds_with_votes": len(vd_by_ward[i]),
            } for i in range(1, nwards + 1)
        },
        "reported_vds": len(total_vds),
    }



def parse_pr_csv(payload: bytes, city: str, year: int) -> dict:
    """Aggregate *municipal party-list PR* only, excluding Ward and District PR.

    Official 2021 CSVs contain a separate row for each party in each voting
    district. Do not use the Ward number as a requirement for PR: the results
    are compared at whole-municipality level, not to 2026 ward boundaries.
    """
    if year != 2021 or city not in CITIES:
        raise ImportErrorIEC("Only the official 2021 municipal PR history is supported")
    _, muni, _, aliases = CITIES[city]
    reader = csv.DictReader(io.StringIO(decode(payload), newline=""))
    if not reader.fieldnames:
        raise ImportErrorIEC("No official IEC CSV header")
    cols = {normalized(col): col for col in reader.fieldnames if col}
    required = {"MUNICIPALITY", "BALLOTTYPE", "PARTYNAME",
                "VOTINGDISTRICT", "TOTALVALIDVOTES"}
    if not required.issubset(cols):
        raise ImportErrorIEC("Official IEC PR columns not recognised")
    totals = defaultdict(int)
    seen = set()
    ballot_labels = set()
    districts = set()
    for row in reader:
        if not any(row.values()):
            continue
        val = lambda k: str(row.get(cols[k]) or "").strip()
        typ = normalized(val("BALLOTTYPE"))
        ballot_labels.add(typ)
        if typ != "PR":
            continue  # explicitly exclude Ward and DC 40% ballots
        raw_muni = " ".join(val("MUNICIPALITY").lower().split())
        if " - " in raw_muni:
            code, name = raw_muni.split(" - ", 1)
            correct = code == muni.lower() and name in aliases
        else:
            correct = raw_muni in aliases
        if not correct:
            raise ImportErrorIEC("Different municipality in PR rows: " + repr(raw_muni[:70]))
        district = val("VOTINGDISTRICT")
        if not re.fullmatch(r"\d{6,12}", district):
            raise ImportErrorIEC("Invalid voting-district identifier in PR rows")
        party = party_label(val("PARTYNAME"))
        ident = (district, party)
        if ident in seen:
            raise ImportErrorIEC("Duplicate IEC municipal PR result row")
        seen.add(ident)
        votes = read_int(val("TOTALVALIDVOTES"))
        totals[party] += votes
        districts.add(district)
    total_votes = sum(totals.values())
    if not totals or total_votes <= 0:
        raise ImportErrorIEC(
            "2021 municipal PR rows missing (ballot labels: " +
            ", ".join(sorted(ballot_labels)[:10]) + ")")
    return {
        "total_votes": total_votes,
        "party_rows": [
            {"name": name, "share": round(votes * 100 / total_votes, 1),
             "votes": votes}
            for name, votes in sorted(totals.items(), key=lambda p: (-p[1], p[0]))
            if votes > 0
        ],
        "reported_vds": len(districts),
        "ballot_type": "PR",
    }


def historic_combined(ward: dict, pr: dict) -> dict:
    """Compute 2021 Ward+municipal-PR shares from exact integer votes.

    Rounded percentages must NEVER be used as weights or interpreted as votes.
    """
    if not ward or not pr:
        raise ImportErrorIEC("Both 2021 ballot types are required")
    total = ward["total_votes"] + pr["total_votes"]
    if total <= 0:
        raise ImportErrorIEC("No valid 2021 ballots to combine")
    sums = defaultdict(int)
    for ballot in (ward, pr):
        if sum(p["votes"] for p in ballot["party_rows"]) != ballot["total_votes"]:
            raise ImportErrorIEC("Incomplete historical party rows")
        for row in ballot["party_rows"]:
            sums[row["name"]] += row["votes"]
    if sum(sums.values()) != total:
        raise ImportErrorIEC("Historical combined valid vote totals disagree")
    return {
        "valid_votes": total,
        "parties": {name: round(100 * votes / total, 1)
                    for name, votes in sums.items() if votes > 0},
        "votes": dict(sums),
        "ballot_type": "Ward + PR",
        "note": "Two municipal ballot papers per voter (when both valid), not unique voters",
    }

def build_results(parsed: dict, urls: dict, event_id: int) -> dict:
    if set(parsed) != set(CITIES):
        raise ImportErrorIEC("All four municipality reports must validate before publication")
    checked = datetime.now(timezone.utc).isoformat()
    metros = {}
    for city, (_, _, nwards, _) in CITIES.items():
        x = parsed[city]
        entries = []
        for n in range(1, nwards + 1):
            w = x["wards"][n]
            number = w["vds_with_votes"]
            entries.append({
                "number": n,
                "status": "Preliminary" if number else "Not yet reported",
                "ballot_type": "Ward",
                # The public party CSV omits how many VDs *should* be in each ward.
                "reporting": f"{number} voting districts with votes (IEC report)" if number
                             else "Not yet reported",
                "parties": w["parties"][:3],
                "valid_votes": w["valid_votes"] if number else None,
                "snapshot_at": None,
                "source_url": urls[city],
            })
        metros[city] = {
            "status": "Preliminary · directly from IEC public CSV",
            "municipality": "Overstrand Local Municipality" if city == "Hermanus" else city,
            "ballot_type": "Ward",
            "districts_reported": x["reported_vds"],
            "districts_total": None,  # not in this IEC CSV report
            "valid_votes": x["total_votes"],
            "parties": x["party_rows"],
            "seats": [],
            "wards": entries,
            "snapshot_at": None,  # never invent an official capture timestamp
            "source_url": urls[city],
        }
    return {
        "updated_at": checked,
        "source": "IEC direct public reports · ward ballot only",
        "source_type": "iec_public_csv",
        "source_verified": True,
        "election_year": 2026,
        "iec_event_id": event_id,
        "download_checked_at": checked,
        "metros": metros,
    }


def build_history(parsed: dict, urls: dict, pr_parsed: dict | None = None) -> dict:
    checked = datetime.now(timezone.utc).isoformat()
    cities = {}
    for city, ward in parsed.items():
        ward_votes = {p["name"]: p["votes"] for p in ward["party_rows"]}
        item = {
            "ballot_type": "Ward", "year": 2021,
            "valid_votes": ward["total_votes"],
            "parties": {p["name"]: p["share"] for p in ward["party_rows"]},
            "votes": ward_votes, "source_url": urls[city], "wards": {},
        }
        if pr_parsed and city in pr_parsed:
            pr = pr_parsed[city]
            if not pr.get("party_rows") or pr["total_votes"] <= 0:
                raise ImportErrorIEC("2021 municipal PR ballot rows are missing")
            item["pr"] = {
                "year": 2021, "ballot_type": "PR",
                "valid_votes": pr["total_votes"],
                "parties": {p["name"]: p["share"] for p in pr["party_rows"]},
                "votes": {p["name"]: p["votes"] for p in pr["party_rows"]},
                "source_url": urls[city],
            }
            item["combined"] = historic_combined(ward, pr)
            item["combined"]["year"] = 2021
            item["combined"]["source_url"] = urls[city]
        cities[city] = item
    return {
        "year": 2021, "ballot_type": "Ward",
        "source": "IEC direct public 2021 ward and municipal PR ballot CSV reports",
        "source_verified": True, "checked_at": checked,
        "notes": "Whole-municipality Ward and municipal PR votes. Ward+PR counts ballot papers, not unique voters. District PR excluded; 2021 ward boundaries are not directly comparable with 2026 wards.",
        "metros": cities,
    }


def main() -> None:
    status_path = Path("iec-source-status.json")
    previous = json.loads(status_path.read_text()) if status_path.exists() else {}
    now = datetime.now(timezone.utc).isoformat()
    report = {"checked_at": now, "source": "Direct official IEC downloadable Ward-ballot CSVs",
              "status": "not_configured", "checks": {}}
    raw_event = os.getenv("IEC_2026_EVENT_ID", "").strip()
    if not re.fullmatch(r"\d{1,8}", raw_event):
        report["note"] = ("The IEC 2026 local-government public-report electoral event ID "
                          "has not been configured. Live ESP results are not re-labelled.")
        status_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        return
    year = 2026
    event_id = int(raw_event)
    if event_id == 1091:
        raise ImportErrorIEC("2021 IEC event ID was mistakenly set as the 2026 event")
    parsed, urls = {}, {}
    for city in CITIES:
        url = report_url(year, event_id, city)
        try:
            parsed[city] = parse_csv(download_report(url), city, year)
            urls[city] = url
            report["checks"][city] = {"status": "ok",
                "valid_votes": parsed[city]["total_votes"],
                "ward_rows_with_votes": sum(bool(w["parties"]) for w in parsed[city]["wards"].values())}
        except Exception as error:
            report["checks"][city] = {"status": "error", "detail": str(error)[:180]}
    if set(parsed) == set(CITIES):
        result = build_results(parsed, urls, event_id)
        Path("results-iec.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        report["status"] = "ok"
        report["note"] = "All four 2026 municipality reports validated against official IEC host."
    else:
        report["status"] = "unavailable"
        report["note"] = ("Direct IEC CSV was not available for every location; "
                          "existing published data was left unchanged. No ESP fallback in this importer.")
    status_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report))
    if report["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
