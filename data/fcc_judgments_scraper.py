"""Crawl the Federal Constitutional Court's judgments and orders (fccp.gov.pk), D-139.

    python3 -I data/fcc_judgments_scraper.py [--out /mnt/e/nizam-data/acquire/fcc] [--delay 2]

The court's site is a single-page app over a public JSON API (read from its own script bundle, 25 Nov 2026):

  * listing  GET /api/public/site/publications/judgement[?cursor=<next>]  ->  {items, total, start, size, next}
    each item: key, body {title, fileName, authors, issuedAt, approvedForReporting, file}, files [{sha256, ...}]
  * file     GET /api/public/site/files/<sha256>

Polite by construction: one request at a time, `--delay` seconds apart, a generic client name and nothing that
identifies the project or its people. A file is kept only when its bytes hash to the sha256 the listing names, and a
file already held is not fetched again, so a run resumes. Writes, under --out:

  fcc_judgments/<key>__<fileName>     the PDFs as served
  fcc_judgments/listing.jsonl         every listing item as served (authors, upload time, reporting flag)
  fcc_judgments/manifest.csv          filename, url, status, sha256 (read by nizam.workers.judgments)
  fcc_judgments.zip                   the folder, for `nizam.workers.judgments --member-prefix fcc_judgments/`
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://fccp.gov.pk"
UA = "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"


def get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip()[:150]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/fcc"))
    ap.add_argument("--delay", type=float, default=2.0)
    a = ap.parse_args()
    folder = a.out / "fcc_judgments"
    folder.mkdir(parents=True, exist_ok=True)

    items, cursor = [], None
    while True:
        url = f"{BASE}/api/public/site/publications/judgement"
        if cursor:
            url += "?" + urllib.parse.urlencode({"cursor": cursor})
        page = json.loads(get(url))
        items += page["items"]
        print(f"listing: {len(items)} of {page['total']}", flush=True)
        cursor = page.get("next")
        time.sleep(a.delay)
        if not cursor:
            break
    if len(items) != page["total"]:
        print(f"warning: listed {len(items)}, the site says {page['total']}", file=sys.stderr)
    with open(folder / "listing.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    rows, got, kept, bad = [], 0, 0, 0
    for it in items:
        body = it["body"]
        sha = (it.get("files") or [{}])[0].get("sha256") or body.get("file")
        name = safe(f"{it['key']}__{body.get('fileName') or body.get('title') or sha}")
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        url = f"{BASE}/api/public/site/files/{sha}"
        path = folder / name
        status = "ok"
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == sha:
            kept += 1
        else:
            try:
                data = get(url)
                if hashlib.sha256(data).hexdigest() != sha:
                    status, bad = "sha_mismatch", bad + 1
                else:
                    path.write_bytes(data)
                    got += 1
            except Exception as exc:                            # noqa: BLE001
                status, bad = f"error: {type(exc).__name__}: {exc}"[:200], bad + 1
            time.sleep(a.delay)
        rows.append(dict(filename=name, url=url, status=status, sha256=sha, title=body.get("title"),
                         issued_at=body.get("issuedAt"), approved_for_reporting=body.get("approvedForReporting"),
                         authors="; ".join(body.get("authors") or [])))
        print(f"{len(rows)}/{len(items)} {status} {name}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    zpath = a.out.parent.parent / "fcc_judgments.zip" if a.out.name == "fcc" else a.out / "fcc_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            z.write(p, f"fcc_judgments/{p.name}")
    print(f"downloaded {got}, already held {kept}, failed {bad}; archive {zpath}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
