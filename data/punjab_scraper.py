#!/usr/bin/env python3
"""
Punjab Code Scraper
====================
Downloads all laws and rules from punjabcode.punjab.gov.pk
organized into a clean folder hierarchy.

Output layout:
    punjab_code/
        Laws/
            1948/
                Essential Personnel (Registration) Ordinance, 1948.pdf
                United Nations (Security Council) Act, 1948.pdf
            1949/
                ...
        Rules/
            Service_Rules/
                Agriculture/
                    some_rule.pdf
            General_Rules/
                Board_of_Revenue/
                    some_rule.pdf
        manifest.csv
        scraper.log

Usage:
    python scraper.py                        # scrape everything
    python scraper.py --laws-only            # only scrape Laws
    python scraper.py --rules-only           # only scrape Rules
    python scraper.py --year 2025            # single year of laws
    python scraper.py --start-year 2000 --end-year 2025
"""

import argparse
import csv
import hashlib
import logging
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from scraper_paths import short_pdf_filename
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

BASE_URL   = "https://punjabcode.punjab.gov.pk"
LAWS_INDEX = BASE_URL + "/en/get_laws"
RULES_URL  = BASE_URL + "/en/get_rules"

OUTPUT_DIR   = Path("punjab_code")
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
    "Referer": BASE_URL,
}

MIN_DELAY        = 1.0    # seconds between requests
MAX_DELAY        = 2.5
MAX_RETRIES      = 4
RETRY_BACKOFF    = 3      # seconds; doubles each retry
MIN_PDF_BYTES    = 2048   # anything smaller is an error page

