#!/usr/bin/env python3
"""
Balochistan Code Scraper v2
============================
Downloads all laws and rules from balochistancode.gob.pk

Key discovery: acts are stored in a hidden <input id="datafield"> as
HTML-encoded strings separated by "@", then rendered by JS pagination.
BeautifulSoup reads the raw value attribute directly — no JS needed.

opento=2 → year listing with acts (confirmed from HTML)
opento=1 → just the chronological navigation index

Output layout:
    balochistan_code/
        Laws/
            2026/
                The Balochistan Agricultural Produce Markets Act 2025.pdf
                ...
        Rules/
            2026/
                ...
        manifest.csv
        scraper.log

Usage:
    python balochistan_scraper.py                   # everything
    python balochistan_scraper.py --laws-only
    python balochistan_scraper.py --rules-only
    python balochistan_scraper.py --year 2026
    python balochistan_scraper.py --start-year 2000 --end-year 2026
"""

import argparse
import csv
import hashlib
import html
import logging
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

BASE_URL = "http://balochistancode.gob.pk"

# opento=2 is the year listing page with actual acts
# opento=1 is just the navigation index (no acts)
YEAR_URL_TEMPLATE = BASE_URL + "/Document.aspx?wise=chronological&year={year}&opento=2&dst="

FIRST_YEAR = 1855
LAST_YEAR  = 2026

OUTPUT_DIR    = Path("balochistan_code")
MANIFEST_PATH = OUTPUT_DIR / "manifest.csv"
LOG_PATH      = OUTPUT_DIR / "scraper.log"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": BASE_URL,
}

MIN_DELAY     = 1.5
MAX_DELAY     = 3.0
MAX_RETRIES   = 4
RETRY_BACKOFF = 3
MIN_PDF_BYTES = 2048


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("balochistancode")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger

log = setup_logging()


# ─────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get(BASE_URL + "/Home.aspx", timeout=15)
        time.sleep(1)
    except Exception:
        pass
    return s


def polite_sleep():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def get_with_retries(session: requests.Session, url: str, **kwargs):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30, **kwargs)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429, 500, 502, 503, 504):
                wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                log.warning(f"HTTP {resp.status_code} attempt {attempt}/{MAX_RETRIES} — retrying in {wait}s")
                time.sleep(wait)
                continue
            log.error(f"HTTP {resp.status_code} for {url}")
            return resp
        except requests.RequestException as e:
            wait = RETRY_BACKOFF * (2 ** (attempt - 1))
            log.warning(f"Error attempt {attempt}/{MAX_RETRIES}: {e} — retrying in {wait}s")
            time.sleep(wait)
    log.error(f"Giving up on {url} after {MAX_RETRIES} attempts")
    return None


# ─────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────

def is_valid_pdf(path: Path) -> bool:
    try:
        if path.stat().st_size < MIN_PDF_BYTES:
            return False
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(". ")
    return name[:200]


# ─────────────────────────────────────────────
# Manifest
# ─────────────────────────────────────────────

MANIFEST_FIELDS = [
    "type", "year", "title", "detail_url",
    "pdf_url", "local_path", "status",
    "http_status", "file_size", "sha256", "error",
]


def load_manifest() -> dict:
    existing = {}
    if not MANIFEST_PATH.exists():
        return existing
    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            existing[row["detail_url"]] = row
    return existing


