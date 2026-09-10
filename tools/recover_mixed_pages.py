"""Append OCR candidates for text-empty pages in active mixed PDFs.

This is diagnosis/recovery evidence, not an overwrite. A zero-word candidate
proves that a rendered page was attempted; a non-empty candidate can later be
reviewed and promoted into a new hybrid document revision while the original
text-layer revision remains immutable.
"""
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pymupdf

from nizam.corpus.ocr import _blocks_from_tsv, _ocr_page, _tesseract_version
from nizam.storage.db import connect

ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))


def _one(task: tuple[int, int, str, str]) -> dict:
    document_id, page_no, object_key, languages = task
    out = {"document_id": document_id, "page_no": page_no,
           "languages": languages}
    try:
        with pymupdf.open(ROOT / object_key) as pdf:
            tsv, dpi = _ocr_page(pdf[page_no - 1], languages)
        blocks, _, confidence_sum, word_count = _blocks_from_tsv(
            tsv, page_no, 0, dpi / 72.0,
        )
        out.update(
            dpi=dpi,
            word_count=word_count,
            confidence=(confidence_sum / word_count / 100.0
                        if word_count else None),
            text="\n".join(b.text for b in blocks),
            blocks=[
                {"block_no": b.block_no,
                 "bbox": [b.x0, b.y0, b.x1, b.y1],
                 "text": b.text, "script": b.script,
                 "confidence": b.confidence}
                for b in blocks
            ],
        )
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:500]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--languages", default="urd+eng")
    ap.add_argument("--workers", type=int,
                    default=max(1, min(4, (os.cpu_count() or 4) - 1)))
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    engine = f"tesseract-{_tesseract_version()}"

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT d.id,p.page_no,b.object_key,%s
                 FROM document d JOIN page p ON p.document_id=d.id
                 JOIN blob b ON b.sha256=d.sha256
                WHERE d.is_active AND d.lane='E3' AND p.char_count=0
                  AND NOT EXISTS (
                      SELECT 1 FROM page_ocr_candidate c
                       JOIN document cd ON cd.id=c.document_id
                       WHERE cd.sha256=d.sha256 AND c.page_no=p.page_no
                         AND c.languages=%s)
                ORDER BY d.id,p.page_no""",
            (args.languages, args.languages),
        )
        tasks = cur.fetchall()
    if args.limit:
        tasks = tasks[:args.limit]
    if not tasks:
        print("no mixed text-empty pages await an OCR candidate")
        return 0

    print(f"OCR candidates: {len(tasks)} mixed pages, {args.workers} workers")
    stored = with_words = failed = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_one, task): task for task in tasks}
        for n, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if "error" in result:
                failed += 1
                print(f"  ERROR doc={result['document_id']} page={result['page_no']} "
                      f"{result['error']}", flush=True)
                continue
            with connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO page_ocr_candidate
                        (document_id,page_no,engine,languages,dpi,text,
                         mean_confidence,word_count,blocks)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                    (result["document_id"], result["page_no"], engine,
                     result["languages"], result["dpi"], result["text"],
                     result["confidence"], result["word_count"],
                     json.dumps(result["blocks"], ensure_ascii=False)),
                )
            stored += 1
            with_words += result["word_count"] > 0
            if n % 20 == 0:
                print(f"  ... {n}/{len(tasks)}", flush=True)
    print(f"stored={stored} pages_with_words={with_words} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
