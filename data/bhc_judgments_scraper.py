"""Crawl the High Court of Balochistan's reported and significant judgments (bhc.gov.pk), D-139.

    python3 -I data/bhc_judgments_scraper.py [--out /mnt/e/nizam-data/acquire/bhc] [--delay 3]

The court lists judgments per judge (25 Nov 2026): https://bhc.gov.pk/resources/judgments links each judge, and
.../<judge>/reported-judgments and .../<judge>/significant-judgments list every entry as a box with the case title, a
reporter citation (an identifier: 'PCrLJ 2024 435') and a 'View Judgment' popup whose data-src is the PDF,
https://bhc.gov.pk/media/judgments/<n>.pdf.

The site's robots.txt disallows /media/. The owner ruled on 25 Nov 2026 that these files are fetched anyway, slowly
(DECISION-LOG D-139); the listing pages themselves are not disallowed. Hence the default --delay of 3 s, one request
at a time, a generic client name, and no file fetched twice. Some files may be law-report reprints: the landing gate
classes those as reporter_reprint and they are not landed (D-120; the owner's 25 Nov rule for Balochistan's reports).

Writes bhc_judgments/<n>.pdf, listing.jsonl, manifest.csv and bhc_judgments.zip (--member-prefix bhc_judgments/).
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
INDEX = "https://bhc.gov.pk/resources/judgments"
BOX = re.compile(r'(?s)<div class="judgmentbox.*?data-src="([^"]+\.pdf)"')


def get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def boxes(page: str, judge: str, listing: str) -> list[dict]:
    out = []
    for block in page.split('<div class="judgmentbox')[1:]:
        src = re.search(r'data-src="([^"]+\.pdf)"', block)
        if not src:
            continue
        url = urllib.parse.urljoin(INDEX, html.unescape(src.group(1)))
        if urllib.parse.urlsplit(url).netloc.lower() not in ("bhc.gov.pk", "www.bhc.gov.pk"):
            continue
        title = re.search(r'(?s)<div class="title">(.*?)</div>', block)
        note = re.search(r'(?s)<div class="note[^"]*">(.*?)</div>', block)
        out.append(dict(url=url, judge=judge, listing=listing, title=text(title.group(1)) if title else None,
                        reporter_citation=text(note.group(1)) if note else None))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/bhc"))
    ap.add_argument("--delay", type=float, default=3.0)
    a = ap.parse_args()
    folder = a.out / "bhc_judgments"
    folder.mkdir(parents=True, exist_ok=True)
    index = get(INDEX).decode("utf-8", "replace")
    judges = sorted(set(re.findall(r"https://bhc\.gov\.pk/resources/judgments/([a-z0-9-]+)", index)))
    time.sleep(a.delay)
    listing: dict[str, dict] = {}
    for slug in judges:
        for kind in ("reported-judgments", "significant-judgments"):
            page = get(f"{INDEX}/{slug}/{kind}").decode("utf-8", "replace")
            rows = boxes(page, slug, kind)
            for r in rows:
                listing.setdefault(r["url"], r)
            print(f"listing {slug} {kind}: {len(rows)} ({len(listing)} distinct so far)", flush=True)
            time.sleep(a.delay)
    with open(folder / "listing.jsonl", "w", encoding="utf-8") as f:
        for r in listing.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    out, got, kept, bad = [], 0, 0, 0
    for n, r in enumerate(listing.values(), 1):
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", urllib.parse.unquote(r["url"].rsplit("/", 1)[-1]))[:150]
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
                    path.write_bytes(data)
                    got += 1
            except Exception as exc:                            # noqa: BLE001
                status, bad = f"error: {type(exc).__name__}: {exc}"[:200], bad + 1
            time.sleep(a.delay)
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if status == "ok" else ""
        out.append(dict(filename=name, url=r["url"], status=status, sha256=sha, title=r["title"], judge=r["judge"],
                        listing=r["listing"], reporter_citation=r["reporter_citation"]))
        if n % 100 == 0:
            print(f"files {n}/{len(listing)}: downloaded {got}, held {kept}, failed {bad}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    zpath = a.out.parent.parent / "bhc_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            z.write(p, f"bhc_judgments/{p.name}")
    print(f"downloaded {got}, already held {kept}, failed {bad}; archive {zpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