def write_manifest_row(row: dict):
    is_new = not MANIFEST_PATH.exists()
    with open(MANIFEST_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if is_new:
            w.writeheader()
        w.writerow(row)


# ─────────────────────────────────────────────
# PDF download
# ─────────────────────────────────────────────

def download_pdf(session: requests.Session, pdf_url: str, dest: Path):
    try:
        resp = session.get(pdf_url, timeout=60, stream=True)
    except requests.RequestException as e:
        return False, 0, 0, str(e)

    if resp.status_code != 200:
        return False, resp.status_code, 0, f"HTTP {resp.status_code}"

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    size = 0
    try:
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
    except (OSError, requests.RequestException) as e:
        tmp.unlink(missing_ok=True)
        return False, resp.status_code, 0, str(e)

    if not is_valid_pdf(tmp):
        tmp.unlink(missing_ok=True)
        return False, resp.status_code, size, "Not a valid PDF"

    tmp.replace(dest)
    return True, resp.status_code, size, ""


# ─────────────────────────────────────────────
# Parsing — year listing page
# ─────────────────────────────────────────────

def get_acts_for_year(session: requests.Session, year: int) -> list[tuple[str, str]]:
    """
    The acts are stored in a hidden <input id="datafield"> as an
    HTML-encoded string, with entries separated by "@".

    Each entry is an HTML fragment like:
      <div class="doclist">
        <b><a href='Document.aspx?wise=opendoc&docid=2113&docc=1965'>
          Title
        </a></b>
        <br><small>metadata</small>
      </div>

    We decode the value, split on "@", parse each chunk, extract
    the <a> tag href and text.
    """
    url  = YEAR_URL_TEMPLATE.format(year=year)
    resp = get_with_retries(session, url)
    polite_sleep()

    if not resp or resp.status_code != 200:
        log.warning(f"Year {year}: failed to fetch {url}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the hidden input holding all the act data
    datafield = soup.find("input", {"id": "datafield"})
    if not datafield:
        log.info(f"Year {year}: no datafield input found (year likely has no acts)")
        return []

    raw_value = datafield.get("value", "").strip()
    if not raw_value:
        log.info(f"Year {year}: datafield is empty")
        return []

    # Split on "@" separator — each chunk is one act's HTML fragment
    chunks = [c.strip() for c in raw_value.split("@") if c.strip()]

    results = []
    seen    = set()

    for chunk in chunks:
        # Each chunk is already HTML (the value attribute was HTML-encoded,
        # but BeautifulSoup already decoded it for us via .get("value"))
        chunk_soup = BeautifulSoup(chunk, "html.parser")
        a = chunk_soup.find("a", href=True)
        if not a:
            continue
        href  = a["href"].strip()
        title = a.get_text(strip=True)
        # Strip trailing year repetition like ", 2026" that the site adds
        title = re.sub(r"\s*,\s*\d{4}\s*$", "", title).strip()
        if not title or href in seen:
            continue
        seen.add(href)
        detail_url = href if href.startswith("http") else urljoin(BASE_URL + "/", href)
        results.append((title, detail_url))

    return results


# ─────────────────────────────────────────────
# Parsing — detail page
# ─────────────────────────────────────────────

def extract_pdf_info(html_text: str) -> tuple[str | None, str]:
    """
    Returns (pdf_url, clean_title).
    PDF link: <a href="http://balochistancode.gob.pk/lawdir/<guid>.pdf" download="Title.pdf">
    Title: from the download attribute, or from #banner_pagehead h2.
    """
    soup = BeautifulSoup(html_text, "html.parser")

    pdf_url     = None
    clean_title = ""

    # Primary: <a href="/lawdir/...pdf">
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if re.search(r"/lawdir/.*\.pdf", href, re.I):
            pdf_url = href if href.startswith("http") else urljoin(BASE_URL, href)
            dl = a.get("download", "")
            if dl:
                clean_title = re.sub(r"\.pdf$", "", dl, flags=re.I).strip()
            break

    # Fallback: iframe pdfviewer src → reconstruct lawdir URL
    if not pdf_url:
        iframe = soup.find("iframe", src=re.compile(r"pdfviewer\.aspx", re.I))
        if iframe:
            m = re.search(r"pdffile=([^&\"']+\.pdf)", iframe["src"], re.I)
            if m:
                pdf_url = BASE_URL + "/lawdir/" + m.group(1)

    # Title from #banner_pagehead h2 (strip the year <span>)
    if not clean_title:
        head = soup.find(id="banner_pagehead")
        if head:
            for span in head.find_all("span"):
                span.decompose()
            clean_title = head.get_text(strip=True)
            # Remove trailing ", YYYY" artifact
            clean_title = re.sub(r"\s*,\s*\d{4}\s*$", "", clean_title).strip()

    return pdf_url, clean_title


# ─────────────────────────────────────────────
# Core processing
# ─────────────────────────────────────────────

def process_entry(
    session: requests.Session,
    title: str,
    detail_url: str,
    dest_dir: Path,
    existing: dict,
    doc_type: str,
    year: int,
) -> dict:
    row = {
        "type": doc_type, "year": str(year),
        "title": title, "detail_url": detail_url,
        "pdf_url": "", "local_path": "", "status": "",
        "http_status": 0, "file_size": 0, "sha256": "", "error": "",
    }

    # Resume support
    prior = existing.get(detail_url)
    if prior and prior.get("status") == "success" and prior.get("local_path"):
        path = Path(prior["local_path"])
        if path.exists() and is_valid_pdf(path):
            log.info(f"  [skip] {title}")
            row.update({
                "status": "skipped",
                "local_path": prior["local_path"],
                "pdf_url": prior.get("pdf_url", ""),
                "file_size": prior.get("file_size", 0),
                "sha256": prior.get("sha256", ""),
            })
            return row

    # 1. Fetch detail page
    resp = get_with_retries(session, detail_url)
    polite_sleep()
    if not resp or resp.status_code != 200:
        row["status"]      = "failed"
        row["http_status"] = resp.status_code if resp else 0
        row["error"]       = "Failed to fetch detail page"
        log.error(f"  [FAIL] {title}: detail page fetch failed")
        return row

    # 2. Extract PDF URL + clean title
    pdf_url, clean_title = extract_pdf_info(resp.text)
    if clean_title:
        row["title"] = clean_title

    if not pdf_url:
        row["status"] = "failed"
        row["error"]  = "No PDF URL found"
        log.error(f"  [FAIL] {title}: no PDF link found")
        return row

    row["pdf_url"] = pdf_url

    # 3. Build destination
    filename = sanitize(row["title"]) + ".pdf"
    dest     = dest_dir / filename
    row["local_path"] = str(dest)

    if dest.exists() and is_valid_pdf(dest):
        row["status"]    = "skipped"
        row["file_size"] = dest.stat().st_size
        row["sha256"]    = sha256_of(dest)
        log.info(f"  [skip] file exists: {filename}")
        return row

    # 4. Download
    success, http_status, size, error = download_pdf(session, pdf_url, dest)
    polite_sleep()
    row["http_status"] = http_status
    row["file_size"]   = size

    if not success:
        row["status"] = "failed"
        row["error"]  = error
        log.error(f"  [FAIL] {title}: {error}")
        return row

    row["status"] = "success"
    row["sha256"] = sha256_of(dest)
    log.info(f"  [OK] {filename} ({size:,} bytes)")
    return row


# ─────────────────────────────────────────────
# Main scrape flow
# ─────────────────────────────────────────────

def scrape(
    session: requests.Session,
    start_year: int,
    end_year: int,
    doc_type: str,       # "law" or "rule" — both use opento=2, same URL pattern
    folder_name: str,    # "Laws" or "Rules"
    existing: dict,
):
    log.info("=" * 60)
    log.info(f"SCRAPING {folder_name.upper()}: {start_year}–{end_year}")
    log.info("=" * 60)

    total_ok = total_skip = total_fail = 0

    for year in range(end_year, start_year - 1, -1):
        log.info(f"── Year {year} ──")
        acts = get_acts_for_year(session, year)
        log.info(f"   {len(acts)} entries found")

        if not acts:
            continue

        dest_dir = OUTPUT_DIR / folder_name / str(year)

        for title, detail_url in acts:
            row = process_entry(
                session, title, detail_url, dest_dir,
                existing, doc_type=doc_type, year=year
            )
            write_manifest_row(row)
            existing[detail_url] = row

            if row["status"] == "success":   total_ok   += 1
            elif row["status"] == "skipped": total_skip += 1
            else:                            total_fail += 1

    log.info(f"{folder_name} done — success={total_ok} skipped={total_skip} failed={total_fail}")
    return total_ok, total_skip, total_fail


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Balochistan Code Scraper v2")
    parser.add_argument("--laws-only",  action="store_true")
    parser.add_argument("--rules-only", action="store_true")
    parser.add_argument("--year",       type=int)
    parser.add_argument("--start-year", type=int, default=FIRST_YEAR)
    parser.add_argument("--end-year",   type=int, default=LAST_YEAR)
    args = parser.parse_args()

    if args.year:
        start_year = end_year = args.year
    else:
        start_year = args.start_year
        end_year   = args.end_year
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session  = make_session()
    existing = load_manifest()

    do_laws  = not args.rules_only
    do_rules = not args.laws_only

    grand_ok = grand_skip = grand_fail = 0

    if do_laws:
        ok, skip, fail = scrape(
            session, start_year, end_year,
            doc_type="law", folder_name="Laws", existing=existing
        )
        grand_ok += ok; grand_skip += skip; grand_fail += fail

    if do_rules:
        ok, skip, fail = scrape(
            session, start_year, end_year,
            doc_type="rule", folder_name="Rules", existing=existing
        )
        grand_ok += ok; grand_skip += skip; grand_fail += fail

    log.info("=" * 60)
    log.info(f"ALL DONE — success={grand_ok} skipped={grand_skip} failed={grand_fail}")
    log.info(f"Output:   {OUTPUT_DIR.resolve()}")
    log.info(f"Manifest: {MANIFEST_PATH.resolve()}")
    if grand_fail:
        log.info("Re-run to retry failed items.")


if __name__ == "__main__":
    main()