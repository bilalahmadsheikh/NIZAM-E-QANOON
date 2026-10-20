"""Refetch a LANDED source and record the dated attempt in acquisition_attempt.

A ``source_incompleteness`` record (migration 0054) is only as good as the
dated attempts behind it: it requires ``attempts_considered >= 1`` and
``evidence.attempt_ids``. ``nizam.workers.recover_acquisition`` cannot make
that attempt. It targets observations that did NOT land, and it records any
valid PDF as ``recovered`` -- which, for a portal that answers with the same
short file, would be false twice over (migration 0055 says why).

This tool asks the official URL again for one landed observation, hashes what
comes back, and records exactly one attempt:

    unchanged_copy  HTTP 2xx, a valid PDF, byte-for-byte the blob already held
    http_error      the server answered, and not with the document
    network_error   the server could not be reached
    invalid_pdf     bytes arrived and are not a readable PDF

and one result it refuses to record here:

    different copy  HTTP 2xx and a valid PDF whose SHA-256 differs from the held
                    blob. That is a new copy, possibly the complete one, and it
                    must be LANDED as its own observation, not filed as an
                    attempt: run nizam/workers/recover_acquisition.py
                    --alternate-for OBSERVATION --url URL --expected-sha256 SHA,
                    then read it before declaring anything.

Every run makes a real request; the dry run makes one too and records nothing,
so the attempt that --apply records is always the fetch made in that same run.
Error bodies are retained under ``evidence/`` like the recovery worker does;
an unchanged copy points at the blob already stored.

    python tools/record_source_refetch.py --observation 3151            dry run
    python tools/record_source_refetch.py --observation 3151 --apply    record

An observation that landed with NO canonical_url (doc 3533, observation 370:
the landing matched no manifest row because the zip entry prints '_' where the
row's local_path prints an apostrophe) takes its URL from the scraper manifest
that catalogued the held file, never from a guess:

    python tools/record_source_refetch.py --observation 370 \\
        --manifest-archive "data/Federal Laws-20260817T002958Z-1-001.zip" \\
        --manifest "Federal Laws/output/manifest.csv"

The manifest's rows whose sha256 is the held blob's must name exactly one
pdf_url; the attempt's ledger text says which manifest (and its SHA-256) the URL
came from. An observation that has a canonical_url refuses the manifest options.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import zipfile
from pathlib import Path

from nizam.storage.db import connect
from nizam.workers.recover_acquisition import (
    fetch, safe_official_url, store_bytes, valid_pdf)

DIFFERENT_COPY = "different_copy"

OBSERVATION = """
SELECT o.id, o.source_id, o.canonical_url, o.outcome::text, o.sha256,
       b.object_key, o.source_metadata ->> 'title'
  FROM source_observation o
  LEFT JOIN blob b ON b.sha256 = o.sha256
 WHERE o.id = %s
"""


def classify(status: int | None, digest: str | None, held_sha256: str,
             pdf_ok: bool, fetch_error: str | None,
             pdf_error: str | None) -> tuple[str, str | None]:
    """What one refetch of a landed source returned: (outcome, error).

    Pure, so the rules can be tested without a portal. `different_copy` is not
    an acquisition_attempt outcome; it is the signal to stop and land the copy.
    """
    if status is None:
        return "network_error", fetch_error or "no response"
    if not 200 <= status < 300:
        return "http_error", fetch_error or f"HTTP {status}"
    if not pdf_ok:
        return "invalid_pdf", pdf_error or "not a readable PDF"
    if digest != held_sha256:
        return DIFFERENT_COPY, (f"valid PDF with SHA-256 {digest}, not the held "
                                f"{held_sha256}")
    return "unchanged_copy", None


def manifest_url(rows: list[dict], held_sha256: str) -> tuple[str, dict]:
    """The one pdf_url a scraper manifest gives for the held blob: (url, row).

    Pure, so the rule can be tested without a portal or an archive. Only rows
    whose sha256 is the held blob's count; they must name exactly one non-empty
    pdf_url (a page scraped twice, 'success' then 'skipped', names it twice)."""
    hits = [r for r in rows if (r.get("sha256") or "").strip().lower() == held_sha256.lower()]
    urls = sorted({(r.get("pdf_url") or "").strip() for r in hits} - {""})
    if len(urls) != 1:
        raise ValueError(f"the manifest names {len(urls)} pdf_url(s) for the held blob "
                         f"{held_sha256} ({len(hits)} matching rows); need exactly one")
    return urls[0], next(r for r in hits if (r.get("pdf_url") or "").strip() == urls[0])


def read_manifest(manifest: str, archive: str | None) -> tuple[list[dict], str]:
    """The manifest's rows and its SHA-256, from a CSV file or a CSV entry of a zip."""
    if archive:
        with zipfile.ZipFile(archive) as zf:
            data = zf.read(manifest)
    else:
        data = Path(manifest).read_bytes()
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    return rows, hashlib.sha256(data).hexdigest()


