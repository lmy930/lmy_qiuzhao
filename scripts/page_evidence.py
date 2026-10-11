"""Full-page, cohort-bound evidence; publication dates never imply application dates."""
import datetime as dt
import re
from html.parser import HTMLParser
from employer_aliases import aliases, normalize

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0; self.title=[]; self.in_title=False; self.heading=[]; self.in_heading=False
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.hidden+=1
        if tag=='title': self.in_title=True
        if tag in ('h1','h2'): self.in_heading=True
        if tag in ('p','div','br','li','h1','h2','section','tr'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.hidden=max(0,self.hidden-1)
        if tag=='title': self.in_title=False
        if tag in ('h1','h2'): self.in_heading=False
        if tag in ('p','div','li','section','tr'): self.parts.append('\n')
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.in_title:self.title.append(data)
            if self.in_heading:self.heading.append(data)

def page_text(raw):
    p=TextParser();p.feed(raw)
    return '\n'.join([''.join(p.title).strip(), ''.join(p.heading).strip()]).strip(), '\n'.join(x.strip() for x in ''.join(p.parts).splitlines() if x.strip())

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
    if re.search(r'子公司|旗下|下属|分公司|分行|研究院|\d+所|[一二三四五六七八九十]+院|中建[一二三四五六七八九]局|国网信通|天翼云|天翼支付|阿里云|阿里国际|网易雷火|网易游戏|顺丰科技',t):
        return 'subsidiary'
    return 'employer'

DATE=r'(?P<y>20\d{2})\s*[年./-]\s*(?P<m>\d{1,2})\s*[月./-]\s*(?P<d>\d{1,2})日?'
START=r'(?:网申(?:开始|开启|启动|时间|日期)?|网上报名(?:时间)?|报名(?:开始|起始|时间|日期)|投递(?:开始|时间)|申请(?:开始|开放|时间))'
def opening_evidence(text, today=None):
    today=today or dt.date.today().isoformat()
    # Require the date in a recruiting section explicitly bound to this cohort.
    cohort=list(re.finditer(r'2027(?:届|年(?:度)?|(?=校园招聘|校招|秋招))|27届',text))
    found=[]
    for mark in cohort:
        block=text[max(0,mark.start()-100):mark.end()+1800]
        if re.search(r'202[4568]届',block):continue
        patterns=[START+r'\s*[:：为是]?\s*'+DATE,
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

def evaluate(name,title,text,today=None):
    scope=match_scope(name,title)
    if re.search(r'即将|敬请期待|预计|拟于|预告',title):return {'accepted':False,'reason':'not_yet_launched'}
    if scope is None:return {'accepted':False,'reason':'employer_ambiguous_or_mismatch'}
    # Do not accept a cohort appearing only in sidebar/footer as headline evidence.
    if not re.search(r'2027|27届',title) or re.search(r'202[4568]届',title):
        return {'accepted':False,'reason':'headline_cohort_mismatch'}
    if not re.search(r'校园招聘|校招|秋招|应届生招聘|毕业生招聘|管培生',title):
        return {'accepted':False,'reason':'not_recruitment'}
    if not re.search(r'2027|27届',text):return {'accepted':False,'reason':'page_cohort_missing'}
    return {'accepted':True,'scope':scope,'opening':opening_evidence(text,today)}
