"""Crawl the High Court of Azad Jammu & Kashmir's judgments (ajkhighcourt.gok.pk), D-139.

    python3 -I data/ajkhc_judgments_scraper.py --cacert CA_BUNDLE [--out /mnt/e/nizam-data/acquire/ajkhc] [--delay 1.5]

The court's judgment search (https://ajkhighcourt.gok.pk/Userside/Judgement) is a form POSTed back to the page:
judgment_tab (judgment: sitting judges; previous: former judges), cmbYear, cmbBench, cmbCategory ('ALL' for each).
The results are a table: case number, title, category, decision date, and a 'View' link to
https://ajkhighcourt.gok.pk/judgment_files/<name>.pdf (25 Nov 2026: 219 + 43 rows). The site has no robots.txt.

The server sends an incomplete certificate chain (its RapidSSL intermediate is missing). Verification stays on: pass
--cacert, a bundle of the system roots plus that intermediate fetched from the certificate's own AIA URL
(E:/nizam-data/acquire/work/ajk_chain.sh builds it).

Completeness: the search is also run per year for the last --check-years years, and the per-year counts are compared
with the all-years result; a difference is printed and fails the run. Polite: one request at a time, --delay apart, a
generic client name. Writes ajkhc_judgments/<file>.pdf, listing.jsonl, manifest.csv and ajkhc_judgments.zip.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import html
import http.cookiejar
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

UA = "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"
SEARCH = "https://ajkhighcourt.gok.pk/Userside/Judgement"
HOST = "ajkhighcourt.gok.pk"


def opener(cacert: Path):
    ctx = ssl.create_default_context(cafile=str(cacert))
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                       urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def fetch(op, url: str, data: dict | None = None, timeout: int = 180) -> bytes:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA, "Accept": "*/*"})
    with op.open(req, timeout=timeout) as r:
        return r.read()


def text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def rows_of(page: str, tab: str) -> list[dict]:
    body = page[page.lower().find("<tbody"):]
    out = []
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", body):
        link = re.search(r"""href=["'](https://ajkhighcourt\.gok\.pk/judgment_files/[^"']+\.pdf)["']""", tr, re.I)
        if not link:
            continue
        cells = re.findall(r"(?is)<td[^>]*>(.*?)</td>", tr)
        case = re.search(r'(?is)class="court-case-no">(.*?)</span>', tr)
        title = re.search(r'(?is)class="court-case-title">(.*?)</span>', tr)
        out.append(dict(tab=tab, url=html.unescape(link.group(1)), case=text(case.group(1)) if case else None,
                        title=text(title.group(1)) if title else None,
                        category=text(cells[2]) if len(cells) > 2 else None,
                        decided=text(cells[3]) if len(cells) > 3 else None))
    return out


def search(op, tab: str, year: str) -> list[dict]:
    page = fetch(op, f"{SEARCH}?judgment_tab={tab}", dict(judgment_tab=tab, cmbYear=year, cmbBench="ALL",
                                                          cmbCategory="ALL", btnSearchJudgment=""))
    return rows_of(page.decode("utf-8", "replace"), tab)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cacert", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/ajkhc"))
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--check-years", type=int, default=6)
    a = ap.parse_args()
    op = opener(a.cacert)
    folder = a.out / "ajkhc_judgments"
    folder.mkdir(parents=True, exist_ok=True)
    fetch(op, SEARCH)                                   # the session cookie the form expects
    time.sleep(a.delay)

    listing: dict[str, dict] = {}
    short = 0
    for tab in ("judgment", "previous"):
        rows = search(op, tab, "ALL")
        time.sleep(a.delay)
        for r in rows:
            listing.setdefault(r["url"], r)
        by_year = collections.Counter((r["decided"] or "")[-4:] for r in rows)
        print(f"listing {tab}: {len(rows)} rows; by year {dict(sorted(by_year.items()))}", flush=True)
        for year in sorted(by_year, reverse=True)[:a.check_years]:
            if not year.isdigit():
                continue
            n = len(search(op, tab, year))
            time.sleep(a.delay)
            flag = "" if n == by_year[year] else "  <-- the all-years search differs"
            short += n != by_year[year]
            print(f"  check {tab} {year}: {n} by year, {by_year[year]} in all-years{flag}", flush=True)
    with open(folder / "listing.jsonl", "w", encoding="utf-8") as f:
        for r in listing.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    out, got, kept, bad, names = [], 0, 0, 0, set()
    for n, r in enumerate(listing.values(), 1):
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", urllib.parse.unquote(r["url"].rsplit("/", 1)[-1]))[:150]
        name = base if base not in names else f"{n}_{base}"
        names.add(name)
        path = folder / name
        status = "ok"
        if path.exists() and path.stat().st_size > 0:
            kept += 1
        else:
            try:
                data = fetch(op, r["url"])
                if not data.startswith(b"%PDF"):
                    status, bad = "not_a_pdf", bad + 1
                else:
                    path.write_bytes(data)
                    got += 1
            except Exception as exc:                            # noqa: BLE001
                status, bad = f"error: {type(exc).__name__}: {exc}"[:200], bad + 1
            time.sleep(a.delay)
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if status == "ok" else ""
        out.append(dict(filename=name, url=r["url"], status=status, sha256=sha, case=r["case"], title=r["title"],
                        category=r["category"], decided=r["decided"], tab=r["tab"]))
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    zpath = a.out.parent.parent / "ajkhc_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            z.write(p, f"ajkhc_judgments/{p.name}")
    print(f"downloaded {got}, already held {kept}, failed {bad}; archive {zpath}; completeness checks failed: {short}")
    return 1 if (bad or short) else 0


if __name__ == "__main__":
    sys.exit(main())
