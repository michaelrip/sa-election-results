"""Update dashboard from public IEC-derived ESP pages; never invent results."""
import json,re,urllib.request
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
class Extract(HTMLParser):
 def __init__(self): super().__init__();self.parts=[]
 def handle_data(self,v):
  v=" ".join(v.split())
  if v:self.parts.append(v)
def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 SA-Metro-Watch"})
 with urllib.request.urlopen(req,timeout=30) as r:
  if r.status!=200:raise ValueError("HTTP "+str(r.status))
  page=r.read(2000000).decode("utf-8","replace")
 p=Extract();p.feed(page);return " ".join(p.parts)
cities={"Cape Town":("western-cape/city-of-cape-town",829,118),"Tshwane":("gauteng/city-of-tshwane",796,107),"Johannesburg":("gauteng/city-of-johannesburg",862,135)}
aliases={"DA":"DA","ANC":"ANC","EFF":"EFF","ActionSA":"ActionSA","PA":"PA","VF PLUS":"FF+","MKP":"MK","ACDP":"ACDP","GOOD":"GOOD","IFP":"IFP","ALJAMA":"Al Jama-ah"}
now=datetime.now(timezone.utc)
path=Path("results.json")
data=json.loads(path.read_text())
report={"checked_at":now.isoformat(),"source":"ESP (IEC-derived public pages)","checks":{},"results_updated":False}
changed=False
for city,(slug,total,nwards) in cities.items():
 url="https://go.esp.info/elections/local/2026/"+slug
 try:
  s=get(url)
  title="City of "+city
  if title not in s or "2026" not in s:raise ValueError("Page identity mismatch")
  m=re.search(re.escape(title)+r"\s*:?\s*(\d[\d\s]*)\s+of\s+(\d[\d\s]*)\s+voting districts in",s)
  if not m:raise ValueError("Reporting count missing")
  count,denom=[int(re.sub(r"\D","",v)) for v in m.groups()]
  if denom!=total or not 0<=count<=total:raise ValueError("Reporting count invalid")
  parties=[]
  if count:
   section=re.search(r"Ward ballot\s*\?\s*[\d\s]+\s+valid votes\s+(.*?)(?:\bPR ballot\b|\bWards\s*[·:]|\bAbout these figures\b)",s)
   if not section:raise ValueError("Ward ballot section missing")
   for match in re.finditer(r"\b\d{1,2}\.\s+(?:Image)?(DA|ANC|EFF|ActionSA|PA|VF PLUS|MKP|ACDP|GOOD|IFP|ALJAMA)\b.{0,100}?\s+\d[\d\s]*\s+(\d{1,3}\.\d)%",section.group(1)):
    name=aliases[match.group(1)];share=float(match.group(2))
    if name not in [p["name"] for p in parties] and 0<=share<=100:parties.append({"name":name,"share":share})
   if not parties:raise ValueError("Party figures could not be verified")
  time_match=re.search(r"IEC data last fetched\s+(\d{1,2}\s+\w+\s+2026,\s*\d{2}:\d{2})\s*SAST",s)
  if not time_match:raise ValueError("Source timestamp missing")
  from datetime import timedelta
  snapshot=datetime.strptime(time_match.group(1),"%d %B %Y, %H:%M").replace(tzinfo=timezone(timedelta(hours=2))).astimezone(timezone.utc)
  if snapshot>now+timedelta(minutes=10) or now-snapshot>timedelta(hours=12):raise ValueError("Source stale or future-dated")
  wards=[]
  for i in range(1,nwards+1):
   w=re.search(r"\bWard\s+"+str(i)+r"\s+(\d+)\s+of\s+(\d+)\s+voting districts in\s+([A-Za-z+ .-]+?)\s+(\d+\.\d)%",s)
   wards.append({"number":i,"status":"Partly counted" if w else "Not yet reported","ballot_type":"Ward","reporting":(w.group(1)+" of "+w.group(2)+" districts") if w else "Not yet reported","parties":[{"name":w.group(3).strip(),"share":float(w.group(4))}] if w else [],"source_url":url,"snapshot_at":snapshot.isoformat()})
  previous=data["metros"].get(city,{})
  if previous.get("snapshot_at") and snapshot.isoformat()<previous["snapshot_at"]:raise ValueError("Timestamp regressed")
  result={"status":"Preliminary · IEC-derived via ESP","ballot_type":"Ward","districts_reported":count,"districts_total":total,"parties":parties,"seats":[],"wards":wards,"snapshot_at":snapshot.isoformat(),"source_url":url}
  if result!=previous:data["metros"][city]=result;changed=True
  report["checks"][city]={"status":"ok","districts_reported":count,"snapshot_at":snapshot.isoformat()}
 except Exception as e:
  report["checks"][city]={"status":"error","detail":str(e)[:180]}
if changed:
 data["updated_at"]=now.isoformat()
 data["source"]="IEC-derived provisional figures from ESP; verify against official IEC"
 path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
 report["results_updated"]=True
report["status"]="ok" if all(v["status"]=="ok" for v in report["checks"].values()) else "partial"
Path("feed-status.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
