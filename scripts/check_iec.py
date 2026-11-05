"""Hourly official IEC API connectivity check. Does not fabricate or overwrite results."""
import json, os, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = "https://api.elections.org.za"
REPORT = Path("feed-status.json")
now = datetime.now(timezone.utc).isoformat()
status = {"checked_at": now, "source": ROOT, "status": "not_verified", "detail": "", "results_updated": False}
event = os.getenv("IEC_EVENT_ID", "").strip()
province = os.getenv("IEC_PROVINCE_ID", "").strip()
municipalities = {"Cape Town": os.getenv("IEC_CAPE_TOWN_ID", "").strip(), "Tshwane": os.getenv("IEC_TSHWANE_ID", "").strip(), "Johannesburg": os.getenv("IEC_JOHANNESBURG_ID", "").strip()}
if not event or not province or not all(municipalities.values()):
    status["detail"] = "Official IEC electoral event, province and municipality identifiers must be independently verified before ingestion."
else:
    status["detail"] = "API identifiers supplied; testing connectivity. Response schema must still be verified before publication."
    checks = {}
    for metro, mid in municipalities.items():
        # The official documented endpoint requires electoral event, province and municipality IDs.
        url = f"{ROOT}/api/v1/LGEBallotResults?ElectoralEventID={event}&ProvinceID={province}&MunicipalityID={mid}"
        try:
            req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"SA-Metro-Election-Watch/1.0"})
            with urllib.request.urlopen(req, timeout=20) as response:
                body = response.read(2000000)
                obj = json.loads(body)
                checks[metro] = {"http_status":response.status,"json_type":type(obj).__name__,"bytes":len(body)}
        except Exception as e:
            checks[metro] = {"error":str(e)[:180]}
    status["checks"] = checks
    status["status"] = "api_probed"
    status["detail"] = "Connectivity only. Election results have not been ingested; IEC response schema and city/province IDs require validation."
REPORT.write_text(json.dumps(status, indent=2)+"\n")
print(json.dumps(status, indent=2))
