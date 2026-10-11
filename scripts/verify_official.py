#!/usr/bin/env python3
"""Conservatively validate reviewed official-source records; never promote search hits."""
import datetime as dt
import html
import json
import pathlib
import re
import urllib.parse
import urllib.request
from page_evidence import opening_evidence, deadline_evidence, page_text
from verify_pages import fetch as fetch_page, set_opening

ROOT=pathlib.Path(__file__).resolve().parents[1]
DIR=ROOT/"data"
TODAY=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
UA="Mozilla/5.0 (compatible; QiuzhaoOfficialVerifier/1.0)"

def domain_ok(url,allowed):
    parsed=urllib.parse.urlsplit(url)
    return parsed.scheme=="https" and parsed.hostname==allowed and not parsed.username and not parsed.password

def get_text(url):
    final,document,digest=fetch_page(url)
    if urllib.parse.urlsplit(final).hostname!=urllib.parse.urlsplit(url).hostname:
        raise ValueError("Redirected outside approved hostname")
    title,text=page_text(document)
    return title+"\n"+text

def main():
    data=json.loads((DIR/"companies.json").read_text(encoding="utf-8"))
    registry=json.loads((DIR/"official_sources.json").read_text(encoding="utf-8"))
    company_by_name={c["name"]:c for c in data["companies"]}
    log=[]
    for source in registry["sources"]:
        name,url,domain=source["company"],source["url"],source["domain"]
        record={"company":name,"source_url":url,"checked_at":TODAY}
        try:
            assert name in company_by_name, "Unknown company"
            assert domain_ok(url,domain), "URL not in approved official domain"
            assert source["year"]==2027, "Wrong cohort"
            if source.get("deadline"):
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}",source["deadline"]), "Invalid deadline"
            content=get_text(url)
            assert any(re.sub(r"\s+","",phrase) in re.sub(r"\s+","",content) for phrase in source["match_any"]), "Official recruitment statement not present"
            assert "2027" in content, "Target class missing"
            target=company_by_name[name]
            opening=opening_evidence(content,TODAY,cohort_bound=True)
            if not opening:
                raise ValueError("No matching explicit application opening date in page body")
            evidence={**opening,"url":url,"scope":"employer","source_kind":"official"}
            set_opening(target,evidence,TODAY,record)
            if record.get("date_conflict"):raise ValueError("Conflicting previously verified application date")
            deadline=deadline_evidence(content,opening)
            if deadline:
                target["deadline"]=deadline["date"]
                target["deadline_evidence"]={**deadline,"url":url,"scope":"employer","checked_at":TODAY}
                target["status"]="已结束" if deadline["date"]<TODAY else "已开启"
            elif target["status"] not in ("已结束",):
                target["status"]="已发布公告（网申待核验）"
            target["source_url"]=url
            target["apply_url"]=source.get("apply_url")
            target["last_checked"]=TODAY
            target["verification_status"]="官网核验"
            target["verification_note"]=source.get("note","")
            record["result"]="official_page_verified"
        except Exception as exc:
            record["result"]="verification_unresolved"
            record["reason"]=f"{type(exc).__name__}: {exc}"
            # Do not delete evidence on transient errors. A prior manual record remains.
        log.append(record)
    (DIR/"verification_report.json").write_text(json.dumps({
        "generated_at":TODAY,
        "sources_checked":len(log),
        "passed":sum(x["result"]=="official_page_verified" for x in log),
        "unresolved":sum(x["result"]=="verification_unresolved" for x in log),
        "checks":log
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    data["generated_at"]=TODAY
    (DIR/"companies.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Official source verification: {sum(x['result']=='official_page_verified' for x in log)}/{len(log)} passed")

if __name__=="__main__":
    main()
