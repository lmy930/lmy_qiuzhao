#!/usr/bin/env python3
"""Report evidence and official-entry gaps without treating unknown as closed."""
import datetime as dt
import json
import pathlib
from discover import OFFICIAL_DOMAIN
from source_documents import source_kind

ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    directory=ROOT/'data'
    companies=json.loads((directory/'companies.json').read_text())['companies']
    baseline=json.loads((directory/'launch_baseline.json').read_text())
    known=set(baseline['known_launch_names'])
    confirmed=[c for c in companies if c['status']!='待核验']
    registry=json.loads((directory/'official_sources.json').read_text())
    registered=set(OFFICIAL_DOMAIN)|{s['company'] for s in registry['sources']}|{c['name'] for c in companies if any(source_kind(c['name'],ch['url'],[ch])=='official_application' for ch in c.get('application_channels',[]))}
    report={
        'checked_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        'companies_total':len(companies),
        'confirmed_total':len(confirmed),
        'baseline_total':len(known),
        'confirmed_after_baseline':sorted(c['name'] for c in confirmed if c['name'] not in known),
        'unconfirmed_total':len(companies)-len(confirmed),
        'confirmed_without_body_hash':sorted(c['name'] for c in confirmed if not c.get('page_verification',{}).get('sha256')),
        'verified_open_date_total':sum(bool(c.get('open_date_evidence')) and c['open_date_evidence'].get('date')==c.get('open_date') and c['open_date_evidence'].get('scope')=='employer' for c in confirmed),
        'official_entry_registered_total':sum(c['name'] in registered for c in companies),
        'official_entry_not_registered':sorted(c['name'] for c in companies if c['name'] not in registered),
        'note':'待核验不等于未开启；官网入口登记不等于成功读取。旧有已确认但尚未补齐正文哈希的记录保留原证据并继续回访。新确认时间与真实开启日期分开。'
    }
    (directory/'coverage_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if not isinstance(v,list)},ensure_ascii=False))
if __name__=='__main__':main()
