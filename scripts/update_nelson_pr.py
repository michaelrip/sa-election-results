"""Update Nelson Mandela Bay municipal PR votes from ESP without altering other municipalities."""
import json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fetch_results import get

ROOT = "https://go.esp.info/elections/local/2026/eastern-cape/nelson-mandela-bay?ballot=pr"
ALTERNATE = "https://sepush.co.za/elections/local/2026/eastern-cape/nelson-mandela-bay?ballot=pr"
DEST = Path("ballots.json")
STATUS = Path("nelson-pr-status.json")
NAMES = {
    "Democratic Alliance":"DA", "African National Congress":"ANC",
    "Economic Freedom Fighters":"EFF", "South African Communist Party":"SACP",
    "Patriotic Alliance":"PA", "Vryheidsfront Plus":"FF+",
    "Freedom Front Plus":"FF+", "United Democratic Movement":"UDM",
    "ActionSA":"ActionSA", "African Christian Democratic Party":"ACDP",
    "Umkhonto Wesizwe Party":"MK", "Inkatha Freedom Party":"IFP",
    "African Transformation Movement":"ATM", "Al Jama-ah":"Al Jama-ah",
    "Mayibuye Civic Movement":"Mayibuye Civic Movement",
    "GOOD":"GOOD", "VF PLUS":"FF+", "MKP":"MK",
    "DA":"DA", "ANC":"ANC", "EFF":"EFF", "SACP":"SACP",
    "PA":"PA", "UDM":"UDM", "ACDP":"ACDP", "IFP":"IFP"
}
def parse(url, now):
    s = get(url)
    if "Nelson Mandela Bay" not in s or "2026" not in s:
        raise ValueError("Unexpected municipality")
    header = re.search(r"\bPR ballot\s*\??\s*[·•]?\s*([\d\s]+)\s+valid votes\b", s, re.I)
    if not header:
        raise ValueError("Municipal PR ballot vote table unavailable")
    votes = int(re.sub(r"\D", "", header.group(1)))
    if votes <= 0:
        raise ValueError("No valid PR votes")
    tm = re.search(r"IEC data last fetched\s+(\d{1,2}\s+\w+\s+2026,\s*\d{2}:\d{2})\s*SAST",s)
    if not tm:
        raise ValueError("IEC source timestamp missing")
    stamp = None
    for fmt in ("%d %b %Y, %H:%M", "%d %B %Y, %H:%M"):
        try:
            stamp = datetime.strptime(tm.group(1),fmt).replace(tzinfo=timezone(timedelta(hours=2))).astimezone(timezone.utc)
            break
        except ValueError:
            pass
    if stamp is None or stamp > now + timedelta(minutes=10) or now-stamp > timedelta(hours=24):
        raise ValueError("Source timestamp invalid")
    section = s[header.end():]
    stop = re.search(r"\b(?:How did Nelson Mandela Bay vote|Wards\s*[·•]|About these figures)\b",section)
    section = section[:stop.start()] if stop else section[:14000]
    parties = []
    prev = 0
    for match in re.finditer(r"(?<!\d)(\d{1,3}(?:\s+\d{3})*)\s+(\d{1,3}\.\d)\s*%",section):
        fragment = section[prev:match.start()][-200:]
        prev = match.end()
        name = next((code for label,code in sorted(NAMES.items(),key=lambda x:-len(x[0])) if re.search(r"(?<![A-Za-z])"+re.escape(label)+r"(?![A-Za-z])",fragment,re.I)),None)
        count = int(re.sub(r"\s","",match.group(1)))
        share = float(match.group(2))
        if not name or any(x["name"]==name for x in parties):
            continue
        if count > votes or abs(100*count/votes-share)>0.21:
            continue
        parties.append({"name":name,"votes":count,"share":share})
    if len(parties)<2 or not {"DA","ANC"}.issubset({p["name"] for p in parties}):
        raise ValueError("Insufficient verified PR party rows")
    if sum(p["votes"] for p in parties)>votes:
        raise ValueError("Party totals exceed valid PR ballots")
    return {"ballot_type":"PR","source_url":url,"snapshot_at":stamp.isoformat(),
            "valid_votes":votes,"parties":sorted(parties,key=lambda x:-x["votes"]),
            "unlisted_votes":votes-sum(p["votes"] for p in parties),
            "note":"Unlisted parties are the residual of valid PR votes, not assigned to named parties."}

def main():
    now=datetime.now(timezone.utc)
    data=json.loads(DEST.read_text(encoding="utf-8"))
    old=data.get("metros",{}).get("Nelson Mandela Bay",{}).get("pr")
    status={"checked_at":now.isoformat(),"status":"error"}
    for url in (ROOT,ALTERNATE):
        try:
            incoming=parse(url,now)
            if old and datetime.fromisoformat(incoming["snapshot_at"]) < datetime.fromisoformat(old["snapshot_at"]):
                raise ValueError("Source timestamp regressed")
            if old and incoming["valid_votes"]<old["valid_votes"]:
                raise ValueError("Valid PR vote count regressed")
            data.setdefault("metros",{}).setdefault("Nelson Mandela Bay",{})["pr"]=incoming
            data["updated_at"]=now.isoformat()
            DEST.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            status.update(status="ok",source_url=url,snapshot_at=incoming["snapshot_at"],valid_votes=incoming["valid_votes"])
            break
        except Exception as exc:
            status["detail"]=str(exc)[:180]
    STATUS.write_text(json.dumps(status,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(status,indent=2))
if __name__=="__main__":
    main()
