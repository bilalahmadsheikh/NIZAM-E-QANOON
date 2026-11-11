#!/usr/bin/env python3
"""
Sindh Code -- Urdu and Sindhi texts (and the English row they belong to)
========================================================================
sindhlaws.gov.pk, as observed 12 Nov 2026 (the older data/sindh_scraper.py predates this layout and finds no PDF
links on it any more):

  * year index      Chrono.aspx?pg=ACT|ORDINANCE|RULE          -> links SindhGazetteDetail.aspx?X=<type>&Year=<y>
  * year listing    SindhGazetteDetail.aspx?X=<type>&Year=<y>  -> <div id="<type>"><table>, one row per law:
                    # | Title | English | Urdu | Sindhi | Date ; each language cell links
                    LawDocument.aspx?PubID=<PubID>&Lang=EN|UR|SD, or has no link when that text is not published
  * official file   DownloadDocument.aspx?PubID=<PubID>&Lang=EN|UR|SD -> application/pdf
                    (Content-Disposition names it <PubID>.pdf, <PubID>-U.pdf, <PubID>-U-S.pdf, ...)

The PubID is the join key: the English file the corpus already holds was landed from
setup/publications_SindhCode/<PubID>.pdf, so a Urdu or Sindhi file is paired with its English instrument by PubID,
never by title. The portal stamps EVERY download: the same file fetched twice on 12 Nov 2026 had the same size and
different SHA-256 (PUB-NEW-23-000005-UR), and the English bytes differ from the August 2026 landing. A byte hash
therefore identifies one fetch, not one document; identity across fetches is the PubID and language.

First run, 12 Nov 2026: 1,819 listing rows (ACT 68 years, ORDINANCE 47, RULE 57); Urdu 1,058, Sindhi 1,056 (Acts and
Ordinances; Rules almost never); 925 of the 1,061 rows with either pair with a released corpus instrument by PubID;
583 listed PubIDs are not in the corpus at all (an English acquisition gap to check separately).

TEXT LAYER (measured 12 Nov 2026, PUB-NEW-23-000005): the Urdu PDF (Jameel Noori Nastaleeq) has a text layer with
letters in reversed visual order and remapped digits ('0299' for 2019); the Sindhi PDF (MB Bhitai Sattar) maps to
wrong letters. Neither may be extracted as text without a verified repair or OCR. This scraper only ACQUIRES.

Output (OUT, default E:/nizam-data/acquire/sindh-language-<date>):
    discovery.csv   one row per listing row: doc_type, year, pub_id, title, date, en/ur/sd availability, listing_url
    manifest.csv    one row per downloaded or failed file (pub_id, lang, url, local_path, status, http_status,
                    file_size, sha256, served_filename, error) -- resumable
    Urdu/<type>/<year>/<PubID>-UR.pdf, Sindhi/<type>/<year>/<PubID>-SD.pdf
    scraper.log

    python data/sindh_language_scraper.py --discover                 # listings only
    python data/sindh_language_scraper.py --download UR,SD           # discover (or reuse discovery.csv) + download
    python data/sindh_language_scraper.py --download UR --type ACT --year 2019 --limit 5
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

BASE_URL = "https://sindhlaws.gov.pk"
DOC_TYPES = ("ACT", "ORDINANCE", "RULE")
LANGS = {"EN": "English", "UR": "Urdu", "SD": "Sindhi"}
CHRONO = BASE_URL + "/Chrono.aspx?pg={doc_type}"
LISTING = BASE_URL + "/SindhGazetteDetail.aspx?X={doc_type}&Year={year}"
DOWNLOAD = BASE_URL + "/DownloadDocument.aspx?PubID={pub_id}&Lang={lang}"
PUB_RX = re.compile(r"PubID=([A-Za-z0-9\-]+)&(?:amp;)?Lang=(EN|UR|SD)", re.I)
USER_AGENT = "Mozilla/5.0 (compatible; statute-corpus-research)"
MIN_DELAY, MAX_DELAY = 2.0, 3.5
MAX_RETRIES, BACKOFF = 4, 3
MIN_PDF_BYTES = 2048

DISCOVERY_FIELDS = ["doc_type", "year", "pub_id", "title", "date", "en", "ur", "sd", "listing_url"]
MANIFEST_FIELDS = ["doc_type", "year", "pub_id", "lang", "title", "url", "local_path", "status", "http_status",
                   "file_size", "sha256", "served_filename", "error"]


# ---------------------------------------------------------------- parsing (pure; tested against saved pages)
def parse_years(html: str, doc_type: str) -> list[int]:
    """Years the chronological index links for this type."""
    rx = re.compile(r"SindhGazetteDetail\.aspx\?X=" + re.escape(doc_type) + r"&(?:amp;)?Year=(\d{4})", re.I)
    return sorted({int(y) for y in rx.findall(html)}, reverse=True)


def parse_listing(html: str, doc_type: str) -> list[dict]:
    """One dict per law row: pub_id, title, date, and which languages link a document."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", id=doc_type)
    table = container.find("table") if container else None
    rows = []
    for tr in (table.find_all("tr") if table else []):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue
        title = cells[1].get_text(" ", strip=True)
        langs, pub_ids = {}, set()
        for cell, lang in zip(cells[2:5], ("EN", "UR", "SD")):
            a = cell.find("a", href=True)
            m = PUB_RX.search(a["href"]) if a else None
            langs[lang] = bool(m and m.group(2).upper() == lang)
            if m:
                pub_ids.add(m.group(1))
        if not title or len(pub_ids) != 1:       # no link at all, or links naming two PubIDs: not paired, skipped
            continue
        rows.append(dict(pub_id=pub_ids.pop(), title=title,
                         date=cells[5].get_text(strip=True) if len(cells) > 5 else "", **{k.lower(): v
                                                                                      for k, v in langs.items()}))
    return rows


