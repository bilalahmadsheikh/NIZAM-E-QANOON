"""Crawl the Supreme Court of Azad Jammu & Kashmir's judgments (ajksupremecourt.gok.pk), D-139.

    python3 -I data/ajksc_judgments_scraper.py [--out /mnt/e/nizam-data/acquire/ajksc] [--delay 2]

The court's site is WordPress (25 Nov 2026). Its HTML pages answer HTTP 500 with the page intact, so the crawl reads
the site's public REST API instead:

  * posts  /wp-json/wp/v2/posts?per_page=100&page=N  (893): one per judgment, titled by the parties, linking the file
    either as an upload on the court's own server or, since 2026, as a Google Drive file the court published;
  * media  /wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&page=N  (967): every PDF uploaded, some not
    judgments (notifications, the Interim Constitution, rules) -- the landing gate holds those.

A Drive file is fetched by its id from drive.google.com/uc?export=download. Polite: one request at a time, --delay
apart, a generic client name; a file already downloaded is not fetched again; a download is kept only if it is a PDF.
Writes ajksc_judgments/<file>.pdf, listing.jsonl, manifest.csv and ajksc_judgments.zip.
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
API = "https://ajksupremecourt.gok.pk/wp-json/wp/v2"
DRIVE = re.compile(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?[^\"']*id=)([A-Za-z0-9_-]{20,})")


def get(url: str, timeout: int = 180) -> bytes:
    parts = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/")))
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def pages(endpoint: str, delay: float) -> list[dict]:
    out, n = [], 1
    while True:
        try:
            batch = json.loads(get(f"{API}/{endpoint}{'&' if '?' in endpoint else '?'}per_page=100&page={n}"))
        except urllib.error.HTTPError as exc:
            if exc.code == 400:                     # past the last page
                break
            raise
        if not batch:
            break
        out += batch
        print(f"{endpoint.split('?')[0]} page {n}: {len(out)}", flush=True)
        n += 1
        time.sleep(delay)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/ajksc"))
    ap.add_argument("--delay", type=float, default=2.0)
    a = ap.parse_args()
    folder = a.out / "ajksc_judgments"
    folder.mkdir(parents=True, exist_ok=True)

    items: dict[str, dict] = {}
    for p in pages("posts", a.delay):
        body = p["content"]["rendered"]
        title = html.unescape(re.sub(r"<[^>]+>", "", p["title"]["rendered"]))
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())[:300]
        for m in DRIVE.finditer(body):
            url = f"https://drive.google.com/uc?export=download&id={m.group(1)}"
            items.setdefault(url, dict(url=url, source="post-drive", title=title, posted=p["date"], note=text))
        for m in re.finditer(r"""href=["'](https?://ajksupremecourt\.gok\.pk/wp-content/uploads/[^"']+\.pdf)["']""",
                             body, re.I):
            url = html.unescape(m.group(1)).replace("http://", "https://", 1)
            items.setdefault(url, dict(url=url, source="post-upload", title=title, posted=p["date"], note=text))
    for m in pages("media?mime_type=application/pdf", a.delay):
        url = m["source_url"].replace("http://", "https://", 1)
        items.setdefault(url, dict(url=url, source="media", title=html.unescape(m["title"]["rendered"]),
                                   posted=m["date"], note=None))
    print(f"listing: {len(items)} files", flush=True)
    with open(folder / "listing.jsonl", "w", encoding="utf-8") as f:
        for r in items.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    out, got, kept, bad, names = [], 0, 0, 0, set()
    for n, r in enumerate(items.values(), 1):
        drive = DRIVE.search(r["url"]) or re.search(r"[?&]id=([A-Za-z0-9_-]{20,})", r["url"])
        base = (f"drive_{drive.group(1)}.pdf" if "drive.google.com" in r["url"]
                else re.sub(r"[^A-Za-z0-9._-]+", "_", urllib.parse.unquote(r["url"].split("/uploads/", 1)[-1])))[:150]
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
                    path.write_bytes(data)
                    got += 1
            except Exception as exc:                            # noqa: BLE001
                status, bad = f"error: {type(exc).__name__}: {exc}"[:200], bad + 1
            time.sleep(a.delay)
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if status == "ok" else ""
        out.append(dict(filename=name, url=r["url"], status=status, sha256=sha, title=r["title"], posted=r["posted"],
                        source=r["source"]))
        if n % 100 == 0:
            print(f"files {n}/{len(items)}: downloaded {got}, held {kept}, failed {bad}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    zpath = a.out.parent.parent / "ajksc_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            z.write(p, f"ajksc_judgments/{p.name}")
    print(f"downloaded {got}, already held {kept}, failed {bad}; archive {zpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
