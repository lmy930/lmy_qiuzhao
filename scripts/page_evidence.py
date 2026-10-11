"""Full-page, cohort-bound evidence; publication dates never imply application dates."""
import datetime as dt
import re
from html.parser import HTMLParser
from employer_aliases import aliases, normalize

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0; self.title=[]; self.in_title=False; self.heading=[]; self.in_heading=False; self.article_depth=0; self.article_parts=[]; self.depth=0; self.stack=[]; self.article_found=False
    def handle_starttag(self, tag, attrs):
        if tag not in ('br','img','meta','link','input','hr','source','wbr'):self.stack.append(tag)
        self.depth=len(self.stack)
        attrs=dict(attrs)
        if not self.article_found and (tag=='article' or re.search(r'v_news_content|vsb_content_|article-content|news-content|article_content|page-content-detail',attrs.get('id','')+' '+attrs.get('class',''))):self.article_depth=self.depth;self.article_found=True
        if tag in ('script','style'): self.hidden+=1
        if tag=='title': self.in_title=True
        if tag in ('h1','h2') or tag in ('h3','h4') and 'tit' in attrs.get('class','').split(): self.in_heading=True
        if tag in ('p','div','br','li','h1','h2','section','tr'):
            self.parts.append('\n')
            if self.article_depth:self.article_parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('br','img','meta','link','input','hr','source','wbr'):return
        if tag in self.stack:
            index=len(self.stack)-1-self.stack[::-1].index(tag)
            self.stack=self.stack[:index]
        self.depth=len(self.stack)
        if self.article_depth>self.depth:self.article_depth=0
        if tag in ('script','style'): self.hidden=max(0,self.hidden-1)
        if tag=='title': self.in_title=False
        if tag in ('h1','h2','h3','h4'): self.in_heading=False
        if tag in ('p','div','li','section','tr'): self.parts.append('\n')
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.article_depth:self.article_parts.append(data)
            if self.in_title:self.title.append(data)
            if self.in_heading:self.heading.append(data)

def page_text(raw):
    p=TextParser();p.feed(raw)
    return '\n'.join([''.join(p.title).strip(), ''.join(p.heading).strip()]).strip(), '\n'.join(x.strip() for x in ''.join(p.article_parts if p.article_found else p.parts).splitlines() if x.strip())

DENIED={
 '中国航空集团有限公司':('航空工业','航空发动机','中国航发'),
 '中国航空工业集团有限公司':('航空发动机','中国航发'),
 '中国农业发展集团有限公司':('农业发展银行','农发行'),
 '中国石油天然气集团有限公司':('中国石油化工','中石化'),
}
def match_scope(name, title):
    t=normalize(title)
    if re.search(r'即将|敬请期待|预计|拟于|预告',t):return None
    if any(x in t for x in DENIED.get(name,())):return None
    if not any(a in t for a in aliases(name)):return None
    # Shared TCL brand alone cannot distinguish the two independently monitored groups.
    if name.startswith('TCL'):
        required=('tcl科技','tcl华星','tcl中环') if '科技' in name else ('tcl实业',)
        if not any(x in t for x in required):return None
    scope_text=t
    if '研究' in name:
        own_stem=re.sub(r'(?:集团)?(?:有限责任公司|股份有限公司|有限公司)$','',normalize(name))
        scope_text=scope_text.replace(own_stem,'')
    if re.search(r'子公司|旗下|下属|分公司|分行|支行|分支机构|直属单位|二级单位|研究所|研究院|研究中心|\d+所|[一二三四五六七八九十]+院|中建[一二三四五六七八九]局|国网信通|天翼云|天翼支付|阿里云|阿里国际|网易雷火|网易游戏|顺丰科技|tcl华星|tcl中环',scope_text):
        return 'subsidiary'
    if name=='中国航空集团有限公司' and any(x in t for x in ('中国国航','中国国际航空')):return 'subsidiary'
    if name=='腾讯控股有限公司' and any(x in t for x in ('腾讯音乐','腾讯云智')):return 'subsidiary'
    if '集团' in name:
        for alias in aliases(name):
            member=re.search(re.escape(alias)+r'[\u4e00-\u9fff]{2,18}(?:股份有限公司|有限公司|公司)',t)
            if member and member.group(0)!=normalize(name):return 'subsidiary'
    group_children={
        '盛虹控股集团有限公司':('东方盛虹',),
        '浙江恒逸集团有限公司':('恒逸石化',),
        '桐昆控股集团有限公司':('桐昆股份',),
        '华友控股集团有限公司':('华友钴业',),
        '浙江卫星控股股份有限公司':('卫星化学',),
        '宁波金田投资控股有限公司':('金田铜业',),

        '中国长江三峡集团有限公司':('中国三峡新能源','三峡新能源'),
        '通威集团有限公司':('通威股份',),
        '牧原实业集团有限公司':('牧原股份',),
        '浙江荣盛控股集团有限公司':('荣盛石化',),
        '恒力集团有限公司':('恒力石化',),
        '亨通集团有限公司':('亨通光电',),
        '天能控股集团有限公司':('天能股份',),
        '浙江吉利控股集团有限公司':('吉利汽车',),
        '华润（集团）有限公司':('华润置地','华润电力'),
        '三一集团有限公司':('三一重工','三一重能'),
    }
    if any(child in t for child in group_children.get(name,())):return 'subsidiary'
    return 'employer'

