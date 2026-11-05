"""Guarded importer of provisional IEC-derived metro and ward results from ESP."""
import json,re,urllib.request
from html.parser import HTMLParser
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT="https://go.esp.info/elections/local/2026/"
CITIES={"Cape Town":("western-cape/city-of-cape-town",829,118),"Tshwane":("gauteng/city-of-tshwane",796,107),"Johannesburg":("gauteng/city-of-johannesburg",862,135)}
ALIASES={"DA":"DA","ANC":"ANC","EFF":"EFF","ActionSA":"ActionSA","PA":"PA","VF PLUS":"FF+","MKP":"MK","IFP":"IFP","GOOD":"GOOD","ACDP":"ACDP","ALJAMA":"Al Jama-ah","RISE":"RISE","H.O.I.":"H.O.I."}
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,v):
  v=" ".join(v.split())
  if v:self.parts.append(v)
 def handle_starttag(self,tag,attrs):
  if tag in ("p","li","div","tr","h1","h2","h3","br"):self.parts.append(" ")
def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; SA-Metro-Watch/1.0)","Accept":"text/html"})
 with urllib.request.urlopen(req,timeout=30) as r:
  if r.status!=200:raise ValueError("HTTP "+str(r.status))
  raw=r.read(3000000).decode("utf-8","replace")
 p=Text();p.feed(raw)
 return " ".join(" ".join(p.parts).split())
def parse(city,slug,total,nwards,now):
 url=ROOT+slug
 s=get(url)
 if "City of "+city not in s or "2026" not in s:raise ValueError("Unexpected page identity")
 m=re.search(r"City of "+re.escape(city)+r"\s+(\d+)\s+of\s+(\d+)\s+voting districts in",s)
 if not m:raise ValueError("Metro voting-district count missing")
 count,denom=map(int,m.groups())
 if denom!=total or not 0<=count<=total:raise ValueError("Metro voting-district count invalid")
 tm=re.search(r"IEC data last fetched\s+(\d{1,2}\s+\w+\s+2026,\s*\d{2}:\d{2})\s*SAST",s)
 if not tm:raise ValueError("IEC source timestamp missing")
 stamp=None
 for fmt in ("%d %b %Y, %H:%M","%d %B %Y, %H:%M"):
  try:stamp=datetime.strptime(tm.group(1),fmt).replace(tzinfo=timezone(timedelta(hours=2))).astimezone(timezone.utc);break
  except ValueError:pass
 if stamp is None or stamp>now+timedelta(minutes=10) or now-stamp>timedelta(hours=24):raise ValueError("IEC timestamp invalid or stale")
 # Parse party votes from the actual numbered rows, bounded by the Wards section.
 start=re.search(r"Ward ballot\s*\?\s*[·•]?\s*([\d\s]+)\s+valid votes",s)
 if not start:raise ValueError("Ward ballot header missing")
 votes=int(re.sub(r"\D","",start.group(1)))
 tail=s[start.end():]
 end=re.search(r"\b(?:How did City of|Wards\s*[·•]|About these figures)\b",tail)
 section=tail[:end.start()] if end else tail[:16000]
 parties=[]
 # Example: '1. ImageDA Democratic Alliance 305 41.8%'
 rows=re.finditer(r"(?:^|\s)(\d{1,3})\.\s*(?:Image\s*)?([A-Za-z][A-Za-z0-9.+-]*(?:\s+PLUS)?)\s+(.{1,130}?)\s+(\d+)\s+(\d{1,3}\.\d)%",section)
 for row in rows:
  key=row.group(2)
  if key not in ALIASES:continue
  share=float(row.group(5));ballots=int(row.group(4))
  if share<0 or share>100 or ballots>votes or abs(100*ballots/max(votes,1)-share)>0.15:continue
  name=ALIASES[key]
  if name not in [p["name"] for p in parties]:parties.append({"name":name,"share":share})
 if count and not parties:raise ValueError("Party vote rows could not be validated")
 ward_section=re.search(r"Wards\s*[·•]\s*"+str(nwards)+r"\b(.*?)(?:About these figures|$)",s)
 if not ward_section:raise ValueError("Ward list missing")
 ward_rows={}
 for w in re.finditer(r"Ward\s+(\d{1,3})\s+(\d+)\s+of\s+(\d+)\s+voting districts in\s+(DA|ANC|ActionSA|EFF|PA|IFP|MKP|VF PLUS|GOOD|ACDP|RISE)\s+(\d{1,3}\.\d)%",ward_section.group(1)):
  n,reported,den=int(w.group(1)),int(w.group(2)),int(w.group(3))
  if 1<=n<=nwards and 0<reported<=den and 0<=float(w.group(5))<=100:
   ward_rows[n]={"number":n,"status":"Partly counted","ballot_type":"Ward","reporting":str(reported)+" of "+str(den)+" districts","winner":ALIASES[w.group(4)],"parties":[{"name":ALIASES[w.group(4)],"share":float(w.group(5))}],"snapshot_at":stamp.isoformat(),"source_url":url}
 wards=[ward_rows.get(i,{"number":i,"status":"Not yet reported","ballot_type":"Ward","reporting":"Not yet reported","parties":[],"snapshot_at":stamp.isoformat(),"source_url":url}) for i in range(1,nwards+1)]
 return {"status":"Preliminary · IEC-derived via ESP","ballot_type":"Ward","districts_reported":count,"districts_total":denom,"parties":parties,"seats":[],"wards":wards,"snapshot_at":stamp.isoformat(),"source_url":url},len(ward_rows)
def main():
 now=datetime.now(timezone.utc)
 path=Path("results.json");data=json.loads(path.read_text());data.setdefault("metros",{})
 report={"checked_at":now.isoformat(),"source":"ESP, IEC-derived preliminary results","checks":{},"results_updated":False}
 updated=False
 for city,(slug,total,nwards) in CITIES.items():
  try:
   item,ward_rows=parse(city,slug,total,nwards,now)
   previous=data["metros"].get(city,{})
   if previous.get("snapshot_at") and item["snapshot_at"]<previous["snapshot_at"]:raise ValueError("Timestamp regressed")
   if item["districts_reported"]<int(previous.get("districts_reported") or 0):raise ValueError("District count regressed")
   if item!=previous:data["metros"][city]=item;updated=True
   report["checks"][city]={"status":"ok","districts_reported":item["districts_reported"],"wards_with_data":ward_rows,"snapshot_at":item["snapshot_at"]}
  except Exception as exc:report["checks"][city]={"status":"error","detail":str(exc)[:200]}
 if updated:
  data["updated_at"]=now.isoformat();data["source"]="Provisional IEC-derived ward-ballot results via ESP"
  path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
  report["results_updated"]=True
 report["status"]="ok" if all(v["status"]=="ok" for v in report["checks"].values()) else "partial"
 Path("feed-status.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps(report,indent=2))
if __name__=="__main__":main()
