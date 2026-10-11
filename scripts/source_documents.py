"""Decode recruitment article APIs and classify primary/secondary evidence sources."""
import html
import json
import re
import urllib.parse
from page_evidence import page_text
from discover import OFFICIAL_DOMAIN

RECRUITMENT_PUBLISHERS={
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
def source_kind(name,url):
    p=urllib.parse.urlsplit(url);host=p.hostname or ''
    if p.scheme!='https' or p.username or p.password:return None
    if host.endswith('.edu.cn'):return 'university'
    if host.endswith('.gov.cn'):return 'government'
    official=OFFICIAL_DOMAIN.get(name)
    if official and (host==official or host.endswith('.'+official)):return 'official'
    if name=='华为投资控股有限公司' and host=='career.huawei.com':return 'official'
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
            title=next((node[k] for k in ('title','articleTitle','name') if isinstance(node.get(k),str)),None)
            content=next((node[k] for k in ('content','articleContent','html','body') if isinstance(node.get(k),str)),None)
            if title and content:candidates.append((title,content))
            else:
                for key in ('data','article','result','detail'):visit(node.get(key),depth+1)
    visit(payload)
    if len(candidates)!=1:raise ValueError('Unrecognized or ambiguous recruitment article JSON schema')
    title,content=candidates[0]
    return '<title>'+html.escape(title)+'</title><article>'+content+'</article>'

def referenced_official_urls(name,document,base):
    """Only known employer-owned hosts can expand the primary-source queue."""
    from university_sources import Anchors
    p=Anchors();p.feed(document)
    urls=[]
    for title,href in p.items:
        url=urllib.parse.urljoin(base,href)
        if source_kind(name,url)=='official':urls.append(url)
    return list(dict.fromkeys(urls))[:3]
