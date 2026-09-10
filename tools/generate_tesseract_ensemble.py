"""Create source-preserving OCR candidates from deterministic image variants.

The active extraction is never modified.  Each distinct reading is appended to
``page_ocr_candidate`` with the preprocessing recipe, language model, PSM and
PDF-point geometry needed for later side-by-side adjudication.
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path

import pymupdf
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from nizam.corpus.ocr import RENDER_DPI, _blocks_from_tsv, _tesseract, _tesseract_version
from nizam.storage.db import connect

ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))


def preprocess(raw: bytes, variant: str) -> bytes:
    with Image.open(io.BytesIO(raw)) as opened:
        image = opened.convert("L")
        if variant == "original":
            result = image
        elif variant == "autocontrast":
            result = ImageOps.autocontrast(image, cutoff=1)
        elif variant == "unsharp":
            base = ImageOps.autocontrast(image, cutoff=1)
            result = base.filter(ImageFilter.UnsharpMask(radius=1.4, percent=170,
                                                          threshold=3))
        elif variant == "threshold":
            # Derive a page-specific global threshold from the grayscale
            # histogram.  This is deterministic and especially useful for
            # yellowed or low-contrast Gazette scans.
            histogram = image.histogram()
            total = sum(histogram)
            weighted = sum(level * count for level, count in enumerate(histogram))
            threshold = max(120, min(220, round(weighted / max(total, 1) * 0.82)))
            result = ImageOps.autocontrast(image, cutoff=1).point(
                lambda value: 255 if value >= threshold else 0, mode="1")
        else:
            raise ValueError(f"unknown variant {variant}")
        buffer = io.BytesIO()
        result.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", type=int, required=True)
    parser.add_argument("--page", type=int, action="append",
                        help="repeat for selected pages; default is every page")
    parser.add_argument("--languages", default="eng")
    parser.add_argument("--dpi", type=int, default=RENDER_DPI)
    parser.add_argument("--variants", default="original,autocontrast,unsharp,threshold")
    parser.add_argument("--psms", default="3,4,6,11")
    args = parser.parse_args()
    variants = [value.strip() for value in args.variants.split(",") if value.strip()]
    psms = [int(value) for value in args.psms.split(",") if value.strip()]

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT b.object_key,d.page_count,d.is_active
                 FROM document d JOIN blob b USING (sha256) WHERE d.id=%s""",
            (args.document,),
        )
        source = cur.fetchone()
    if source is None:
        raise SystemExit("document not found")
    object_key, page_count, active = source
    if not active:
        raise SystemExit("document is not active")
    pages = sorted(set(args.page or range(1, page_count + 1)))
    if pages and (pages[0] < 1 or pages[-1] > page_count):
        raise SystemExit("page outside document")

    inserted = existing = empty = 0
    tessdata = "tessdata_best" if "tessdata_best" in os.environ.get(
        "TESSDATA_PREFIX", "") else "system-tessdata"
    version = _tesseract_version()
    with pymupdf.open(ROOT / object_key) as pdf:
        for page_no in pages:
            page = pdf[page_no - 1]
            raw = page.get_pixmap(dpi=args.dpi, colorspace=pymupdf.csGRAY).tobytes("png")
            for variant in variants:
                prepared = preprocess(raw, variant)
                for psm in psms:
                    tsv = _tesseract(prepared, args.languages, args.dpi, psm=psm)
                    blocks, _, confidence_sum, word_count = _blocks_from_tsv(
                        tsv, page_no, 0, args.dpi / 72.0,
                    )
                    text = "\n".join(block.text for block in blocks)
                    confidence = (confidence_sum / word_count / 100.0
                                  if word_count else None)
                    payload = [{
                        "block_no": block.block_no,
                        "reading_order": block.reading_order,
                        "bbox": [block.x0, block.y0, block.x1, block.y1],
                        "text": block.text,
                        "script": block.script,
                        "confidence": block.confidence,
                    } for block in blocks]
                    engine = (f"tesseract-{version}+{tessdata}+{variant}"
                              f"+psm{psm}+ensemble-v1")
                    with connect() as conn, conn.cursor() as cur:
                        cur.execute(
                            """SELECT id FROM page_ocr_candidate
                                WHERE document_id=%s AND page_no=%s
                                  AND engine=%s AND languages=%s AND text=%s
                                ORDER BY id DESC LIMIT 1""",
                            (args.document, page_no, engine, args.languages, text),
                        )
                        if cur.fetchone():
                            existing += 1
                        else:
                            cur.execute(
                                """INSERT INTO page_ocr_candidate
                                   (document_id,page_no,engine,languages,dpi,text,
                                    mean_confidence,word_count,blocks,origin_document_id)
                                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                                (args.document, page_no, engine, args.languages,
                                 args.dpi, text, confidence, word_count,
                                 json.dumps(payload, ensure_ascii=False), args.document),
                            )
                            inserted += 1
                    empty += word_count == 0
                    print(f"doc={args.document} page={page_no} {variant:<12} "
                          f"psm={psm:<2} words={word_count:<4} conf={confidence}",
                          flush=True)
    print(f"inserted={inserted} existing={existing} empty={empty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
