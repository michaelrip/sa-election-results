"""Guarded importer of provisional IEC-derived metro and ward results from ESP."""
import json,re,urllib.request
from html.parser import HTMLParser
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT="https://go.esp.info/elections/local/2026/"
ALT_ROOT="https://esp.info/elections/local/2026/"
WARD_BALLOT_HEADER=re.compile(r"\bWard ballot\s*\??\s*[·•]?\s*([\d\s]+)\s+valid votes\b",re.I)
CITIES={"Cape Town":("western-cape/city-of-cape-town",829,118),"Tshwane":("gauteng/city-of-tshwane",796,107),"Johannesburg":("gauteng/city-of-johannesburg",862,135),"Hermanus":("western-cape/overstrand",37,15)}
ALIASES={"DA":"DA","ANC":"ANC","EFF":"EFF","ActionSA":"ActionSA","PA":"PA","VF PLUS":"FF+","MKP":"MK","IFP":"IFP","GOOD":"GOOD","ACDP":"ACDP","ALJAMA":"Al Jama-ah","RISE":"RISE","H.O.I.":"H.O.I."}
class Text(HTMLParser):
 def __init__(self):
  super().__init__()
  self.parts=[]
  self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ("script","style","noscript"):self.skip+=1
  if self.skip:return
  if tag in ("p","li","div","tr","h1","h2","h3","br"):self.parts.append(" ")
  # HTML text excludes image alt text, but ESP uses logo alt for party codes.
  if tag=="img":
   alt=(dict(attrs).get("alt") or "").strip()
   if alt in ("DA","ANC","PA","EFF","ActionSA","VF PLUS","MKP","IFP","ACDP","GOOD","ALJAMA","RISE","H.O.I.","CCC","UDM","ATM","BOSA"):
    self.parts.append(" "+alt+" ")
 def handle_endtag(self,tag):
  if tag in ("script","style","noscript") and self.skip:self.skip-=1
 def handle_data(self,v):
  if not self.skip:
   v=" ".join(v.split())
   if v:self.parts.append(v)
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
 municipality="Overstrand" if city=="Hermanus" else "City of "+city
 if municipality not in s or "2026" not in s:raise ValueError("Unexpected page identity")
 # If the public ESP alias temporarily returns only the summary without its
 # detailed ward-ballot table, try the other official ESP hostname. Do not
 # invent results from percentages: the alternative must still pass all
 # municipality, district, timestamp and per-party-vote validations below.
 if not WARD_BALLOT_HEADER.search(s):
  alt_url=ALT_ROOT+slug
  try:
   alternate=get(alt_url)
   if municipality in alternate and "2026" in alternate and WARD_BALLOT_HEADER.search(alternate):
    s=alternate
    url=alt_url
  except (OSError,ValueError,TimeoutError):
   pass
 m=re.search(re.escape(municipality)+r"\s+(\d+)\s+of\s+(\d+)\s+voting districts in",s)
 if not m:raise ValueError("Metro voting-district count missing")
 count,denom=map(int,m.groups())
 if denom!=total or not 0<=count<=total:raise ValueError("Metro voting-district count invalid")
 # Overstrand's authenticated tracker currently reports zero districts; never
 # imply an IEC snapshot or invent votes while awaiting its first result.
 if city=="Hermanus" and count==0:
  if not re.search(r"Wards\s*[·•]\s*"+str(nwards)+r"\b",s):
   raise ValueError("Overstrand 2026 ward count missing")
  wards=[{"number":i,"status":"Not yet reported","ballot_type":"Ward",
          "reporting":"Not yet reported","parties":[],"snapshot_at":None,
          "source_url":url+"/ward-"+str(i)} for i in range(1,nwards+1)]
  return {"status":"Awaiting verified Overstrand results · IEC-derived via ESP",
          "municipality":"Overstrand Local Municipality",
          "ballot_type":"Ward","districts_reported":0,"districts_total":denom,
          "valid_votes":None,"parties":[],"seats":[],"wards":wards,
          "snapshot_at":None,"source_url":url},0
 tm=re.search(r"IEC data last fetched\s+(\d{1,2}\s+\w+\s+2026,\s*\d{2}:\d{2})\s*SAST",s)
 if not tm:raise ValueError("IEC source timestamp missing")
 stamp=None
 for fmt in ("%d %b %Y, %H:%M","%d %B %Y, %H:%M"):
  try:stamp=datetime.strptime(tm.group(1),fmt).replace(tzinfo=timezone(timedelta(hours=2))).astimezone(timezone.utc);break
  except ValueError:pass
 if stamp is None or stamp>now+timedelta(minutes=10) or now-stamp>timedelta(hours=24):raise ValueError("IEC timestamp invalid or stale")
 # Parse party votes from the actual numbered rows, bounded by the Wards section.
 start=WARD_BALLOT_HEADER.search(s)
 if not start:raise ValueError("Ward ballot header missing")
 votes=int(re.sub(r"\D","",start.group(1)))
 tail=s[start.end():]
 end=re.search(r"\b(?:How did City of|How did Overstrand|Wards\s*[·•]|About these figures)\b",tail)
 section=tail[:end.start()] if end else tail[:16000]
 # Read source party votes without relying on <ol> numbers (HTML adds those
 # visually, but HTMLParser does not see them). Also recognise full party names,
 # even when their abbreviations occur only in logo alt text.
 names={
  "Democratic Alliance":"DA","African National Congress":"ANC",
  "Patriotic Alliance":"PA","Economic Freedom Fighters":"EFF",
  "ActionSA":"ActionSA","Vryheidsfront Plus":"FF+","Freedom Front Plus":"FF+",
  "Umkhonto Wesizwe Party":"MK","Inkatha Freedom Party":"IFP",
  "African Christian Democratic Party":"ACDP","Al Jama-ah":"Al Jama-ah",
  "Home of Independence":"H.O.I.","Rise Mzansi":"RISE",
  "National Coloured Congress":"CCC","United Democratic Movement":"UDM",
  "African Transformation Movement":"ATM","Build One South Africa":"BOSA",
  "South African Communist Party":"SACP",
  "VF PLUS":"FF+","ALJAMA":"Al Jama-ah","MKP":"MK","H.O.I.":"H.O.I.",
  "GOOD":"GOOD","DA":"DA","ANC":"ANC","PA":"PA","EFF":"EFF",
  "IFP":"IFP","ACDP":"ACDP","RISE":"RISE"
 }
 def label_of(prefix):
  # Prefer longer full names to short codes.
  for name,code in sorted(names.items(),key=lambda x:-len(x[0])):
   if re.search(r"(?<![A-Za-z])"+re.escape(name)+r"(?![A-Za-z])",prefix,re.I):
    return code
  return None
 parties=[]
 prev=0
 method="checked party-vote rows"
 for match in re.finditer(r"(?<!\d)(\d{1,3}(?:\s+\d{3})*)\s+(\d{1,3}\.\d)\s*%",section):
  fragment=section[prev:match.start()]
  prev=match.end()
  party=label_of(fragment[-180:])
  ballot_count=int(re.sub(r"\s","",match.group(1)))
  share=float(match.group(2))
  if not party or party in [p["name"] for p in parties]:continue
  if not 0<=share<=100 or ballot_count>votes:continue
  if abs(100*ballot_count/max(votes,1)-share)>0.21:continue
  parties.append({"name":party,"share":share,"votes":ballot_count})
 # When vote rows are unavailable, accept only the explicitly labelled ward
 # ballot summary. These are source shares, not estimates or invented totals.
 if not parties:
  summary=re.search(r"Vote breakdown\s*[·•]\s*Ward ballot\s+(.*?)(?:Stations open|Voting stations|Counting\s+\d)",s)
  if summary:
   method="ESP ward-ballot summary (detailed vote rows unavailable)"
   for match in re.finditer(r"([A-Za-z. +\-]{2,35}?)\s+(\d{1,3}\.\d)\s*%",summary.group(1)):
    party=label_of(match.group(1))
    share=float(match.group(2))
    if party and party not in [p["name"] for p in parties] and 0<=share<=100:
     parties.append({"name":party,"share":share})
   if sum(p["share"] for p in parties)>100.4:
    parties=[]
 # Never publish a collection of party votes that exceeds all valid ward-ballot votes.
 # Unknown parties can be omitted; published vote counts must be verbatim and consistent.
 if sum(p.get("votes",0) for p in parties)>votes:
  raise ValueError("Party vote totals exceed source valid ward-ballot votes")
 parties.sort(key=lambda p:-p["share"])
 if count and not parties:raise ValueError("Party vote rows could not be validated")
 ward_section=re.search(r"Wards\s*[·•]\s*"+str(nwards)+r"\b(.*?)(?:About these figures|$)",s)
 if not ward_section:raise ValueError("Ward list missing")
 ward_rows={}
 for w in re.finditer(r"Ward\s+(\d{1,3})\s+(\d+)\s+of\s+(\d+)\s+voting districts in\s+(DA|ANC|ActionSA|EFF|PA|IFP|MKP|VF PLUS|GOOD|ACDP|RISE)\s+(\d{1,3}\.\d)%",ward_section.group(1)):
  n,reported,den=int(w.group(1)),int(w.group(2)),int(w.group(3))
  if 1<=n<=nwards and 0<reported<=den and 0<=float(w.group(5))<=100:
   ward_rows[n]={"number":n,"status":"Partly counted","ballot_type":"Ward","reporting":str(reported)+" of "+str(den)+" districts","winner":ALIASES[w.group(4)],"parties":[{"name":ALIASES[w.group(4)],"share":float(w.group(5))}],"snapshot_at":stamp.isoformat(),"source_url":url+"/ward-"+str(n)}
 wards=[ward_rows.get(i,{"number":i,"status":"Not yet reported","ballot_type":"Ward","reporting":"Not yet reported","parties":[],"snapshot_at":stamp.isoformat(),"source_url":url+"/ward-"+str(i)}) for i in range(1,nwards+1)]
 return {"status":"Preliminary · IEC-derived via ESP","municipality":"Overstrand Local Municipality" if city=="Hermanus" else None,"ballot_type":"Ward","districts_reported":count,"districts_total":denom,"valid_votes":votes,"parties":parties,"seats":[],"wards":wards,"snapshot_at":stamp.isoformat(),"source_url":url},len(ward_rows)
def main():
 now=datetime.now(timezone.utc)
 path=Path("results.json");data=json.loads(path.read_text());data.setdefault("metros",{})
 report={"checked_at":now.isoformat(),"source":"ESP public pages (IEC-derived, unofficial; not direct IEC API)","checks":{},"results_updated":False}
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
  data["updated_at"]=now.isoformat();data["source"]="Provisional IEC-derived ward-ballot results via ESP (unofficial)"
  path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
  report["results_updated"]=True
 report["status"]="ok" if all(v["status"]=="ok" for v in report["checks"].values()) else "partial"
 Path("feed-status.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps(report,indent=2))
if __name__=="__main__":main()
