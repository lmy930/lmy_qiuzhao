#!/usr/bin/env python3
"""Daily discovery across all monitored employers. Unverified links never become 'open'."""
import concurrent.futures as cf
import datetime as dt
import email.utils
import json
import pathlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from employer_aliases import primary, aliases as employer_aliases

BASE=pathlib.Path(__file__).resolve().parents[1]
DATA=BASE/"data"/"companies.json"
OUTPUT=BASE/"data"/"leads.json"
NOW=dt.datetime.now(dt.timezone.utc)
TODAY=(NOW+dt.timedelta(hours=8)).date().isoformat()
UA="Mozilla/5.0 (compatible; QiuzhaoCalendarBot/1.1)"
Y="2027"
ALIASES={
"华为投资控股有限公司":"华为","比亚迪股份有限公司":"比亚迪",
"中国移动通信集团有限公司":"中国移动","中国电信集团有限公司":"中国电信",
"中国联合网络通信集团有限公司":"中国联通",
"中国工商银行股份有限公司":"工商银行","中国农业银行股份有限公司":"农业银行",
"中国银行股份有限公司":"中国银行","中国建设银行股份有限公司":"建设银行",
"中国邮政储蓄银行股份有限公司":"邮储银行",
"国家能源投资集团有限责任公司":"国家能源集团",
"中国石油天然气集团有限公司":"中国石油",
"中国石油化工集团有限公司":"中国石化",
"中国海洋石油集团有限公司":"中国海油",
"中国第一汽车集团有限公司":"中国一汽",
"中国大唐集团有限公司":"中国大唐",
"中国电子科技集团有限公司":"中国电科",
"中国航天科工集团有限公司":"航天科工",
"中国民生银行股份有限公司":"民生银行",
"上海浦东发展银行股份有限公司":"浦发银行",
"浙商银行股份有限公司":"浙商银行",
"国家电网有限公司":"国家电网",
"中粮集团有限公司":"中粮集团",
}
RECRUIT=("校园招聘","秋季招聘","秋招","校招","应届生招聘","毕业生招聘","高校毕业生招聘")
def search_name(s):
    return primary(s)
def normalize(s):
    return re.sub(r"\s+|[（）()·]","",s or "").lower()
