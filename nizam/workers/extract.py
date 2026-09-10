"""Run L1 extraction over the blob store.

    uv run python -m nizam.workers.extract --sha256 e2cd2bb9...   # one document
    uv run python -m nizam.workers.extract --source pk-federal --limit 20
    uv run python -m nizam.workers.extract --all

Resumable by construction: blobs that already have a document are skipped, so an
interrupted run continues where it stopped rather than starting over (09a §6).
Rejections are reported and counted, never silently swallowed — Document 02 §8,
"Nothing reaches retrieval because a script finished."
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from nizam.corpus.extract import extract_pdf
from nizam.shared.corpus_types import ExtractionRejected
from nizam.storage import corpus_write

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))


def _blob_path(object_key: str) -> Path:
    return CORPUS_ROOT / object_key


EXTRACTOR_TAG = f"pymupdf-{getattr(__import__('pymupdf'), '__version__', 'unknown')}"


def run(targets: list[tuple[str, str, int]], verbose: bool = True) -> tuple[int, int]:
    """Extract each target, recording every attempt whether it succeeds or not.

    A rejection is data, not an error to swallow: doc 02 §4 routes the pages a
    text layer cannot serve to OCR, and that backlog has to be queryable
    afterwards (v_extract_queue).
    """
    done = rejected = 0
    started = time.time()
    for n, (sha256, object_key, byte_length) in enumerate(targets, 1):
        path = _blob_path(object_key)
        source_id = object_key.split("/")[1] if "/" in object_key else "unknown"
        t0 = time.time()

        if not path.exists():
            corpus_write.record_attempt(
                sha256, EXTRACTOR_TAG, "error", reason="blob missing from the store",
                detail={"expected_path": str(path)})
            print(f"  MISSING  {sha256[:12]}  {path}", file=sys.stderr)
            rejected += 1
            continue

        corpus_write.register_blob(sha256, source_id, object_key, byte_length)
        try:
            doc = extract_pdf(path.read_bytes(), sha256)
        except ExtractionRejected as exc:
            corpus_write.record_attempt(
                sha256, EXTRACTOR_TAG, "rejected", lane="E2", reason=str(exc),
                duration_ms=int((time.time() - t0) * 1000))
            print(f"  reject  {sha256[:12]}  {exc}", file=sys.stderr)
            rejected += 1
            continue
        except Exception as exc:                      # corrupt PDF, unreadable stream
            corpus_write.record_attempt(
                sha256, EXTRACTOR_TAG, "error", lane="E2",
                reason=f"{type(exc).__name__}: {exc}"[:500],
                duration_ms=int((time.time() - t0) * 1000))
            print(f"  ERROR   {sha256[:12]}  {type(exc).__name__}: {exc}", file=sys.stderr)
            rejected += 1
            continue

        doc_id = corpus_write.save_document(doc)
        corpus_write.record_attempt(
            sha256, doc.extractor, "extracted", lane=doc.lane, document_id=doc_id,
            detail={"pages": doc.page_count, "blocks": len(doc.blocks),
                    "printable_ratio": float(doc.printable_ratio)},
            duration_ms=int((time.time() - t0) * 1000))
        done += 1
        if verbose:
            print(f"  {n:>5}/{len(targets)}  #{doc_id:<5} {sha256[:12]}  "
                  f"{doc.page_count:>4}p  {doc.char_count:>9,}c  "
                  f"{doc.printable_ratio:.4f}  {len(doc.blocks):>6,}b", flush=True)

    elapsed = time.time() - started
    print(f"\nextracted {done}, rejected {rejected}, in {elapsed:.1f}s "
          f"({done / elapsed:.1f}/s)" if elapsed else "")
    return done, rejected


def main() -> int:
    ap = argparse.ArgumentParser(description="L1 extraction (doc 02 §4, lane E2)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sha256", help="extract one blob by hash (prefix allowed)")
    g.add_argument("--all", action="store_true", help="every blob not yet extracted")
    ap.add_argument("--source", help="restrict to one source, e.g. pk-federal")
    ap.add_argument("--limit", type=int, help="stop after N blobs")
    ap.add_argument("--retry-failed", action="store_true",
                    help="also retry blobs a previous run rejected (use after the extractor changes)")
    ap.add_argument("--redo", action="store_true",
                    help="create a new extraction revision even when an active one exists")
    ap.add_argument("--quiet", action="store_true", help="print only totals and failures")
    a = ap.parse_args()

    if a.sha256:
        if a.redo:
            pending = corpus_write.blobs_for_reextraction(
                sha_prefix=a.sha256, source_id=a.source)
        else:
            pending = corpus_write.blobs_needing_extraction(
                source_id=a.source, retry_failed=True)
        targets = [t for t in pending if t[0].startswith(a.sha256)]
        if not targets:
            # Already extracted, or no such blob -- say which.
            from nizam.storage.db import connect
            with connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT id, sha256 FROM document WHERE sha256 LIKE %s",
                            (a.sha256 + "%",))
                row = cur.fetchone()
            if row:
                print(f"already extracted as document #{row[0]} ({row[1][:12]}). "
                      f"Re-run replaces it only if the extractor version changed.")
                return 0
            print(f"no blob matching {a.sha256!r} awaiting extraction", file=sys.stderr)
            return 1
    else:
        if a.redo:
            targets = corpus_write.blobs_for_reextraction(
                source_id=a.source, limit=a.limit)
        else:
            targets = corpus_write.blobs_needing_extraction(
                limit=a.limit, source_id=a.source, retry_failed=a.retry_failed)

    if not targets:
        print("nothing to extract -- every blob already has a document")
        return 0

    print(f"extracting {len(targets)} blob(s) from {CORPUS_ROOT}\n")
    done, rejected = run(targets, verbose=not a.quiet)
    return 0 if done or not rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())
