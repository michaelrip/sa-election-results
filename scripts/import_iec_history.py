"""Refresh 2021 municipality-wide history from DIRECT official IEC report CSVs.

The IEC publishes 2021 Ward-ballot results under public electoral event 1091.
Historical ward numbers/boundaries are not mixed into 2026 ward comparisons.
No ESP pages or source data are used by this importer.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from import_iec_reports import CITIES, build_history, download_report, parse_csv, parse_pr_csv, report_url

def main():
    checked = datetime.now(timezone.utc).isoformat()
    status = {
        "checked_at": checked, "status": "unavailable",
        "source": "IEC official public 2021 Ward and municipal PR CSV",
        "checks": {},
    }
    rows, pr_rows, urls = {}, {}, {}
    for city in CITIES:
        url = report_url(2021, 1091, city)
        try:
            # One official municipal CSV contains both separately typed ballots.
            source = download_report(url)
            ward = parse_csv(source, city, 2021)
            municipal_pr = parse_pr_csv(source, city, 2021)
            combined = build_history({city: ward}, {city: url},
                                     {city: municipal_pr})["metros"][city]["combined"]
            rows[city] = ward
            pr_rows[city] = municipal_pr
            urls[city] = url
            status["checks"][city] = {
                "status": "ok",
                "ward_valid_votes": ward["total_votes"],
                "pr_valid_votes": municipal_pr["total_votes"],
                "combined_valid_ballots": combined["valid_votes"],
            }
        except Exception as error:
            status["checks"][city] = {
                "status": "error", "detail": str(error)[:230],
            }
    if set(rows) == set(CITIES) and set(pr_rows) == set(CITIES):
        payload = build_history(rows, urls, pr_rows)
        Path("history-iec-2021.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        status["status"] = "ok"
    status["note"] = (
        "2021 whole-municipality Ward and PR shares come from exact official "
        "ballot votes. Ward + PR totals count papers, not individual people. "
        "Overstrand District PR is not included. No historic 2021 ward shares "
        "are inferred from current ward boundaries.")
    Path("iec-history-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status))
    if status["status"] != "ok":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