def attempt_note(outcome: str, byte_length: int, digest: str | None,
                 note: str | None) -> str | None:
    """The `error` text the ledger carries for this attempt."""
    if outcome == "unchanged_copy":
        base = (f"portal serves the byte-identical copy already held "
                f"({byte_length} bytes, SHA-256 {digest})")
        return f"{base}; {note.strip()}" if note and note.strip() else base
    return note.strip() if note and note.strip() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--observation", type=int, required=True,
                    help="a LANDED source_observation id")
    ap.add_argument("--note", help="what this attempt shows, e.g. where the "
                                   "copy stops; appended to the ledger text")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--apply", action="store_true",
                    help="record the attempt (default: fetch and report only)")
    ap.add_argument("--manifest", help="for an observation with no canonical_url: the "
                                       "scraper manifest CSV (a path, or an entry of "
                                       "--manifest-archive) whose row for the held blob "
                                       "names the URL")
    ap.add_argument("--manifest-archive", help="zip holding --manifest")
    a = ap.parse_args()
    if a.manifest_archive and not a.manifest:
        raise SystemExit("--manifest-archive needs --manifest")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(OBSERVATION, (a.observation,))
        row = cur.fetchone()
    if row is None:
        raise SystemExit(f"no source_observation {a.observation}")
    (obs_id, source_id, raw_url, outcome_then, held_sha256, blob_key,
     title) = row
    if outcome_then != "landed" or not held_sha256:
        raise SystemExit(
            f"observation {obs_id} did not land ({outcome_then}); retry it with "
            "nizam/workers/recover_acquisition.py --observation, not this tool")

    url_source = None
    if a.manifest:
        if (raw_url or "").strip():
            raise SystemExit(f"observation {obs_id} has canonical_url {raw_url!r}; the "
                             "manifest options are only for one landed without a URL")
        rows, manifest_sha256 = read_manifest(a.manifest, a.manifest_archive)
        try:
            raw_url, manifest_row = manifest_url(rows, held_sha256)
        except ValueError as exc:
            raise SystemExit(str(exc))
        where = f"{a.manifest_archive}::{a.manifest}" if a.manifest_archive else a.manifest
        url_source = (f"URL from manifest {where} (SHA-256 {manifest_sha256}), row "
                      f"local_path {manifest_row.get('local_path')!r}")
    elif not (raw_url or "").strip():
        raise SystemExit(f"observation {obs_id} has no canonical_url; pass --manifest "
                         "(and --manifest-archive) naming the manifest that catalogued it")
    url = safe_official_url(raw_url)
    status, final_url, media_type, data, fetch_error = fetch(
        url, attempts=a.attempts, timeout=a.timeout)
    digest = hashlib.sha256(data).hexdigest() if data else None
    pdf_ok, pdf_error = valid_pdf(data) if data else (False, None)
    outcome, error = classify(status, digest, held_sha256, pdf_ok,
                              fetch_error, pdf_error)

    print(f"observation : {obs_id} {source_id} {title or ''}")
    print(f"url         : {url}")
    if url_source:
        print(f"url source  : {url_source}")
    print(f"held        : {held_sha256}")
    print(f"returned    : HTTP {status} {media_type} {len(data)} bytes "
          f"{digest or '-'}")
    print(f"outcome     : {outcome}{' -- ' + error if error else ''}")

    if outcome == DIFFERENT_COPY:
        print("\nNOT RECORDED: the portal now serves a different valid PDF. "
              "Land it as its own observation and read it:\n"
              f"  python -m nizam.workers.recover_acquisition --alternate-for "
              f"{obs_id} --url '{url}' --expected-sha256 {digest}")
        return 2

    text = attempt_note(outcome, len(data), digest, a.note)
    if outcome != "unchanged_copy":
        text = "; ".join(x for x in (error, text) if x) or None
    if url_source:
        text = "; ".join(x for x in (text, url_source) if x)

    if not a.apply:
        print("\ndry run -- pass --apply to record this attempt "
              "(a new request is made then)")
        return 0

    if outcome == "unchanged_copy":
        object_key = blob_key
    else:
        object_key = (store_bytes("evidence", source_id, digest, data)
                      if data else None)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO acquisition_attempt
              (source_observation_id, requested_url, final_url, http_status,
               media_type, byte_length, response_sha256, object_key, outcome,
               error)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id, attempted_at
        """, (obs_id, url, final_url, status, media_type,
              len(data) if data else None, digest, object_key, outcome,
              text[:1000] if text else None))
        attempt_id, attempted_at = cur.fetchone()
        conn.commit()
    print(f"\nrecorded acquisition_attempt {attempt_id} at {attempted_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
