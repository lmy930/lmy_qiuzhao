#!/usr/bin/env python3
"""Promote independently verified multi-source recruitment evidence to the dashboard.

This script consumes links discovered by search, fetches their actual pages, and
classifies *2027 recruitment launched*, not necessarily *application still open*.
No manual review is required for high-confidence discoveries. Unknown remains unknown.
"""
import concurrent.futures as cf
import datetime as dt
import html
import json
import pathlib
import re
import urllib.parse
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
DIR=ROOT/"data"
DATE=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=8)).date()
UA="Mozilla/5.0 (compatible; QiuzhaoEvidenceVerifier/2.0)"
KWORDS=("校园招聘","秋季校园招聘","校招","秋招","应届生招聘","毕业生招聘")
EXCLUDE=("2026届校园招聘","2025届校园招聘")
CORP_DOMAINS=("career.huawei.com","job.byd.com","job.icbc.com.cn","job.10086.cn","zp.czbank.com.cn")
TRUSTED_GOV=("sasac.gov.cn","gov.cn")
TRUSTED_UNIV=(".edu.cn",)
TRUSTED_PUBLISHERS=("国务院国有资产监督管理委员会","国资委","中国农业大学新闻网","南京审计大学","上观新闻")
LAUNCH_WORDS=("启动","正式开启","全面启动","校园招聘开始","秋季校园招聘","秋招开启","火热进行中")
RENAME={
"华为投资控股有限公司":["华为"],
"中国工商银行股份有限公司":["工商银行","中国工商银行"],
"中国移动通信集团有限公司":["中国移动"],
"浙江吉利控股集团有限公司":["吉利控股","吉利"],
"中粮集团有限公司":["中粮集团"],
"比亚迪股份有限公司":["比亚迪"],
"上海浦东发展银行股份有限公司":["浦发银行"],
"国家能源投资集团有限责任公司":["国家能源集团"],
}
def normalize(s):return re.sub(r"\s+|[（）()【】［］\-]","",s or "").lower()
def names(c):
 s=c["name"]
 a=RENAME.get(s,[])
 shorter=re.sub(r"(控股集团股份有限公司|股份有限公司|有限责任公司|集团有限公司|有限公司)$","",s)
 return [normalize(t) for t in dict.fromkeys([s,shorter]+a) if len(t)>=3]
def trust(url):
 try:host=urllib.parse.urlparse(url).hostname or ""
 except ValueError:return False
 return host in CORP_DOMAINS or any(host==v or host.endswith("."+v) for v in TRUSTED_GOV) or any(host.endswith(v) for v in TRUSTED_UNIV)
def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
 with urllib.request.urlopen(req,timeout=8) as r:
  if "text/html" not in (r.headers.get("Content-Type","text/html")).lower():return ""
  data=r.read(280000)
  h=r.headers.get_content_charset() or "utf-8"
 text=data.decode(h,errors="replace")
 text=re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>"," ",text,flags=re.S|re.I)
 return normalize(html.unescape(re.sub(r"<[^>]+>"," ",text)))
def check(c,entry):
 hits=entry.get("hits",[])[:25]
 aggregate=[h for h in hits if h.get("evidence_level")=="aggregate_nearby_text"]
 agg_hosts={urllib.parse.urlsplit(h.get("url","")).hostname for h in aggregate}
 good=[]
 if len(agg_hosts)>=2:
  good=[{"url":h["url"],"title":h["title"],"source":"两个及以上独立2027届招聘汇总站点匹配","seen":str(DATE)} for h in aggregate[:3]]
 for h in hits:
  if h.get("evidence_level")=="aggregate_nearby_text":continue
  url=h.get("url","")
  if not url.startswith("https://"):continue
  # News RSS is a discovery source: resolve the original publisher only if available.
  # Otherwise require two independent recruitment-index hits before recording launch.
  if "news.google.com/rss/articles/" in url:
   title=h.get("title","")
   if "2027" not in title or not any(k in title for k in LAUNCH_WORDS):continue
   if not any(k in title for k in TRUSTED_PUBLISHERS):continue
   if not any(n in normalize(title) for n in names(c)):continue
   good.append({"url":url,"title":title[:160],"source":"可信发布方的招聘资讯摘要（正文未独立验证）","seen":str(DATE)})
   continue
  if not trust(url):continue
  try:
   body=fetch(url)
   if not body or "2027" not in body or not any(x in body for x in KWORDS):continue
   if not any(alias in body for alias in names(c)):continue
   title=normalize(h.get("title",""))
   if "2027" not in title and not any(k in title for k in KWORDS):continue
   good.append({"url":url,"title":h.get("title","")[:160],"source":"官网/政府/高校就业网","seen":str(DATE)})
  except Exception:continue
 return c["name"],good
def main():
 path=DIR/"companies.json"
 data=json.loads(path.read_text(encoding="utf-8"))
 leads=json.loads((DIR/"leads.json").read_text(encoding="utf-8"))
 candidates={x["name"]:x for x in leads.get("leads",[]) if x.get("hits")}
 targets=[c for c in data["companies"] if c["name"] in candidates]
 results={}
 with cf.ThreadPoolExecutor(max_workers=10) as executor:
  for name,good in executor.map(lambda c:check(c,candidates[c["name"]]), targets):
   results[name]=good
 promoted=[]
 for c in data["companies"]:
  good=results.get(c["name"],[])
  if not good:continue
  c["evidence_sources"]=good
  c["evidence_last_checked"]=str(DATE)
  c["discovered_2027"]=True
  # An official corporate, government or university announcement establishes launch.
  # It does not establish that applications are still open or the precise opening date.
  if c["status"]=="待核验":
   c["status"]="已发布公告（网申待核验）"
   c["announcement_source_url"]=good[0]["url"]
   c["verification_note"]="后台自动交叉检索到2027届招聘已发布（官方/高校招聘信息或两个独立聚合平台）；启动日期和报名截止需另行确认。"
   promoted.append(c["name"])
 data["generated_at"]=str(DATE)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (DIR/"auto_verification_report.json").write_text(json.dumps({"checked_at":str(DATE),"candidates":len(targets),"verified":sum(bool(x) for x in results.values()),"newly_promoted":len(promoted),"promoted":promoted,"scope":"2027届招聘已发布，不保证报名仍开放"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(f"AUTO_VERIFIED={sum(bool(x) for x in results.values())} NEW_PROMOTED={len(promoted)}")
if __name__=="__main__":main()
