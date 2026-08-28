#!/usr/bin/env python3
"""
Pakistan Code Scraper
======================
Downloads all federal laws from pakistancode.gov.pk, organized into
year-based folders, with integrity validation and a resumable manifest.

Output layout:
    output/
        2026/
            Virtual Assets Act, 2026.pdf
            ...
        2025/
            Pakistan Nursing and Midwifery Council Ordinance, 2025.pdf
            ...
        manifest.csv
        scraper.log

Usage:
    python scraper.py                          # scrape all years (1839-2026)
    python scraper.py --start-year 2015 --end-year 2025
    python scraper.py --year 2025               # single year
    python scraper.py --resume                  # skip already-validated files (default behavior anyway)
"""

import argparse
import csv
import hashlib
import logging
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE_URL = "https://pakistancode.gov.pk/english/"
YEAR_INDEX_TEMPLATE = BASE_URL + "LGu0xBD?year={year}&page={page}&action=inactive"

OUTPUT_DIR = Path("output")
MANIFEST_PATH = OUTPUT_DIR / "manifest.csv"
LOG_PATH = OUTPUT_DIR / "scraper.log"

# Be a polite, identifiable client. Government servers may rate-limit or
# block requests with no User-Agent / generic script signatures.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MIN_DELAY = 1.0       # seconds, minimum delay between requests
MAX_DELAY = 2.5       # seconds, maximum delay between requests
MAX_RETRIES = 4
RETRY_BACKOFF_BASE = 3  # seconds; doubles each retry
MIN_PDF_SIZE_BYTES = 2048  # reject anything smaller as probable error page

FIRST_YEAR = 1839
LAST_YEAR = 2026


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass
class ActEntry:
    year: int
    title: str
    detail_url: str
    pdf_url: str = ""
    local_path: str = ""
    status: str = ""          # success | failed | skipped
    http_status: int = 0
    file_size: int = 0
    sha256: str = ""
    error: str = ""


# --------------------------------------------------------------------------
# Logging setup
# --------------------------------------------------------------------------

def setup_logging():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("pakcode")
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


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def polite_sleep():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def get_with_retries(session: requests.Session, url: str, **kwargs) -> requests.Response | None:
    """GET a URL with retry + exponential backoff. Returns None on total failure."""
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30, **kwargs)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429, 500, 502, 503, 504):
                wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                log.warning(
                    f"HTTP {resp.status_code} on attempt {attempt}/{MAX_RETRIES} "
                    f"for {url} — retrying in {wait}s"
                )
                time.sleep(wait)
                continue
            # Other status codes (404 etc.) — no point retrying
            log.error(f"HTTP {resp.status_code} for {url} (not retrying)")
            return resp
        except requests.RequestException as e:
            last_exc = e
            wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            log.warning(
                f"Request error on attempt {attempt}/{MAX_RETRIES} for {url}: {e} "
                f"— retrying in {wait}s"
            )
            time.sleep(wait)
    log.error(f"Giving up on {url} after {MAX_RETRIES} attempts. Last error: {last_exc}")
    return None


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def extract_acts_from_year_page(html: str, year: int) -> list[tuple[str, str]]:
    """
    Returns list of (title, detail_url) tuples found in the
    '#primary-legislation' (Federal Laws) tab of a year-index page.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", id="primary-legislation")
    if container is None:
        return []

    results = []
    seen_hrefs = set()
    for a in container.select(".accordion-section-title a[href]"):
        href = a.get("href", "").strip()
        if not href or href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # Title text includes a leading "<strong>N.</strong>" — strip it.
        title = a.get_text(strip=True)
        title = re.sub(r"^\d+\.\s*", "", title).strip()
        if not title:
            continue

        detail_url = urljoin(BASE_URL, href)
        results.append((title, detail_url))

    return results


def extract_pdf_url_from_detail_page(html: str) -> str | None:
    """
    Looks for the direct PDF link inside the '#download' tab:
        <a href="https://pakistancode.gov.pk/pdffiles/administrator<hash>.pdf" ...>
    Falls back to scanning the whole page for any /pdffiles/ link, and then
    to the ViewerJS iframe src, in case markup shifts slightly.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Primary: the download tab anchor
    download_div = soup.find("div", id="download")
    if download_div:
        a = download_div.find("a", href=re.compile(r"/pdffiles/.*\.pdf", re.I))
        if a:
            return a["href"].strip()

    # Fallback 1: any anchor anywhere pointing at /pdffiles/
    a = soup.find("a", href=re.compile(r"/pdffiles/.*\.pdf", re.I))
    if a:
        return a["href"].strip()

    # Fallback 2: ViewerJS iframe, e.g. src="...ViewerJS/#../pdffiles/xxx.pdf"
    iframe = soup.find("iframe", src=re.compile(r"pdffiles/.*\.pdf", re.I))
    if iframe:
        src = iframe["src"]
        match = re.search(r"(https?://[^#]*pdffiles/[^\"'#]+\.pdf)", src)
        if match:
            return match.group(1)
        # Relative form like "../pdffiles/xxx.pdf" after the '#'
        match = re.search(r"pdffiles/[^\"'#]+\.pdf", src)
        if match:
            return urljoin(BASE_URL, match.group(0))

    return None


