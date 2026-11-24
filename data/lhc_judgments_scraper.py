"""Crawl the Lahore High Court's judgments approved for reporting (data.lhc.gov.pk), D-139.

    python3 -I data/lhc_judgments_scraper.py [--out /mnt/e/nizam-data/acquire/lhc] [--from 2011] [--delay 1.5]

The court's two listing pages (current judges; former judges) load their results from plain GET endpoints, one
response per year with every row (read from the pages' own scripts, 25 Nov 2026):

  https://data.lhc.gov.pk/dynamic/approved_judgments_result_new.php?year=<Y>&...
  https://data.lhc.gov.pk/dynamic/approved_judgments_result_former_judges.php?year=<Y>&...

Each row links the judgment at https://sys.lhc.gov.pk/appjudgments/<citation>.pdf ('2025LHC8203'), under the judge's
name (an <h2>), with the case, title, decision date, LHC citation, other citations and a tag line. The tag line is the
court's own listing metadata, never judgment text; other citations ('PLJ 2026 Lahore 474') are reporter identifiers,
kept as identifiers only (D-120).

Polite: one request at a time, --delay seconds apart, a generic client name, nothing identifying the project or its
people. A PDF already downloaded is not fetched again, so a run resumes. Writes, under --out:

  lhc_judgments/<citation>.pdf        the PDFs as served
  lhc_judgments/listing.jsonl         one row per listing entry (list, year, judge, title, tag line, upload date)
  lhc_judgments/manifest.csv          filename, url, status, sha256 (read by nizam.workers.judgments)
  lhc_judgments.zip                   for `nizam.workers.judgments --member-prefix lhc_judgments/`
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

UA = "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"
LISTS = {"current": "https://data.lhc.gov.pk/dynamic/approved_judgments_result_new.php",
         "former": "https://data.lhc.gov.pk/dynamic/approved_judgments_result_former_judges.php"}
QUERY = "&debug=&courtName=&caseNumber=&citationTag=&partyName=&decisionDate0=&decisionDate1=&uploadDate=&uploadDate1="
LINK = re.compile(r"href='(https://sys\.lhc\.gov\.pk/appjudgments/([^']+?)\.pdf)'")
JUDGE = re.compile(r"<h2>(.*?)</h2>", re.S)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def get(url: str, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def rows_of(page: str, which: str, year: int) -> list[dict]:
    """Listing rows in page order, each under the last judge heading before it. A row is its own <table>: serial,
    case (type and number), title, decision date, LHC citation, other citations (reporter identifiers), the link;
    then a 'Tag Line:' row."""
    judge, out = None, []
    for block in re.split(r"(?=<table|<h2>)", page):
        j = JUDGE.match(block)
        if j:
            judge = text(j.group(1))
            continue
        link = LINK.search(block)
        if not link:
            continue
        cells = [text(c) for c in CELL.findall(block)]
        tag = re.search(r"Tag Line:\s*</strong>(.*?)</td>", block, re.S)
        get_ = (lambda k: cells[k] if len(cells) > k else None)
        out.append(dict(list=which, year=year, judge=judge, citation=link.group(2), url=html.unescape(link.group(1)),
                        case=get_(1), title=get_(2), decided=get_(3), lhc_citation=get_(4),
                        other_citations=get_(5) or None, tag_line=(text(tag.group(1)) or None) if tag else None))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/lhc"))
    ap.add_argument("--from", dest="first", type=int, default=2011)
    ap.add_argument("--delay", type=float, default=1.5)
    a = ap.parse_args()
    folder = a.out / "lhc_judgments"
    folder.mkdir(parents=True, exist_ok=True)

    listing: dict[str, dict] = {}
    for which, base in LISTS.items():
        for year in range(dt.date.today().year, a.first - 1, -1):
            page = get(f"{base}?year={year}{QUERY}").decode("utf-8", "replace")
            rows = rows_of(page, which, year)
            for r in rows:
                listing.setdefault(r["citation"], r)        # a judgment listed twice is one file
            print(f"listing {which} {year}: {len(rows)} rows ({len(listing)} distinct so far)", flush=True)
            time.sleep(a.delay)
    with open(folder / "listing.jsonl", "w", encoding="utf-8") as f:
        for r in listing.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    out, got, kept, bad = [], 0, 0, 0
    for n, r in enumerate(listing.values(), 1):
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", r["citation"]) + ".pdf"
        path = folder / name
        status = "ok"
        if path.exists() and path.stat().st_size > 0:
            kept += 1
        else:
            try:
                data = get(r["url"])
                if not data.startswith(b"%PDF"):
                    status, bad = "not_a_pdf", bad + 1
                else:
                    tmp = path.with_suffix(".tmp")
                    tmp.write_bytes(data)
                    tmp.replace(path)
                    got += 1
            except Exception as exc:                            # noqa: BLE001
                status, bad = f"error: {type(exc).__name__}: {exc}"[:200], bad + 1
            time.sleep(a.delay)
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if status == "ok" else ""
        out.append(dict(filename=name, url=r["url"], status=status, sha256=sha, citation=r["citation"],
                        case=r["case"], title=r["title"], decided=r["decided"], judge=r["judge"], year=r["year"],
                        other_citations=r["other_citations"], list=r["list"]))
        if n % 100 == 0:
            print(f"files {n}/{len(listing)}: downloaded {got}, held {kept}, failed {bad}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    zpath = a.out.parent.parent / "lhc_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            if p.suffix != ".tmp":
                z.write(p, f"lhc_judgments/{p.name}")
    print(f"downloaded {got}, already held {kept}, failed {bad}; archive {zpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
