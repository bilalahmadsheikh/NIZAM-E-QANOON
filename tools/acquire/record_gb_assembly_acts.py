"""record_gb_assembly_acts.py [--apply] : catalogue the Acts the Gilgit-Baltistan Assembly lists, as observations.

Lead, 14 Nov 2026. GB was taken into scope that day (docs/02 §2.2 names the GB Assembly as a P1 source). The Assembly's
site (gbassembly.gbit.gov.pk /pages/acts) answers and lists its Acts in a table -- Act No, title, passed on, assented on
-- but every PDF it links answers HTTP 404 (probed 14 Nov 2026 with the path as linked, space-encoded and colon-encoded,
and under /storage/; the government portal gilgitbaltistan.gov.pk refuses connections and gba.gov.pk presents an
expired certificate). docs/02 §3.1: "Record missing links ... as first-class observations." So each listed Act becomes
a source_observation with outcome 'failed', source pk-gb, carrying the row as printed. The recovery worker
(nizam.workers.recover_acquisition --observation N) then retries each and records the dated attempts, and an
acquisition_exception can be declared from those attempts; a later fetch that succeeds lands the file in the ordinary
way and supersedes the exception.

Rows whose title is a site test entry ('test-2', 'test-3') are not Acts and are not catalogued. Idempotent: a row is
not recorded twice (same source and URL under this scraper version).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nizam.storage.db import connect  # noqa: E402
from nizam.workers.recover_acquisition import fetch, safe_official_url  # noqa: E402

PAGE = "https://gbassembly.gbit.gov.pk/pages/acts"
VERSION = "recrawl-2026-11-14/4"
ROW = re.compile(r"<tr[^>]*>\s*<td>\s*\d+\s*</td>\s*<td>(?P<no>.*?)</td>\s*<td>\s*<a[^>]*href=\"(?P<href>[^\"]+)\"[^>]*>"
                 r"(?P<title>.*?)</a>\s*</td>\s*<td>(?P<passed>.*?)</td>\s*<td>(?P<assented>.*?)</td>\s*<td>(?P<type>.*?)</td>",
                 re.S)


def clean(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    status, _final, _mt, body, err = fetch(safe_official_url(PAGE), attempts=4, timeout=120)
    if status != 200:
        print(f"listing did not answer: {err or status}"); return 1
    rows = []
    for m in ROW.finditer(body.decode("utf-8", "replace")):
        title = clean(m["title"])
        if re.fullmatch(r"(?i)test[-\s]*\d*", title):
            continue
        href = " ".join(m["href"].split())             # the page wraps long hrefs across lines
        y = re.findall(r"\b(20\d\d|19\d\d)\b", title)
        rows.append({"title": re.sub(r"(?i)\.pdf$", "", title).rstrip(". "), "number": clean(m["no"]),
                     "passed_on": clean(m["passed"]), "assented_on": clean(m["assented"]), "type": clean(m["type"]),
                     "year": y[-1] if y else None, "url": href})
    print(f"{len(rows)} Acts listed")
    if not a.apply:
        for r in rows:
            print(f"  {r['number']:<22} {r['title'][:80]}")
        print("dry run; pass --apply"); return 0
    n = 0
    with connect() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute("SELECT 1 FROM source_observation WHERE source_id='pk-gb' AND canonical_url=%s AND scraper_version=%s",
                        (r["url"], VERSION))
            if cur.fetchone():
                continue
            meta = {"title": r["title"], "year": r["year"], "type": "act", "number": r["number"],
                    "passed_on": r["passed_on"], "assented_on": r["assented_on"], "listing": "gb-assembly:acts",
                    "detail_url": PAGE, "recrawl": "2026-11-14"}
            cur.execute("""INSERT INTO source_observation (source_id, canonical_url, referring_url, discovered_at, fetched_at,
                               http_status, scraper_version, source_metadata, outcome, error_code)
                           VALUES ('pk-gb', %s, %s, now(), NULL, NULL, %s, %s, 'failed', 'catalogued; fetched by the recovery worker')""",
                        (r["url"], PAGE, VERSION, json.dumps({k: v for k, v in meta.items() if v}, ensure_ascii=False)))
            n += 1
        conn.commit()
    print(f"recorded {n} observation(s) under {VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
