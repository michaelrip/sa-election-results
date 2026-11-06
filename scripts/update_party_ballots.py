"""Fetch separately counted municipal PR and district PR ballots via ESP.

The ward importer remains authoritative for Ward ballots. Party counts in this
feed come only from validated numbered ballot rows, never from a headline or
rounded percentage. An absent/stale source is reported, not fabricated.
"""
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fetch_results import CITIES, get

OUTPUT = Path("ballots.json")
STATUS = Path("ballot-status.json")
HOSTS = ("https://go.esp.info/elections/local/2026/",
         "https://esp.info/elections/local/2026/",
         "https://zero.esp.info/elections/local/2026/")
CANONICAL = {
    "Democratic Alliance": "DA", "African National Congress": "ANC",
    "Economic Freedom Fighters": "EFF", "Patriotic Alliance": "PA",
    "ActionSA": "ActionSA", "Vryheidsfront Plus": "FF+",
    "Freedom Front Plus": "FF+", "VF PLUS": "FF+",
    "Umkhonto Wesizwe Party": "MK", "Inkatha Freedom Party": "IFP",
    "African Christian Democratic Party": "ACDP", "Al Jama-ah": "Al Jama-ah",
    "Home of Independence": "H.O.I.", "National Coloured Congress": "CCC",
    "Rise Mzansi": "RISE", "United Democratic Movement": "UDM",
    "African Transformation Movement": "ATM", "Build One South Africa": "BOSA",
    "South African Communist Party": "SACP", "Land Party": "LAND",
    "Congress of the People": "COPE", "National Freedom Party": "NFP",
    "Cape Independence Party": "CAPEXIT", "Africa Restoration Alliance": "ARA",
    "People's Movement for Change": "PMC", "Pan Africanist Congress of Azania": "PAC",
    "United Independent Movement": "UIM", "Sizwe Ummah Nation": "SUN",
    "Organic Humanity Movement": "OHM", "Cape Muslim Congress": "CMC",
    "Democratic People's Alternative": "DPA", "Operation Dudula": "OD",
    "African Independent Congress": "AIC",
    "DA": "DA", "ANC": "ANC", "EFF": "EFF", "PA": "PA", "MKP": "MK",
    "IFP": "IFP", "ACDP": "ACDP", "GOOD": "GOOD", "ALJAMA": "Al Jama-ah",
    "RISE": "RISE", "ATM": "ATM", "UDM": "UDM", "BOSA": "BOSA", "SACP": "SACP",
    "CCC": "CCC", "H.O.I.": "H.O.I.", "D.P.A": "DPA",
    "VF+": "FF+", "CAPEXIT": "CAPEXIT", "PMC": "PMC", "PAC": "PAC",
    "AIC": "AIC", "UIM": "UIM", "ARA": "ARA", "NFP": "NFP",
    "LAND": "LAND", "CMC": "CMC", "COPE": "COPE",
}
ORDERED = sorted(CANONICAL.items(), key=lambda x: -len(x[0]))
TSTAMP = re.compile(r"IEC data last fetched\s+(\d{1,2}\s+\w+\s+2026,\s*\d{2}:\d{2})\s*SAST")
ROW = re.compile(r"(?<!\d)(\d{1,3}(?:\s+\d{3})*)\s+(\d{1,3}\.\d)\s*%")
ENDBLOCK = re.compile(r"\b(?:How did (?:City of|Overstrand)|Wards\s*[·•]|About these figures|District councils\s*[·•])\b", re.I)
TYPE_LABELS = {"pr": "PR ballot", "dc": "DC 40% ballot"}


def parsed_time(source: str, now: datetime) -> str:
    match = TSTAMP.search(source)
    if not match:
        raise ValueError("IEC timestamp missing")
    for fmt in ("%d %b %Y, %H:%M", "%d %B %Y, %H:%M"):
        try:
            dt = datetime.strptime(match.group(1), fmt).replace(
                tzinfo=timezone(timedelta(hours=2))).astimezone(timezone.utc)
            if dt > now + timedelta(minutes=12) or now - dt > timedelta(hours=24):
                raise ValueError("Source timestamp is stale or in the future")
            return dt.isoformat()
        except ValueError as err:
            if "stale or in the future" in str(err):
                raise
    raise ValueError("Unrecognised IEC timestamp")


def party_name(fragment: str) -> str | None:
    # The HTML parser often renders image logos as ImageDA, ImageEFF, etc.
    # Check longest formal party names first to avoid short-code overlap.
    for label, code in ORDERED:
        if re.search(r"(?<![A-Za-z])" + re.escape(label) + r"(?![A-Za-z])", fragment, re.I):
            return code
    return None


