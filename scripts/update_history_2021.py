"""Import 2021 ward-ballot comparison shares for the three 2026 metro dashboards.

Metro shares: completed 2021 ward ballots from ESP's IEC-derived metro pages.
Ward shares: The Ledger SA's 2021 ward-ballot figures matched by voting-district
number to each *2026* ward area. These are NOT necessarily the official 2021
ward boundaries or the complete area after splits/new districts.

Only source-reported shares are stored. A party not among source-published top
rows is unknown (not zero). No historic vote share is imputed or invented.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from fetch_results import get

OUTPUT = Path("history-2021.json")
REPORT = Path("history-2021-status.json")
CITIES = {
    "Cape Town": ("cape-town", "western-cape/city-of-cape-town", 118),
    "Tshwane": ("tshwane", "gauteng/city-of-tshwane", 107),
    "Johannesburg": ("johannesburg", "gauteng/city-of-johannesburg", 135),
}
NAME_ALIASES = {
    "Democratic Alliance": "DA", "African National Congress": "ANC",
    "Economic Freedom Fighters": "EFF", "Patriotic Alliance": "PA",
    "ActionSA": "ActionSA", "Vryheidsfront Plus": "FF+",
    "Freedom Front Plus": "FF+", "VF+": "FF+", "VF PLUS": "FF+",
    "Inkatha Freedom Party": "IFP", "African Christian Democratic Party": "ACDP",
    "AFRICAN CHRISTIAN DEMOCRATIC PARTY": "ACDP",
    "GOOD": "GOOD", "Al Jama-ah": "Al Jama-ah",
    "ALJAMA": "Al Jama-ah", "National Coloured Congress": "CCC",
    "CAPE COLOURED CONGRESS": "CCC", "CAPE COLOURED CONGRESS PARTY": "CCC",
    "CCC": "CCC", "African Transformation Movement": "ATM",
    "United Democratic Movement": "UDM", "Build One South Africa": "BOSA",
    "South African Communist Party": "SACP", "RISE MZANSI": "RISE",
    "Independent candidates": "Independent", "INDEPENDENT": "Independent",
    "CAPE INDEPENDENCE PARTY / KAAPSE ONAFHANKLIKHEIDS PARTY": "CAPEXIT",
    "CAPEXIT": "CAPEXIT", "Al Jama-ah": "Al Jama-ah",
    "DA": "DA", "ANC": "ANC", "EFF": "EFF", "PA": "PA",
    "IFP": "IFP", "ACDP": "ACDP", "DOP": "DOP",
}
ALIAS_ORDER = sorted(NAME_ALIASES.items(), key=lambda pair: -len(pair[0]))
METRO_VOTE_ROW = re.compile(r"(?<!\d)(\d{1,3}(?:\s+\d{3})*)\s+(\d{1,3}\.\d)%")
SHARE = re.compile(r"(\d{1,3}\.\d)\s*%")
WARD_HEADER = re.compile(r"\b2021\s+ward\s+ballot\b", re.I)
WARD_SECTION_END = re.compile(r"\b(?:Turnout\s+\d|2021\s+party\s*\(PR\)\s+ballot|Earlier results|##|2024\s+(?:national|provincial)\s+ballot)\b", re.I)
COVERAGE = re.compile(r"(\d+)\s+of\s+this\s+ward[’']s\s+(\d+)\s+voting\s+districts\s+have\s+results\s+for\s+that\s+year", re.I)
MAX_WORKERS = 8


def canonical(fragment: str) -> str | None:
    fragment = re.sub(r"Image(?=[A-Z])", " ", fragment)
    for label, party in ALIAS_ORDER:
        if re.search(r"(?<![A-Za-z])" + re.escape(label) + r"(?![A-Za-z])", fragment, re.I):
            return party
    return None


def parse_metro(text: str, city: str, source_url: str) -> dict:
    if "City of " + city not in text or "2021" not in text:
        raise ValueError("Wrong metro or election year")
    header = re.search(r"Ward ballot\s*\?\s*[·•]?\s*([\d\s]+)\s+valid votes", text)
    if not header:
        raise ValueError("Missing 2021 ward-ballot vote total")
    total = int(re.sub(r"\D", "", header.group(1)))
    if total <= 0:
        raise ValueError("Invalid 2021 metro vote total")
    tail = text[header.end():]
    end = re.search(r"\b(?:PR ballot|Wards\s*[·•]|About these figures|How did City of)\b", tail)
    region = tail[:end.start()] if end else tail[:12000]
    parties = {}
    prev = 0
    for hit in METRO_VOTE_ROW.finditer(region):
        party = canonical(region[prev:hit.start()][-190:])
        prev = hit.end()
        votes = int(re.sub(r"\s", "", hit.group(1)))
        share = float(hit.group(2))
        if party is None or party in parties:
            continue
        if votes > total or not 0 <= share <= 100:
            continue
        if abs(100 * votes / total - share) > 0.22:
            continue
        parties[party] = share
    if len(parties) < 3 or sum(parties.values()) > 100.6:
        raise ValueError("Fewer than three valid 2021 metro parties or invalid shares")
    return {
        "ballot_type": "Ward", "year": 2021,
        "valid_votes": total, "parties": parties, "source_url": source_url,
        "comparison": "Completed 2021 local-election ward ballot, whole municipality",
    }


def parse_ward(text: str, number: int, source_url: str) -> dict:
    if not re.search(r"\bWard\s+" + str(number) + r"\b", text):
        raise ValueError("Wrong ward page")
    header = WARD_HEADER.search(text)
    if not header:
        raise ValueError("2021 ward-ballot section missing")
    tail = text[header.end():]
    stop = WARD_SECTION_END.search(tail)
    block = tail[:stop.start()] if stop else tail[:1700]
    # Each Ledger 2026-area ward page publishes up to five parties + Others.
    matches = list(SHARE.finditer(block))
    if not 3 <= len(matches) <= 12:
        raise ValueError("Unexpected 2021 ward-share row count")
    shares = {}
    prev = 0
    for hit in matches:
        fragment = block[prev:hit.start()][-170:]
        prev = hit.end()
        party = canonical(fragment)
        percentage = float(hit.group(1))
        if party is None or party in shares:
            continue
        if not 0 <= percentage <= 100:
            raise ValueError("Impossible historical ward percentage")
        shares[party] = percentage
    if len(shares) < 2 or sum(shares.values()) > 100.6:
        raise ValueError("Missing validated 2021 ward party breakdown")
    coverage = COVERAGE.search(tail[:600])
    if not coverage:
        raise ValueError("Source does not disclose 2021 ward-district coverage")
    matched, total = map(int, coverage.groups())
    if not (0 < matched <= total <= 99):
        raise ValueError("Invalid matched historical district coverage")
    return {
        "ballot_type": "Ward", "year": 2021, "parties": shares,
        "matched_districts": matched, "districts_in_2026_ward": total,
        "source_url": source_url,
        "comparison": "2021 votes in voting districts matched to this 2026 ward, not official 2021 ward boundaries",
    }


def get_ward(name: str, city_slug: str, number: int):
    url = f"https://theledgersa.com/metros/{city_slug}/wards-2026/{number}/"
    return name, number, parse_ward(get(url), number, url)


def get_metro(name: str, esp_slug: str):
    url = "https://go.esp.info/elections/local/2021/" + esp_slug
    return parse_metro(get(url), name, url)


def main():
    now = datetime.now(timezone.utc).isoformat()
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {"metros": {}}
    existing = previous.get("metros", {})
    history = {"year": 2021, "ballot_type": "Ward", "checked_at": now,
               "notes": "Wards use voting districts matched to 2026 boundaries; historic 2021 shares can be incomplete where districts changed.",
               "metros": {}}
    checks = {}
    queue = []
    for name, (city_slug, esp_slug, nwards) in CITIES.items():
        prior = existing.get(name, {})
        metro = None
        err = None
        try:
            metro = get_metro(name, esp_slug)
        except Exception as error:
            err = str(error)[:160]
            if isinstance(prior.get("parties"), dict) and len(prior["parties"]) >= 3:
                metro = {k: v for k, v in prior.items() if k != "wards"}
        if metro is None:
            metro = {"year": 2021, "ballot_type": "Ward", "parties": {}}
        kept = {}
        for number in range(1, nwards + 1):
            prior_ward = (prior.get("wards") or {}).get(str(number))
            if isinstance(prior_ward, dict) and prior_ward.get("year") == 2021 \
               and prior_ward.get("ballot_type") == "Ward" and len(prior_ward.get("parties") or {}) >= 2 \
               and isinstance(prior_ward.get("matched_districts"), int) and prior_ward["matched_districts"] > 0:
                kept[str(number)] = prior_ward
            else:
                queue.append((name, city_slug, number))
        history["metros"][name] = {**metro, "wards": kept}
        checks[name] = {"metro_status": "ok" if not err else "cached_or_missing",
                        "metro_error": err, "wards_cached": len(kept),
                        "wards_downloaded": 0, "wards_error": 0, "sample_errors": []}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        jobs = {executor.submit(get_ward, *item): item[0] for item in queue}
        for future in as_completed(jobs):
            name = jobs[future]
            try:
                metro, number, row = future.result()
                history["metros"][metro]["wards"][str(number)] = row
                checks[metro]["wards_downloaded"] += 1
            except Exception as error:
                checks[name]["wards_error"] += 1
                if len(checks[name]["sample_errors"]) < 4:
                    checks[name]["sample_errors"].append(str(error)[:160])
    total_ok = 0
    for city, (_, _, expected) in CITIES.items():
        rows = history["metros"][city]["wards"]
        history["metros"][city]["wards"] = dict(sorted(rows.items(), key=lambda p: int(p[0])))
        checks[city]["wards_available"] = len(rows)
        checks[city]["wards_expected"] = expected
        total_ok += len(rows)
    OUTPUT.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = {"checked_at": now, "status": "ok" if total_ok == 360 and
              all(len(history["metros"][city].get("parties", {})) >= 3 for city in CITIES)
              else "partial", "checks": checks,
              "warning": "2021 ward percentages are matched to the current 2026 ward's voting districts; missing parties are unknown, never zero."}
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
