#!/usr/bin/env python3
"""
Sindh Code Scraper
===================
Downloads Acts, Ordinances, and Rules from sindhlaws.gov.pk

Structure confirmed from real HTML:
  - Three doc types, each with its own chronological index:
      sindhlaws.gov.pk/Chrono.aspx?pg=ACT
      sindhlaws.gov.pk/Chrono.aspx?pg=ORDINANCE
      sindhlaws.gov.pk/Chrono.aspx?pg=RULE

  - Year index page shows year buttons (e.g. 2025, 2024, ...)
    Each button links to:
      SindhGazetteDetail.aspx?X=ACT&Year=2025

  - Year listing page contains a table inside <div id="ACT"> (or RULE/ORDINANCE)
    Table columns: # | TITLE | ENGLISH | URDU | SINDHI | DATE
    English link (red)  → real PDF  e.g. setup/publications_SindhCode/PUB-15-000066.pdf
    Urdu/Sindhi (grey)  → directory only (missing PDF)

  - Missing PDFs: href ends with "/" (directory, not file) → logged as "missing"

Output layout:
    sindh_code/
        Acts/
            2025/
                Some Act Title.pdf
            2024/
                ...
        Ordinances/
            2025/
                ...
        Rules/
            2005/
                Land Utilization Department Rules.pdf
        manifest.csv      ← all entries including missing ones
        missing.csv       ← just the missing PDFs for easy review
        scraper.log

Usage:
    python sindh_scraper.py                         # everything
    python sindh_scraper.py --acts-only
    python sindh_scraper.py --ordinances-only
    python sindh_scraper.py --rules-only
    python sindh_scraper.py --year 2025             # single year, all types
    python sindh_scraper.py --type ACT --year 2025  # specific type + year
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

BASE_URL = "https://sindhlaws.gov.pk"

# Chronological index pages per doc type
CHRON_URLS = {
    "ACT":       BASE_URL + "/Chrono.aspx?pg=ACT",
    "ORDINANCE": BASE_URL + "/Chrono.aspx?pg=ORDINANCE",
    "RULE":      BASE_URL + "/Chrono.aspx?pg=RULE",
}

# Year listing URL template
YEAR_LISTING_TEMPLATE = BASE_URL + "/SindhGazetteDetail.aspx?X={doc_type}&Year={year}"

# Folder names per doc type
FOLDER_NAMES = {
    "ACT":       "Acts",
    "ORDINANCE": "Ordinances",
    "RULE":      "Rules",
}

OUTPUT_DIR    = Path("sindh_code")
MANIFEST_PATH = OUTPUT_DIR / "manifest.csv"
MISSING_PATH  = OUTPUT_DIR / "missing.csv"
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
    logger = logging.getLogger("sindhcode")
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
        s.get(BASE_URL + "/Index.aspx", timeout=15)
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


def is_real_pdf_link(href: str) -> bool:
    """
    Grey/missing links point to a directory: 'setup/publications_SindhCode/'
    Real PDF links end with '.pdf'.
    """
    return bool(href) and href.lower().endswith(".pdf")


# ─────────────────────────────────────────────
# Manifest & missing log
# ─────────────────────────────────────────────

MANIFEST_FIELDS = [
    "doc_type", "year", "title", "pdf_url",
    "local_path", "status",
    "http_status", "file_size", "sha256", "error",
]

MISSING_FIELDS = [
    "doc_type", "year", "title", "listing_url",
    "urdu_available", "sindhi_available",
]


def load_manifest() -> dict:
    existing = {}
    if not MANIFEST_PATH.exists():
        return existing
    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = f"{row['doc_type']}|{row['year']}|{row['title']}"
            existing[key] = row
    return existing


def write_manifest_row(row: dict):
    is_new = not MANIFEST_PATH.exists()
    with open(MANIFEST_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if is_new:
            w.writeheader()
        w.writerow(row)


def write_missing_row(row: dict):
    is_new = not MISSING_PATH.exists()
    with open(MISSING_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MISSING_FIELDS)
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
# Parsing — chronological year index
# ─────────────────────────────────────────────

def get_years_for_type(session: requests.Session, doc_type: str) -> list[int]:
    """
    Scrape Chrono.aspx?pg=ACT (or ORDINANCE/RULE) and return list of years
    that have data (shown as clickable year buttons).

    Year buttons on this site are rendered as <a> or <button> elements
    with the year as text. From Image 1 they appear as styled buttons.
    """
    url  = CHRON_URLS[doc_type]
    resp = get_with_retries(session, url)
    polite_sleep()
    if not resp or resp.status_code != 200:
        log.error(f"Failed to fetch {doc_type} chronological index")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    years = set()

    # Year buttons/links — text is a 4-digit year
    # They may be <a href="...Year=2025"> or onclick buttons
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if re.match(r"^\d{4}$", text):
            years.add(int(text))

    # Also check for button elements with year text
    for btn in soup.find_all(["button", "input"]):
        text = btn.get_text(strip=True) or btn.get("value", "")
        if re.match(r"^\d{4}$", text.strip()):
            years.add(int(text.strip()))

    # Also check onclick attributes for year patterns
    for el in soup.find_all(onclick=True):
        m = re.search(r"Year=(\d{4})", el.get("onclick", ""))
        if m:
            years.add(int(m.group(1)))

    # Last resort: scan all text nodes for 4-digit years in the content area
    if not years:
        content = soup.get_text()
        for m in re.finditer(r"\b(1[89]\d{2}|20[012]\d)\b", content):
            years.add(int(m.group(1)))

    result = sorted(years, reverse=True)
    log.info(f"{doc_type}: found {len(result)} years: {result[:10]}{'...' if len(result) > 10 else ''}")
    return result


# ─────────────────────────────────────────────
# Parsing — year listing page
# ─────────────────────────────────────────────

def get_entries_for_year(
    session: requests.Session,
    doc_type: str,
    year: int,
) -> list[dict]:
    """
    Returns list of entry dicts:
    {
        title: str,
        english_href: str | None,   # None if PDF missing
        urdu_available: bool,
        sindhi_available: bool,
        date: str,
    }

    The table lives inside <div id="ACT"> (or RULE/ORDINANCE).
    Even though JS sets display:none on others, all divs ARE in the HTML.
    We parse the correct one directly.
    """
    url  = YEAR_LISTING_TEMPLATE.format(doc_type=doc_type, year=year)
    resp = get_with_retries(session, url)
    polite_sleep()
    if not resp or resp.status_code != 200:
        log.warning(f"{doc_type} {year}: failed to fetch {url}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the correct div by id (ACT, ORDINANCE, or RULE)
    container = soup.find("div", id=doc_type)
    if not container:
        # Fallback: try ContentPlaceHolder div
        container = soup.find("div", id=f"ContentPlaceHolder1_DV{doc_type}")
    if not container:
        log.info(f"{doc_type} {year}: no content div found (year likely empty)")
        return []

    entries = []
    table = container.find("table")
    if not table:
        log.info(f"{doc_type} {year}: no table found")
        return []

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue  # skip header row (th) or malformed rows

        title = cells[1].get_text(strip=True)
        if not title:
            continue

        # English PDF link
        eng_a    = cells[2].find("a", href=True)
        eng_href = eng_a["href"].strip() if eng_a else None

        # Urdu/Sindhi availability (grey links point to directory = unavailable)
        urd_a  = cells[3].find("a", href=True)
        sin_a  = cells[4].find("a", href=True)
        urdu_available   = is_real_pdf_link(urd_a["href"]) if urd_a else False
        sindhi_available = is_real_pdf_link(sin_a["href"]) if sin_a else False

        date = cells[5].get_text(strip=True) if len(cells) > 5 else ""

        entries.append({
            "title":            title,
            "english_href":     eng_href if is_real_pdf_link(eng_href) else None,
            "urdu_available":   urdu_available,
            "sindhi_available": sindhi_available,
            "date":             date,
        })

    return entries


# ─────────────────────────────────────────────
# Core processing
# ─────────────────────────────────────────────

def process_entry(
    session: requests.Session,
    entry: dict,
    doc_type: str,
    year: int,
    dest_dir: Path,
    listing_url: str,
    existing: dict,
) -> dict:
    title      = entry["title"]
    eng_href   = entry["english_href"]
    manifest_key = f"{doc_type}|{year}|{title}"

    row = {
        "doc_type":    doc_type,
        "year":        str(year),
        "title":       title,
        "pdf_url":     "",
        "local_path":  "",
        "status":      "",
        "http_status": 0,
        "file_size":   0,
        "sha256":      "",
        "error":       "",
    }

    # Handle missing English PDF
    if not eng_href:
        row["status"] = "missing"
        row["error"]  = "No English PDF available on source site"
        log.warning(f"  [missing] {title}")
        write_missing_row({
            "doc_type":         doc_type,
            "year":             str(year),
            "title":            title,
            "listing_url":      listing_url,
            "urdu_available":   str(entry["urdu_available"]),
            "sindhi_available": str(entry["sindhi_available"]),
        })
        return row

    # Build absolute PDF URL
    pdf_url = eng_href if eng_href.startswith("http") else urljoin(BASE_URL + "/", eng_href)
    row["pdf_url"] = pdf_url

    # Resume support
    prior = existing.get(manifest_key)
    if prior and prior.get("status") == "success" and prior.get("local_path"):
        path = Path(prior["local_path"])
        if path.exists() and is_valid_pdf(path):
            log.info(f"  [skip] {title}")
            row.update({
                "status":     "skipped",
                "local_path": prior["local_path"],
                "pdf_url":    prior.get("pdf_url", pdf_url),
                "file_size":  prior.get("file_size", 0),
                "sha256":     prior.get("sha256", ""),
            })
            return row

    # Build destination filename from PDF filename (descriptive, e.g. PUB-16-000113.pdf)
    pdf_filename = pdf_url.split("/")[-1]
    # Use title as primary name, fall back to PDF filename
    filename = short_pdf_filename(pdf_url)
    dest     = dest_dir / filename
    row["local_path"] = str(dest)

    # Skip if already on disk
    if dest.exists() and is_valid_pdf(dest):
        row["status"]    = "skipped"
        row["file_size"] = dest.stat().st_size
        row["sha256"]    = sha256_of(dest)
        log.info(f"  [skip] file exists: {filename}")
        return row

    # Download
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

def scrape_type(
    session: requests.Session,
    doc_type: str,
    year_filter: int | None,
    existing: dict,
):
    folder = FOLDER_NAMES[doc_type]
    log.info("=" * 60)
    log.info(f"SCRAPING {folder.upper()}")
    log.info("=" * 60)

    years = get_years_for_type(session, doc_type)
    if year_filter:
        years = [y for y in years if y == year_filter]
        if not years:
            log.warning(f"{doc_type}: year {year_filter} not found in index")
            return 0, 0, 0, 0

    total_ok = total_skip = total_fail = total_missing = 0

    for year in years:
        log.info(f"── {doc_type} Year {year} ──")
        listing_url = YEAR_LISTING_TEMPLATE.format(doc_type=doc_type, year=year)
        entries = get_entries_for_year(session, doc_type, year)
        log.info(f"   {len(entries)} entries found")

        if not entries:
            continue

        dest_dir = OUTPUT_DIR / folder / str(year)

        for entry in entries:
            row = process_entry(
                session, entry, doc_type, year,
                dest_dir, listing_url, existing
            )
            write_manifest_row(row)
            key = f"{doc_type}|{year}|{entry['title']}"
            existing[key] = row

            if row["status"] == "success":   total_ok      += 1
            elif row["status"] == "skipped": total_skip    += 1
            elif row["status"] == "missing": total_missing += 1
            else:                            total_fail    += 1

    log.info(
        f"{folder} done — "
        f"success={total_ok} skipped={total_skip} "
        f"failed={total_fail} missing={total_missing}"
    )
    return total_ok, total_skip, total_fail, total_missing


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sindh Code Scraper")
    parser.add_argument("--acts-only",        action="store_true")
    parser.add_argument("--ordinances-only",  action="store_true")
    parser.add_argument("--rules-only",       action="store_true")
    parser.add_argument("--year",             type=int, help="Single year to scrape")
    parser.add_argument("--type",             choices=["ACT", "ORDINANCE", "RULE"],
                        help="Specific doc type to scrape")
    args = parser.parse_args()

    # Determine which types to scrape
    if args.type:
        types = [args.type]
    elif args.acts_only:
        types = ["ACT"]
    elif args.ordinances_only:
        types = ["ORDINANCE"]
    elif args.rules_only:
        types = ["RULE"]
    else:
        types = ["ACT", "ORDINANCE", "RULE"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session  = make_session()
    existing = load_manifest()

    grand_ok = grand_skip = grand_fail = grand_missing = 0

    for doc_type in types:
        ok, skip, fail, missing = scrape_type(
            session, doc_type, year_filter=args.year, existing=existing
        )
        grand_ok      += ok
        grand_skip    += skip
        grand_fail    += fail
        grand_missing += missing

    log.info("=" * 60)
    log.info(
        f"ALL DONE — "
        f"success={grand_ok} skipped={grand_skip} "
        f"failed={grand_fail} missing={grand_missing}"
    )
    log.info(f"Output:   {OUTPUT_DIR.resolve()}")
    log.info(f"Manifest: {MANIFEST_PATH.resolve()}")
    if grand_missing:
        log.info(f"Missing:  {MISSING_PATH.resolve()} ({grand_missing} entries with no English PDF)")
    if grand_fail:
        log.info("Re-run to retry failed items — successful downloads are skipped automatically.")


if __name__ == "__main__":
    main()
