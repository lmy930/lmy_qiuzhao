#!/usr/bin/env python3
"""Reconcile recruiting leads into employer launch status with auditable evidence.
Only confirms the 2027 cohort LAUNCHED; never infers applications are still open.
"""
import datetime as dt
import json
import pathlib
import re
import urllib.parse
from collections import defaultdict
from page_evidence import match_scope
from employer_aliases import aliases as canonical_aliases
ROOT=pathlib.Path(__file__).resolve().parents[1]
DIR=ROOT/"data"
TODAY=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=8)).date().isoformat()
YEAR=("2027","27届","27级")
LAUNCH=("正式启动","全面启动","正式开启","正式开招","招聘启动","校招开启","校招开始","秋招启动","秋招开启","校园招聘开启","招聘正式启动","校园招聘正式","2027校园招聘","2027届校园招聘","2027年度校园招聘","校园招聘公告","秋季校园招聘","校招火热进行","秋招宣讲会","招聘宣讲会")
IGNORE=("2026届","2025届","2024届","2028届")
HIGH_TRUST=("国务院国有资产监督管理委员会","国资委","银行官网","集团官方网站","就业指导中心","学校就业网","高校就业网","大学新闻网","edu.cn")
ALIASES={
"中国航天科技集团有限公司":["中国航天科技集团","航天科技集团"],
"中国航天科工集团有限公司":["中国航天科工","航天科工"],
"中国航空发动机集团有限公司":["中国航空发动机","中国航发"],
"中国航空集团有限公司":["中国国航","中国航空集团"],
"中国海洋石油集团有限公司":["中国海油"],
"中国电信集团有限公司":["中国电信"],
"中国联合网络通信集团有限公司":["中国联通"],
"中国移动通信集团有限公司":["中国移动"],
"中国远洋海运集团有限公司":["中远海运","中国远洋海运"],
"中国东方航空集团有限公司":["中国东航","东方航空"],
"中国第一汽车集团有限公司":["中国一汽","一汽集团"],
"中国大唐集团有限公司":["中国大唐","大唐集团"],
"中国东方电气集团有限公司":["东方电气集团"],
"国家能源投资集团有限责任公司":["国家能源集团"],
"国家开发投资集团有限公司":["国投集团","国家开发投资集团"],
"中粮集团有限公司":["中粮集团"],
"华为投资控股有限公司":["华为"],
"腾讯控股有限公司":["腾讯"],
"比亚迪股份有限公司":["比亚迪"],
"京东集团":["京东集团"],
"中国工商银行股份有限公司":["中国工商银行","工商银行"],
"中国农业银行股份有限公司":["中国农业银行","农业银行"],
"中国建设银行股份有限公司":["中国建设银行","建设银行"],
"中国邮政储蓄银行股份有限公司":["中国邮政储蓄银行","邮储银行"],
"上海浦东发展银行股份有限公司":["浦发银行","上海浦东发展银行"],
"中国光大银行股份有限公司":["中国光大银行","光大银行"],
"广发银行股份有限公司":["广发银行"],
"浙商银行股份有限公司":["浙商银行"],
"招商银行股份有限公司":["招商银行"],
"携程集团有限公司":["携程集团"],
}
def norm(s):
 return re.sub(r"\s+|[（）()【】\[\]·•_\-－]","",s or "").lower()
def company_aliases(name):
 short=re.sub(r"(控股集团股份有限公司|集团股份有限公司|股份有限公司|有限责任公司|集团有限公司|有限公司)$","",name)
 return [norm(x) for x in dict.fromkeys(ALIASES.get(name,[])+[name,short]) if len(norm(x))>=4]
def hosts(h):
 u=h.get("url","");netloc=urllib.parse.urlsplit(u).hostname or ""
 if netloc=="news.google.com":
  # RSS article links proxy different publishers: use the publisher appended to the title.
  t=h.get("title","")
  return norm(t.rsplit(" - ",1)[-1]) if " - " in t else "news.google.com"
 return netloc
def score(name,h):
 title=h.get("title","")
 t=norm(title)
 if not any(y in t for y in YEAR) or any(y in t for y in IGNORE):return 0
 if not any(a in t for a in canonical_aliases(name)):return 0
 if name=="中国航空集团有限公司" and any(x in t for x in ("航空发动机","中国航发","中国航空工业")):return 0
 if name=="中国农业发展集团有限公司" and any(x in t for x in ("农业发展银行","农发行")):return 0
 if name=="中国石油天然气集团有限公司" and any(x in t for x in ("中国石油化工","中石化")):return 0
 if not any(norm(x) in t for x in LAUNCH) and not any(x in t for x in ("校园招聘","校招","秋招","管培生招聘","2027届管培生计划")) and not re.search(r"(招聘|校招|秋招).{0,10}(启动|开启|开始|进行|发布)",t):return 0
 # Explicit 2027 launch headlines from a trusted government or university publication.
 publisher=hosts(h)
 if match_scope(name,title) is None:return 0
 if (urllib.parse.urlsplit(h.get("url","")).hostname or "").endswith(".edu.cn"):return 3
 host=urllib.parse.urlsplit(h.get("url","")).hostname or ""
 if host.endswith(".gov.cn"):return 3
 # Other clearly attributable 2027 recruitment headlines are discovery evidence.
 return 1
def main():
 path=DIR/"companies.json"
 data=json.loads(path.read_text(encoding="utf-8"))
 raw=json.loads((DIR/"leads.json").read_text(encoding="utf-8"))
 leads={x["name"]:x for x in raw.get("leads",[])}
 changed=[]
 details=[]
 for c in data["companies"]:
  hits=leads.get(c["name"],{}).get("hits",[])
  positive=[(h,score(c["name"],h)) for h in hits]
  positive=[(h,k) for h,k in positive if k]
  publishers={hosts(h) for h,k in positive if hosts(h)}
  strong=any(k>=3 for h,k in positive)
  corroborated=len(publishers)>=2
  launched=strong
  if positive:
   c["evidence_last_checked"]=TODAY
   c["evidence_sources"]=[{"title":h.get("title",""),"url":h.get("url",""),"publisher":hosts(h),"classification":"trusted" if k>=3 else "discovery"} for h,k in positive[:8]]
  if launched and c.get("status")=="待核验":
   c["status"]="已发布公告（网申待核验）"
   c["discovered_2027"]=True
   trusted_hit=next(h for h,k in positive if k>=3)
   c["source_scope"]=match_scope(c["name"],trusted_hit.get("title",""))
   c["announcement_source_url"]=trusted_hit.get("url")
   c["verification_note"]="自动确认2027届校招曾启动：政府/高校实际域名上的明确校招标题。当前报名是否仍开放、首次启动日期尚未确认。"
   changed.append(c["name"])
  details.append({"name":c["name"],"evidence":len(positive),"publishers":len(publishers),"accepted":launched})
 data["generated_at"]=TODAY
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 report={"checked_at":TODAY,"employers":len(data["companies"]),"lead_companies":len(leads),"positive_evidence_companies":sum(x["evidence"]>0 for x in details),"accepted_companies":sum(x["accepted"] for x in details),"newly_promoted":len(changed),"promoted":changed,"note":"已启动不等于仍可报名；原始证据在companies.json，只有明确日期才进入日历"}
 (DIR/"auto_verification_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
