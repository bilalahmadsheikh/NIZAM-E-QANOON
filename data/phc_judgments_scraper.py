"""Crawl the Peshawar High Court's reported judgments (peshawarhighcourt.gov.pk), D-139.

    python3 -I data/phc_judgments_scraper.py [--out /mnt/e/nizam-data/acquire/phc] [--from 2010] [--delay 1.5]

The court's Reported Judgments page answers a GET per year with every row (25 Nov 2026):

  https://www.peshawarhighcourt.gov.pk/PHCCMS/reportedJudgments.php?action=search&year=<Y>&judge=&category=

A row's cells: serial, case, remarks, other citation (a reporter identifier), PHC neutral citation ('2026 PHC 1'),
decision date, S.C. status, category, the judgment link, and the Supreme Court's judgment link where one exists. Only
the court's own judgment is taken; a linked Supreme Court judgment is that court's, crawled from its own site.

The site's pages carry injected third-party links (seen 25 Nov 2026), so only links on the court's own host, ending in
.pdf, are followed, and a download is kept only if it is a PDF. Polite: one request at a time, --delay seconds apart,
a generic client name. A file already downloaded is not fetched again. Writes, under --out:

  phc_judgments/<file>.pdf, listing.jsonl, manifest.csv;  phc_judgments.zip (--member-prefix phc_judgments/)
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
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

UA = "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"
HOST = "www.peshawarhighcourt.gov.pk"
SEARCH = f"https://{HOST}/PHCCMS/reportedJudgments.php?action=search&year={{year}}&judge=&category="
HREF = re.compile(r"""href\s*=\s*['"]?([^'"\s>]+\.pdf)""", re.I)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)


def get(url: str, timeout: int = 240) -> bytes:
    parts = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(parts.path, safe="/%")))
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def rows_of(page: str, year: int) -> list[dict]:
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = CELL.findall(tr)
        if len(cells) < 9:
            continue
        links = [HREF.search(c) for c in cells]
        own = links[8]
        if not own or urllib.parse.urlsplit(own.group(1)).netloc.lower() != HOST:
            continue
        t = [text(c) for c in cells]
        out.append(dict(year=year, case=t[1], remarks=t[2] or None, other_citation=t[3] or None,
                        phc_citation=t[4] or None, decided=t[5] or None, sc_status=t[6] or None, category=t[7] or None,
                        url=html.unescape(own.group(1))))                # '&amp;' in an href is '&'
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/phc"))
    ap.add_argument("--from", dest="first", type=int, default=2010)
    ap.add_argument("--delay", type=float, default=1.5)
    a = ap.parse_args()
    folder = a.out / "phc_judgments"
    folder.mkdir(parents=True, exist_ok=True)

    listing: dict[str, dict] = {}
    for year in range(dt.date.today().year, a.first - 1, -1):
        page = get(SEARCH.format(year=year)).decode("utf-8", "replace")
        rows = rows_of(page, year)
        for r in rows:
            listing.setdefault(r["url"], r)
        print(f"listing {year}: {len(rows)} rows ({len(listing)} distinct so far)", flush=True)
        time.sleep(a.delay)
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
        out.append(dict(filename=name, url=r["url"], status=status, sha256=sha, case=r["case"],
                        phc_citation=r["phc_citation"], decided=r["decided"], category=r["category"],
                        other_citation=r["other_citation"], year=r["year"]))
        if n % 100 == 0:
            print(f"files {n}/{len(listing)}: downloaded {got}, held {kept}, failed {bad}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    zpath = a.out.parent.parent / "phc_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            if p.suffix != ".tmp":
                z.write(p, f"phc_judgments/{p.name}")
    print(f"downloaded {got}, already held {kept}, failed {bad}; archive {zpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
