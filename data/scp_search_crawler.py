"""The Supreme Court's judgment search (scp.gov.pk/JudgmentsSearch), driven in a visible Chrome window with the owner
present (owner ruling, D-148): the owner answers any captcha challenge in the window; this script fills the form, reads
the results and saves them. It never solves, bypasses or replays a captcha token: each search is the form's own
submit in the owner's window, and paging is the grid's own postback.

    python data/scp_search_crawler.py explore [--year 2025]   one search, the page saved, its structure printed
    python data/scp_search_crawler.py crawl [--years 2026-1980] [--delay 4]
    python data/scp_search_crawler.py queue                    files not held -> the site archive's listing.jsonl

crawl: one search per case year (the form's only broad filter), 100 rows a page, every page saved
(search/y<year>-p<n>.html) and every row appended to search/rows.jsonl with its judgment and upload dates (these also
date judgments the archive holds undated). A year whose pages are all saved is marked done and skipped on a rerun.
queue: rows whose file neither the September archive (scp_judgments.zip) nor the site archive holds are appended to
scp_site_judgments/listing.jsonl, so data/scp_judgments_scraper.py (in WSL) downloads them and they land as D-144's did.
Robots.txt says ai-train=no: this text never enters a training set (D-144).
Windows Python with Playwright and installed Chrome (a fresh profile under E:/nizam-data/acquire/scp/browser-profile,
never the owner's own). Output: E:/nizam-data/acquire/scp/search/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as htmlmod
import json
import re
import sys
import time
import urllib.parse
import zipfile
from pathlib import Path

URL = "https://www.scp.gov.pk/JudgmentsSearch"
BASE = "https://www.scp.gov.pk"
ACQ = Path("E:/nizam-data/acquire/scp")
OUT = ACQ / "search"
PROFILE = ACQ / "browser-profile"
SEPT = Path("E:/nizam-data/scp_judgments.zip")
SITE = ACQ / "scp_site_judgments"
WAIT_FOR_OWNER = 15 * 60
FIELDS = ("subject", "case_number", "title", "author_judge", "judgment_date", "upload_date", "citation",
          "sc_citation")
INFO = re.compile(r"Showing\s+([\d,]+)\s+to\s+([\d,]+)\s+of\s+([\d,]+)\s+records", re.I)
NONE = re.compile(r"No\s+(?:judgments?|records?|results?|data)\b[^<]{0,40}found", re.I)


def say(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def _cell(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def rows_of(page: str) -> list[dict]:
    """The grid's inner rows (class 'data-row ...'), ten cells each, the last holding the file link; a 'has-tagline'
    row is followed by its tagline row (the court's own words, kept, read for nothing: D-120)."""
    rows = []
    for tr, tag in re.findall(r'<tr class="data-row[^"]*">(.*?)</tr>(\s*<tr class="tagline-row">.*?</tr>)?',
                              page, re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", tr, re.S)
        link = re.search(r'href="([^"]+\.pdf)"', tr, re.I)
        if len(cells) != 10 or not link:
            raise ValueError(f"unexpected row ({len(cells)} cells): {_cell(tr)[:120]!r}")
        row = dict(zip(FIELDS, (_cell(c) for c in cells[1:9])))
        url = urllib.parse.urljoin(BASE + "/", htmlmod.unescape(link.group(1)))
        row.update(url=url, filename=urllib.parse.unquote(url.rsplit("/", 1)[-1]), tagline=_cell(tag))
        rows.append(row)
    # a tagline may link another file ("Urdu Version. (Main Judgment)" -> the English judgment, 25 Nov, case year
    # 2024): that is the court's note, not a row, so tagline rows are left out of the count
    untagged = re.sub(r'<tr class="tagline-row">.*?</tr>', "", page, flags=re.S)
    n_links = len(set(re.findall(r'href="([^"]+\.pdf)"', untagged, re.I)))
    if len({r["url"] for r in rows}) != n_links:
        raise ValueError(f"{len(rows)} rows read, but the page links {n_links} files")
    return rows


def info(page_html: str):
    m = INFO.search(page_html)
    return tuple(int(x.replace(",", "")) for x in m.groups()) if m else None


def complete(h: str, first: int):
    """The page's record info when it starts at row `first` and every row it promises was served and parses (a
    response cut short leaves the DOM closed mid-row: seen on 25 Nov, case year 2025, page 1 ended at row 71)."""
    i = info(h)
    if not i or i[0] != first:
        return None
    try:
        return i if len(rows_of(h)) == i[1] - i[0] + 1 else None
    except ValueError:
        return None


REFUSED = re.compile(r"Unable to verify this search", re.I)


class Refused(Exception):
    """The site's own verification declined the request (its reCAPTCHA v3 score); answered by waiting, never by
    altering the browser or the token."""


def wait_for(page, want, what: str, limit: float = WAIT_FOR_OWNER):
    """Poll until want(html) is truthy; after 20 s say the owner may be needed. Gives up after `limit` seconds."""
    t0, told = time.time(), False
    while time.time() - t0 < limit:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            h = page.content()
            got = want(h)
            if got:
                return got, h
            # the message element is always in the page, hidden; the site shows it when its check declines
            if page.evaluate("""() => { const e = document.getElementById('spnCaptchaError');
                                        return !!e && getComputedStyle(e).display !== 'none'; }"""):
                raise Refused(what)
        except Refused:
            raise
        except Exception:                                   # noqa: BLE001 -- a navigation in flight
            pass
        if not told and time.time() - t0 > 20:
            say(f"waiting for {what}: if the Chrome window shows a challenge, please solve it there")
            told = True
            try:                                            # what the window shows, for the log
                OUT.joinpath("waiting.html").write_text(page.content(), encoding="utf-8")
                page.screenshot(path=str(OUT / "waiting.png"), full_page=True)
                msg = page.evaluate("""() => [...document.querySelectorAll('.recaptcha-wrap, .state-panel, '
                    + '.alert, .error, [class*=error], [class*=msg]')].filter(e => e.offsetParent !== null)
                    .map(e => e.innerText.trim()).filter(Boolean)
                    .slice(0, 5).join(' | ')""")
                if msg:
                    say(f"  the page says: {msg[:300]}")
            except Exception:                               # noqa: BLE001
                pass
        time.sleep(2)
    raise TimeoutError(f"gave up waiting for {what}")


def search(page, year: str):
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_selector("#MainContent_ddlCaseYear", state="attached")
    # the select is hidden behind a styled control: set its value and fire change, as a choice in the control does
    page.evaluate("""y => { const s = document.getElementById('MainContent_ddlCaseYear'); s.value = y;
                            s.dispatchEvent(new Event('change', {bubbles: true})); }""", year)
    time.sleep(1.5)
    page.click("input[name='ctl00$MainContent$btnSearch']")
    return wait_for(page, lambda h: info(h) or ("none" if NONE.search(h) and "searchResults" in h else None),
                    f"the results of case year {year}")


PER = 50   # rows a page: at 100 the server cut responses short (25 Nov, case years 2025 and 2024)


def page_size(page):
    page.evaluate("""n => { const s = document.getElementById('MainContent_ddlPageSize'); s.value = String(n);
                            __doPostBack('ctl00$MainContent$ddlPageSize', ''); }""", PER)
    return wait_for(page, lambda h: (i := info(h)) and i[0] == 1 and (i[1] - i[0] + 1 == PER or i[1] == i[2]) and i,
                    f"{PER} rows a page", limit=120)


def goto_page(page, n: int):
    """Page n by the grid's own postback (Refused or TimeoutError propagate to crawl_year's caller)."""
    page.evaluate("n => __doPostBack('ctl00$MainContent$gvJudgments', 'Page$' + n)", n)
    return wait_for(page, lambda h: complete(h, (n - 1) * PER + 1), f"page {n} complete", limit=90)


def crawl_year(page, year: str, first: int, delay: float, log, today: str) -> int:
    """Pages first.. of one case year, from a fresh search. Returns the year's page count once every page is saved;
    a refusal or a cut response propagates, and the caller resumes at the first unsaved page."""
    got, h = search(page, year)
    if got == "none":
        say(f"{year}: no records")
        return 0
    total = got[2]
    pages = (total + PER - 1) // PER
    if total > 25:
        time.sleep(delay)
        got, h = page_size(page)
    for n in range(first, pages + 1):
        if n > 1 or not complete(h, 1):
            time.sleep(delay)
            got, h = goto_page(page, n)
        (OUT / f"y{year}-p{n}.html").write_text(h, encoding="utf-8")
        rows = rows_of(h)
        expect = got[1] - got[0] + 1
        if len(rows) != expect:
            raise SystemExit(f"{year} page {n}: {len(rows)} rows read, the page says {expect}")
        for r in rows:
            log.write(json.dumps(dict(r, case_year=year, page=n, seen_on=today), ensure_ascii=False) + "\n")
        log.flush()
        (OUT / f"y{year}.next").write_text(f"{n + 1}\n")
        say(f"{year}: page {n}/{pages}, rows to {got[1]} of {total}")
    return pages


def crawl(years: list[str], delay: float) -> None:
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    with sync_playwright() as p, open(OUT / "rows.jsonl", "a", encoding="utf-8") as log:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False,
                                                   viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for year in years:
            done, nxt = OUT / f"y{year}.done", OUT / f"y{year}.next"
            if done.exists():
                say(f"{year}: done before, skipped")
                continue
            refusals = 0
            while True:
                first = int(nxt.read_text()) if nxt.exists() else 1
                try:
                    pages = crawl_year(page, year, first, delay, log, today)
                    done.write_text(f"{pages} pages\n")
                    break
                except Refused as exc:
                    refusals += 1
                    if refusals > 8:
                        raise SystemExit(f"{year}: the site declined 8 times in a row; stopping")
                    wait = min(60 * 2 ** (refusals - 1), 900)
                    say(f"{year}: the site declined ({exc}); waiting {wait}s before asking again from page {first}")
                    time.sleep(wait)
                except TimeoutError as exc:
                    say(f"{year}: {exc}; starting the year again from page {first}")
                    time.sleep(delay * 3)
            time.sleep(delay)
        ctx.close()


def queue() -> None:
    with zipfile.ZipFile(SEPT) as z:
        held = {n.rsplit("/", 1)[-1].lower() for n in z.namelist() if n.lower().endswith(".pdf")}
    held |= {p.name.lower() for p in SITE.glob("*.pdf")}
    listing = SITE / "listing.jsonl"
    known = {(r["url"], r["upload_date"]) for r in map(json.loads, listing.read_text(encoding="utf-8").splitlines())}
    rows = [json.loads(ln) for ln in (OUT / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    new, seen = [], set()
    for r in rows:
        f = r["filename"].lower()
        if f in held or f in seen or (r["url"], r["upload_date"]) in known:
            continue
        seen.add(f)
        new.append({k: r[k] for k in (*FIELDS, "url", "filename", "tagline")} | {"seen_on": r["seen_on"],
                                                                                  "via": "search"})
    with open(listing, "a", encoding="utf-8") as fh:
        for r in new:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    files = {r["filename"].lower() for r in rows}
    say(f"{len(rows)} rows, {len(files)} files; {len(files & held)} held already; {len(new)} queued for download")


def explore(year: str) -> None:
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False,
                                                   viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        got, h = search(page, year)
        (OUT / f"explore-y{year}-p1.html").write_text(h, encoding="utf-8")
        say(f"saved; {got}; {len(rows_of(h))} rows")
        ctx.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["explore", "crawl", "queue"])
    ap.add_argument("--year", default="2025")
    ap.add_argument("--years", default="2026-1980")
    ap.add_argument("--delay", type=float, default=4.0)
    a = ap.parse_args()
    if a.mode == "explore":
        explore(a.year)
    elif a.mode == "crawl":
        hi, _, lo = a.years.partition("-")
        lo = lo or hi
        step = -1 if int(hi) >= int(lo) else 1
        crawl([str(y) for y in range(int(hi), int(lo) + step, step)], a.delay)
    else:
        queue()
    return 0


if __name__ == "__main__":
    sys.exit(main())
