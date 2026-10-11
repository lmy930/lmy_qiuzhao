#!/usr/bin/env python3
"""Discover possible 2027 campus recruitment announcements. Search hits are leads, NOT confirmed openings."""
import datetime as dt
import json
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "companies.json"
OUTPUT = ROOT / "data" / "leads.json"
TODAY = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
KEYWORDS = ("2027", "校招", "校园招聘", "秋招", "招聘")
DISCARD = ("2026届", "2025届", "2024届")
USER_AGENT = "Mozilla/5.0 (compatible; RecruitmentCalendarBot/1.0)"

def search(company):
    q = f'"{company}" "2027" ("校园招聘" OR "秋季招聘")'
    url = "https://www.bing.com/search?format=rss&q=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=14) as response:
        feed = ET.fromstring(response.read(250000))
    hits = []
    for item in feed.findall(".//item")[:8]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = re.sub("<[^>]+>", " ", item.findtext("description") or "").strip()
        body = title + " " + description
        if "2027" not in body or not any(k in body for k in ("校招","校园招聘","秋招")):
            continue
        if any(k in body for k in DISCARD):
            continue
        if link.startswith("https://") or link.startswith("http://"):
            hits.append({"title":title[:150],"url":link,"snippet":description[:260]})
    return hits[:5]

def main():
    companies = json.loads(DATA.read_text(encoding="utf-8"))["companies"]
    existing = {}
    if OUTPUT.exists():
        try:
            old = json.loads(OUTPUT.read_text(encoding="utf-8"))
            existing = {entry["name"]:entry for entry in old.get("leads",[])}
        except (OSError,ValueError,KeyError):
            pass
    # Cycle through all 619 companies, plus daily attention to a smaller priority set.
    priority = ["国家电网有限公司","中国移动通信集团有限公司","中国工商银行股份有限公司",
                "中国农业银行股份有限公司","中国银行股份有限公司","中国建设银行股份有限公司",
                "中国邮政储蓄银行股份有限公司","交通银行股份有限公司",
                "华为投资控股有限公司","比亚迪股份有限公司","宁德时代新能源科技股份有限公司"]
    n = len(companies)
    start = (TODAY.toordinal() * 36) % n
    chosen = [companies[(start+i)%n]["name"] for i in range(min(n,36))]
    chosen = list(dict.fromkeys(priority + chosen))
    checked,errors = 0,0
    for name in chosen:
        try:
            hits = search(name)
            previous = existing.get(name,{})
            if hits:
                previous["name"] = name
                previous["hits"] = hits
                previous["last_found"] = str(TODAY)
                existing[name] = previous
            checked += 1
        except Exception as exc:
            errors += 1
            print(f"Search unavailable for {name}: {type(exc).__name__}: {exc}")
        time.sleep(1.1)
    payload = {
        "scanned_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "searches_attempted":len(chosen),
        "searches_succeeded":checked,
        "searches_failed":errors,
        "disclaimer":"仅为搜索发现的待核验线索，不能当作已开启公告。状态和开启日期必须经官方来源人工核验。",
        "leads":sorted(existing.values(), key=lambda c:c.get("last_found",""), reverse=True)
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Scanned {len(chosen)} companies, successful {checked}, failed {errors}, accumulated leads {len(existing)}")

if __name__ == "__main__":
    main()
