"""portal_diff.py : list an official code portal today and say which listed laws the corpus does not hold (read-only).

Acquisition is closed for the August 2026 catalogue (CLAUDE.md); portals publish after that and sometimes list items the
first crawl never reached. This re-reads each portal's LISTING pages with the scraper that first crawled it (data/*.py,
same parsing, same polite delays) and compares every row with what the corpus holds:

    known.csv   tools/acquire/known_sources.sql output: every observation URL and every title the corpus holds
    manifests   the August scrape manifests (detail_url / pdf_url of every row the first crawl saw)

A listed row is HELD when its detail URL is in a manifest or in known.csv, or its normalised title is a held title.
Otherwise it is a CANDIDATE: only candidates have their detail page fetched (to learn the file URL), and a candidate
whose file URL the corpus already holds is reclassified HELD (renamed listing). Nothing is downloaded and nothing is
written to the database.

    python tools/acquire/portal_diff.py PORTAL --known known.csv --out DIR [--manifest CSV ...] [--years 2020-2026]
    PORTAL: fed | punjab | kp | balochistan

Writes DIR/<portal>-listing.csv (every row, with its verdict) and prints the counts. A title match is a strong but
not a proof of identity (series collide: docs memory l2-metadata), so a HELD-by-title row is reported as such.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
csv.field_size_limit(10 ** 8)


def norm(title: str) -> str:
    t = (title or "").lower().replace("&", " and ")
    t = re.sub(r"\(\s*under review\s*\)", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"^\s*the\s+", "", t)
    t = re.sub(r"\b(no|number)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def load_known(path: Path, manifests: list[Path]) -> tuple[set, set]:
    urls, titles = set(), set()
    with path.open(encoding="utf-8", newline="") as fh:
        for kind, value in csv.reader(fh):
            if kind == "url":
                urls.add(value.strip())
            elif kind == "title" and norm(value):
                titles.add(norm(value))
    for m in manifests:
        with m.open(encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                if (r.get("status") or "success") != "success":
                    continue  # a row the first crawl failed on is not held because it was listed
                for k in ("detail_url", "pdf_url"):
                    if r.get(k):
                        urls.add(r[k].strip())
    return urls, titles


def listing(portal: str, mod, years: range | None):
    s = mod.make_session()
    if portal == "fed":
        for y in (years or range(mod.FIRST_YEAR, mod.LAST_YEAR + 1)):
            for title, url in mod.fetch_year_acts(s, y):
                yield "law", str(y), title, url
    elif portal == "punjab":
        for y, yurl in mod.get_year_urls_from_index(s):
            if years and y not in years:
                continue
            for title, url in mod.get_acts_for_year(s, y, yurl):
                yield "law", str(y), title, url
        if not years:
            for tab, depts in mod.get_rule_departments(s).items():
                for dept, durl in depts:
                    for title, url in mod.get_rules_for_dept(s, durl):
                        yield "rule", dept, title, url
    elif portal == "kp":
        for y, yurl in mod.get_year_listing_urls(s):
            if years and y not in years:
                continue
            for title, url in mod.get_acts_from_listing(s, yurl, y):
                yield "law", str(y), title, url
        if not years:
            # 13 Nov 2026: /homepage/rules is now a year index (search_by_year_rule/N) whose year pages use the laws'
            # artlist layout; kp_scraper.get_rules reads the old flat page and finds nothing.
            from bs4 import BeautifulSoup
            r = mod.get_with_retries(s, mod.RULES_INDEX); mod.polite_sleep()
            soup = BeautifulSoup(r.text if r else "", "html.parser")
            for a in soup.find_all("a", href=True):
                if "search_by_year_rule" in a["href"] and re.match(r"^\d{4}$", a.get_text(strip=True)):
                    y = int(a.get_text(strip=True))
                    for title, url in mod.get_acts_from_listing(s, a["href"], y):
                        yield "rule", str(y), title, url
    elif portal == "balochistan":
        for y in sorted(years or range(mod.FIRST_YEAR, mod.LAST_YEAR + 1), reverse=True):
            for title, url in mod.get_acts_for_year(s, y):
                yield "law_or_rule", str(y), title, url
    else:
        raise SystemExit(f"unknown portal {portal}")


def file_url(portal: str, mod, session, detail_url: str) -> str | None:
    r = mod.get_with_retries(session, detail_url)
    mod.polite_sleep()
    if not r or r.status_code != 200:
        return None
    if portal == "fed":
        return mod.extract_pdf_url_from_detail_page(r.text)
    if portal == "punjab":
        return mod.extract_pdf_url_from_detail(r.text)
    if portal == "kp":
        return mod.extract_pdf_info(r.text, "")[0]
    if portal == "balochistan":
        return mod.extract_pdf_info(r.text)[0]


MODULE = {"fed": "scraper", "punjab": "punjab_scraper", "kp": "kp_scraper", "balochistan": "balochistan_scraper"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("portal", choices=sorted(MODULE))
    ap.add_argument("--known", required=True, type=Path)
    ap.add_argument("--manifest", action="append", default=[], type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--years", help="e.g. 2024-2026 (laws only; rules are listed only on a full run)")
    a = ap.parse_args()
    years = None
    if a.years:
        lo, hi = (int(x) for x in a.years.split("-"))
        years = range(lo, hi + 1)
    urls, titles = load_known(a.known, a.manifest)
    a.out.mkdir(parents=True, exist_ok=True)
    work = a.out / f"_{a.portal}-scraper-cwd"  # the scrapers create their log folder in the working directory
    work.mkdir(exist_ok=True)
    os.chdir(work)
    sys.path.insert(0, str(ROOT / "data"))
    mod = importlib.import_module(MODULE[a.portal])
    session = mod.make_session()
    rows, counts = [], {}
    for kind, year, title, detail in listing(a.portal, mod, years):
        verdict, pdf = None, ""
        if detail in urls:
            verdict = "held_url"
        elif norm(title) in titles:
            verdict = "held_title"
        else:
            pdf = file_url(a.portal, mod, session, detail) or ""
            verdict = "held_file_url" if pdf and pdf in urls else ("candidate" if pdf else "candidate_no_file")
        counts[verdict] = counts.get(verdict, 0) + 1
        rows.append({"portal": a.portal, "kind": kind, "year_or_dept": year, "title": title, "detail_url": detail,
                     "pdf_url": pdf, "verdict": verdict})
        if verdict.startswith("candidate"):
            print(f"{verdict}: {year} {title} {pdf}", flush=True)
    dst = a.out / f"{a.portal}{'-' + a.years if a.years else ''}-listing.csv"
    with dst.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["portal"])
        w.writeheader(); w.writerows(rows)
    print(a.portal, counts, "->", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
