"""Append an OCR candidate for one damaged born-digital PDF page.

The candidate never replaces text-layer evidence.  A reviewer can compare the
rendered page, original decoded blocks and OCR text before promoting anything.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pymupdf

from nizam.corpus.ocr import RENDER_DPI, _blocks_from_tsv, _ocr_page, _tesseract_version
from nizam.storage.db import connect


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", type=int, required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--lang", default="urd+eng")
    args = parser.parse_args()
    root = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT b.object_key,d.page_count FROM document d
                 JOIN blob b USING (sha256) WHERE d.id=%s""",
            (args.document,),
        )
        row = cur.fetchone()
        if row is None:
            raise SystemExit("document not found")
        object_key, page_count = row
        if not 1 <= args.page <= page_count:
            raise SystemExit("page outside document")

    with pymupdf.open(root / object_key) as pdf:
        tsv, dpi = _ocr_page(pdf[args.page - 1], args.lang)
    blocks, _, confidence_sum, word_count = _blocks_from_tsv(
        tsv, args.page, 0, dpi / 72.0,
    )
    if not blocks:
        raise SystemExit("OCR produced no candidate blocks")
    text = "\n".join(block.text for block in blocks)
    confidence = confidence_sum / word_count / 100.0 if word_count else None
    payload = [
        {"block_no": b.block_no, "bbox": [b.x0, b.y0, b.x1, b.y1],
         "text": b.text, "script": b.script, "confidence": b.confidence}
        for b in blocks
    ]
    engine = f"tesseract-{_tesseract_version()}"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO page_ocr_candidate
                (document_id,page_no,engine,languages,dpi,text,mean_confidence,
                 word_count,blocks)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING id""",
            (args.document, args.page, engine, args.lang, dpi, text, confidence,
             word_count, json.dumps(payload, ensure_ascii=False)),
        )
        candidate_id = cur.fetchone()[0]
    print(f"candidate={candidate_id} document={args.document} page={args.page} "
          f"words={word_count} confidence={confidence:.4f} blocks={len(blocks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
