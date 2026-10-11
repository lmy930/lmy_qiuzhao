#!/usr/bin/env python3
"""Track first confirmations and newly verified dates as separate, idempotent events."""
import datetime as dt
import json
import pathlib
DATA=pathlib.Path(__file__).resolve().parents[1]/'data'
TODAY=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
CONFIRMED={'已开启','已结束','已发布公告（网申待核验）'}

def verified_date(company):
    evidence=company.get('open_date_evidence') or {}
    return company.get('open_date') if evidence.get('date')==company.get('open_date') and evidence.get('scope')=='employer' else None

def update_history(companies,history,today):
    known={c['name'] for c in companies if c.get('status') in CONFIRMED or c.get('announcement_date')}
    initial=history is None
    if initial:history={'schema_version':2,'initialized_at':today,'events':[],'known_launch_names':sorted(known)}
    prior=set(history.get('known_launch_names',[]));new_names=known-prior
    old_dates=history.get('known_open_dates');current_dates={c['name']:verified_date(c) for c in companies if verified_date(c)}
    new_dates=set()
    if not initial:
        for c in companies:
            date=current_dates.get(c['name'])
            if not date:continue
            evidence=c['open_date_evidence'];first=evidence.get('first_verified_at',evidence.get('checked_at',''))[:10]
            if (old_dates is not None and old_dates.get(c['name'])!=date) or (old_dates is None and first==today):new_dates.add(c['name'])
    existing={(e['kind'],e['date'],e['name'],e.get('opening_date')) for e in history['events']}
    for c in companies:
        for kind,selected in (('first_confirmed',new_names),('date_verified',new_dates)):
            if c['name'] not in selected:continue
            event={'date':today,'name':c['name'],'groups':c.get('groups',[]),'scope':c.get('source_scope','employer'),'opening_date':verified_date(c),'kind':kind}
            key=(kind,today,c['name'],event['opening_date'])
            if key not in existing:history['events'].append(event);existing.add(key)
    history['schema_version']=2;history['known_launch_names']=sorted(known|prior)
    history['known_open_dates']={**(old_dates or {}),**current_dates};history['last_scanned_at']=today
    history['events'].sort(key=lambda e:(e['date'],e['name'],e['kind']),reverse=True)
    return history,len(new_names),len(new_dates)

def main():
    companies=json.loads((DATA/'companies.json').read_text())['companies'];path=DATA/'daily_changes.json'
    history=json.loads(path.read_text()) if path.exists() else None
    history,newly,dates=update_history(companies,history,TODAY)
    path.write_text(json.dumps(history,ensure_ascii=False,indent=2)+'\n')
    print(f'DAILY_NEWLY_CONFIRMED={newly} NEWLY_VERIFIED_DATES={dates} TOTAL_HISTORY={len(history["events"])}')
if __name__=='__main__':main()
