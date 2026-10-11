#!/usr/bin/env python3
"""Measure entry access; never treat readable homepages as recruiting evidence."""
import concurrent.futures as cf
import datetime as dt
import json
from aggregate_sources import PAGES,load,KEYWORDS,normalize
from broad_sources import SCHOOLS,DATA,safe_read

def platform_check(url):
    try:
        page=load(url)
        return {'site':url,'readable':True,'article_links':len(page['links']),
                'cohort_links':sum(any(normalize(k) in normalize(title) for k in KEYWORDS) for title,_ in page['links'])}
    except Exception as error:return {'site':url,'readable':False,'error':str(error)[:200]}

def main():
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        platforms=list(pool.map(platform_check,PAGES))
        extra=[]
        for school,page in zip(SCHOOLS[-4:],pool.map(safe_read,[s['url'] for s in SCHOOLS[-4:]])):
            extra.append({'name':school['name'],**{k:v for k,v in page.items() if k not in ('document','items')},'links_read':len(page.get('items',[]))})
    report={'checked_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
            'platform_checks':platforms,'added_university_checks':extra,
            'note':'仅验证公开入口和线索可读性；成功读取首页不代表已覆盖该平台，失败不代表企业未开招。'}
    (DATA/'source_access_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'platforms_attempted':len(platforms),'platforms_read':sum(x['readable'] for x in platforms),'platforms_with_cohort_links':sum(x.get('cohort_links',0)>0 for x in platforms),'added_university_pages_read':sum('error' not in x for x in extra)},ensure_ascii=False))
if __name__=='__main__':main()
