"""Safely import top-three preliminary WARD ballot parties from individual ESP ward pages.

ESP metro pages contain only the ward's *leader* in their ward summaries.
Read each ward's own Ward-ballot table to show 2nd/3rd party truthfully.
Never derive opponents from metro-wide percentages. A failure leaves existing
validated detail intact, but the browser displays it ONLY while it matches
the current metro summary's leading party, share and district count.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fetch_results import get

RESULTS = Path("results.json")
DETAILS = Path("ward-details.json")
STATUS = Path("ward-detail-status.json")
METROS = ("Cape Town", "Tshwane", "Johannesburg", "Nelson Mandela Bay", "Hermanus")
MAX_REQUESTS = 180  # cap requests per scheduled run; retry unfilled wards next run
WORKERS = 8
NAME_TO_CODE = {
    "Democratic Alliance": "DA", "African National Congress": "ANC",
    "Patriotic Alliance": "PA", "Economic Freedom Fighters": "EFF",
    "ActionSA": "ActionSA", "Freedom Front Plus": "FF+",
    "Vryheidsfront Plus": "FF+", "Umkhonto Wesizwe Party": "MK",
    "Inkatha Freedom Party": "IFP",
    "African Christian Democratic Party": "ACDP",
    "Al Jama-ah": "Al Jama-ah", "Home of Independence": "H.O.I.",
    "Rise Mzansi": "RISE", "National Coloured Congress": "CCC",
    "United Democratic Movement": "UDM", "African Transformation Movement": "ATM",
    "Build One South Africa": "BOSA", "South African Communist Party": "SACP",
    "Democratic People's Alternative": "DPA", "Pan Africanist Congress of Azania": "PAC",
    "Cape Independence Party": "CAPEXIT", "Truth and Solidarity Movement": "TRUTH",
    "Independent": "Independent", "Land Party": "LAND", "LAND": "LAND",
    "VF PLUS": "FF+", "ALJAMA": "Al Jama-ah", "MKP": "MK",
    "GOOD": "GOOD", "DA": "DA", "ANC": "ANC", "PA": "PA", "EFF": "EFF",
    "IFP": "IFP", "ACDP": "ACDP", "RISE": "RISE",
    "CCC": "CCC", "UDM": "UDM", "ATM": "ATM", "BOSA": "BOSA",
    "SACP": "SACP", "H.O.I.": "H.O.I.",
}
SORTED_LABELS = sorted(NAME_TO_CODE.items(), key=lambda kv: -len(kv[0]))
ROW_PATTERN = re.compile(r"(?<!\d)(\d{1,3}(?:\s+\d{3})*)\s+(\d{1,3}\.\d)\s*%")
HEADER_PATTERN = re.compile(r"Ward ballot\s*\?\s*[·•]?\s*([\d\s]+)\s+valid votes")
TIMESTAMP_PATTERN = re.compile(r"IEC data last fetched\s+(\d{1,2}\s+\w+\s+2026,\s*\d{2}:\d{2})\s*SAST")


def source_time(source: str, now: datetime) -> str:
    m = TIMESTAMP_PATTERN.search(source)
    if not m:
        raise ValueError("Missing IEC-source timestamp")
    for fmt in ("%d %b %Y, %H:%M", "%d %B %Y, %H:%M"):
        try:
            stamp = datetime.strptime(m.group(1), fmt).replace(tzinfo=timezone(timedelta(hours=2)))
            stamp = stamp.astimezone(timezone.utc)
            if now - timedelta(hours=24) > stamp or stamp > now + timedelta(minutes=12):
                raise ValueError("Ward source timestamp is stale or in future")
            return stamp.isoformat()
        except ValueError as error:
            if "stale or in future" in str(error):
                raise
    raise ValueError("Unrecognised IEC timestamp")


def party_name(prefix: str) -> str | None:
    # ESP uses ImageDA / ImageANC with no separator before the logo alt text.
    prefix = prefix.replace("Image", " ")
    for label, code in SORTED_LABELS:
        if re.search(r"(?<![A-Za-z])" + re.escape(label) + r"(?![A-Za-z])", prefix, re.I):
            return code
    return None


def source_url_for(ward: dict) -> str:
    url = str(ward.get("source_url") or "")
    if not url.startswith("https://go.esp.info/elections/local/2026/"):
        raise ValueError("Unexpected ward URL origin")
    if not re.search(r"/ward-\d{1,3}$", url):
        raise ValueError("Source URL does not identify a ward")
    return url


def valid_candidate(current: dict, detail: dict, now: datetime) -> bool:
    """True only if saved parties still match the latest metro ward summary."""
    if not isinstance(current, dict) or not isinstance(detail, dict):
        return False
    current_parts = current.get("parties") or []
    parties = detail.get("parties") or []
    if not current_parts or len(parties) < 2:
        return False
    if current.get("reporting") != detail.get("reporting"):
        return False
    if str(current_parts[0].get("name")) != str(parties[0].get("name")):
        return False
    if abs(float(current_parts[0].get("share", -100)) - float(parties[0].get("share", 100))) > 0.21:
        return False
    if not all(
        isinstance(p.get("name"), str) and isinstance(p.get("share"), (float, int))
        and 0 <= p["share"] <= 100 and isinstance(p.get("votes"), int) and p["votes"] >= 0
        for p in parties[:3]
    ):
        return False
    try:
        stamp = datetime.fromisoformat(detail["source_at"]).astimezone(timezone.utc)
    except (ValueError, KeyError, TypeError):
        return False
    return now - timedelta(hours=24) <= stamp <= now + timedelta(minutes=12)


def parse_ward_page(source: str, metro: str, number: int, current: dict, now: datetime) -> dict:
    if not re.search(r"\bWard\s+" + re.escape(str(number)) + r"\b", source):
        raise ValueError("Wrong ward page identity")
    municipality = "Overstrand" if metro == "Hermanus" else metro
    if municipality not in source and ("City of " + municipality) not in source:
        raise ValueError("Wrong municipality on source page")
    fetched_at = source_time(source, now)
    header = HEADER_PATTERN.search(source)
    if not header:
        raise ValueError("Ward ballot votes are not available")
    valid_votes = int(re.sub(r"\D", "", header.group(1)))
    if valid_votes <= 0:
        raise ValueError("No counted valid ward-ballot votes")
    following = source[header.end():]
    boundary = re.search(r"\b(?:PR ballot|Voting stations|Candidates|Ward history|About these figures|This ward in earlier elections)\b", following, re.I)
    region = following[:boundary.start()] if boundary else following[:12000]
    rows = list(ROW_PATTERN.finditer(region))
    if len(rows) < 2:
        raise ValueError("Fewer than two ranked ballot rows")
    parties = []
    prev = 0
    for match in rows[:3]:
        prefix = region[prev:match.start()][-180:]
        prev = match.end()
        name = party_name(prefix)
        votes = int(re.sub(r"\s", "", match.group(1)))
        share = float(match.group(2))
        if not name or name in (p["name"] for p in parties):
            raise ValueError("Unrecognised or repeated party among first three")
        if votes > valid_votes or not 0 <= share <= 100:
            raise ValueError("Impossible ward ballot row")
        if abs(100 * votes / valid_votes - share) > 0.21:
            raise ValueError("Ward ballot votes and percentage disagree")
        parties.append({"name": name, "share": share, "votes": votes})
    if any(parties[i]["votes"] < parties[i+1]["votes"] for i in range(len(parties)-1)):
        raise ValueError("Ward party ranking is not in descending order")
    if sum(p["votes"] for p in parties) > valid_votes:
        raise ValueError("Ward votes exceed the valid-ballot total")
    result = {
        "parties": parties, "valid_votes": valid_votes,
        "reporting": str(current.get("reporting") or ""),
        "source_at": fetched_at, "source_url": source_url_for(current),
    }
    if not valid_candidate(current, result, now):
        raise ValueError("Ward breakdown does not match latest metro leader or reporting")
    # Where the page exposes its own voting-district count, check it too.
    district = re.search(r"This ward\s+(\d+)\s+of\s+(\d+)\s+voting districts in", source)
    if district:
        own = f"{district.group(1)} of {district.group(2)} districts"
        if own != current.get("reporting"):
            raise ValueError("Ward page district count differs from metro summary")
    return result


def fetch_one(metro: str, current: dict, now: datetime):
    number = int(current["number"])
    url = source_url_for(current)
    return metro, number, parse_ward_page(get(url + "?ballot=ward"), metro, number, current, now)


def main():
    now = datetime.now(timezone.utc)
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    prior = json.loads(DETAILS.read_text(encoding="utf-8")) if DETAILS.exists() else {"metros": {}}
    new = {"source": "Individual ESP 2026 ward-ballot pages (IEC-derived; provisional)", "checked_at": now.isoformat(), "metros": {}}
    pending = {m: [] for m in METROS}
    cached = {m: 0 for m in METROS}
    skipped = {m: 0 for m in METROS}
    for metro in METROS:
        current_wards = results["metros"][metro]["wards"]
        previous = (prior.get("metros") or {}).get(metro) or {}
        entries = {}
        for ward in current_wards:
            key = str(ward["number"])
            if not ward.get("parties"):
                skipped[metro] += 1
                continue
            old = previous.get(key)
            if valid_candidate(ward, old, now):
                entries[key] = old
                cached[metro] += 1
            else:
                pending[metro].append(ward)
        new["metros"][metro] = entries

    # Evenly distribute the initial backlog across all three metros.
    work = []
    while len(work) < MAX_REQUESTS and any(pending.values()):
        for metro in METROS:
            if pending[metro] and len(work) < MAX_REQUESTS:
                work.append((metro, pending[metro].pop(0)))
    stats = {m: {"cached": cached[m], "enriched": 0, "not_reported": skipped[m], "pending": len(pending[m]), "errors": 0, "example_errors": []} for m in METROS}
    if work:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            jobs = {pool.submit(fetch_one, metro, ward, now): metro for metro, ward in work}
            for job in as_completed(jobs):
                metro = jobs[job]
                try:
                    name, number, detail = job.result()
                    new["metros"][name][str(number)] = detail
                    stats[name]["enriched"] += 1
                except Exception as error:
                    stats[metro]["errors"] += 1
                    if len(stats[metro]["example_errors"]) < 3:
                        stats[metro]["example_errors"].append(str(error)[:160])

    for name in METROS:
        # Preserve valid detail only; skipped entries aren't published as top-3 results.
        new["metros"][name] = dict(sorted(new["metros"][name].items(), key=lambda kv: int(kv[0])))
        stats[name]["top_three_available"] = len(new["metros"][name])

    DETAILS.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    status = {
        "checked_at": now.isoformat(), "metros": stats,
        "status": "ok" if all(stats[m]["errors"] == 0 and stats[m]["pending"] == 0 for m in METROS) else "partial",
        "note": "Each ward's top-three parties are shown only if individually sourced and match its metro summary.",
    }
    STATUS.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
