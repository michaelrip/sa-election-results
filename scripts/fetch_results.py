"""Import preliminary IEC-derived ward-ballot results from public ESP pages.
Strict source checks: any parse failure leaves existing city figures unchanged.
"""
import json,re,urllib.request
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
from pathlib import Path
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,v):
  v=" ".join(v.split())
  if v:self.parts.append(v)
def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; MetroWatch/1.0)","Accept":"text/html"})
 with urllib.request.urlopen(req,timeout=25) as r:
  if r.status!=200:raise ValueError("HTTP "+str(r.status))
  raw=r.read(3000000).decode("utf-8","replace")
 parser=Text();parser.feed(raw);return " ".join(parser.parts)
base="https://go.esp.info/elections/local/2026/"
cities={"Cape Town":("western-cape/city-of-cape-town",829,118),"Tshwane":("gauteng/city-of-tshwane",796,107),"Johannesburg":("gauteng/city-of-johannesburg",862,135)}
aliases={"DA":"DA","ANC":"ANC","EFF":"EFF","ActionSA":"ActionSA","PA":"PA","VF PLUS":"FF+","MKP":"MK","IFP":"IFP","GOOD":"GOOD","ACDP":"ACDP","RISE":"RISE"}
now=datetime.now(timezone.utc)
data=json.loads(Path("results.json").read_text())
data.setdefault("metros",{})
report={"checked_at":now.isoformat(),"source":"ESP, reporting IEC-derived preliminary results","checks":{},"results_updated":False}
updated=False
for city,(slug,expected,ward_count) in cities.items():
 url=base+slug
 try:
  s=fetch(url)
  if "City of "+city not in s or "2026" not in s:raise ValueError("Source page identity mismatch")
  m=re.search(r"City of "+re.escape(city)+r"\s+(\d[\d\s]*)\s+of\s+(\d[\d\s]*)\s+voting districts in",s)
  if not m:raise ValueError("Metro progress missing")
  count,total=[int(re.sub(r"\D","",x)) for x in m.groups()]
  if total!=expected or not 0<=count<=total:raise ValueError("Metro progress failed validation")
  timestamp=re.search(r"IEC data last fetched\s+(\d{1,2}\s+\w+\s+2026,\s*\d{2}:\d{2})\s*SAST",s)
  if not timestamp:raise ValueError("IEC source timestamp missing")
  snap=datetime.strptime(timestamp.group(1),"%d %b %Y, %H:%M").replace(tzinfo=timezone(timedelta(hours=2))).astimezone(timezone.utc)
  if snap>now+timedelta(minutes=10) or now-snap>timedelta(hours=24):raise ValueError("IEC source timestamp stale or future-dated")
  start=re.search(r"Ward ballot\s*\?\s*[·•]?\s*[\d\s]+\s+valid votes",s)
  if not start:raise ValueError("Ward ballot section missing")
  tail=s[start.end():]
  end=re.search(r"\b(?:PR ballot|How did City of|Wards\s*[·•]|About these figures)\b",tail)
  section=tail[:end.start()] if end else tail[:10000]
  parties=[]
  pattern=r"\b\d{1,2}\.\s+(?:Image)?(ActionSA|VF PLUS|MKP|ACDP|GOOD|EFF|ANC|DA|PA|IFP|RISE)\b.{0,115}?\s+\d[\d\s]*\s+(\d{1,3}\.\d)%"
  for found in re.finditer(pattern,section):
   party=aliases[found.group(1)];share=float(found.group(2))
   if party not in [x["name"] for x in parties] and 0<=share<=100:parties.append({"name":party,"share":share})
  if count and not parties:raise ValueError("Ward party rows missing")
  ward_part=s.split("Wards · "+str(ward_count),1)
  if len(ward_part)<2:raise ValueError("Ward index missing")
  ward_text=ward_part[1].split("About these figures",1)[0]
  ward_rows={}
  for w in re.finditer(r"Ward\s+(\d{1,3})\s+(\d+)\s+of\s+(\d+)\s+voting districts in\s+(.+?)\s+(\d{1,3}\.\d)%",ward_text):
   n,reported,denom=int(w.group(1)),int(w.group(2)),int(w.group(3))
   if 1<=n<=ward_count and 0<=reported<=denom and denom>0:
    ward_rows[n]={"number":n,"status":"Partly counted","ballot_type":"Ward","reporting":str(reported)+" of "+str(denom)+" districts","parties":[{"name":w.group(4).strip(),"share":float(w.group(5))}],"snapshot_at":snap.isoformat(),"source_url":url}
  wards=[ward_rows.get(i,{"number":i,"status":"Not yet reported","ballot_type":"Ward","reporting":"Not yet reported","parties":[],"snapshot_at":snap.isoformat(),"source_url":url}) for i in range(1,ward_count+1)]
  prev=data["metros"].get(city,{})
  if prev.get("snapshot_at") and snap.isoformat()<prev["snapshot_at"]:raise ValueError("Source timestamp went backwards")
  if count<int(prev.get("districts_reported") or 0):raise ValueError("District count went backwards")
  entry={"status":"Preliminary IEC-derived via ESP","ballot_type":"Ward","districts_reported":count,"districts_total":total,"parties":parties,"seats":[],"wards":wards,"snapshot_at":snap.isoformat(),"source_url":url}
  if entry!=prev:data["metros"][city]=entry;updated=True
  report["checks"][city]={"status":"ok","districts_reported":count,"wards_with_data":len(ward_rows),"snapshot_at":snap.isoformat()}
 except Exception as exc:report["checks"][city]={"status":"error","detail":str(exc)[:200]}
if updated:
 data["updated_at"]=now.isoformat()
 data["source"]="Provisional IEC-derived ward ballot figures via ESP; verify with IEC"
 Path("results.json").write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
 report["results_updated"]=True
report["status"]="ok" if all(x["status"]=="ok" for x in report["checks"].values()) else "partial"
Path("feed-status.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
