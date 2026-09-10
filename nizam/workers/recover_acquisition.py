"""Non-destructively retry failed official PDF observations.

Only allow-listed government hosts are contacted.  Every HTTP body is hashed;
valid PDFs become content-addressed corpus blobs and a NEW landed observation.
Invalid/error responses are retained under ``evidence/`` and recorded in the
append-only acquisition_attempt ledger.  The failed source observation is never
updated or deleted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import pymupdf

from nizam.storage.db import connect

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
ALLOWED_HOSTS = {
    "pakistancode.gov.pk",
    "punjabcode.punjab.gov.pk",
    "sindhlaws.gov.pk",
    "kpcode.kp.gov.pk",
    "balochistancode.gob.pk",
}
USER_AGENT = "Nizam-e-Qanoon corpus recovery/1 (+official legal research)"


def safe_official_url(raw: str) -> str:
    parts = urlsplit(raw.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or host not in ALLOWED_HOSTS:
        raise ValueError(f"not an allow-listed official URL: {raw}")
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%:@"),
                       quote(parts.query, safe="=&%:@/?"), ""))


def valid_pdf(data: bytes) -> tuple[bool, str | None]:
    if not data.startswith(b"%PDF-"):
        return False, "magic bytes are not %PDF-"
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.page_count < 1:
                return False, "PDF has no pages"
            # Force page-tree access; malformed downloads often open but fail here.
            for page_no in range(pdf.page_count):
                pdf.load_page(page_no)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, None


def targets(observation_id: int | None, limit: int | None,
            after_observation: int | None = None) -> list[tuple]:
    q = """
        SELECT o.id,o.source_id,o.canonical_url,o.referring_url,o.source_metadata
         FROM source_observation o
         WHERE o.outcome <> 'landed' AND o.canonical_url IS NOT NULL
           AND btrim(o.canonical_url) <> ''
           AND NOT EXISTS (
             SELECT 1 FROM acquisition_attempt a
              WHERE a.source_observation_id=o.id AND a.outcome='recovered'
           )
    """
    params: list = []
    if observation_id is not None:
        q += " AND o.id=%s"
        params.append(observation_id)
    if after_observation is not None:
        q += " AND o.id>%s"
        params.append(after_observation)
    q += " ORDER BY o.id"
    if limit:
        q += " LIMIT %s"
        params.append(limit)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(q, params)
        return cur.fetchall()


def fetch(url: str, attempts: int = 3,
          timeout: int = 60) -> tuple[int | None, str, str, bytes, str | None]:
    last_error = None
    for n in range(attempts):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*;q=0.2"})
            with urlopen(req, timeout=timeout) as response:
                return (response.status, response.geturl(),
                        response.headers.get_content_type(), response.read(), None)
        except HTTPError as exc:
            body = exc.read()
            return exc.code, exc.geturl(), exc.headers.get_content_type(), body, f"HTTP {exc.code}"
        except (URLError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if n + 1 < attempts:
                time.sleep(2 ** n)
    return None, url, "application/octet-stream", b"", last_error


def store_bytes(kind: str, source_id: str, digest: str, data: bytes) -> str:
    rel = f"{kind}/{source_id}/{digest}"
    dest = CORPUS_ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"content-address collision at {dest}")
        return rel
    tmp_dir = CORPUS_ROOT / "recovery" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="response-", dir=tmp_dir)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, dest)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return rel


def persist(row: tuple, requested_url: str, status: int | None, final_url: str,
            media_type: str, data: bytes, fetch_error: str | None) -> str:
    observation_id, source_id, _url, referring_url, metadata = row
    digest = hashlib.sha256(data).hexdigest() if data else None
    ok, pdf_error = valid_pdf(data) if data else (False, fetch_error or "empty response")
    if ok and status is not None and 200 <= status < 300:
        object_key = store_bytes("raw", source_id, digest, data)
        outcome, error = "recovered", None
    else:
        object_key = store_bytes("evidence", source_id, digest, data) if data else None
        outcome = "http_error" if status is not None and not (200 <= status < 300) else (
            "network_error" if status is None else "invalid_pdf")
        error = fetch_error or pdf_error

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO acquisition_attempt
              (source_observation_id,requested_url,final_url,http_status,media_type,
               byte_length,response_sha256,object_key,outcome,error)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (observation_id, requested_url, final_url, status, media_type,
                  len(data), digest, object_key, outcome, error))
        if outcome == "recovered":
            cur.execute("""
                INSERT INTO blob (sha256,source_id,object_key,byte_length,media_type,first_seen)
                VALUES (%s,%s,%s,%s,'application/pdf',now())
                ON CONFLICT (sha256) DO NOTHING
                """, (digest, source_id, object_key, len(data)))
            recovered_meta = dict(metadata or {})
            recovered_meta["recovery_of"] = observation_id
            cur.execute("""
                INSERT INTO source_observation
                  (source_id,canonical_url,referring_url,discovered_at,fetched_at,
                   http_status,media_type,byte_length,sha256,object_key,
                   scraper_version,source_metadata,outcome)
                VALUES (%s,%s,%s,now(),now(),%s,'application/pdf',%s,%s,%s,
                        'recover-acquisition/1',%s,'landed')
                ON CONFLICT DO NOTHING
                """, (source_id, final_url, referring_url, status, len(data), digest,
                      object_key, json.dumps(recovered_meta, ensure_ascii=False)))
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry failed official PDF observations")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--observation", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--after-observation", type=int,
                        help="resume strictly after this observation id")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=60,
                        help="seconds per HTTP attempt")
    args = parser.parse_args()
    if not args.all and args.observation is None:
        parser.error("one of --all or --observation is required")

    if args.attempts < 1 or args.timeout < 1:
        parser.error("--attempts and --timeout must be positive")
    rows = targets(args.observation, args.limit, args.after_observation)
    recovered = failed = 0
    for n, row in enumerate(rows, 1):
        observation_id, source_id, raw_url, _ref, metadata = row
        title = (metadata or {}).get("title", "")
        try:
            url = safe_official_url(raw_url)
            status, final_url, media_type, data, error = fetch(
                url, attempts=args.attempts, timeout=args.timeout)
            outcome = persist(row, url, status, final_url, media_type, data, error)
        except Exception as exc:
            outcome = "network_error"
            with connect() as conn, conn.cursor() as cur:
                cur.execute("""INSERT INTO acquisition_attempt
                    (source_observation_id,requested_url,outcome,error)
                    VALUES (%s,%s,'network_error',%s)""",
                    (observation_id, raw_url, f"{type(exc).__name__}: {exc}"[:1000]))
        recovered += outcome == "recovered"
        failed += outcome != "recovered"
        print(f"{n:>3}/{len(rows)} {outcome:<13} observation={observation_id} "
              f"{source_id:<15} {title[:60]}", flush=True)
    print(f"\nrecovered {recovered}; unresolved {failed}; attempts {len(rows)}")
    return 0 if recovered or not rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
