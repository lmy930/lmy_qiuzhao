#!/usr/bin/env python3
"""Direct monitoring of government recruitment index titles for 2027 alumni.
No reliance on general RSS indexing; keep dates as publication dates, not application starts.
"""
import datetime as dt
import html
import json
import pathlib
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from employer_aliases import aliases as canonical_aliases
from html.parser import HTMLParser
from page_evidence import match_scope
ROOT=pathlib.Path(__file__).resolve().parents[1]
DIR=ROOT/"data"
TODAY=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=8)).date().isoformat()
SOURCES=[
 ("国务院国资委","https://wap.sasac.gov.cn/n2588035/n2588325/n2588350/index.html"),
 ("上海市国资委","https://www.gzw.sh.gov.cn/shgzw_xxgk_cqzp/")]
ALIASES={
"中国航空工业集团有限公司":["航空工业集团"],
"中国航空发动机集团有限公司":["中国航空发动机","中国航发"],
"中国航天科工集团有限公司":["航天科工"],
"中国航天科技集团有限公司":["航天科技"],
"中国第一汽车集团有限公司":["中国一汽"],
"中国移动通信集团有限公司":["中国移动"],
"中国海洋石油集团有限公司":["中国海油"],
"中国电信集团有限公司":["中国电信"],
"中国远洋海运集团有限公司":["中远海运","中国远洋海运"],
"中国机械工业集团有限公司":["国机集团"],
"中国东方航空集团有限公司":["中国东方航空"],
"中国大唐集团有限公司":["中国大唐"],
"中国铝业集团有限公司":["中国铝业集团"],
"中国电子科技集团有限公司":["中国电科"],
"中国石油天然气集团有限公司":["中国石油"],
"中国绿发投资集团有限公司":["中国绿发"],
"上海浦东发展银行股份有限公司":["浦发银行"],
"上海银行股份有限公司":["上海银行"],
}
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.stack=0;self.parts=[];self.links=[];self.href=None;self.linktext=[]
 def handle_starttag(self,tag,attrs):
  if tag=="a":self.href=dict(attrs).get("href");self.linktext=[]
 def handle_data(self,txt):
  if self.href is not None:self.linktext.append(txt)
 def handle_endtag(self,tag):
  if tag=="a" and self.href is not None:
   s=" ".join(self.linktext).strip()
   if s:self.links.append((re.sub(r"\s+","",html.unescape(s)),self.href))
   self.href=None
def read(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; QiuzhaoScanner/2.0)"})
 with urllib.request.urlopen(req,timeout=16) as r:
  content=r.read(550000);encoding=r.headers.get_content_charset() or "utf-8"
 p=Parser();p.feed(content.decode(encoding,errors="replace"));return p.links
def rss_fallback(source_url):
 domain=urllib.parse.urlsplit(source_url).hostname or ""
 site="sasac.gov.cn" if domain.endswith("sasac.gov.cn") else domain
 hits=[]
 for phrase in ("2027届 校园招聘","2027 校招 启动"):
  query=f'site:{site} {phrase}'
  url="https://www.bing.com/search?format=rss&q="+urllib.parse.quote(query)
  req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/rss+xml"})
  with urllib.request.urlopen(req,timeout=13) as r:feed=ET.fromstring(r.read(450000))
  for item in feed.findall(".//item"):
   title=(item.findtext("title") or "").strip()
   link=(item.findtext("link") or "").strip()
   host=urllib.parse.urlsplit(link).hostname or ""
   if host==site or host.endswith("."+site):
    hits.append((title,link))
 return list(dict.fromkeys(hits))
def norm(s):return re.sub(r"\s+|[（）()【】]","",s or "").lower()
def aliases(name):
 short=re.sub(r"(集团股份有限公司|股份有限公司|有限责任公司|集团有限公司|有限公司)$","",name)
 return list(dict.fromkeys(canonical_aliases(name)+[norm(x) for x in ALIASES.get(name,[]) if len(norm(x))>=4]))
def valid(title, name):
 t=norm(title)
 if not any(x in t for x in ("2027","27届")):return False
 if not any(x in t for x in ("校园招聘","校招","秋招","高校毕业生招聘","招聘启动","招聘正式启动","校园招聘开启")):return False
 if match_scope(name,title) is None:return False
 if name=="中国航空工业集团有限公司" and ("航空发动机" in t or "中国航发" in t):return False
 if name=="中国航空集团有限公司" and ("中国航空工业" in t or "航空发动机" in t):return False
 if name=="中国农业发展集团有限公司" and ("农业发展银行" in t or "农发行" in t):return False
 if name=="中国航空发动机集团有限公司" and "航空工业集团" in t:return False
 return True
def main():
 path=DIR/"companies.json";data=json.loads(path.read_text(encoding="utf-8"))
 leads_path=DIR/"leads.json";leads=json.loads(leads_path.read_text());leadmap={e["name"]:e for e in leads.get("leads",[])}
 report=[];changed=[]
 for source,url in SOURCES:
  mode="direct"
  direct_error=None
  try:links=read(url)
  except Exception as e:
   direct_error=str(e)[:160]
   try:links=rss_fallback(url);mode="indexed_fallback"
   except Exception as fallback:
    report.append({"source":source,"direct_error":direct_error,"fallback_error":str(fallback)[:160]});continue
  matches=0
  for c in data["companies"]:
   found=[(title,href) for title,href in links if valid(title,c["name"])]
   if not found:continue
   matches+=1
   title,href=found[0]
   entry=leadmap.setdefault(c["name"],{"name":c["name"],"hits":[],"last_found":TODAY})
   for title,href in found:
    link=urllib.parse.urljoin(url,href)
    if not any(h.get("url")==link for h in entry["hits"]):
     entry["hits"].append({"title":title,"url":link,"published_at":None,"discovered_via":source,"evidence_level":"government_article_discovery"})
     changed.append(c["name"])
   entry["last_found"]=TODAY
  report.append({"source":source,"mode":mode,"direct_error":direct_error,"links":len(links),"matched_employers":matches})
 leads["leads"]=sorted(leadmap.values(),key=lambda x:x.get("last_found",""),reverse=True)
 leads_path.write_text(json.dumps(leads,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (DIR/"government_scan_report.json").write_text(json.dumps({"scanned_at":TODAY,"sources":report,"new_candidate_employers":sorted(set(changed)),"note":"政府栏目标题只用于发现，必须读取正文后才能确认。"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
