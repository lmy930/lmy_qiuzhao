"""Decode recruitment article APIs and classify primary/secondary evidence sources."""
import html
import json
import re
import urllib.parse
from page_evidence import page_text, TextParser
from discover import OFFICIAL_DOMAIN

RECRUITMENT_PUBLISHERS={
    'iguopin.com':'国聘招聘信息',
    'zhaopin.com':'智联招聘信息',
    '51job.com':'前程无忧招聘信息',
    'yingjiesheng.com':'应届生招聘信息',
    'yinhangzhaopin.com':'银行招聘信息',
    'yhks.cn':'银行考试网招聘信息',
    'liepin.com':'猎聘招聘信息',
    'zhipin.com':'BOSS招聘信息',
    'ncss.cn':'国家大学生就业服务平台',
    'fenbi.com':'粉笔招聘信息',
    'eoffcn.com':'中公招聘信息',
    'gwy.com':'高顿招聘信息',
    'givemeoc.com':'招聘信息聚合',
    'gankinterview.cn':'招聘信息聚合',
    'mianlingai.com':'招聘信息聚合',
    'qiuzhaowang.com':'秋招网',
    'offerqianxian.com':'招聘信息聚合',
    'offerstar.cn':'招聘信息聚合',
    'nowcoder.com':'牛客招聘信息',
}
def source_kind(name,url,channels=None):
    try:p=urllib.parse.urlsplit(url);host=p.hostname or ''
    except ValueError:return None
    if p.scheme!='https' or p.username or p.password:return None
    if host.endswith('.edu.cn'):return 'university'
    if host.endswith('.gov.cn'):return 'government'
    official=OFFICIAL_DOMAIN.get(name)
    if official and (host==official or host.endswith('.'+official)):return 'official'
    if name=='华为投资控股有限公司' and host=='career.huawei.com':return 'official'
    for channel in channels or []:
        if channel.get('company')!=name or not channel.get('proof_sha256'):continue
        proof=source_kind(name,channel.get('proof_url',''))
        prefix=channel.get('url_prefix','')
        route=application_route(channel.get('url',''))
        if not route or route['url_prefix']!=prefix:continue
        same_route=url.split('#',1)[0]==channel.get('url','').split('#',1)[0] if channel.get('exact_url') else url==prefix.rstrip('/') or url.startswith(prefix)
        if proof in ('official','government','university') and prefix and same_route:
            return 'official_application'
    if any(host==domain or host.endswith('.'+domain) for domain in RECRUITMENT_PUBLISHERS):return 'recruitment'
    return None

def publisher_key(url):
    host=urllib.parse.urlsplit(url).hostname or ''
    return next((domain for domain in RECRUITMENT_PUBLISHERS if host==domain or host.endswith('.'+domain)),host)

def decode_document(raw,content_type='text/html'):
    if 'json' not in content_type.lower():return raw
    payload=json.loads(raw)
    candidates=[]
    def visit(node,depth=0):
        if depth>6:return
        if isinstance(node,dict):
            title=next((node[k] for k in ('title','articleTitle','name','zpzt') if isinstance(node.get(k),str)),None)
            content=next((node[k] for k in ('content','articleContent','html','body','zpxxEditor') if isinstance(node.get(k),str)),None)
            if title and content:
                if 'zpxxEditor' in node and isinstance(node.get('dwjs'),str):content=node['dwjs']+'\n'+content
                candidates.append((title,content))
            else:
                for key in ('data','article','result','detail'):visit(node.get(key),depth+1)
    visit(payload)
    if len(candidates)!=1:raise ValueError('Unrecognized or ambiguous recruitment article JSON schema')
    title,content=candidates[0]
    return '<title>'+html.escape(title)+'</title><article>'+content+'</article>'

def resolve_url(base,href):
    try:return urllib.parse.urljoin(base,href)
    except ValueError:return None

def referenced_official_urls(name,document,base,channels=None):
    """Only known employer-owned hosts can expand the primary-source queue."""
    from university_sources import Anchors
    p=Anchors();p.feed(document)
    urls=[]
    for title,href in p.items:
        url=resolve_url(base,href)
        if url and source_kind(name,url,channels) in ('official','official_application'):urls.append(url)
    urls.extend(channel['url'] for channel in channels or [] if source_kind(name,channel['url'],channels)=='official_application')
    return list(dict.fromkeys(urls))[:3]

def application_route(url):
    try:parsed=urllib.parse.urlsplit(url);host=parsed.hostname or ''
    except ValueError:return None
    if parsed.scheme!='https' or parsed.username or parsed.password:return None
    generic={'www','app','m','wecruit','hr','campus','jobs','job','career','careers','recruitment','recruit'}
    dedicated=any(host.endswith(suffix) for suffix in ('.zhiye.com','.hotjob.cn','.wintalent.cn')) and host.split('.')[0] not in generic
    shared=(host in ('campus.51job.com','campus.chinahr.com','app.mokahr.com','www.mokahr.com') and len([x for x in parsed.path.split('/') if x])>=2)
    hotjob_tenant=re.match(r'^/(SU[a-fA-F0-9]{12,})/',parsed.path) if host.endswith('.hotjob.cn') and not dedicated else None
    if hotjob_tenant:return {'url':url,'url_prefix':'https://'+parsed.netloc+'/'+hotjob_tenant.group(1)+'/','exact_url':False}
    if not (dedicated or shared):return None
    prefix='https://'+parsed.netloc+'/' if dedicated else 'https://'+parsed.netloc+parsed.path.rstrip('/')
    if shared and not parsed.query:prefix+='/'
    if shared and parsed.query:prefix=url
    return {'url':url,'url_prefix':prefix,'exact_url':bool(shared and parsed.query)}

def application_links(document,base):
    """Only links in the article body to dedicated employer application routes."""
    class Assets(TextParser):
        def __init__(self):super().__init__();self.links=[]
        def handle_starttag(self,tag,attrs):
            super().handle_starttag(tag,attrs)
            if tag=='a' and self.article_depth:
                href=dict(attrs).get('href','');url=resolve_url(base,href)
                if url:self.links.append(url)
    parser=Assets();parser.feed(document)
    if not parser.article_found:return []
    body=''.join(parser.article_parts)
    for match in re.finditer(r'https://[^\s<>"\u4e00-\u9fff，。；）]+',body):
        if re.search(r'投递|网申|报名|应聘|招聘网站',body[max(0,match.start()-100):match.end()+100]):parser.links.append(match.group(0).rstrip('.,;）)'))
    results=[]
    for url in dict.fromkeys(parser.links):
        route=application_route(url)
        if route:results.append(route)
    return results[:3]
