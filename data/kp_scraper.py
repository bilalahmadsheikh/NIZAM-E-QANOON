#!/usr/bin/env python3
"""
KP Code Scraper
================
Downloads all laws from kpcode.kp.gov.pk organized by year.

Structure confirmed from real HTML:
  - Chronological index: /homepage/chronological
    → year links like /homepage/advance_search_process_index/1875528
  - Year listing page: /homepage/advance_search_process_index/{id}
    → acts in <div class="artlist"><a href="/homepage/lawDetails/{id}">Title</a></div>
    → year visible in <div class="artdets">...|Year:2025</div>
  - Detail page: /homepage/lawDetails/{id}
    → PDF at /uploads/FILENAME.pdf (Download button)
  - Rules section: /homepage/rules (separate listing)

Output layout:
    kp_code/
        Laws/
            2025/
                The Khyber Pakhtunkhwa Climate Action Board Act 2025.pdf
                ...
            2024/
                ...
        Rules/
            some_rule.pdf
            ...
        manifest.csv
        scraper.log

Usage:
    python kp_scraper.py                    # everything
    python kp_scraper.py --laws-only
    python kp_scraper.py --rules-only
    python kp_scraper.py --year 2025        # single year of laws
"""

import argparse
import csv
import hashlib
import logging
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from scraper_paths import short_pdf_filename
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

BASE_URL       = "https://kpcode.kp.gov.pk"
CHRON_INDEX    = BASE_URL + "/homepage/chronological"
RULES_INDEX    = BASE_URL + "/homepage/rules"

OUTPUT_DIR    = Path("kp_code")
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
    "Connection": "keep-alive",
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
    logger = logging.getLogger("kpcode")
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
        s.get(BASE_URL, timeout=15)
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
# Parsing — chronological index
# ─────────────────────────────────────────────

def get_year_listing_urls(session: requests.Session) -> list[tuple[int, str]]:
    """
    Scrape /homepage/chronological and return [(year, listing_url), ...]
    Year links look like:
      <a href="https://kpcode.kp.gov.pk/homepage/advance_search_process_index/1875528">2025</a>
    """
    resp = get_with_retries(session, CHRON_INDEX)
    polite_sleep()
    if not resp or resp.status_code != 200:
        log.error("Failed to fetch chronological index")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    seen_years = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True)
        # Real pattern confirmed from debug output:
        # href=https://kpcode.kp.gov.pk/homepage/search_by_year/164  text='1860'
        if "search_by_year" in href and re.match(r"^\d{4}$", text):
            year = int(text)
            if year not in seen_years:
                seen_years.add(year)
                url = href if href.startswith("http") else urljoin(BASE_URL, href)
                results.append((year, url))

    results.sort(key=lambda x: x[0], reverse=True)
    log.info(f"Found {len(results)} year links in chronological index")
    return results


# ─────────────────────────────────────────────
# Parsing — year listing page
# ─────────────────────────────────────────────

def get_acts_from_listing(session: requests.Session, listing_url: str, year: int) -> list[tuple[str, str]]:
    """
    Scrape a year listing page and return [(title, detail_url), ...]

    Acts are in:
      <div class="artlist">
        <a href="https://kpcode.kp.gov.pk/homepage/lawDetails/1617">Title</a>
      </div>
    """
    resp = get_with_retries(session, listing_url)
    polite_sleep()
    if not resp or resp.status_code != 200:
        log.warning(f"Year {year}: failed to fetch {listing_url}")
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
        if not title or href in seen:
            continue
        seen.add(href)
        detail_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        results.append((title, detail_url))

    return results


# ─────────────────────────────────────────────
# Parsing — detail page
# ─────────────────────────────────────────────

def extract_pdf_info(html_text: str, fallback_title: str) -> tuple[str | None, str]:
    """
    Returns (pdf_url, clean_title).

    PDF link confirmed as:
      <a href="https://kpcode.kp.gov.pk/uploads/THE_KHYBER_PAKHTUNKHWA_...pdf">Download</a>
    or the download button href.

    Title from the <h2> or <h3> heading on the page.
    """
    soup = BeautifulSoup(html_text, "html.parser")

    pdf_url     = None
    clean_title = ""

    # Primary: any <a href> pointing at /uploads/*.pdf
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if re.search(r"/uploads/.*\.pdf", href, re.I):
            pdf_url = href if href.startswith("http") else urljoin(BASE_URL, href)
            break

    # Fallback: look for iframe or embed src with .pdf
    if not pdf_url:
        for tag in soup.find_all(["iframe", "embed", "object"], src=True):
            src = tag["src"]
            if re.search(r"\.pdf", src, re.I):
                m = re.search(r"(https?://[^\s\"']+\.pdf)", src)
                if m:
                    pdf_url = m.group(1)
                    break
                m = re.search(r"(/uploads/[^\s\"']+\.pdf)", src, re.I)
                if m:
                    pdf_url = urljoin(BASE_URL, m.group(1))
                    break

    # Title: from <h2> or <h3> in the content area (not the header)
    content = soup.find(id="content")
    if content:
        for tag in ["h2", "h3", "h4"]:
            el = content.find(tag)
            if el and el.get_text(strip=True):
                clean_title = el.get_text(strip=True)
                break

    # Fallback title from <title> tag
    if not clean_title:
        if soup.title:
            t = soup.title.get_text(strip=True)
            if t and t.lower() not in ("kp code", "laws", "details"):
                clean_title = t

    if not clean_title:
        clean_title = fallback_title

    return pdf_url, clean_title


