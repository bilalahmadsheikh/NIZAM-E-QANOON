"""Run EasyOCR as an append-only, independently reviewable OCR candidate.

This tool never changes active text blocks or document revisions.  It can emit
JSON for a visual benchmark and, when a source document/page is supplied,
append the same result to ``page_ocr_candidate`` with PDF-point geometry.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path

from PIL import Image


def _bbox(points: list[list[float]]) -> list[float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--languages", default="ur,en")
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--decoder", choices=("greedy", "beamsearch", "wordbeamsearch"),
                        default="beamsearch")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--document", type=int)
    parser.add_argument("--page", type=int)
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()
    if (args.document is None) != (args.page is None):
        parser.error("--document and --page must be supplied together")

    # Import lazily so --help remains usable without the optional benchmark stack.
    import easyocr

    languages = [value.strip() for value in args.languages.split(",") if value.strip()]
    reader = easyocr.Reader(
        languages,
        gpu=False,
        model_storage_directory=str(args.models),
        download_enabled=True,
        verbose=True,
    )
    results = reader.readtext(
        str(args.image),
        decoder=args.decoder,
        detail=1,
        paragraph=False,
        batch_size=1,
        workers=0,
        rotation_info=[90, 180, 270],
        contrast_ths=0.05,
        adjust_contrast=0.7,
    )
    blocks = []
    weighted_confidence = 0.0
    words = 0
    for order, (points, text, confidence) in enumerate(results):
        token_count = max(1, len(text.split()))
        weighted_confidence += float(confidence) * token_count
        words += token_count
        blocks.append({
            "block_no": order,
            "reading_order": order,
            "bbox_pixels": _bbox(points),
            "polygon_pixels": [[round(float(x), 3), round(float(y), 3)]
                               for x, y in points],
            "text": text,
            "confidence": round(float(confidence), 6),
        })
    text = "\n".join(block["text"] for block in blocks)
    mean_confidence = weighted_confidence / words if words else None
    version = importlib.metadata.version("easyocr")
    payload = {
        "engine": f"easyocr-{version}",
        "languages": languages,
        "decoder": args.decoder,
        "image": str(args.image),
        "word_count": words,
        "mean_confidence": mean_confidence,
        "text": text,
        "blocks": blocks,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if args.document is not None:
        from nizam.storage.db import connect

        with Image.open(args.image) as image:
            image_width, image_height = image.size
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT p.width,p.height,d.is_active
                     FROM page p JOIN document d ON d.id=p.document_id
                    WHERE p.document_id=%s AND p.page_no=%s""",
                (args.document, args.page),
            )
            source = cur.fetchone()
            if source is None:
                raise SystemExit("source page not found")
            width, height, active = source
            if not active:
                raise SystemExit("source document is not active")
            sx, sy = float(width) / image_width, float(height) / image_height
            stored_blocks = []
            for block in blocks:
                x0, y0, x1, y1 = block["bbox_pixels"]
                stored_blocks.append({
                    **block,
                    "bbox": [round(x0 * sx, 3), round(y0 * sy, 3),
                             round(x1 * sx, 3), round(y1 * sy, 3)],
                })
            engine = f"easyocr-{version}+{args.decoder}+rotations"
            cur.execute(
                """SELECT id FROM page_ocr_candidate
                    WHERE document_id=%s AND page_no=%s AND engine=%s
                      AND text=%s ORDER BY id DESC LIMIT 1""",
                (args.document, args.page, engine, text),
            )
            existing = cur.fetchone()
            if existing:
                print(f"candidate already exists: {existing[0]}")
            else:
                cur.execute(
                    """INSERT INTO page_ocr_candidate
                       (document_id,page_no,engine,languages,dpi,text,
                        mean_confidence,word_count,blocks,origin_document_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                       RETURNING id""",
                    (args.document, args.page, engine, "+".join(languages),
                     args.dpi, text, mean_confidence, words,
                     json.dumps(stored_blocks, ensure_ascii=False), args.document),
                )
                print(f"candidate inserted: {cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
