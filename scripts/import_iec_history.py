"""Refresh 2021 municipality-wide history from DIRECT official IEC report CSVs.

The IEC publishes 2021 Ward-ballot results under public electoral event 1091.
Historical ward numbers/boundaries are not mixed into 2026 ward comparisons.
No ESP pages or source data are used by this importer.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from import_iec_reports import CITIES, build_history, download_report, parse_csv, report_url

def main():
    checked = datetime.now(timezone.utc).isoformat()
    status = {"checked_at": checked, "status": "unavailable", "source": "IEC official public 2021 party-result CSV", "checks": {}}
    rows, urls = {}, {}
    for city in CITIES:
        url = report_url(2021, 1091, city)
        try:
            rows[city] = parse_csv(download_report(url), city, 2021)
            urls[city] = url
            status["checks"][city] = {"status": "ok", "valid_votes": rows[city]["total_votes"]}
        except Exception as error:
            status["checks"][city] = {"status": "error", "detail": str(error)[:180]}
    if set(rows) == set(CITIES):
        payload = build_history(rows, urls)
        Path("history-iec-2021.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        status["status"] = "ok"
    status["note"] = ("Only source-validated 2021 municipality-wide Ward-ballot shares are published. "
                      "No 2026 ward historic shares are derived from the old boundaries.")
    Path("iec-history-status.json").write_text(json.dumps(status, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(status))
    if status["status"] != "ok":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