def extract_title_from_detail_page(html: str, fallback: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return fallback


# --------------------------------------------------------------------------
# Filesystem / validation helpers
# --------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """Remove characters illegal on Windows/Mac/Linux filesystems."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(". ")  # Windows disallows trailing dots/spaces
    return name[:200]  # keep paths sane


def is_valid_pdf(path: Path) -> bool:
    """Magic-byte + minimum-size check."""
    try:
        if path.stat().st_size < MIN_PDF_SIZE_BYTES:
            return False
        with open(path, "rb") as f:
            header = f.read(5)
        return header == b"%PDF-"
    except OSError:
        return False


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# Manifest (CSV audit log, append-as-you-go + resumability)
# --------------------------------------------------------------------------

MANIFEST_FIELDS = [
    "year", "title", "detail_url", "pdf_url", "local_path",
    "status", "http_status", "file_size", "sha256", "error",
]


def load_existing_manifest() -> dict[str, ActEntry]:
    """Key: detail_url -> ActEntry, for resuming."""
    existing = {}
    if not MANIFEST_PATH.exists():
        return existing
    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry = ActEntry(
                year=int(row["year"]) if row["year"] else 0,
                title=row["title"],
                detail_url=row["detail_url"],
                pdf_url=row.get("pdf_url", ""),
                local_path=row.get("local_path", ""),
                status=row.get("status", ""),
                http_status=int(row["http_status"]) if row.get("http_status") else 0,
                file_size=int(row["file_size"]) if row.get("file_size") else 0,
                sha256=row.get("sha256", ""),
                error=row.get("error", ""),
            )
            existing[entry.detail_url] = entry
    return existing


def append_to_manifest(entry: ActEntry):
    is_new = not MANIFEST_PATH.exists()
    with open(MANIFEST_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "year": entry.year,
            "title": entry.title,
            "detail_url": entry.detail_url,
            "pdf_url": entry.pdf_url,
            "local_path": entry.local_path,
            "status": entry.status,
            "http_status": entry.http_status,
            "file_size": entry.file_size,
            "sha256": entry.sha256,
            "error": entry.error,
        })


# --------------------------------------------------------------------------
# Core scraping logic
# --------------------------------------------------------------------------

def fetch_year_acts(session: requests.Session, year: int) -> list[tuple[str, str]]:
    """
    Paginate through a year's index pages until a page yields zero acts.
    Returns deduplicated list of (title, detail_url).
    """
    all_acts: list[tuple[str, str]] = []
    seen_urls = set()
    page = 1

    while True:
        url = YEAR_INDEX_TEMPLATE.format(year=year, page=page)
        resp = get_with_retries(session, url)
        polite_sleep()

        if resp is None or resp.status_code != 200:
            log.warning(f"Year {year} page {page}: failed to fetch ({url})")
            break

        acts = extract_acts_from_year_page(resp.text, year)
        if not acts:
            if page == 1:
                log.info(f"Year {year}: no acts found (likely none promulgated)")
            break

        new_count = 0
        for title, detail_url in acts:
            if detail_url not in seen_urls:
                seen_urls.add(detail_url)
                all_acts.append((title, detail_url))
                new_count += 1

        log.info(f"Year {year} page {page}: {len(acts)} acts found ({new_count} new)")

        # If this page added nothing new, we've looped — stop.
        if new_count == 0:
            break

        page += 1

    return all_acts


def download_pdf(session: requests.Session, pdf_url: str, dest_path: Path) -> tuple[bool, int, int, str]:
    """
    Streams the PDF to disk. Returns (success, http_status, size_bytes, error_msg).
    """
    try:
        resp = session.get(pdf_url, timeout=60, stream=True)
    except requests.RequestException as e:
        return False, 0, 0, str(e)

    if resp.status_code != 200:
        return False, resp.status_code, 0, f"HTTP {resp.status_code}"

    content_type = resp.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
        log.warning(f"Unexpected Content-Type '{content_type}' for {pdf_url} — saving anyway, will validate by magic bytes")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    size = 0
    try:
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
    except (OSError, requests.RequestException) as e:
        tmp_path.unlink(missing_ok=True)
        return False, resp.status_code, 0, str(e)

    if not is_valid_pdf(tmp_path):
        tmp_path.unlink(missing_ok=True)
        return False, resp.status_code, size, "Failed validation (not a valid PDF or too small)"

    tmp_path.replace(dest_path)
    return True, resp.status_code, size, ""


