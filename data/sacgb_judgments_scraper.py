"""Crawl the Supreme Appellate Court Gilgit-Baltistan's judgments (sacgb.gov.pk), D-139.

    python3 -I data/sacgb_judgments_scraper.py [--out /mnt/e/nizam-data/acquire/sacgb] [--delay 1.5]

The court publishes one static page, https://sacgb.gov.pk/Judgments.html: a table whose rows carry the case title, the
case reference (CPLA, Civil Appeal, Cr. PLA, SMC, HRC ...) and a link to the PDF under Judgments/ (25 Nov 2026; 752
distinct links, some printed with a stray leading space). The site has no robots.txt (404).

Polite: one request at a time, --delay seconds apart, a generic client name. Only links on the court's own host are
followed, a download is kept only if it is a PDF, and a file already downloaded is not fetched again. Writes, under
--out: sacgb_judgments/<file>.pdf, listing.jsonl, manifest.csv; and sacgb_judgments.zip (--member-prefix
sacgb_judgments/).
"""
from __future__ import annotations

import argparse
import csv
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
INDEX = "https://sacgb.gov.pk/Judgments.html"
HOSTS = {"sacgb.gov.pk", "www.sacgb.gov.pk"}


def get(url: str, timeout: int = 180) -> bytes:
    parts = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/")))
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def rows_of(page: str) -> list[dict]:
    out, seen = [], set()
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        m = re.search(r"""href\s*=\s*["']\s*([^"']+?\.pdf)\s*["']""", tr, re.I)
        if not m:
            continue
        url = urllib.parse.urljoin(INDEX, html.unescape(m.group(1)).strip())     # '&amp;' in an href is '&'
        if urllib.parse.urlsplit(url).netloc.lower() not in HOSTS or url in seen:
            continue
        seen.add(url)
        cells = [text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
        out.append(dict(url=url, cells=[c for c in cells if c]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/sacgb"))
    ap.add_argument("--delay", type=float, default=1.5)
    a = ap.parse_args()
    folder = a.out / "sacgb_judgments"
    folder.mkdir(parents=True, exist_ok=True)
    rows = rows_of(get(INDEX).decode("utf-8", "replace"))
    print(f"listing: {len(rows)} judgments", flush=True)
    with open(folder / "listing.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    out, got, kept, bad, names = [], 0, 0, 0, set()
    for n, r in enumerate(rows, 1):
        path_part = urllib.parse.unquote(urllib.parse.urlsplit(r["url"]).path)
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", path_part.strip("/").replace("Judgments/", "", 1))[:150]
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
        out.append(dict(filename=name, url=r["url"], status=status, sha256=sha, listed=" | ".join(r["cells"])[:500]))
        if n % 100 == 0:
            print(f"files {n}/{len(rows)}: downloaded {got}, held {kept}, failed {bad}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    zpath = a.out.parent.parent / "sacgb_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            if p.suffix != ".tmp":
                z.write(p, f"sacgb_judgments/{p.name}")
    print(f"downloaded {got}, already held {kept}, failed {bad}; archive {zpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
