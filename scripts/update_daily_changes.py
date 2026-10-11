#!/usr/bin/env python3
"""Persist new 2027 recruitment confirmations after each automated scan.
This does not invent an employer's actual application opening date.
"""
import datetime as dt
import json
import pathlib

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
TODAY=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=8)).date().isoformat()
CONFIRMED={"已开启","已结束","已发布公告（网申待核验）"}

def main():
    companies=json.loads((DATA/"companies.json").read_text(encoding="utf-8"))["companies"]
    path=DATA/"daily_changes.json"
    known={x["name"] for x in companies if x.get("status") in CONFIRMED or x.get("announcement_date")}
    if path.exists():
        history=json.loads(path.read_text(encoding="utf-8"))
        existing=set(history.get("known_launch_names",[]))
        new_names=known-existing
    else:
        # Initial baseline: no retroactive false 'new today' alerts.
        history={"schema_version":1,"initialized_at":TODAY,"events":[]}
        existing=known
        new_names=set()
    for c in companies:
        if c["name"] not in new_names: continue
        # Event means first confirmed by this system, NOT the true opening date.
        history["events"].append({
            "date":TODAY, "name":c["name"], "groups":c.get("groups",[]),
            "scope":c.get("source_scope","employer"),
            "opening_date":c.get("open_date") if c.get("open_date_evidence",{}).get("date")==c.get("open_date") and c.get("open_date_evidence",{}).get("scope")=="employer" else None,
            "kind":"first_confirmed"
        })
    history["known_launch_names"]=sorted(known|existing)
    history["last_scanned_at"]=TODAY
    history["events"].sort(key=lambda x:(x["date"],x["name"]),reverse=True)
    path.write_text(json.dumps(history,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"DAILY_NEWLY_CONFIRMED={len(new_names)} TOTAL_HISTORY={len(history['events'])}")
if __name__=="__main__":main()