DATE=r'(?P<y>20\d{2})\s*[年./-]\s*(?P<m>\d{1,2})\s*[月./-]\s*(?P<d>\d{1,2})日?'
START=r'(?:网申(?:报名)?(?:开始|开启|启动|起止)?(?:时间|日期)?|网上报名(?:时间|日期)?|报名(?:开始|起始|起止)?(?:时间|日期)|(?:简历)?投递(?:开始|时间|日期)|申请(?:开始|开放|时间))'
def opening_evidence(text, today=None, cohort_bound=False):
    today=today or dt.date.today().isoformat()
    # Require the date in a recruiting section explicitly bound to this cohort.
    cohort=list(re.finditer(r'2027(?:届|年(?:度)?|(?=校园招聘|校招|秋招))|27届',text))
    found=[]
    blocks=[(text,cohort[0])] if cohort_bound and cohort and not re.search(r'202[4568]届',text) else [(text[max(0,mark.start()-100):mark.end()+6000],mark) for mark in cohort]
    for block,mark in blocks:
        if re.search(r'202[4568]届',block):continue
        patterns=[START+r'[\s:：为是自从]*'+DATE,
                  DATE+r'\s*(?:起|开始|正式开启|启动)\s*(?:接受)?(?:网申|网上报名|报名|投递|申请)']
        for pattern in patterns:
            for m in re.finditer(pattern,block):
                try: date=dt.date(int(m['y']),int(m['m']),int(m['d'])).isoformat()
                except ValueError:continue
                # 2027 cohort autumn applications occur in the preceding year.
                if not ('2026-01-01'<=date<=min(today,'2027-12-31')):continue
                if re.match(r'\s*(?:截止|前|之前|以前|结束)',block[m.end():]):continue
                found.append({'date':date,'quote':m.group(0),'cohort_quote':mark.group(0)})
    dates={x['date'] for x in found}
    return found[0] if len(dates)==1 else None

def body_affiliation(name,title,text):
    """A child brand must be declared in its own introduction, with explicit parentage."""
    introduction=re.search(r'(?:公司简介|企业简介|公司介绍|企业介绍|关于我们)(.{0,650})',text,re.S)
    if not introduction:return None
    intro=introduction.group(1)
    declared=re.findall(r'(?:以下简称|简称)[“"‘]?([\u4e00-\u9fffA-Za-z0-9]{3,20})',intro)
    if not any(normalize(child) in normalize(title) for child in declared):return None
    compact=normalize(intro)
    for alias in aliases(name):
        if len(alias)<4:continue
        patterns=[re.escape(alias)+r'.{0,25}(?:旗下|下属|子企业|子公司|成员企业|控股企业|骨干企业)',r'(?:隶属于|隶属|属于|直属于|所属).{0,20}'+re.escape(alias)]
        for pattern in patterns:
            match=re.search(pattern,compact)
            if match and not re.search(r'客户|服务|合作|供应商',compact[max(0,match.start()-45):match.start()]):
                return {'scope':'subsidiary','quote':compact[max(0,match.start()-45):match.end()+35]}
    return None

