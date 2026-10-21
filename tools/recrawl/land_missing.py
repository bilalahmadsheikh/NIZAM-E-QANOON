"""Land the items tools/recrawl/diff_listing.py found missing. Lead, 20 Oct 2026.

    python tools/recrawl/land_missing.py MISSING.jsonl REPORT.json [--apply] [--limit N]

For each item: the PDF URL (from the listing, or read off the official detail page), one fetch through the recovery
worker's allow-listed fetch(), a PDF validity check, the bytes stored content-addressed (raw/{source}/{sha256}),
and a blob row plus a LANDED source_observation carrying the listing's provenance in source_metadata
(title, year, type, listing, detail_url, number, date; scraper_version 'recrawl-2026-10-20/1').

Refused and reported, never inserted: no PDF link, an HTTP/network failure, not a PDF, or bytes the corpus already
holds as a blob (a held file under a new URL is not a missing law). Dry run by default (fetches nothing).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nizam.storage.db import connect  # noqa: E402
from nizam.workers.recover_acquisition import fetch, safe_official_url, store_bytes, valid_pdf  # noqa: E402

PDF_ON_DETAIL = {
    "pk-federal": re.compile(r"""(https?://[^"'#\s]*pdffiles/[^"'#\s]+\.pdf)""", re.I),
    "pk-kp": re.compile(r"""(https?://kpcode\.kp\.gov\.pk/uploads/[^"'\s]+\.pdf)""", re.I),
    "pk-punjab": re.compile(r"""((?:https?://punjabcode\.punjab\.gov\.pk)?/uploads/articles/[^"'#\s]+\.pdf)""", re.I),
    "pk-balochistan": re.compile(r"""((?:https?://balochistancode\.gob\.pk)?/?lawdir/[^"'\s]+\.pdf)""", re.I),
}
BASES = {"pk-federal": "https://pakistancode.gov.pk/english/", "pk-kp": "https://kpcode.kp.gov.pk/",
         "pk-punjab": "https://punjabcode.punjab.gov.pk/",
         "pk-balochistan": "http://balochistancode.gob.pk/", "pk-sindh": "https://sindhlaws.gov.pk/"}


DRS_PDF = re.compile(r'''data-pdf-url=["'](/pdf/[^"']+\.pdf)["']''', re.I)


def pdf_url_for(it: dict) -> tuple[str | None, str | None]:
    if it.get("pdf_url"):
        return it["pdf_url"], None
    if (it.get("listing") or "").startswith("drs:"):
        status, _final, _mt, body, err = fetch(safe_official_url(it["detail_url"]), attempts=3, timeout=120)
        m = DRS_PDF.search(body.decode("utf-8", "replace")) if status == 200 else None
        return (f"https://drs.molaw.gov.pk{m.group(1)}", None) if m else (None, f"DRS page: {err or status or 'no data-pdf-url'}")
    pat = PDF_ON_DETAIL.get(it["source_id"])
    if not pat or not it.get("detail_url"):
        return None, "no PDF link and no detail page"
    status, _final, _mt, body, err = fetch(safe_official_url(it["detail_url"]), attempts=3, timeout=90)
    if status != 200:
        return None, f"detail page: {err or status}"
    m = pat.search(body.decode("utf-8", "replace"))
    if not m:
        return None, "detail page carries no PDF link"
    return urljoin(BASES[it["source_id"]], m.group(1)), None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("missing"); ap.add_argument("report")
    ap.add_argument("--apply", action="store_true"); ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    items = [json.loads(l) for l in open(a.missing, encoding="utf-8") if l.strip()][: a.limit]
    report = {"landed": [], "refused": [], "already_held_bytes": []}
    if not a.apply:
        print(f"dry run: {len(items)} item(s) would be fetched; pass --apply"); return 0
    with connect() as conn, conn.cursor() as cur:
        # resumable: an item already landed by an earlier run (same detail page, or same PDF URL) is skipped
        cur.execute("""SELECT referring_url, canonical_url, source_metadata->>'detail_url' FROM source_observation
                        WHERE scraper_version='recrawl-2026-10-20/1'""")
        done = {u for row in cur.fetchall() for u in row if u}
        for n, it in enumerate(items, 1):
            if it.get("detail_url") in done or it.get("pdf_url") in done:
                report.setdefault("already_landed", []).append(it.get("detail_url") or it.get("pdf_url")); continue
            try:
                land_one(it, cur, conn, report)
            except Exception as exc:                            # noqa: BLE001 -- one bad download is never fatal
                conn.rollback()
                report["refused"].append({**it, "why": f"{type(exc).__name__}: {str(exc)[:200]}"})
            if n % 25 == 0:
                print(f"{n}/{len(items)} landed {len(report['landed'])} refused {len(report['refused'])} "
                      f"held-bytes {len(report['already_held_bytes'])}", flush=True)
    json.dump(report, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"landed {len(report['landed'])}; refused {len(report['refused'])}; "
          f"already held bytes {len(report['already_held_bytes'])}; already landed "
          f"{len(report.get('already_landed', []))}")
    return 0


def land_one(it: dict, cur, conn, report: dict) -> None:
    """Fetch, validate, store and record one item; every refusal is reported, never raised."""
    sid = it["source_id"]
    url, why = pdf_url_for(it)
    if not url:
        report["refused"].append({**it, "why": why}); return
    status, final, mt, data, err = fetch(safe_official_url(url), attempts=3, timeout=300)
    if status is None or not 200 <= status < 300 or not data:
        report["refused"].append({**it, "pdf_url": url, "why": err or f"HTTP {status}"}); return
    ok, perr = valid_pdf(data)
    if not ok:
        report["refused"].append({**it, "pdf_url": url, "why": f"not a readable PDF: {perr}"}); return
    digest = hashlib.sha256(data).hexdigest()
    cur.execute("SELECT 1 FROM blob WHERE sha256=%s", (digest,))
    if cur.fetchone():
        report["already_held_bytes"].append({**it, "pdf_url": final, "sha256": digest}); return
    key = store_bytes("raw", sid, digest, data)
    meta = {k: v for k, v in {"title": it.get("title"), "year": str(it["year"]) if it.get("year") else None,
                              "type": it.get("kind"), "listing": it.get("listing"),
                              "detail_url": it.get("detail_url"), "number": it.get("number"),
                              "date": it.get("date"), "recrawl": "2026-10-20"}.items() if v}
    cur.execute("""INSERT INTO blob (sha256,source_id,object_key,byte_length,media_type,first_seen)
                   VALUES (%s,%s,%s,%s,'application/pdf',now()) ON CONFLICT (sha256) DO NOTHING""",
                (digest, sid, key, len(data)))
    cur.execute("""INSERT INTO source_observation
                     (source_id,canonical_url,referring_url,discovered_at,fetched_at,http_status,media_type,
                      byte_length,sha256,object_key,scraper_version,source_metadata,outcome)
                   VALUES (%s,%s,%s,now(),now(),%s,'application/pdf',%s,%s,%s,'recrawl-2026-10-20/1',%s,'landed')
                   ON CONFLICT DO NOTHING RETURNING id""",
                (sid, final, it.get("detail_url"), status, len(data), digest, key,
                 json.dumps(meta, ensure_ascii=False)))
    row = cur.fetchone()
    conn.commit()
    report["landed"].append({**it, "pdf_url": final, "sha256": digest, "observation_id": row[0] if row else None})


if __name__ == "__main__":
    raise SystemExit(main())
