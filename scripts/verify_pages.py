#!/usr/bin/env python3
"""Automatically revisit source pages, including launched employers with unknown dates."""
import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import pathlib
import urllib.parse
import urllib.request
from page_evidence import evaluate, page_text
from discover import OFFICIAL_DOMAIN
ROOT=pathlib.Path(__file__).resolve().parents[1]

def trusted(name,url):
    p=urllib.parse.urlsplit(url); h=p.hostname or ''
    domain=OFFICIAL_DOMAIN.get(name)
    return p.scheme=='https' and not p.username and not p.password and (
        h.endswith('.edu.cn') or h.endswith('.gov.cn') or
        bool(domain and (h==domain or h.endswith('.'+domain))) or
        (name=='华为投资控股有限公司' and h=='career.huawei.com'))

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (QiuzhaoEvidence/2.0)'})
    with urllib.request.urlopen(req,timeout=15) as r:
        final=r.geturl()
        if 'html' not in r.headers.get('Content-Type','').lower():raise ValueError('not_html')
        raw=r.read(1500001)
        if len(raw)>1500000:raise ValueError('page_too_large')
        encoding=r.headers.get_content_charset() or 'utf-8'
        return final,raw.decode(encoding),hashlib.sha256(raw).hexdigest()

def scan(data,leads,limit=0,registry=None):
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()
    today=now[:10]; jobs={}; by_name={c['name']:c for c in data['companies']}
    for c in data['companies']:
        hits=next((x.get('hits',[]) for x in leads.get('leads',[]) if x['name']==c['name']),[])
        hits=hits+c.get('evidence_sources',[])
        hits += [{'url':c.get(k),'title':c.get('announcement_title','')} for k in ('source_url','announcement_source_url') if c.get(k)]
        for h in hits:
            url=h.get('url','')
            if trusted(c['name'],url):jobs.setdefault(url,[]).append((c['name'],h.get('title','')))
    for source in (registry or {}).get("sources",[]):
        if source["company"] in by_name and trusted(source["company"],source["url"]):
            jobs.setdefault(source["url"],[]).append((source["company"],""))
    urls=list(jobs)
    if limit:urls=urls[:limit]
    records=[]; newly=set(); dated=set()
    def one(url):
        try:return url,fetch(url),None
        except Exception as e:return url,None,f'{type(e).__name__}: {e}'
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        for url,result,error in pool.map(one,urls):
            if error:
                records.append({'url':url,'result':'fetch_failed','error':error});continue
            final,raw,digest=result; title,text=page_text(raw)
            for name in dict.fromkeys(name for name,hint in jobs[url]):
                if not trusted(name,final):
                    records.append({'company':name,'url':url,'result':'untrusted_redirect'});continue
                # The fetched title must independently identify the employer; never substitute search hints.
                ev=evaluate(name,title,text,today)
                record={'company':name,'url':final,'title':title,'sha256':digest,**ev}
                records.append(record)
                if not ev['accepted']:continue
                c=by_name[name]
                if ev['scope']=='employer' or c.get('page_verification',{}).get('scope')!='employer':
                    c['source_scope']=ev['scope']
                c['last_checked']=today
                if ev['scope']=='employer' or c.get('page_verification',{}).get('scope')!='employer':
                    c['page_verification']={'url':final,'title':title,'sha256':digest,'checked_at':now,'scope':ev['scope']}
                if c['status']=='待核验':
                    c['status']='已发布公告（网申待核验）';c['discovered_2027']=True
                    c['announcement_source_url']=final;newly.add(name)
                opening=ev['opening']
                # A subsidiary start must not become a group-wide calendar date.
                if opening and ev['scope']=='employer':
                    old=c.get('open_date')
                    if old and old!=opening['date']:
                        record['date_conflict']=old;continue
                    c['open_date']=opening['date'];c['open_date_basis']='正文明确网申起始时间'
                    c['open_date_evidence']={**opening,'url':final,'sha256':digest,'checked_at':now,'scope':'employer'}
                    if not old:dated.add(name)
                elif opening:
                    c.setdefault('subsidiary_openings',[])
                    evidence={**opening,'url':final,'title':title,'scope':'subsidiary'}
                    if evidence not in c['subsidiary_openings']:c['subsidiary_openings'].append(evidence)
    report={'scanned_at':now,'companies_total':len(by_name),'candidate_pages':len(jobs),'pages_attempted':len(urls),
            'pages_read':sum(1 for u in urls if not any(r.get('url')==u and r.get('result')=='fetch_failed' for r in records)),
            'accepted_employers':len({r['company'] for r in records if r.get('accepted')}),
            'confirmed_total':sum(c.get('status')!='待核验' for c in by_name.values()),
            'recorded_date_total':sum(bool(c.get('open_date')) for c in by_name.values()),
            'verified_date_total':sum(c.get('open_date_evidence',{}).get('date')==c.get('open_date') and c.get('open_date_evidence',{}).get('scope')=='employer' for c in by_name.values()),
            'missing_date_total':sum(c.get('status')!='待核验' and not c.get('open_date') for c in by_name.values()),
            'newly_confirmed':sorted(newly),'new_open_dates':sorted(dated),'checks':records}
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=0);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    directory=ROOT/'data';data=json.loads((directory/'companies.json').read_text());leads=json.loads((directory/'leads.json').read_text())
    registry=json.loads((directory/"official_sources.json").read_text())
    report=scan(data,leads,a.limit,registry)
    report_path=directory/'page_verification_report.json'
    if report_path.exists():
        previous=json.loads(report_path.read_text())
        last_success=previous if previous.get('pages_read',0)>0 else previous.get('last_successful_scan')
        if last_success:
            report['last_successful_scan']={k:v for k,v in last_success.items() if k!='last_successful_scan'}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if not a.dry_run:(directory/'companies.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False))
    if not report['pages_read']:raise SystemExit('All candidate pages failed; see page_verification_report.json')
if __name__=='__main__':main()