def body_identity(name,title,text):
    """Bind an unregistered recruiting brand to an explicit legal self-introduction."""
    introduction=re.search(r'(?:公司简介|企业简介|公司介绍|企业介绍|关于我们)(.{0,500})',text,re.S)
    if not introduction:return None
    intro=introduction.group(1)
    legal=re.sub(r'\s*[（(][^）)]{1,18}[）)]\s*$','',name)
    legal=normalize(legal)
    if len(legal)<8:return None
    compact=normalize(intro);position=compact.find(legal)
    if position<0 or position>200:return None
    if re.search(r'客户|服务|合作|供应商|股东|旗下|隶属|所属',compact[max(0,position-30):position]):return None
    after_legal=compact[position+len(legal):position+len(legal)+100]
    declared=re.findall(r'^[，,:：\s]{0,4}(?:以下简称|简称)[“"‘]?([\u4e00-\u9fffA-Za-z0-9]{2,20})',after_legal)
    declared=[brand for brand in declared if brand not in ('公司','集团','企业','本公司','我司')]
    if not any(normalize(brand) in normalize(title) for brand in declared):return None
    return {'scope':'employer','quote':compact[max(0,position-15):position+len(legal)+100]}

def evaluate(name,title,text,today=None):
    scope=match_scope(name,title)
    affiliation=body_affiliation(name,title,text) if scope is None else None
    if affiliation:scope=affiliation['scope']
    identity=body_identity(name,title,text) if scope is None else None
    if identity:scope=identity['scope']
    if re.search(r'即将|敬请期待|预计|拟于|预告',title):return {'accepted':False,'reason':'not_yet_launched'}
    if scope is None:return {'accepted':False,'reason':'employer_ambiguous_or_mismatch'}
    # Do not accept a cohort appearing only in sidebar/footer as headline evidence.
    if not re.search(r'2027|27届',title) or re.search(r'202[4568]届',title):
        return {'accepted':False,'reason':'headline_cohort_mismatch'}
    if not re.search(r'校园招聘|校招|秋招|应届生招聘|毕业生招聘|管培生',title):
        return {'accepted':False,'reason':'not_recruitment'}
    if re.search(r'202[4568]届',text) and not re.search(r'2027|27届',text):return {'accepted':False,'reason':'page_cohort_mismatch'}
    # A dedicated article headline binds its own job details to the cohort.
    # Do not require employers to repeat the year in every paragraph or job table.
    body_without_headline=text
    for line in title.splitlines():
        if line.strip():body_without_headline=body_without_headline.replace(line.strip(),'')
    if not re.search(r'招聘对象|招聘岗位|应聘|报名|投递|网申|申请|工作地点|本科|硕士|毕业生|招聘流程|专业|职位',body_without_headline):
        return {'accepted':False,'reason':'recruitment_body_missing'}
    if '宣讲会' in title and not re.search(r'招聘岗位|招聘职位|招聘对象|简历|网申|应聘|投递',body_without_headline):
        return {'accepted':False,'reason':'meeting_notice_without_applications'}
    content=title+'\n'+text
    opening=opening_evidence(content,today,cohort_bound=True)
    result={'accepted':True,'scope':scope,'opening':opening,'deadline':deadline_evidence(content,opening)}
    if affiliation:result['affiliation_evidence']=affiliation
    if identity:result['identity_evidence']=identity
    return result


def deadline_evidence(text, opening=None):
    """A deadline comes from application language, never a publication timestamp."""
    if re.search(r'202[4568]届',text):return None
    found=[]
    pattern=r'(?:网申|网上报名|报名|投递|申请)(?:截止|结束)(?:时间|日期)?[\s:：为至]*'+DATE
    for match in re.finditer(pattern,text):
        try:date=dt.date(int(match['y']),int(match['m']),int(match['d'])).isoformat()
        except ValueError:continue
        if '2026-01-01'<=date<='2027-12-31':found.append({'date':date,'quote':match.group(0)})
    if opening:
        end=r'(?:(?P<ey>20\d{2})\s*[年./-]\s*)?(?P<em>\d{1,2})\s*[月./-]\s*(?P<ed>\d{1,2})日?'
        pattern=START+r'[\s:：为是自从]*'+DATE+r'\s*(?:至|到|[-~—–～])\s*'+end
        for match in re.finditer(pattern,text):
            try:
                start=dt.date(int(match['y']),int(match['m']),int(match['d']))
                date=dt.date(int(match['ey'] or match['y']),int(match['em']),int(match['ed']))
            except ValueError:continue
            if start.isoformat()==opening['date'] and start<=date and date.isoformat()<='2027-12-31':found.append({'date':date.isoformat(),'quote':match.group(0)})
    return found[0] if len({item['date'] for item in found})==1 else None
