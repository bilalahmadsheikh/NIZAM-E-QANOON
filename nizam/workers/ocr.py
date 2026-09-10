"""Run lane E4 (OCR) over the scans that lane E2 could not read.

    uv run python -m nizam.workers.ocr --all --workers 6
    uv run python -m nizam.workers.ocr --sha256 d6fb61cd0d4f

Only touches blobs that have no document and whose last attempt was a rejection
from E2 -- OCR is the fallback, never the first choice. Doc 02 §4: "OCR is a
fallback, not the default."

Rendering and OCR are CPU-bound and independent per document, so this runs a
process pool. Everything a worker returns is written by the parent, so the
database sees one writer.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from nizam.corpus.ocr import REVIEW_THRESHOLD, ocr_pdf
from nizam.shared.corpus_types import ExtractionRejected
from nizam.storage import corpus_write

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))


def _one(task: tuple[str, str, int]) -> dict:
    """Runs in a worker process: read, OCR, hand the result back."""
    sha256, object_key, byte_length = task
    path = CORPUS_ROOT / object_key
    started = time.time()
    out = {"sha256": sha256, "object_key": object_key, "byte_length": byte_length}
    if not path.exists():
        out["error"] = "blob missing from the store"
        return out
    try:
        out["doc"] = ocr_pdf(path.read_bytes(), sha256)
    except ExtractionRejected as exc:
        out["rejected"] = str(exc)
    except Exception as exc:                       # a corrupt scan, a killed child
        out["error"] = f"{type(exc).__name__}: {exc}"[:400]
    out["ms"] = int((time.time() - started) * 1000)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="L1 extraction, lane E4 (OCR)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="every scan E2 could not read")
    g.add_argument("--sha256", help="one blob by hash prefix")
    ap.add_argument("--redo", action="store_true",
                    help="explicitly create a new extraction revision even when one is active")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    if a.redo:
        targets = corpus_write.blobs_for_reextraction(sha_prefix=a.sha256)
    else:
        targets = corpus_write.blobs_needing_extraction(retry_failed=True)
        if a.sha256:
            targets = [t for t in targets if t[0].startswith(a.sha256)]
    if a.limit:
        targets = targets[: a.limit]
    if not targets:
        print("nothing to OCR -- every blob already has a document")
        return 0

    print(f"OCR: {len(targets)} document(s), {a.workers} workers, 300 DPI\n")
    done = flagged = failed = 0
    started = time.time()

    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(_one, t): t for t in targets}
        for n, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            sha = r["sha256"]
            source_id = r["object_key"].split("/")[1]
            corpus_write.register_blob(sha, source_id, r["object_key"], r["byte_length"])

            if "doc" in r:
                doc = r["doc"]
                doc_id = corpus_write.save_document(doc)
                conf = float(doc.printable_ratio)
                review = conf < REVIEW_THRESHOLD
                corpus_write.record_attempt(
                    sha, doc.extractor, "extracted", lane="E4", document_id=doc_id,
                    detail={"pages": doc.page_count, "blocks": len(doc.blocks),
                            "mean_confidence": conf,
                            "language": doc.pdf_metadata.get("ocr_language"),
                            "needs_review": review},
                    duration_ms=r["ms"])
                done += 1
                flagged += review
                mark = "REVIEW" if review else "ok    "
                print(f"  {n:>3}/{len(targets)}  {mark} #{doc_id:<5} {sha[:12]} "
                      f"{doc.page_count:>4}p  conf={conf:.3f}  "
                      f"{doc.pdf_metadata.get('ocr_language')}  "
                      f"{len(doc.blocks):>5} blocks  {r['ms']/1000:.0f}s", flush=True)
            else:
                reason = r.get("rejected") or r.get("error") or "unknown"
                corpus_write.record_attempt(
                    sha, "tesseract", "rejected" if "rejected" in r else "error",
                    lane="E4", reason=reason, duration_ms=r.get("ms"))
                failed += 1
                print(f"  {n:>3}/{len(targets)}  FAIL   {sha[:12]}  {reason}", file=sys.stderr)

    elapsed = time.time() - started
    print(f"\nOCR complete: {done} extracted ({flagged} flagged for review below "
          f"{REVIEW_THRESHOLD:.2f} confidence), {failed} failed, in {elapsed/60:.1f} min")
    return 0 if done else 1


if __name__ == "__main__":
    raise SystemExit(main())