def served_filename(content_disposition: str | None) -> str:
    m = re.search(r'filename\*?="?([^";]+)"?', content_disposition or "")
    return m.group(1) if m else ""


# ---------------------------------------------------------------- network
def make_session():
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Referer": BASE_URL})
    return s


def polite_sleep() -> None:
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def get(session, url, log, **kw):
    import requests
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=60, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            return r
        except requests.RequestException as e:
            wait = BACKOFF * 2 ** (attempt - 1)
            log.warning(f"{url}: {e} (attempt {attempt}/{MAX_RETRIES}); retrying in {wait}s")
            time.sleep(wait)
    return None


# ---------------------------------------------------------------- steps
def discover(session, out: Path, types, only_year, log) -> list[dict]:
    rows = []
    for doc_type in types:
        r = get(session, CHRONO.format(doc_type=doc_type), log); polite_sleep()
        if r is None or r.status_code != 200:
            log.error(f"{doc_type}: chronological index failed"); continue
        years = parse_years(r.text, doc_type)
        if only_year:
            years = [y for y in years if y == only_year]
        log.info(f"{doc_type}: {len(years)} years")
        for year in years:
            url = LISTING.format(doc_type=doc_type, year=year)
            r = get(session, url, log); polite_sleep()
            if r is None or r.status_code != 200:
                log.warning(f"{doc_type} {year}: listing failed"); continue
            found = parse_listing(r.text, doc_type)
            for x in found:
                rows.append(dict(doc_type=doc_type, year=year, listing_url=url, **x))
            log.info(f"{doc_type} {year}: {len(found)} rows, UR {sum(x['ur'] for x in found)}, "
                     f"SD {sum(x['sd'] for x in found)}")
    with open(out / "discovery.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DISCOVERY_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows


def download(session, out: Path, rows, langs, limit, log) -> dict:
    manifest = out / "manifest.csv"
    done = set()
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as f:
            done = {(r["pub_id"], r["lang"]) for r in csv.DictReader(f) if r["status"] == "downloaded"}
    counts = dict(downloaded=0, already=0, failed=0)
    todo = [(r, lang) for r in rows for lang in langs if str(r[lang.lower()]).lower() in ("true", "1")]
    if limit:
        todo = todo[:limit]
    new = not manifest.exists()
    with open(manifest, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if new:
            w.writeheader()
        for r, lang in todo:
            if (r["pub_id"], lang) in done:
                counts["already"] += 1; continue
            url = DOWNLOAD.format(pub_id=r["pub_id"], lang=lang)
            dest = out / LANGS[lang] / r["doc_type"] / str(r["year"]) / f"{r['pub_id']}-{lang}.pdf"
            row = dict(doc_type=r["doc_type"], year=r["year"], pub_id=r["pub_id"], lang=lang, title=r["title"],
                       url=url, local_path="", status="failed", http_status=0, file_size=0, sha256="",
                       served_filename="", error="")
            resp = get(session, url, log); polite_sleep()
            if resp is None:
                row["error"] = "no response"
            else:
                body = resp.content
                row.update(http_status=resp.status_code, file_size=len(body),
                           served_filename=served_filename(resp.headers.get("content-disposition")))
                if resp.status_code != 200:
                    row["error"] = f"HTTP {resp.status_code}"
                elif body[:5] != b"%PDF-" or len(body) < MIN_PDF_BYTES:
                    row["error"] = "not a PDF"
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dest.with_suffix(".pdf.part")
                    tmp.write_bytes(body)
                    tmp.replace(dest)
                    row.update(status="downloaded", sha256=hashlib.sha256(body).hexdigest(),
                               local_path=str(dest.relative_to(out)).replace("\\", "/"))
            counts["downloaded" if row["status"] == "downloaded" else "failed"] += 1
            w.writerow(row); f.flush()
            log.info(f"{r['pub_id']} {lang}: {row['status']} {row['file_size']} {row['error']}")
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=f"E:/nizam-data/acquire/sindh-language-{date.today():%Y-%m-%d}")
    ap.add_argument("--discover", action="store_true", help="read the listings only")
    ap.add_argument("--download", help="comma-separated languages to download: UR,SD (EN is the corpus's own lane)")
    ap.add_argument("--rediscover", action="store_true", help="re-read listings even if discovery.csv exists")
    ap.add_argument("--type", choices=DOC_TYPES)
    ap.add_argument("--year", type=int)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("sindh-language")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(out / "scraper.log", encoding="utf-8")):
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
        log.addHandler(h)
    types = (args.type,) if args.type else DOC_TYPES
    session = make_session()
    if args.discover or args.rediscover or not (out / "discovery.csv").exists():
        rows = discover(session, out, types, args.year, log)
    else:
        with open(out / "discovery.csv", newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f)
                    if (not args.type or r["doc_type"] == args.type) and (not args.year or int(r["year"]) == args.year)]
    log.info(f"discovery: {len(rows)} rows; UR {sum(str(r['ur']) == 'True' for r in rows)}, "
             f"SD {sum(str(r['sd']) == 'True' for r in rows)}")
    if args.download:
        langs = [x.strip().upper() for x in args.download.split(",") if x.strip()]
        bad = [x for x in langs if x not in ("UR", "SD")]
        if bad:
            ap.error(f"--download takes UR and/or SD, not {bad}")
        log.info(f"download: {download(session, out, rows, langs, args.limit, log)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
