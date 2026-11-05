"""Safe hourly election feed check.

This deliberately does not publish numerical results until an official,
machine-readable IEC endpoint and response schema are verified.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

now = datetime.now(timezone.utc).isoformat()
report = {
    "checked_at": now,
    "source": "https://results.elections.org.za/",
    "status": "awaiting_verified_api",
    "results_updated": False,
    "checks": {
        city: {"status": "not_connected", "detail": "IEC machine-readable ward and metro endpoint not yet verified"}
        for city in ("Cape Town", "Tshwane", "Johannesburg")
    }
}
try:
    req = urllib.request.Request("https://results.elections.org.za/", headers={"User-Agent": "SA-Metro-Watch/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        report["portal_http_status"] = response.status
except Exception as exc:
    report["portal_check_error"] = str(exc)[:160]
Path("feed-status.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
