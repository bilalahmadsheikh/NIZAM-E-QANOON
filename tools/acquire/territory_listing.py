"""territory_listing.py {ajk|ict|gb} --out CSV : list the law PDFs a territory's official site publishes (no DB, no download).

ICT, AJK and GB were taken into scope on 14 Nov 2026 (docs/02 §2.2 lists the AJK Legislative Assembly and the GB
Assembly as P1 sources; "ingestion must not mislabel it as federal"). Each site is listed from its own pages, the
link text being the title as the site prints it; the CSV feeds tools/acquire/stage_candidates.py (columns portal,
kind, year_or_dept, title, detail_url, pdf_url), which downloads and grades each file.

  ajk  law.gok.pk (Law, Justice & Parliamentary Affairs Department, Government of AJK): /acts/, /ordinance/,
       /revised-volume/, /adopted-laws-in-ajk/, /publications/. Compiled code volumes on /publications/ ('Volume II
       (1963-1970)') are left out: they bundle hundreds of laws, each of which is listed on its own.
  ict  www.cda.gov.pk (Capital Development Authority): /public/lawsAndRegulations, /public/cdaOrdinance. CDA is a
       federal body: its instruments are filed 'fed' and land under source pk-federal (docs/SCHEMA.md, Territories).
  gb   gilgitbaltistan.gov.pk /pages/acts and gbassembly.gbit.gov.pk /pages/acts.
Islamabad's Acts of Parliament are not listed here: they are federal Acts, held from Pakistan Code under 'fed'.

The sites are slow and drop connections: each page is tried 4 times with growing pauses; a page that never answers is
reported on stderr and the listing goes on (re-run to fill it in). A generic user agent is sent.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"}
SITES = {
    "ajk": [("act", "https://law.gok.pk/acts/"), ("ordinance", "https://law.gok.pk/ordinance/"),
            ("revised", "https://law.gok.pk/revised-volume/"), ("adopted", "https://law.gok.pk/adopted-laws-in-ajk/"),
            ("publication", "https://law.gok.pk/publications/")],
    "ict": [("regulation", "https://www.cda.gov.pk/public/lawsAndRegulations"),
            ("ordinance", "https://www.cda.gov.pk/public/cdaOrdinance")],
    "gb": [("act", "https://gilgitbaltistan.gov.pk/pages/acts"), ("act", "https://gbassembly.gbit.gov.pk/pages/acts")],
}
VOLUME = re.compile(r"(?i)^\s*(?:azad jammu .{0,30})?(?:law,?\s*codes?\s*)?volume\b|\bvol[-_ ]?\d")
YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


def get(url: str) -> str | None:
    for n in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=(45, 180))
            if r.status_code == 200:
                return r.text
            print(f"  {url}: HTTP {r.status_code}", file=sys.stderr)
            return None
        except requests.RequestException as e:
            print(f"  {url}: try {n + 1}: {type(e).__name__}", file=sys.stderr)
            time.sleep(10 * (n + 1))
    return None


def rows_for(portal: str) -> list[dict]:
    out, seen = [], set()
    for kind, page in SITES[portal]:
        html = get(page)
        if html is None:
            print(f"UNLISTED {page}", file=sys.stderr)
            continue
        soup = BeautifulSoup(html, "html.parser")
        n = 0
        for a in soup.find_all("a", href=True):
            href = urljoin(page, a["href"].strip())
            if ".pdf" not in urlsplit(href).path.lower() or href in seen:
                continue
            title = " ".join(a.get_text(" ", strip=True).split())
            # a bare 'Download' / 'View PDF' link: the row's own text is the title
            if len(re.findall(r"[A-Za-z]", title)) < 8 or re.fullmatch(r"(?i)(download|(click (here )?to )?view( pdf)?|read more|pdf)", title):
                row = a.find_parent(["tr", "li", "p", "div"])
                title = " ".join((row.get_text(" ", strip=True) if row else title).split())
            if portal == "ajk" and kind == "publication" and VOLUME.search(title + " " + href):
                continue
            seen.add(href); n += 1
            y = YEAR.findall(title)
            out.append({"portal": portal, "kind": kind, "year_or_dept": y[-1] if y else "", "title": title[:300],
                        "detail_url": page, "pdf_url": href})
        print(f"{page}: {n} PDFs", file=sys.stderr)
    return out


def media_rows(portal: str, listed: set[str]) -> list[dict]:
    """law.gok.pk is WordPress: /wp-json/wp/v2/media lists every uploaded PDF. Those no page links (the /acts/ page
    often does not answer) are added with kind 'media' and the media title (usually the file name) as title."""
    import json
    base = {"ajk": "https://law.gok.pk"}[portal]
    out, page = [], 1
    while True:
        body = get(f"{base}/wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&page={page}"
                   "&_fields=source_url,title,date")
        if body is None:
            print(f"UNLISTED media page {page}", file=sys.stderr)
            break
        items = json.loads(body)
        if not items:
            break
        for m in items:
            href = m["source_url"]
            if href in listed:
                continue
            listed.add(href)
            title = BeautifulSoup(m["title"]["rendered"], "html.parser").get_text(" ", strip=True)
            title = re.sub(r"[-_]+", " ", title)
            y = YEAR.findall(title)
            out.append({"portal": portal, "kind": "media", "year_or_dept": y[-1] if y else "", "title": title[:300],
                        "detail_url": f"{base}/wp-json/wp/v2/media", "pdf_url": href})
        if len(items) < 100:
            break
        page += 1
    print(f"media: {len(out)} PDFs no page links", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("portal", choices=sorted(SITES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--media", action="store_true", help="ajk: add PDFs in the WordPress media library no page links")
    a = ap.parse_args()
    rows = rows_for(a.portal)
    if a.media:
        rows += media_rows(a.portal, {r["pdf_url"] for r in rows})
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["portal", "kind", "year_or_dept", "title", "detail_url", "pdf_url"])
        w.writeheader(); w.writerows(rows)
    print(f"{a.portal}: {len(rows)} PDFs listed -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