# Years in the chronological index (extracted from HTML)
FIRST_YEAR = 1855
LAST_YEAR  = 2026


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("punjabcode")
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
            log.warning(f"Request error attempt {attempt}/{MAX_RETRIES}: {e} — retrying in {wait}s")
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
    """Make a string safe for use as a filename or folder name."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(". ")
    return name[:200]


# ─────────────────────────────────────────────
# Manifest (CSV audit log)
# ─────────────────────────────────────────────

MANIFEST_FIELDS = [
    "type", "year_or_dept", "title", "detail_url",
    "pdf_url", "local_path", "status",
    "http_status", "file_size", "sha256", "error",
]


def load_manifest() -> dict[str, dict]:
    """Returns dict keyed by detail_url for resume support."""
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
    """
    Download PDF to dest.
    Returns (success: bool, http_status: int, size: int, error: str).
    """
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
        return False, resp.status_code, size, "Not a valid PDF (magic-byte check failed)"

    tmp.replace(dest)
    return True, resp.status_code, size, ""


# ─────────────────────────────────────────────
# Parsing — Laws
# ─────────────────────────────────────────────

def get_year_urls_from_index(session: requests.Session) -> list[tuple[int, str]]:
    """
    Scrape the chronological index page and return [(year, url), ...]
    for every year that has an actual link (years with no laws are plain text).
    """
    resp = get_with_retries(session, LAWS_INDEX)
    polite_sleep()
    if not resp or resp.status_code != 200:
        log.error("Failed to fetch laws index page")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    chron_div = soup.find("div", id="chronological")
    if not chron_div:
        log.error("Could not find #chronological tab in laws index")
        return []

    results = []
    seen = set()
    for a in chron_div.find_all("a", href=True):
        href = a["href"].strip()
        # Only year links like /en/articles_by_year/YYYY
        m = re.search(r"/en/articles_by_year/(\d{4})$", href)
        if m:
            year = int(m.group(1))
            url  = urljoin(BASE_URL, href)
            if year not in seen:
                seen.add(year)
                results.append((year, url))

    results.sort(key=lambda x: x[0], reverse=True)
    log.info(f"Found {len(results)} years with laws in the index")
    return results


def get_acts_for_year(session: requests.Session, year: int, year_url: str) -> list[tuple[str, str]]:
    """
    Returns [(title, detail_url), ...] for all acts in a given year.
    Handles the site's 100-per-page pagination if needed.
    """
    all_acts = []
    seen_urls = set()

    # The year page doesn't paginate like the alphabetical page does;
    # it shows all entries for that year in one page (confirmed from HTML).
    resp = get_with_retries(session, year_url)
    polite_sleep()
    if not resp or resp.status_code != 200:
        log.warning(f"Year {year}: failed to fetch {year_url}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Acts are in <div class="artlist"><a href="...">TITLE</a></div>
    for div in soup.find_all("div", class_="artlist"):
        a = div.find("a", href=True)
        if not a:
            continue
        href  = a["href"].strip()
        title = a.get_text(strip=True)
        if not href or not title or href in seen_urls:
            continue
        seen_urls.add(href)
        detail_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        all_acts.append((title, detail_url))

    return all_acts


def extract_pdf_url_from_detail(html: str) -> str | None:
    """
    Find the direct PDF download link on an act detail page.
    The download button links to /uploads/articles/<filename>.pdf
    """
    soup = BeautifulSoup(html, "html.parser")

    # Primary: any <a href> pointing at /uploads/articles/*.pdf
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if re.search(r"/uploads/articles/.*\.pdf", href, re.I):
            return href if href.startswith("http") else urljoin(BASE_URL, href)

    # Fallback: look inside any embedded <iframe> or <embed> for a PDF src
    for tag in soup.find_all(["iframe", "embed"], src=True):
        src = tag["src"]
        if re.search(r"\.pdf", src, re.I):
            # Extract the direct URL if it's wrapped in a viewer like ViewerJS
            m = re.search(r"(https?://[^#]+\.pdf)", src)
            if m:
                return m.group(1)
            # Relative path
            m = re.search(r"/uploads/articles/[^\"'#\s]+\.pdf", src, re.I)
            if m:
                return urljoin(BASE_URL, m.group(0))

    return None


def extract_title_from_detail(html: str, fallback: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Page uses an <h1> or <h2> for the act title
    for tag in ["h1", "h2"]:
        el = soup.find(tag)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    if soup.title and soup.title.get_text(strip=True):
        t = soup.title.get_text(strip=True)
        # Strip site name suffix if present
        t = re.sub(r"\s*[-|]\s*The Punjab Code.*$", "", t, flags=re.I).strip()
        if t:
            return t
    return fallback


# ─────────────────────────────────────────────
# Parsing — Rules
# ─────────────────────────────────────────────

def get_rule_departments(session: requests.Session) -> dict[str, list[tuple[str, str]]]:
    """
    Returns {
        'Service Rules': [(dept_name, dept_url), ...],
        'General Rules': [(dept_name, dept_url), ...]
    }
    """
    resp = get_with_retries(session, RULES_URL)
    polite_sleep()
    if not resp or resp.status_code != 200:
        log.error("Failed to fetch rules index page")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {}

    # The page has two tabs rendered on the same URL; we need to hit each tab.
    # From the HTML screenshots: Service Rules tab and General Rules tab both
    # list departments with links like /en/service_rules_by_department/DEPT_ID or
    # /en/general_rules_by_department/DEPT_ID
    # (confirmed from live debug output — no "get_" prefix)
    for tab_type, pattern in [
        ("Service Rules", r"/en/service_rules_by_department/\d+"),
        ("General Rules", r"/en/general_rules_by_department/\d+"),
    ]:
        depts = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if re.search(pattern, href):
                dept_name = a.get_text(strip=True)
                # Strip trailing count like "(27)"
                dept_name = re.sub(r"\s*\(\d+\)\s*$", "", dept_name).strip()
                url = href if href.startswith("http") else urljoin(BASE_URL, href)
                if dept_name:
                    depts.append((dept_name, url))
        result[tab_type] = depts

    return result


def get_rules_for_dept(session: requests.Session, dept_url: str) -> list[tuple[str, str]]:
    """
    Returns [(title, detail_url), ...] for all rules in a department.
    """
    resp = get_with_retries(session, dept_url)
    polite_sleep()
    if not resp or resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    seen = set()

    for div in soup.find_all("div", class_="artlist"):
        a = div.find("a", href=True)
        if not a:
            continue
        href  = a["href"].strip()
        title = a.get_text(strip=True)
        if not href or not title or href in seen:
            continue
        seen.add(href)
        detail_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        results.append((title, detail_url))

    return results


# ─────────────────────────────────────────────
# Core processing
# ─────────────────────────────────────────────

def process_entry(
    session: requests.Session,
    title: str,
    detail_url: str,
    dest_dir: Path,
    existing: dict,
    entry_type: str,
    year_or_dept: str,
) -> dict:
    """
    Fetch detail page → extract PDF URL → download → validate.
    Returns a manifest row dict.
    """
    row = {
        "type": entry_type,
        "year_or_dept": year_or_dept,
        "title": title,
        "detail_url": detail_url,
        "pdf_url": "",
        "local_path": "",
        "status": "",
        "http_status": 0,
        "file_size": 0,
        "sha256": "",
        "error": "",
    }

    # Resume: skip if already successfully downloaded
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
        row["status"] = "failed"
        row["http_status"] = resp.status_code if resp else 0
        row["error"] = "Failed to fetch detail page"
        log.error(f"  [FAIL] {title}: could not fetch detail page")
        return row

    # 2. Extract PDF URL and clean title
    pdf_url   = extract_pdf_url_from_detail(resp.text)
    clean_title = extract_title_from_detail(resp.text, fallback=title)
    row["title"] = clean_title

    if not pdf_url:
        row["status"] = "failed"
        row["error"] = "No PDF URL found on detail page"
        log.error(f"  [FAIL] {title}: no PDF link found")
        return row

    row["pdf_url"] = pdf_url

    # 3. Build destination path
    filename = short_pdf_filename(pdf_url)
    dest     = dest_dir / filename
    row["local_path"] = str(dest)

    # Skip if file already exists and is valid (even without manifest)
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
# Main scrape flows
# ─────────────────────────────────────────────

def scrape_laws(session: requests.Session, start_year: int, end_year: int, existing: dict):
    log.info("=" * 60)
    log.info(f"SCRAPING LAWS: {start_year}–{end_year}")
    log.info("=" * 60)

    year_urls = get_year_urls_from_index(session)
    # Filter to requested range
    year_urls = [(y, u) for y, u in year_urls if start_year <= y <= end_year]

    total_ok = total_skip = total_fail = 0

    for year, year_url in year_urls:
        log.info(f"── Year {year} ──")
        acts = get_acts_for_year(session, year, year_url)
        log.info(f"   {len(acts)} acts found")

        dest_dir = OUTPUT_DIR / "Laws" / str(year)

        for title, detail_url in acts:
            row = process_entry(
                session, title, detail_url, dest_dir,
                existing, entry_type="law", year_or_dept=str(year)
            )
            write_manifest_row(row)
            existing[detail_url] = row

            if row["status"] == "success":   total_ok   += 1
            elif row["status"] == "skipped": total_skip += 1
            else:                            total_fail += 1

    log.info(f"Laws done — success={total_ok} skipped={total_skip} failed={total_fail}")
    return total_ok, total_skip, total_fail


def scrape_rules(session: requests.Session, existing: dict):
    log.info("=" * 60)
    log.info("SCRAPING RULES")
    log.info("=" * 60)

    dept_map = get_rule_departments(session)
    if not dept_map:
        log.error("No rule departments found — skipping rules")
        return 0, 0, 0

    total_ok = total_skip = total_fail = 0

    for tab_name, depts in dept_map.items():
        # "Service Rules" → "Service_Rules"
        tab_folder = tab_name.replace(" ", "_")
        log.info(f"── {tab_name} ({len(depts)} departments) ──")

        for dept_name, dept_url in depts:
            log.info(f"   Department: {dept_name}")
            rules = get_rules_for_dept(session, dept_url)
            log.info(f"   {len(rules)} rules found")

            dest_dir = OUTPUT_DIR / "Rules" / tab_folder / sanitize(dept_name)

            for title, detail_url in rules:
                row = process_entry(
                    session, title, detail_url, dest_dir,
                    existing, entry_type=f"rule_{tab_folder}",
                    year_or_dept=dept_name
                )
                write_manifest_row(row)
                existing[detail_url] = row

                if row["status"] == "success":   total_ok   += 1
                elif row["status"] == "skipped": total_skip += 1
                else:                            total_fail += 1

    log.info(f"Rules done — success={total_ok} skipped={total_skip} failed={total_fail}")
    return total_ok, total_skip, total_fail


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Punjab Code Scraper")
    parser.add_argument("--laws-only",  action="store_true", help="Only scrape Laws")
    parser.add_argument("--rules-only", action="store_true", help="Only scrape Rules")
    parser.add_argument("--year",       type=int, help="Single year to scrape")
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
        ok, skip, fail = scrape_laws(session, start_year, end_year, existing)
        grand_ok += ok; grand_skip += skip; grand_fail += fail

    if do_rules:
        ok, skip, fail = scrape_rules(session, existing)
        grand_ok += ok; grand_skip += skip; grand_fail += fail

    log.info("=" * 60)
    log.info(f"ALL DONE — success={grand_ok} skipped={grand_skip} failed={grand_fail}")
    log.info(f"Output:   {OUTPUT_DIR.resolve()}")
    log.info(f"Manifest: {MANIFEST_PATH.resolve()}")
    if grand_fail:
        log.info("Re-run to retry failed items — successful downloads are skipped automatically.")


if __name__ == "__main__":
    main()