def process_act(session: requests.Session, year: int, title: str, detail_url: str,
                 existing_manifest: dict[str, ActEntry]) -> ActEntry:

    # Resume support: skip if already successfully downloaded & validated on disk
    prior = existing_manifest.get(detail_url)
    if prior and prior.status == "success" and prior.local_path:
        local_path = Path(prior.local_path)
        if local_path.exists() and is_valid_pdf(local_path):
            log.info(f"  [skip] already downloaded: {title}")
            prior.status = "skipped"
            return prior

    entry = ActEntry(year=year, title=title, detail_url=detail_url)

    # 1. Fetch detail page
    resp = get_with_retries(session, detail_url)
    polite_sleep()
    if resp is None or resp.status_code != 200:
        entry.status = "failed"
        entry.http_status = resp.status_code if resp else 0
        entry.error = "Failed to fetch detail page"
        log.error(f"  [FAIL] {title}: could not fetch detail page")
        return entry

    # 2. Extract clean title + PDF URL
    clean_title = extract_title_from_detail_page(resp.text, fallback=title)
    pdf_url = extract_pdf_url_from_detail_page(resp.text)

    if not pdf_url:
        entry.status = "failed"
        entry.error = "No PDF URL found on detail page"
        log.error(f"  [FAIL] {title}: no PDF link found")
        return entry

    entry.title = clean_title
    entry.pdf_url = pdf_url

    # 3. Build destination path
    filename = sanitize_filename(clean_title) + ".pdf"
    dest_path = OUTPUT_DIR / str(year) / filename
    entry.local_path = str(dest_path)

    # If file already exists & valid (even without manifest record), skip re-download
    if dest_path.exists() and is_valid_pdf(dest_path):
        entry.status = "skipped"
        entry.file_size = dest_path.stat().st_size
        entry.sha256 = sha256_of_file(dest_path)
        log.info(f"  [skip] file already exists and is valid: {filename}")
        return entry

    # 4. Download
    success, http_status, size, error = download_pdf(session, pdf_url, dest_path)
    polite_sleep()
    entry.http_status = http_status
    entry.file_size = size

    if not success:
        entry.status = "failed"
        entry.error = error
        log.error(f"  [FAIL] {title}: {error}")
        return entry

    entry.status = "success"
    entry.sha256 = sha256_of_file(dest_path)
    log.info(f"  [OK] {filename} ({size:,} bytes)")
    return entry


def run(start_year: int, end_year: int):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = make_session()
    existing_manifest = load_existing_manifest()

    years = range(end_year, start_year - 1, -1)  # newest first

    total_success = 0
    total_failed = 0
    total_skipped = 0

    for year in years:
        log.info(f"=== Year {year} ===")
        acts = fetch_year_acts(session, year)
        log.info(f"Year {year}: {len(acts)} total acts to process")

        for title, detail_url in acts:
            entry = process_act(session, year, title, detail_url, existing_manifest)
            append_to_manifest(entry)

            if entry.status == "success":
                total_success += 1
            elif entry.status == "skipped":
                total_skipped += 1
            else:
                total_failed += 1

    log.info("=" * 60)
    log.info(f"DONE. success={total_success} skipped={total_skipped} failed={total_failed}")
    log.info(f"Manifest: {MANIFEST_PATH.resolve()}")
    log.info(f"Output dir: {OUTPUT_DIR.resolve()}")
    if total_failed:
        log.info("Re-run the script to retry failed items — already-downloaded "
                  "files will be skipped automatically.")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scrape Pakistan Code laws by year.")
    parser.add_argument("--year", type=int, help="Scrape a single year only")
    parser.add_argument("--start-year", type=int, default=FIRST_YEAR, help="First year (inclusive)")
    parser.add_argument("--end-year", type=int, default=LAST_YEAR, help="Last year (inclusive)")
    args = parser.parse_args()

    if args.year:
        start_year = end_year = args.year
    else:
        start_year, end_year = args.start_year, args.end_year

    if start_year > end_year:
        start_year, end_year = end_year, start_year

    log.info(f"Starting scrape: years {start_year}-{end_year}")
    run(start_year, end_year)


if __name__ == "__main__":
    main()