def feed(name, term=None, backfill=False):
    short=term or search_name(name)
    query=f'"{short}" ("2027" OR "27届") ("校园招聘" OR "校招" OR "秋招" OR "毕业生招聘")'
    if backfill:query+=' ("网申时间" OR "报名时间" OR "投递")'
    url="https://www.bing.com/search?format=rss&q="+urllib.parse.quote(query)
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/rss+xml,application/xml,text/xml"})
    with urllib.request.urlopen(req,timeout=11) as response:
        if response.status!=200: raise RuntimeError(f"HTTP {response.status}")
        raw=response.read(350000)
    tree=ET.fromstring(raw)
    hits=[]
    for item in tree.findall(".//item")[:12]:
        title=(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        description=re.sub("<[^>]*>"," ",item.findtext("description") or "").strip()
        body=normalize(title+" "+description)
        if not any(x in body for x in ("2027","27届")) or not any(x in body for x in RECRUIT): continue
        if normalize(short) not in body: continue
        if not link.startswith("https://"): continue
        if not urllib.parse.urlsplit(link).hostname: continue
        stamp=item.findtext("pubDate")
        try: pub=email.utils.parsedate_to_datetime(stamp).date().isoformat() if stamp else None
        except (ValueError,TypeError): pub=None
        hits.append({"title":title[:160],"url":link,"snippet":description[:280],"published_at":pub})
    return hits[:5]
def google_news(name):
    short=search_name(name)
    query=f'"{short}" "2027" "校园招聘"'
    url="https://news.google.com/rss/search?q="+urllib.parse.quote(query)+"&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=11) as response:
        root=ET.fromstring(response.read(350000))
    hits=[]
    for item in root.findall(".//item")[:12]:
        title=(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        body=normalize(title+" "+(item.findtext("description") or ""))
        if any(x in body for x in ("2027","27届")) and any(x in body for x in RECRUIT) and normalize(short) in body and link.startswith("https://"):
            hits.append({"title":title[:160],"url":link,"snippet":"","published_at":None})
    return hits[:5]

SOURCES=json.loads((BASE/"data"/"source_catalog.json").read_text(encoding="utf-8"))["sources"]
OFFICIAL_DOMAIN={
"兴业银行股份有限公司":"xyyh.com.cn",
"中国农业发展银行":"adbc.com.cn",
"中国核工业集团有限公司":"cnnc.com.cn",
"国家电力投资集团有限公司":"spic.com.cn",
"中国中化控股有限责任公司":"sinochem.com",
"中国中煤能源集团有限公司":"chinacoal.com",
"中国中车集团有限公司":"crrcgc.cc",
"中国广核集团有限公司":"cgnpc.com.cn",
"中国长江三峡集团有限公司":"ctg.com.cn",
"国家开发投资集团有限公司":"sdic.com.cn",
"中国铝业集团有限公司":"chinalco.com.cn",
"浙商银行股份有限公司":"czbank.com.cn",
"中国华电集团有限公司":"chd.com.cn",
"国家电网有限公司":"sgcc.com.cn",
"中国电力建设集团有限公司":"powerchina.cn",
"中国建筑集团有限公司":"cscec.com",
"中国工商银行股份有限公司":"icbc.com.cn",
"中国农业银行股份有限公司":"abchina.com",
"中国建设银行股份有限公司":"ccb.com",
"中国银行股份有限公司":"bankofchina.com",
"招商银行股份有限公司":"cmbchina.com",
"中国邮政储蓄银行股份有限公司":"psbc.com",
"中国石油天然气集团有限公司":"cnpc.com.cn",
"中国石油化工集团有限公司":"sinopecgroup.com",
"中国海洋石油集团有限公司":"cnooc.com.cn",
}

def site_feed(c):
    # Rotate across all registered sites without multiplying search load by 25.
    relevant=[x for x in SOURCES if any(g in x["groups"] for g in c.get("groups",[]))]
    if not relevant:return []
    n=(dt.date.fromisoformat(TODAY).toordinal()+sum(ord(k) for k in c["name"]))%len(relevant)
    source=relevant[n]
    official=OFFICIAL_DOMAIN.get(c["name"])
    if official:source={"name":"该企业官网优先","domain":official}
    short=search_name(c["name"])
    query=f'site:{source["domain"]} "{short}" "2027" (校招 OR 秋招 OR 校园招聘)'
    url="https://www.bing.com/search?format=rss&q="+urllib.parse.quote(query)
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=11) as response:root=ET.fromstring(response.read(350000))
    hits=[]
    for item in root.findall(".//item")[:15]:
        title=(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        description=re.sub("<[^>]+>"," ",item.findtext("description") or "").strip()
        body=normalize(title+" "+description)
        if not any(x in body for x in ("2027","27届")) or not any(k in body for k in RECRUIT) or normalize(short) not in body:continue
        if not link.startswith("https://"):continue
        hits.append({"title":title[:160],"url":link,"snippet":description[:280],"published_at":None,"discovered_via":source["name"]})
    return hits[:5]

def worker(c):
    hits=[]; failures=[]; successes=0
    terms=list(dict.fromkeys([search_name(c["name"]),*employer_aliases(c["name"])]))
    term=terms[dt.date.fromisoformat(TODAY).toordinal()%len(terms)]
    backfill=c.get("status")!="待核验" and not c.get("open_date_evidence")
    for provider in (lambda name:feed(name,term,backfill),google_news,lambda _:site_feed(c)):
        try:
            hits+=provider(c["name"]);successes+=1
        except Exception as exc:failures.append(str(exc)[:90])
    unique=list({hit["url"]:hit for hit in hits}.values())[:12]
    return c["name"],unique,None if successes else "; ".join(failures)[:160],failures
def main():
    payload=json.loads(DATA.read_text(encoding="utf-8"))
    companies=payload["companies"]
    targets=sorted(companies,key=lambda c:(c.get("status")!="待核验",bool(c.get("open_date_evidence")),c["name"]))
    former={}
    if OUTPUT.exists():
        try: former={x["name"]:x for x in json.loads(OUTPUT.read_text(encoding="utf-8")).get("leads",[])}
        except (ValueError,KeyError): pass
    results={}
    # Limit parallelism to avoid overloading search providers. RSS blocking/rate limits are reported.
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        for name,hits,error,failures in pool.map(worker,targets):
            results[name]=(hits,error,failures)
    errors=[]
    good=0
    for c in companies:
        name=c["name"]
        hits,error,failures=results[name]
        if error:
            errors.append({"name":name,"error":error})
            c["last_search_error"]=error
        else:
            good+=1
            c["last_searched_at"]=TODAY
            c.pop("last_search_error",None)
            if hits:
                old=former.get(name,{})
                merged={h["url"]:h for h in old.get("hits",[])}
                merged.update({h["url"]:h for h in hits})
                old.update({"name":name,"hits":list(merged.values()),"last_found":TODAY})
                former[name]=old
            # Preserve old leads if new search returns empty: an empty RSS result isn't proof of no recruiting.
        c["discovery_count"]=len(former.get(name,{}).get("hits",[]))
    OUTPUT.write_text(json.dumps({
        "scanned_at":NOW.isoformat(),
        "companies_total":len(companies),
        "registered_sources":len(SOURCES),
        "search_methods":["rotating legal/brand alias Bing RSS; date backfill for known launches","Google News RSS","rotating domain-targeted Bing RSS"],
        "searches_attempted":len(companies),
        "searches_succeeded":good,
        "companies_with_new_hits":sum(bool(results[c["name"]][0]) for c in companies),
        "companies_with_any_leads":len(former),
        "note":"搜索成功指至少一个搜索服务返回结果，未必找到招聘公告；未发现不代表未开启。",
        "searches_failed":len(errors),
        "provider_requests_attempted":3*len(companies),
        "provider_requests_failed":sum(len(results[c["name"]][2]) for c in companies),
        "partial_provider_errors":[{"name":c["name"],"errors":results[c["name"]][2]} for c in companies if results[c["name"]][2]],
        "errors":errors[:30],
        "disclaimer":"RSS搜索发现属于未核验线索，不能据此宣称开放网申。来源可能包含转发、旧消息、伪相关。请以官方招聘公告为准。",
        "leads":sorted(former.values(),key=lambda x:x.get("last_found",""),reverse=True)
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    DATA.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"SEARCH_TOTAL={len(companies)} SUCCEEDED={good} FAILED={len(errors)} LEAD_COMPANIES={len(former)}")
    if good==0: raise RuntimeError("Search provider returned zero successful requests; preserving prior records")
if __name__=="__main__":main()
