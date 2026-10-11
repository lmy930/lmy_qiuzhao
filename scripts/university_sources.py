#!/usr/bin/env python3
"""Directly scan paginated university recruitment listings rather than hoping for RSS.
Records only school-posted headlines explicitly mentioning the 2027 cohort and employer.
Never fabricates application start dates from page publication dates.
"""
import concurrent.futures as cf
import datetime as dt
from html.parser import HTMLParser
import json
import pathlib
import re
import urllib.parse
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
DIR=ROOT/"data"
TODAY=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=8)).date().isoformat()
from employer_aliases import aliases
from page_evidence import match_scope
BASE="https://career.nankai.edu.cn"
PAGES=[BASE+"/correcruit/index.html"]+[BASE+"/correcruit/index/p/"+str(n)+".html" for n in range(2,66)]
RECRUIT=("校园招聘","秋招","校招","招聘启动","招聘开启","管培生招聘","秋季招聘","应届生招聘","毕业生招聘")
class Anchors(HTMLParser):
 def __init__(self):
  super().__init__();self.items=[];self.href=None;self.text=[]
 def handle_starttag(self,tag,attrs):
  if tag=="a":
   self.href=dict(attrs).get("href","");self.text=[]
 def handle_data(self,data):
  if self.href is not None:self.text.append(data)
 def handle_endtag(self,tag):
  if tag=="a" and self.href is not None:
   label=re.sub(r"\s+","",''.join(self.text))
   if label:self.items.append((label,self.href))
   self.href=None;self.text=[]
def norm(s):return re.sub(r"\s+|[（）()【】［］\[\]·•－-]","",(s or "")).lower()
def get_one(url):
 try:
  req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
  with urllib.request.urlopen(req,timeout=15) as r:
   if "html" not in r.headers.get("Content-Type","text/html"):raise ValueError("non HTML page")
   payload=r.read(900000);encoding=r.headers.get_content_charset() or "utf-8"
  parser=Anchors();parser.feed(payload.decode(encoding,errors="replace"))
  return {"url":url,"items":parser.items}
 except Exception as exc:return {"url":url,"error":str(exc)[:180]}
def main():
 data=json.loads((DIR/"companies.json").read_text(encoding="utf-8"))
 old=json.loads((DIR/"leads.json").read_text(encoding="utf-8"))
 leadmap={x["name"]:x for x in old.get("leads",[])}
 employers=data["companies"]
 normalized=[(c["name"],aliases(c["name"])) for c in employers]
 coverage=[];additions=0
 with cf.ThreadPoolExecutor(max_workers=6) as pool:
  pages=list(pool.map(get_one,PAGES))
 for page in pages:
  if "error" in page:
   coverage.append({"page":page["url"],"error":page["error"]});continue
  matched=set()
  for title,href in page["items"]:
   if not re.search(r"/correcruit/content/id/\d+",href,re.I):continue
   t=norm(title)
   if "2027" not in t and "27届" not in t:continue
   if not any(x in t for x in RECRUIT):continue
   if any(x in t for x in ("2025届","2026届","2028届")):continue
   url=urllib.parse.urljoin(BASE,href)
   if not url.startswith(BASE+"/"):continue
   for name,names in normalized:
    # For short brands (e.g. 京东) require a literal brand in the job headline.
    if match_scope(name,title) is None:continue
    if name=="中国航空集团有限公司" and "航空发动机" in t:continue
    entry=leadmap.setdefault(name,{"name":name,"hits":[],"last_found":TODAY})
    if not any(h.get("url")==url for h in entry["hits"]):
     entry["hits"].append({"title":title+" - 南开大学就业网","url":url,"snippet":"南开大学就业信息网2027届招聘信息","published_at":None,"evidence_level":"university_listing","discovered_via":"南开大学就业信息网"})
     additions+=1
    entry["last_found"]=TODAY
    matched.add(name)
  coverage.append({"page":page["url"],"matched_employers":len(matched)})
 old["leads"]=sorted(leadmap.values(),key=lambda x:x.get("last_found",""),reverse=True)
 old["university_scan_at"]=TODAY
 old["university_pages_ok"]=sum("error" not in p for p in pages)
 old["university_new_hits"]=additions
 (DIR/"leads.json").write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (DIR/"university_scan_report.json").write_text(json.dumps({"checked_at":TODAY,"pages_ok":old["university_pages_ok"],"pages_attempted":len(PAGES),"new_hits":additions,"pages":coverage},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(f"UNIVERSITY_PAGES_OK={old['university_pages_ok']}/{len(PAGES)} NEW_HITS={additions}")
if __name__=="__main__":main()
