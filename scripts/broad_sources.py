#!/usr/bin/env python3
"""Official-first discovery, followed by multiple public university archives.

Listings are leads only: verify_pages must read the article before confirming.
Uses observed pagination, never equates an HTTP response with employer coverage.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import pathlib
import re
import urllib.parse
import urllib.request
from collections import Counter
from discover import OFFICIAL_DOMAIN
from page_evidence import match_scope, page_text, evaluate
from source_documents import source_kind, resolve_url

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
SCHOOLS=[
    {'name':'南开大学','url':'https://career.nankai.edu.cn/correcruit/index.html','mode':'correcruit','cap':50},
    {'name':'河北工业大学','url':'https://career.hebut.edu.cn/correcruit/index.html','mode':'correcruit','cap':120},
    {'name':'天津工业大学','url':'https://jobs.tiangong.edu.cn/correcruit/index.html','mode':'correcruit','cap':100},
    {'name':'华中科技大学','url':'https://job.hust.edu.cn/searchJob.do?type=2','mode':'hust','cap':100},
    {'name':'广州大学','url':'https://jy.gzhu.edu.cn/web/Index/jobs-brief-list','mode':'gzhu','cap':30},
    {'name':'清华大学','url':'https://career.tsinghua.edu.cn/','mode':'auto','cap':12},
    {'name':'北京大学','url':'https://scc.pku.edu.cn/','mode':'auto','cap':12},
    {'name':'上海交通大学','url':'https://career.sjtu.edu.cn/','mode':'auto','cap':12},
    {'name':'复旦大学','url':'https://career.fudan.edu.cn/','mode':'auto','cap':12},
    {'name':'浙江大学','url':'https://career.zju.edu.cn/','mode':'auto','cap':12},
    {'name':'南京大学','url':'https://job.nju.edu.cn/','mode':'auto','cap':12},
    {'name':'中国科学技术大学','url':'https://job.ustc.edu.cn/','mode':'auto','cap':12},
    {'name':'武汉大学','url':'https://career.whu.edu.cn/','mode':'auto','cap':12},
    {'name':'西安交通大学','url':'https://job.xjtu.edu.cn/','mode':'auto','cap':12},
    {'name':'北京邮电大学','url':'https://job.bupt.edu.cn/','mode':'auto','cap':12},
    {'name':'电子科技大学','url':'https://jiuye.uestc.edu.cn/','mode':'auto','cap':12},
    {'name':'华南理工大学','url':'https://career.scut.edu.cn/','mode':'auto','cap':12},
    {'name':'深圳大学','url':'https://job.szu.edu.cn/','mode':'auto','cap':12},
    {'name':'西南交通大学' ,'url':'https://jiuye.swjtu.edu.cn/career/index','mode':'onclick','cap':1},
    {'name':'西南财经大学','url':'https://career.swufe.edu.cn/','mode':'auto','cap':12},
    {'name':'中国农业大学','url':'https://job.cau.edu.cn/','mode':'auto','cap':12},
    {'name':'中国石油大学','url':'https://career.cup.edu.cn/','mode':'auto','cap':12},
    {'name':'厦门大学嘉庚学院','url':'https://career.xujc.com/2026/0928/c3959a173096/page.htm','mode':'auto','cap':12},
]
RECRUIT=r'校园招聘|校招|秋招|秋季招聘|应届生招聘|毕业生招聘|管培生招聘|管培生计划'

class ListingParser(HTMLParser):
    """Read normal anchors, title attributes and server-rendered onclick cards."""
    def __init__(self):
        super().__init__();self.items=[];self.active=[];self.depth=0;self.hidden=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style'):self.hidden+=1
        void=tag in ('br','img','meta','link','input','hr','source','wbr')
        if not void:self.depth+=1
        href=attrs.get('href') if tag=='a' else None
        onclick=attrs.get('onclick','')
        match=re.search(r'windowOpen\(\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\s*\)',onclick)
        if match:
            value=match.group(1)
            try:href=json.loads(value) if value.startswith('"') else value[1:-1].replace('\\/','/')
            except ValueError:href=None
        if href and not self.hidden:
            self.active.append({'depth':self.depth,'href':href,'title':attrs.get('title',''),'parts':[]})
    def handle_data(self,data):
        if not self.hidden:
            for item in self.active:item['parts'].append(data)
    def handle_endtag(self,tag):
        if tag in ('br','img','meta','link','input','hr','source','wbr'):return
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        finished=[item for item in self.active if item['depth']==self.depth]
        for item in finished:
            label=re.sub(r'\s+',' ',''.join(item['parts'])).strip()
            # The title attribute often contains the complete employer name when text is truncated.
            title=item['title'].strip() or label
            if title:self.items.append((title[:350],item['href']))
            self.active.remove(item)
        self.depth=max(0,self.depth-1)

def read_page(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (QiuzhaoSources/1.0)','Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=15) as response:
        if 'html' not in response.headers.get('Content-Type','text/html'):raise ValueError('not_html')
        raw=response.read(1500001)
        if len(raw)>1500000:raise ValueError('page_too_large')
        meta=re.search(br'charset\s*=\s*["\']?([\w-]+)',raw[:4096],re.I)
        encoding=response.headers.get_content_charset() or (meta.group(1).decode() if meta else 'utf-8')
        document=raw.decode(encoding,errors='replace');final=response.url
    parser=ListingParser();parser.feed(document)
    return {'url':url,'final_url':final,'sha256':hashlib.sha256(raw).hexdigest(),'items':parser.items,'bytes':len(raw),'document':document}

def safe_read(url):
    try:return read_page(url)
    except Exception as error:return {'url':url,'error':f'{type(error).__name__}: {error}'[:240]}

def article_url(school,href,base):
    url=resolve_url(base,href)
    if not url:return None
    p=urllib.parse.urlsplit(url)
    host=urllib.parse.urlsplit(school['url']).hostname
    if p.hostname!=host:return None
    if p.scheme=='http':url=urllib.parse.urlunsplit(('https',p.netloc,p.path,p.query,''))
    elif p.scheme!='https':return None
    mode=school['mode']
    patterns={'correcruit':r'/correcruit/content/id/\d+\.html','hust':r'/zpinfo\d/\d+\.htm','gzhu':r'/jobs-brief-detail\?id=','onclick':r'/career/(?:news/view|zpxx/view/zpxx|index/(?:job|recruit|xyxjh))','auto':r'/(?:[^?#]+/(?:view|detail|content|info)[^?#]*|[^?#]+\.(?:html?|jsp|jspa|do)(?:\?|$))'}
    return url if re.search(patterns[mode],url,re.I) else None

def archive_pages(school,page,backfill):
    cap=school['cap'] if backfill else min(school['cap'],12)
    candidates=[]
    for label,href in page.get('items',[]):
        u=resolve_url(page.get('final_url',school['url']),href)
        if not u:continue
        if urllib.parse.urlsplit(u).hostname!=urllib.parse.urlsplit(school['url']).hostname:continue
        if school['mode']=='correcruit':m=re.search(r'/correcruit/index/p/(\d+)\.html',u)
        elif school['mode']=='hust':m=re.search(r'/searchJob_(\d+)\.do',u)
        elif school['mode']=='gzhu':m=re.search(r'[?&]p=(\d+)',u)
        else:m=None
        if school['mode']=='auto' and re.search(r'招聘信息|招聘简章|校园招聘|招聘公告',label) and not re.search(r'招聘会|宣讲会',label):
            if urllib.parse.urlsplit(u).scheme=='http':u='https://'+u.split('://',1)[1]
            if u not in candidates and len(candidates)<cap:candidates.append(u)
        if m:candidates.append(int(m.group(1)))
    if school['mode']=='auto':return candidates
    maximum=min(max(candidates,default=1),cap)
    origin='https://'+urllib.parse.urlsplit(school['url']).hostname
    result=[]
    for n in range(2,maximum+1):
        if school['mode']=='correcruit':url=origin+f'/correcruit/index/p/{n}.html'
        elif school['mode']=='hust':url=origin+f'/searchJob_{n}.do?type=2'
        elif school['mode']=='gzhu':url=origin+f'/web/Index/jobs-brief-list?p={n}'
        else:continue
        result.append(url)
    return result

def relevant_title(title):
    return bool(re.search(r'2027|27届',title) and re.search(RECRUIT,title) and not re.search(r'202[4568]届|取消|敬请期待|即将|预告|暑期实习|日常实习|实习生招聘',title))

def weak_brand_keys(name):
    """Fetch candidates only; these short fragments are never confirmation evidence."""
    name=re.sub(r'\s+|[（）()]','',name).lower()
    name=re.sub(r'^(?:内蒙古|黑龙江|北京|上海|天津|重庆|山东|浙江|江苏|广东|福建|河北|河南|安徽|湖南|湖北|山西|陕西|四川|辽宁|深圳|青岛|宁波|苏州|厦门|珠海)','',name)
    name=re.sub(r'(?:控股|集团|股份|有限责任|有限公司|公司)','',name)[:10]
    generic={'中国','国有','集团','控股','公司','股份','有限','责任','建设','工程','开发','国际','商业','银行','科技','技术','产业','制造','机械','服务','医药','汽车','化工','能源','电力','钢铁','运输','电子','网络','设备','投资','实业','信息','食品','贸易','物流','材料','金属','电气','地产','商业','建筑','精密','环保','控股','新能','能源','工业','新材'}
    return {name[i:i+2] for i in range(len(name)-1) if name[i:i+2] not in generic}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backfill',action='store_true');args=parser.parse_args()
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat();today=now[:10]
    companies=json.loads((DATA/'companies.json').read_text())['companies']
    leads=json.loads((DATA/'leads.json').read_text())
    byname={x['name']:x for x in leads.get('leads',[])}
    reports=[];additions=0;matched_names=set();official_attempts=set()
    def add(name,title,url,source):
        nonlocal additions
        entry=byname.setdefault(name,{'name':name,'hits':[],'last_found':today})
        if not any(h.get('url')==url for h in entry['hits']):
            entry['hits'].append({'title':title,'url':url,'snippet':'待正文核验，不凭列表确认启动','published_at':None,'evidence_level':'article_discovery','discovered_via':source});additions+=1
        entry['last_found']=today;matched_names.add(name)
    # Always visit known official entry points before public reposts.
    official_jobs={}
    for c in companies:
        domain=OFFICIAL_DOMAIN.get(c['name'])
        if domain:official_jobs.setdefault('https://www.'+domain+'/',set()).add(c['name'])
        for channel in c.get('application_channels',[]):
            if source_kind(c['name'],channel['url'],c['application_channels'])=='official_application':official_jobs.setdefault(channel['url'],set()).add(c['name'])
    for entry in json.loads((DATA/'official_sources.json').read_text()).get('sources',[]):
        official_jobs.setdefault(entry['url'],set()).add(entry['company'])
    follow={}
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for page in pool.map(safe_read,official_jobs):
            names=official_jobs[page['url']];official_attempts.update(names)
            reports.append({'phase':'official','companies':sorted(names),**{k:v for k,v in page.items() if k not in ('items','document')}})
            if 'error' in page:continue
            for name in names:
                company=next(c for c in companies if c['name']==name)
                if source_kind(name,page['final_url'],company.get('application_channels')) not in ('official','official_application'):continue
                for title,href in page['items']:
                    url=resolve_url(page['final_url'],href)
                    if not url:continue
                    if source_kind(name,url)!='official':continue
                    if relevant_title(title) and match_scope(name,title):add(name,title,url,'企业官网链接')
                    if re.search(r'招聘|人才|校招|careers?|recruit|campus',title+' '+url,re.I) and len(follow.get(name,[]))<4:
                        follow.setdefault(name,[]).append(url)
    urlnames={}
    for name,urls in follow.items():
        for url in urls:urlnames.setdefault(url,set()).add(name)
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for page in pool.map(safe_read,urlnames):
            reports.append({'phase':'official_recruitment','companies':sorted(urlnames[page['url']]),**{k:v for k,v in page.items() if k not in ('items','document')}})
            if 'error' in page:continue
            for name in urlnames[page['url']]:
                if source_kind(name,page['final_url'])!='official':continue
                for title,href in page['items']:
                    url=resolve_url(page['final_url'],href)
                    if not url:continue
                    if relevant_title(title) and match_scope(name,title) and source_kind(name,url)=='official':add(name,title,url,'官网招聘栏目')
    # Archive pages add candidates, never state changes. The full articles are subsequently read.
    list_jobs={s['url']:s for s in SCHOOLS};all_pages=[];extra_jobs={};weak_keys={c['name']:weak_brand_keys(c['name']) for c in companies if c['status']=='待核验'}
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        first=list(pool.map(safe_read,list_jobs))
    archive_jobs={}
    for page in first:
        school=list_jobs[page['url']];all_pages.append((school,page))
        if 'error' not in page:
            for url in archive_pages(school,page,args.backfill):archive_jobs[url]=school
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for page in pool.map(safe_read,archive_jobs):all_pages.append((archive_jobs[page['url']],page))
    for school,page in all_pages:
        matched=set();article_links=0
        if 'error' not in page:
            for title,href in page['items']:
                url=article_url(school,href,page['final_url'])
                if not url or not relevant_title(title):continue
                article_links+=1
                for name,keys in weak_keys.items():
                    if match_scope(name,title) is None and any(key in title.lower() for key in keys):extra_jobs.setdefault(url,set()).add(name)
                for c in companies:
                    if match_scope(c['name'],title) is not None:
                        add(c['name'],title,url,school['name']+'公开招聘档案');matched.add(c['name'])
        reports.append({'phase':'university_archive','source':school['name'],'candidate_employers':sorted(matched),'recruitment_articles':article_links,**{k:v for k,v in page.items() if k not in ('items','document')}})
    # Read potentially matching articles to bind unfamiliar brands to their own legal introduction.
    # Customer/supplier mentions and a short-name overlap cannot confirm an employer.
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for page in pool.map(safe_read,extra_jobs):
            accepted=[]
            if 'error' not in page:
                title,text=page_text(page['document'])
                for name in sorted(extra_jobs[page['url']]):
                    evidence=evaluate(name,title,text,today)
                    if evidence.get('accepted'):
                        add(name,title,page['final_url'],'高校招聘正文中的企业身份/关联证据');accepted.append(name)
            reports.append({'phase':'unregistered_brand_backfill','candidate_employers':sorted(extra_jobs[page['url']]),'body_matched_employers':accepted,**{k:v for k,v in page.items() if k not in ('items','document')}})
    leads['leads']=sorted(byname.values(),key=lambda x:x.get('last_found',''),reverse=True)
    leads['broad_scan_at']=now
    (DATA/'leads.json').write_text(json.dumps(leads,ensure_ascii=False,indent=2)+'\n')
    report={'scanned_at':now,'mode':'historical_backfill' if args.backfill else 'daily_recent','companies_total':len(companies),'official_company_entries_attempted':len(official_attempts),'official_entry_not_registered':sorted(c['name'] for c in companies if c['name'] not in official_attempts),'pages_attempted':len(reports),'pages_read':sum('error' not in r for r in reports),'source_failures':dict(Counter(r.get('error','').split(':',1)[0] for r in reports if 'error' in r)),'new_lead_urls':additions,'candidate_employers':sorted(matched_names),'note':'页面读取与列表匹配只是发现线索；只有招聘正文核验后才能更新状态。未找到官网入口或来源失败仍是覆盖缺口。','checks':reports}
    (DATA/'broad_source_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','official_entry_not_registered','candidate_employers')},ensure_ascii=False))
    print('CANDIDATE_EMPLOYERS',len(matched_names))
    if report['pages_read']==0:raise SystemExit('No source pages could be read; see broad_source_report.json')
if __name__=='__main__':main()
