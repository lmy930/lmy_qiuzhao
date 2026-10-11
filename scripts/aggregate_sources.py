#!/usr/bin/env python3
"""Supplement search with publicly readable 2027 recruitment aggregate lists.

Every hit keeps the actual site URL and a nearby text excerpt. Presence on an
aggregate is evidence that 2027 recruitment has been published, NOT proof of
a precise launch date or that applications are currently open.
"""
import concurrent.futures as cf
import datetime as dt
import html
import json
import pathlib
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from broad_sources import ListingParser
from source_documents import resolve_url
from employer_aliases import aliases as employer_aliases

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"leads.json"
COMP=ROOT/"data"/"companies.json"
REG=ROOT/"data"/"source_catalog.json"
TODAY=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=8)).date().isoformat()
KEYWORDS=("27届秋招","2027届秋招","2027届校园招聘","2027校招","27秋招","2027届招聘","2027秋招","2027年校园招聘")
PAGES=[
"https://www.givemeoc.com/",
"https://www.gankinterview.cn/campus",
"https://www.mianlingai.com/jobs/",
"https://qiuzhaowang.com/latest",
"https://offerqianxian.com/",
"https://www.offerstar.cn/recruitment",
"https://campus.sma-wiki.cn/",
"https://mnowpick.nowcoder.com/m/school/schedule",
"https://www2.iguopin.com/",
"https://www.zhaopin.com/",
"https://www.51job.com/",
"https://www.yingjiesheng.com/",
"https://www.yinhangzhaopin.com/yhks/",
"https://www.yhks.cn/",
"https://www.liepin.com/",
"https://www.zhipin.com/",
"https://www.ncss.cn/",
]
ALIASES={"中国移动通信集团有限公司":["中国移动"],"中国联合网络通信集团有限公司":["中国联通"],"中国工商银行股份有限公司":["工商银行"],"中国农业银行股份有限公司":["农业银行"],"中国建设银行股份有限公司":["建设银行"],"中国邮政储蓄银行股份有限公司":["邮储银行"],"国家能源投资集团有限责任公司":["国家能源集团"],"中国海洋石油集团有限公司":["中国海油"],"中国第一汽车集团有限公司":["中国一汽"],"华为投资控股有限公司":["华为"],"比亚迪股份有限公司":["比亚迪"],"腾讯控股有限公司":["腾讯"],"阿里巴巴控股集团有限公司":["阿里巴巴"],"上海浦东发展银行股份有限公司":["浦发银行"]}
class Extract(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ("script","style","svg","noscript"):self.skip+=1
  if tag in ("li","tr","p","article","div","td","h1","h2","h3","br"):self.parts.append("\n")
 def handle_endtag(self,tag):
  if tag in ("script","style","svg","noscript") and self.skip:self.skip-=1
 def handle_data(self,data):
  if not self.skip:self.parts.append(data)
def load(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; QiuzhaoBot/1.0)","Accept":"text/html"})
 with urllib.request.urlopen(req,timeout=17) as r:
  if "html" not in r.headers.get("Content-Type","text/html"):raise ValueError("Non HTML page")
  raw=r.read(1800000); encoding=r.headers.get_content_charset() or "utf-8"
 document=raw.decode(encoding,errors="replace")
 links=ListingParser();links.feed(document)
 p=Extract();p.feed(document)
 text=html.unescape("".join(p.parts))
 return {"text":re.sub(r"[ \t\r]+"," ",text),"links":links.items}
def normalize(s):return re.sub(r"\s+|[（）()【】（）·]","",s or "").lower()
def names(c):
 name=c["name"];stub=re.sub(r"(控股集团股份有限公司|集团股份有限公司|股份有限公司|有限责任公司|集团有限公司|有限公司)$","",name)
 return list(dict.fromkeys([x for x in [name,stub] if len(x)>=4]+[x for x in ALIASES.get(name,[])+employer_aliases(name) if len(x)>=2]))
def inspect(item,companies):
 url,text,error=item
 if error:return [],{"site":url,"error":error}
 # Each line-local window must mention the company and the class/cohort,
 # rather than inferring every employer on a general 2027 landing page is recruiting.
 document=text if isinstance(text,dict) else {"text":text,"links":[]}
 compact=normalize(document["text"])
 matches=[]
 # Preserve actual article links; a platform homepage is never the original announcement.
 for title,href in document["links"]:
  if not any(k in normalize(title) for k in map(normalize,KEYWORDS)):continue
  target_url=resolve_url(url,href)
  if not target_url or not target_url.startswith("https://"):continue
  for c in companies:
   if any(normalize(alias) in normalize(title) for alias in names(c)):
    matches.append({"name":c["name"],"hit":{"title":title,"url":target_url,"snippet":title,"published_at":None,"discovered_via":"招聘平台文章链接","evidence_level":"article_link"}})

 for c in companies:
  for alias in names(c):
   target=normalize(alias)
   if len(target)<2:continue
   match=re.search(re.escape(target),compact)
   if not match:continue
   idx=match.start(); excerpt=compact[max(0,idx-70):idx+len(target)+110]
   if not any(k in excerpt for k in map(normalize,KEYWORDS)):continue
   if any(w in excerpt for w in ("仅限2026届","2025届校招")):continue
   matches.append({"name":c["name"],"hit":{"title":c["name"]+" 2027届秋招｜招聘信息汇总","url":url,"snippet":excerpt[:175],"published_at":None,"discovered_via":"2027届招聘聚合页","evidence_level":"aggregate_nearby_text"}})
   break
 return matches,{"site":url,"matched":len(matches)}
def main():
 companies=json.loads(COMP.read_text(encoding="utf-8"))["companies"]
 leads=json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"leads":[]}
 byname={x["name"]:x for x in leads.get("leads",[])}
 def fetch_one(url):
  try:return url,load(url),None
  except Exception as e:return url,"",str(e)[:180]
 with cf.ThreadPoolExecutor(max_workers=4) as pool:
  checks=[inspect(x,companies) for x in pool.map(fetch_one,PAGES)]
 added=0
 for pairs,report in checks:
  for x in pairs:
   name=x["name"];entry=byname.setdefault(name,{"name":name,"hits":[],"last_found":TODAY})
   if not any(h["url"]==x["hit"]["url"] for h in entry["hits"]):
    entry["hits"].append(x["hit"]);added+=1
   entry["last_found"]=TODAY
 leads["leads"]=sorted(byname.values(),key=lambda x:x.get("last_found",""),reverse=True)
 leads["aggregate_sources_scanned"]=len(PAGES)
 leads["aggregate_report"]=[report for pairs,report in checks]
 OUT.write_text(json.dumps(leads,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("AGGREGATE_SOURCES="+str(len(PAGES))+" NEW_HITS="+str(added)+" "+json.dumps(leads["aggregate_report"],ensure_ascii=False))
if __name__=="__main__":main()
