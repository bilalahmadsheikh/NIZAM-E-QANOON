"""Land the items tools/recrawl/diff_listing.py found missing. Lead, 20 Oct 2026.

    python tools/recrawl/land_missing.py MISSING.jsonl REPORT.json [--apply] [--limit N]
                                         [--scraper-version recrawl-YYYY-MM-DD/N]   (default the 20 Oct run)

For each item: the PDF URL (from the listing, or read off the official detail page), one fetch through the recovery
worker's allow-listed fetch(), a PDF validity check, the bytes stored content-addressed (raw/{source}/{sha256}),
and a blob row plus a LANDED source_observation carrying the listing's provenance in source_metadata
(title, year, type, listing, detail_url, number, date; scraper_version 'recrawl-2026-10-20/1').

Refused and reported, never inserted: no PDF link, an HTTP/network failure, not a PDF, or bytes the corpus already
holds as a blob (a held file under a new URL is not a missing law). Dry run by default (fetches nothing).

--staged DIR (14 Nov 2026): the items carry staged_sha256 (tools/acquire/select_landing.py) and DIR is the
tools/acquire/stage_candidates.py directory that fetched them the same day, TLS-verified, from the same official URL.
The staged bytes are landed instead of a second fetch (law.gok.pk serves ~1 file a minute), dated by their staging
fetch (fetched_at and source_metadata.staged_fetch), and only while they still hash to the staged sha256.

An item carrying archived_capture (16 Nov 2026, tools/acquire/stage_wayback.py) was staged from the Internet Archive's
raw capture of the official URL, its SHA-1 equal to the archive's recorded digest. canonical_url is still the official
URL; source_metadata.archived_capture says where the bytes came from, and staged_fetch names stage_wayback.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
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


SCRAPER_VERSION = "recrawl-2026-10-20/1"
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
    # a later recrawl lands under its own version, so its pipeline run selects only what it landed (14 Nov 2026)
    ap.add_argument("--scraper-version", default=SCRAPER_VERSION)
    ap.add_argument("--staged", type=Path, help="a tools/acquire/stage_candidates.py directory: land the bytes it "
                    "fetched (files/<sha256>.pdf) instead of fetching again")
    a = ap.parse_args()
    if not re.fullmatch(r"recrawl-\d{4}-\d{2}-\d{2}/\d+", a.scraper_version):
        ap.error("--scraper-version must read recrawl-YYYY-MM-DD/N")
    items = [json.loads(l) for l in open(a.missing, encoding="utf-8") if l.strip()][: a.limit]
    report = {"landed": [], "refused": [], "already_held_bytes": []}
    if not a.apply:
        print(f"dry run: {len(items)} item(s) would be fetched; pass --apply"); return 0
    with connect() as conn, conn.cursor() as cur:
        # resumable: an item already landed by an earlier run (same detail page, or same PDF URL) is skipped
        # The key is the item's PDF URL when it has one: a territory listing gives every row the same listing page as
        # detail_url, so keying on detail_url would skip a whole page after its first file landed (14 Nov 2026).
        cur.execute("""SELECT canonical_url, source_metadata->>'listed_pdf_url', referring_url,
                              source_metadata->>'detail_url' FROM source_observation WHERE scraper_version=%s""",
                    (a.scraper_version,))
        rows = cur.fetchall()
        done_pdf = {u for r in rows for u in r[:2] if u}
        done_detail = {u for r in rows for u in r[2:] if u}
        for n, it in enumerate(items, 1):
            pdf = it.get("pdf_url")
            landed = (pdf in done_pdf or _quoted(pdf) in done_pdf) if pdf else it.get("detail_url") in done_detail
            if landed:
                report.setdefault("already_landed", []).append(pdf or it.get("detail_url")); continue
            try:
                land_one(it, cur, conn, report, a.scraper_version, a.staged)
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


def _quoted(url: str | None) -> str | None:
    try:
        return safe_official_url(url) if url else None
    except ValueError:
        return None


def staged_bytes(staged: Path, it: dict) -> tuple[bytes, str] | None:
    """The bytes tools/acquire/stage_candidates.py fetched for this item, with their fetch time, or None.

    The staging fetch was a TLS-verified GET of the same official URL that answered 200 with a %PDF body, stored as
    files/<sha256>.pdf. The file is accepted only when its bytes still hash to the staged sha256, so a file changed or
    damaged on disk since staging is never landed under that identity."""
    sha = it.get("staged_sha256")
    p = staged / "files" / f"{sha}.pdf" if sha else None
    if not p or not p.exists():
        return None
    data = p.read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise ValueError(f"staged file {p.name} no longer hashes to its name")
    return data, datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")


def land_one(it: dict, cur, conn, report: dict, scraper_version: str = None, staged: Path | None = None) -> None:
    """Fetch (or take the staged bytes), validate, store and record one item; every refusal is reported, never raised."""
    scraper_version = scraper_version or SCRAPER_VERSION
    recrawl_day = scraper_version.split("-", 1)[1].split("/")[0]
    sid = it["source_id"]
    url, why = pdf_url_for(it)
    if not url:
        report["refused"].append({**it, "why": why}); return
    got = staged_bytes(staged, it) if staged else None
    fetched_at = None
    if got:
        data, fetched_at = got
        status, final, err = 200, safe_official_url(url), None
        cap = it.get("archived_capture")
        if cap and re.fullmatch(r"\d{14}", cap.get("timestamp") or ""):
            # the official host served these bytes when the archive captured them: that is the date the corpus can
            # attest the text was published (nizam/storage/legal_write.observed_on opens provision validity there)
            t = cap["timestamp"]
            fetched_at = f"{t[:4]}-{t[4:6]}-{t[6:8]}T{t[8:10]}:{t[10:12]}:{t[12:14]}+00:00"
    else:
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
                              "date": it.get("date"), "recrawl": recrawl_day, "listed_pdf_url": it.get("pdf_url"),
                              # bytes from the Internet Archive's capture of the official URL (16 Nov 2026): the
                              # capture, its timestamp and the digest the staged bytes were verified against
                              "archived_capture": it.get("archived_capture"),
                              "staged_fetch": ({"tool": ("tools/acquire/stage_wayback.py" if it.get("archived_capture")
                                                         else "tools/acquire/stage_candidates.py"),
                                                "fetched_at": fetched_at}
                                               if fetched_at else None)}.items() if v}
    cur.execute("""INSERT INTO blob (sha256,source_id,object_key,byte_length,media_type,first_seen)
                   VALUES (%s,%s,%s,%s,'application/pdf',now()) ON CONFLICT (sha256) DO NOTHING""",
                (digest, sid, key, len(data)))
    cur.execute("""INSERT INTO source_observation
                     (source_id,canonical_url,referring_url,discovered_at,fetched_at,http_status,media_type,
                      byte_length,sha256,object_key,scraper_version,source_metadata,outcome)
                   VALUES (%s,%s,%s,coalesce(%s::timestamptz,now()),coalesce(%s::timestamptz,now()),%s,
                           'application/pdf',%s,%s,%s,%s,%s,'landed')
                   ON CONFLICT DO NOTHING RETURNING id""",
                (sid, final, it.get("detail_url"), fetched_at, fetched_at, status, len(data), digest, key,
                 scraper_version, json.dumps(meta, ensure_ascii=False)))
    row = cur.fetchone()
    conn.commit()
    report["landed"].append({**it, "pdf_url": final, "sha256": digest, "observation_id": row[0] if row else None})


if __name__ == "__main__":
    raise SystemExit(main())