# ─────────────────────────────────────────────
# Rules parsing
# ─────────────────────────────────────────────

def get_rules(session: requests.Session) -> list[tuple[str, str]]:
    """
    Scrape /homepage/rules and return [(title, detail_url), ...]
    Same artlist structure as laws.
    """
    resp = get_with_retries(session, RULES_INDEX)
    polite_sleep()
    if not resp or resp.status_code != 200:
        log.error("Failed to fetch rules index")
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
        if not title or href in seen:
            continue
        seen.add(href)
        detail_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        results.append((title, detail_url))

    # Check for pagination — "Total Records Found: N" tells us if there are more pages
    total_el = soup.find("span", class_="total_row")
    if total_el:
        try:
            total = int(total_el.get_text(strip=True))
            if total > len(results):
                log.warning(
                    f"Rules: page shows {len(results)} but total is {total}. "
                    f"Pagination may be needed — check manually."
                )
        except ValueError:
            pass

    log.info(f"Rules: found {len(results)} entries")
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
    doc_type: str,
    year: int | str,
) -> dict:
    row = {
        "type": doc_type,
        "year": str(year),
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
    pdf_url, clean_title = extract_pdf_info(resp.text, fallback_title=title)
    if clean_title:
        row["title"] = clean_title

    if not pdf_url:
        row["status"] = "failed"
        row["error"]  = "No PDF URL found"
        log.error(f"  [FAIL] {title}: no PDF link found")
        return row

    row["pdf_url"] = pdf_url

    # 3. Build destination
    filename = short_pdf_filename(pdf_url)
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
# Main scrape flows
# ─────────────────────────────────────────────

def scrape_laws(
    session: requests.Session,
    year_filter: int | None,
    existing: dict,
):
    log.info("=" * 60)
    log.info("SCRAPING LAWS")
    log.info("=" * 60)

    year_urls = get_year_listing_urls(session)
    if year_filter:
        year_urls = [(y, u) for y, u in year_urls if y == year_filter]
        if not year_urls:
            log.warning(f"Year {year_filter} not found in chronological index")
            return 0, 0, 0

    total_ok = total_skip = total_fail = 0

    for year, listing_url in year_urls:
        log.info(f"── Year {year} ──")
        acts = get_acts_from_listing(session, listing_url, year)
        log.info(f"   {len(acts)} acts found")

        if not acts:
            continue

        dest_dir = OUTPUT_DIR / "Laws" / str(year)

        for title, detail_url in acts:
            row = process_entry(
                session, title, detail_url, dest_dir,
                existing, doc_type="law", year=year
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

    rules = get_rules(session)
    if not rules:
        log.warning("No rules found")
        return 0, 0, 0

    dest_dir = OUTPUT_DIR / "Rules"
    total_ok = total_skip = total_fail = 0

    for title, detail_url in rules:
        row = process_entry(
            session, title, detail_url, dest_dir,
            existing, doc_type="rule", year="N/A"
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
    parser = argparse.ArgumentParser(description="KP Code Scraper")
    parser.add_argument("--laws-only",  action="store_true")
    parser.add_argument("--rules-only", action="store_true")
    parser.add_argument("--year",       type=int, help="Scrape a single year of laws")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session  = make_session()
    existing = load_manifest()

    do_laws  = not args.rules_only
    do_rules = not args.laws_only

    grand_ok = grand_skip = grand_fail = 0

    if do_laws:
        ok, skip, fail = scrape_laws(session, year_filter=args.year, existing=existing)
        grand_ok += ok; grand_skip += skip; grand_fail += fail

    if do_rules:
        ok, skip, fail = scrape_rules(session, existing=existing)
        grand_ok += ok; grand_skip += skip; grand_fail += fail

    log.info("=" * 60)
    log.info(f"ALL DONE — success={grand_ok} skipped={grand_skip} failed={grand_fail}")
    log.info(f"Output:   {OUTPUT_DIR.resolve()}")
    log.info(f"Manifest: {MANIFEST_PATH.resolve()}")
    if grand_fail:
        log.info("Re-run to retry failed items — successful downloads are skipped automatically.")


if __name__ == "__main__":
    main()
