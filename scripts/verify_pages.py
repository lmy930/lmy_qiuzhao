#!/usr/bin/env python3
"""Read primary pages and recruitment reposts; keep uncorroborated dates as candidates."""
import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.request
from collections import defaultdict
from difflib import SequenceMatcher
from page_evidence import evaluate, page_text
from source_documents import source_kind, publisher_key, decode_document, referenced_official_urls
ROOT=pathlib.Path(__file__).resolve().parents[1]

def trusted(name,url):
    return source_kind(name,url) is not None

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (QiuzhaoEvidence/3.0)','Accept':'text/html,application/json'})
    with urllib.request.urlopen(req,timeout=15) as r:
        final=r.geturl();content_type=r.headers.get('Content-Type','').lower()
        if not any(t in content_type for t in ('html','json')):raise ValueError('not_html_or_article_json')
        raw=r.read(1500001)
        if len(raw)>1500000:raise ValueError('page_too_large')
        meta=re.search(br'charset\s*=\s*["\']?([\w-]+)',raw[:4096],re.I)
        encoding=r.headers.get_content_charset() or (meta.group(1).decode('ascii') if meta else 'utf-8')
        document=decode_document(raw.decode(encoding),content_type)
        return final,document,hashlib.sha256(raw).hexdigest()

def set_opening(c,evidence,now,record):
    previous=c.get('open_date_evidence') or {};old=c.get('open_date')
    if old and old!=evidence['date']:
        if previous.get('date')==old:
            record['date_conflict']=old;return False
        c.setdefault('historical_open_dates',[]).append({'date':old,'basis':c.get('open_date_basis'),'reason':'superseded_by_explicit_body_evidence'})
    first=previous.get('first_verified_at',previous.get('checked_at',now)) if previous.get('date')==evidence['date'] else now
    c['open_date']=evidence['date'];c['open_date_basis']='正文明确网申起始时间'
    c['open_date_evidence']={**evidence,'checked_at':now,'first_verified_at':first,'scope':'employer'}
    return previous.get('date')!=evidence['date']