def parse_ballot(source: str, city: str, ballot: str, url: str, now: datetime) -> dict:
    if ballot not in TYPE_LABELS or (ballot == "dc" and city != "Hermanus"):
        raise ValueError("Unsupported ballot type for this municipality")
    muni = "Overstrand" if city == "Hermanus" else ("Nelson Mandela Bay" if city == "Nelson Mandela Bay" else "City of " + city)
    if muni not in source or "2026" not in source:
        raise ValueError("Wrong election year or municipality")
    when = parsed_time(source, now)
    label = TYPE_LABELS[ballot]
    header = re.search(re.escape(label) + r"\s*\??\s*[·•]?\s*([\d\s]+)\s+valid votes\b", source, re.I)
    if not header:
        raise ValueError("No source-confirmed " + label + " vote table")
    valid_votes = int(re.sub(r"\D", "", header.group(1)))
    if valid_votes <= 0:
        raise ValueError("No published valid votes for " + label)
    text = source[header.end():]
    stop = ENDBLOCK.search(text)
    text = text[:stop.start()] if stop else text[:18000]
    parties = []
    prev = 0
    for row in ROW.finditer(text):
        fragment = text[prev:row.start()][-220:]
        prev = row.end()
        name = party_name(fragment)
        votes = int(re.sub(r"\s", "", row.group(1)))
        share = float(row.group(2))
        if not name or any(p["name"] == name for p in parties):
            continue
        if not 0 <= share <= 100 or votes > valid_votes:
            continue
        if abs(100 * votes / valid_votes - share) > .21:
            continue
        parties.append({"name": name, "votes": votes, "share": share})
    known = sum(x["votes"] for x in parties)
    if len(parties) < 3 or known > valid_votes or known < valid_votes * .70:
        raise ValueError("Missing/contradictory source party rows")
    parties.sort(key=lambda p: (-p["votes"], p["name"]))
    return {
        "ballot_type": "PR" if ballot == "pr" else "District PR",
        "source_url": url,
        "snapshot_at": when,
        "valid_votes": valid_votes,
        "parties": parties,
        "unlisted_votes": valid_votes - known,
        "note": "Other/unlisted votes equal source total minus individually validated named party votes.",
    }


def try_ballot(city: str, ballot: str, now: datetime) -> dict:
    slug = CITIES[city][0]
    last_errors = []
    for host in HOSTS:
        url = host + slug + "?ballot=" + ballot
        try:
            return parse_ballot(get(url), city, ballot, url, now)
        except (ValueError, TimeoutError, OSError) as err:
            last_errors.append(host.split("//")[1].split("/")[0]+": "+str(err)[:110])
    raise ValueError("; ".join(last_errors)[:370])


def main():
    now = datetime.now(timezone.utc)
    report = {"checked_at": now.isoformat(), "source": "ESP individual 2026 PR and DC 40% ballot pages", "checks": {}, "status": "partial"}
    old = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {"metros": {}}
    result = {"updated_at": now.isoformat(), "source": "IEC-derived via ESP: separate validated ballot pages", "metros": {}}
    successes = 0
    for city in CITIES:
        result["metros"][city] = {}
        report["checks"][city] = {}
        for typ in (("pr", "dc") if city == "Hermanus" else ("pr",)):
            try:
                current = try_ballot(city, typ, now)
                previous = old.get("metros", {}).get(city, {}).get(typ)
                if previous and previous.get("snapshot_at") and current["snapshot_at"] < previous["snapshot_at"]:
                    raise ValueError("IEC source snapshot regressed")
                result["metros"][city][typ] = current
                report["checks"][city][typ] = {"status": "ok", "valid_votes": current["valid_votes"], "snapshot_at": current["snapshot_at"]}
                successes += 1
            except Exception as err:
                report["checks"][city][typ] = {"status": "unavailable", "detail": str(err)[:370]}
                # Do not display old PR/DC data as live when the source stops updating.
                oldrow = old.get("metros", {}).get(city, {}).get(typ)
                if oldrow:
                    try:
                        stamp = datetime.fromisoformat(oldrow["snapshot_at"])
                        if now - stamp <= timedelta(minutes=90) and stamp <= now:
                            result["metros"][city][typ] = oldrow
                            report["checks"][city][typ]["status"] = "cached"
                    except (ValueError, KeyError, TypeError):
                        pass
    report["status"] = "ok" if successes == 6 else "partial"
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    STATUS.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