def scan(data,leads,limit=0,registry=None):
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat();today=now[:10]
    jobs={};by_name={c['name']:c for c in data['companies']}
    leadmap={entry['name']:entry.get('hits',[]) for entry in leads.get('leads',[])}
    companies=sorted(data['companies'],key=lambda c:(c.get('status')!='待核验',bool(c.get('open_date_evidence')),c['name']))
    for c in companies:
        hits=leadmap.get(c['name'],[])+c.get('evidence_sources',[])
        hits+=[{'url':c[k]} for k in ('source_url','announcement_source_url') if c.get(k)]
        for hit in hits:
            url=hit.get('url','')
            if trusted(c['name'],url):jobs.setdefault(url,set()).add(c['name'])
    for source in (registry or {}).get('sources',[]):
        if source['company'] in by_name and trusted(source['company'],source['url']):jobs.setdefault(source['url'],set()).add(source['company'])
    records=[];newly=set();dated=set();secondaries=defaultdict(list);read_urls=set();attempted=set();primary_accepted=set()
    def one(url):
        try:return url,fetch(url),None
        except Exception as error:return url,None,f'{type(error).__name__}: {error}'
    queue=list(jobs)
    # Reposts may contain authoritative application links. Follow only employer-owned hosts.
    for round_number in range(2):
        if limit:queue=queue[:max(0,limit-len(attempted))]
        followups={}
        with cf.ThreadPoolExecutor(max_workers=5) as pool:
            for url,result,error in pool.map(one,queue):
                attempted.add(url)
                if error:
                    records.append({'url':url,'companies':sorted(jobs[url]),'result':'fetch_failed','error':error});continue
                read_urls.add(url);final,document,digest=result;title,text=page_text(document)
                for name in sorted(jobs[url]):
                    kind=source_kind(name,final)
                    if not kind:
                        records.append({'company':name,'url':url,'result':'untrusted_redirect'});continue
                    ev=evaluate(name,title,text,today)
                    record={'company':name,'url':final,'title':title,'sha256':digest,'source_kind':kind,**ev};records.append(record)
                    if not ev['accepted']:continue
                    c=by_name[name];opening=ev['opening']
                    for linked in referenced_official_urls(name,document,final):
                        if linked not in attempted:followups.setdefault(linked,set()).add(name)
                    if kind=='recruitment':
                        record['accepted']=False;record['result']='secondary_candidate'
                        candidate={**record,'publisher':publisher_key(final),'text_sha256':hashlib.sha256(re.sub(r'\s+','',text).encode()).hexdigest(),'article_text':re.sub(r'\s+','',text)[:6000]}
                        secondaries[name].append(candidate)
                        if opening:
                            value={**opening,'url':final,'publisher':candidate['publisher'],'sha256':digest,'scope':ev['scope'],'checked_at':now}
                            candidates=c.setdefault('opening_date_candidates',[])
                            candidates[:]=[x for x in candidates if x.get('url')!=final]
                            candidates.append(value)
                        continue
                    primary_accepted.add(name);record['result']='verified_recruitment'
                    if ev['scope']=='employer' or c.get('page_verification',{}).get('scope')!='employer':
                        c['source_scope']=ev['scope'];c['page_verification']={'url':final,'title':title,'sha256':digest,'checked_at':now,'scope':ev['scope'],'source_kind':kind}
                    c['last_checked']=today
                    if ev.get('deadline') and ev['scope']=='employer':
                        c['deadline']=ev['deadline']['date']
                        c['deadline_evidence']={**ev['deadline'],'url':final,'scope':'employer','checked_at':now}
                    if c['status']=='待核验':
                        c['status']='已发布公告（网申待核验）';c['discovered_2027']=True;c['announcement_source_url']=final;newly.add(name)
                    if opening and ev['scope']=='employer':
                        if set_opening(c,{**opening,'url':final,'sha256':digest,'source_kind':kind},now,record):dated.add(name)
                    elif opening:
                        evidence={**opening,'url':final,'title':title,'scope':'subsidiary'}
                        openings=c.setdefault('subsidiary_openings',[])
                        if evidence not in openings:openings.append(evidence)
                    if ev.get('deadline') and ev['scope']=='employer':
                        if ev['deadline']['date']<today:c['status']='已结束'
                        elif c.get('open_date_evidence',{}).get('date')==c.get('open_date') and c.get('open_date')<=today:c['status']='已开启'
        jobs.update({u:jobs.get(u,set())|names for u,names in followups.items()})
        queue=[u for u in followups if u not in attempted]
        if not queue:break
    corroborated=set()
    for name,candidates in secondaries.items():
        scoped=[r for r in candidates if r.get('opening') and r['scope']=='employer']
        dates={r['opening']['date'] for r in scoped}
        # Different pages on one publisher, identical syndicated text and conflicting dates do not suffice.
        if len(dates)!=1 or len({r['publisher'] for r in scoped})<2 or len({r['text_sha256'] for r in scoped})<2:continue
        if any(SequenceMatcher(None,a['article_text'],b['article_text'],autojunk=False).ratio()>=0.85 for i,a in enumerate(scoped) for b in scoped[i+1:]):continue
        sources=[{'url':r['url'],'quote':r['opening']['quote'],'publisher':r['publisher'],'sha256':r['sha256']} for r in scoped]
        c=by_name[name];record=scoped[0]
        evidence={**record['opening'],'url':record['url'],'sha256':record['sha256'],'source_kind':'corroborated_recruitment','corroborating_sources':sources}
        if c.get('open_date_evidence',{}).get('date')!=evidence['date']:
            if set_opening(c,evidence,now,record):dated.add(name)
        if record.get('date_conflict'):continue
        corroborated.add(name);c['source_scope']='employer';c['last_checked']=today
        if c['status']=='待核验':
            c['status']='已发布公告（网申待核验）';c['discovered_2027']=True;c['announcement_source_url']=record['url'];newly.add(name)
        for r in records:
            if r.get('company')==name and r.get('result')=='secondary_candidate':r['result']='secondary_corroborated';r['accepted']=True
    return {'scanned_at':now,'companies_total':len(by_name),'candidate_pages':len(jobs),'pages_attempted':len(attempted),'pages_read':len(read_urls),
            'accepted_employers':len(primary_accepted|corroborated),'secondary_candidate_employers':len(secondaries),'corroborated_recruitment_employers':len(corroborated),
            'confirmed_total':sum(c.get('status')!='待核验' for c in by_name.values()),'recorded_date_total':sum(bool(c.get('open_date')) for c in by_name.values()),
            'verified_date_total':sum(c.get('open_date_evidence',{}).get('date')==c.get('open_date') and c.get('open_date_evidence',{}).get('scope')=='employer' for c in by_name.values()),
            'missing_verified_date_total':sum(c.get('status')!='待核验' and not c.get('open_date_evidence') for c in by_name.values()),
            'newly_confirmed':sorted(newly),'new_open_dates':sorted(dated),'checks':records}

def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=0);p.add_argument('--dry-run',action='store_true');args=p.parse_args()
    if args.limit<0:p.error('--limit must be nonnegative')
    directory=ROOT/'data';data=json.loads((directory/'companies.json').read_text());leads=json.loads((directory/'leads.json').read_text());registry=json.loads((directory/'official_sources.json').read_text())
    report=scan(data,leads,args.limit,registry);path=directory/'page_verification_report.json'
    if path.exists():
        previous=json.loads(path.read_text());last=previous if previous.get('pages_read',0)>0 else previous.get('last_successful_scan')
        if last:report['last_successful_scan']={k:v for k,v in last.items() if k!='last_successful_scan'}
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if not args.dry_run:(directory/'companies.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','last_successful_scan')},ensure_ascii=False))
    if not report['pages_read']:raise SystemExit('All candidate pages failed; see page_verification_report.json')
if __name__=='__main__':main()
