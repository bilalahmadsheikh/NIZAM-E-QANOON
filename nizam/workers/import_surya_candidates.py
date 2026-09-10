"""Import Surya results as non-destructive page OCR candidates.

Surya is an independent second reading, never an automatic replacement.  This
loader preserves its raw HTML, confidence, reading order and geometry while
scaling image pixels back into the PDF-point coordinate system used by Nizam.

Input file stems start with the active document id.  A rendered single-page
image may use ``<document-id>-page<source-page>``; PDF results use their normal
one-based page number.

    POSTGRES_DB=nizam_clean uv run python -m \
      nizam.workers.import_surya_candidates results.json
"""
from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from nizam.storage.db import connect

ENGINE = "surya-ocr-0.22.1+surya-2-gguf+llama.cpp-b10516"
_DOC_ID = re.compile(r"^(\d+)(?:-page(\d+))?$")
_WORD = re.compile(r"\w+", re.UNICODE)
_ARABIC = re.compile(r"[\u0600-\u06ff]")


class _TextExtractor(HTMLParser):
    """Retain meaningful HTML boundaries without storing markup as text."""

    BREAKS = {"br", "p", "div", "li", "tr", "table", "h1", "h2", "h3",
              "h4", "h5", "h6"}
    CELLS = {"td", "th"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.BREAKS and self.parts:
            self.parts.append("\n")
        elif tag in self.CELLS and self.parts:
            self.parts.append("\t")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BREAKS:
            self.parts.append("\n")
        elif tag in self.CELLS:
            self.parts.append("\t")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(html.unescape(value or ""))
    text = "".join(parser.parts)
    text = re.sub(r"\t+", "\t", text)
    text = re.sub(r"\n[\n\t ]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return unicodedata.normalize("NFC", text.strip(" \t\n"))


def parse_result_name(name: str, result_page: int) -> tuple[int, int]:
    match = _DOC_ID.fullmatch(name)
    if not match:
        raise ValueError(f"result key {name!r} is not <document-id>[-pageN]")
    document_id = int(match.group(1))
    source_page = int(match.group(2)) if match.group(2) else result_page
    return document_id, source_page


def _scaled_blocks(raw_blocks: list[dict], image_bbox: list[float],
                   page_width: float, page_height: float) -> tuple[list[dict], str,
                                                                   float | None, int]:
    image_width = float(image_bbox[2]) - float(image_bbox[0])
    image_height = float(image_bbox[3]) - float(image_bbox[1])
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Surya result has a non-positive image bbox")
    sx, sy = page_width / image_width, page_height / image_height
    blocks: list[dict] = []
    weighted_confidence = 0.0
    weighted_words = 0
    text_parts = []
    for fallback_order, raw in enumerate(sorted(
            raw_blocks, key=lambda block: block.get("reading_order", 10**9))):
        text = html_to_text(raw.get("html", ""))
        if not text:
            continue
        x0, y0, x1, y1 = (float(v) for v in raw["bbox"])
        confidence = raw.get("confidence")
        word_count = len(_WORD.findall(text))
        if confidence is not None:
            weighted_confidence += float(confidence) * max(word_count, 1)
            weighted_words += max(word_count, 1)
        order = int(raw.get("reading_order", fallback_order))
        blocks.append({
            "block_no": order,
            "reading_order": order,
            "bbox": [round(x0 * sx, 3), round(y0 * sy, 3),
                     round(x1 * sx, 3), round(y1 * sy, 3)],
            "text": text,
            "script": "arabic" if _ARABIC.search(text) else "latin",
            "confidence": round(float(confidence), 4) if confidence is not None else None,
            "label": raw.get("label"),
            "raw_label": raw.get("raw_label"),
            "html": raw.get("html", ""),
            "skipped": bool(raw.get("skipped", False)),
            "error": bool(raw.get("error", False)),
        })
        text_parts.append(text)
    combined = "\n\n".join(text_parts)
    mean_confidence = (weighted_confidence / weighted_words
                       if weighted_words else None)
    return blocks, combined, mean_confidence, len(_WORD.findall(combined))


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Surya JSON as OCR candidates")
    parser.add_argument("results", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--document-id", type=int,
                        help="source document for a one-page result whose input stem is unavailable")
    parser.add_argument("--page-no", type=int,
                        help="source page for --document-id (defaults to the result page)")
    args = parser.parse_args()
    payload = json.loads(args.results.read_text(encoding="utf-8"))

    result_count = sum(len(pages) for pages in payload.values())
    if args.document_id is not None and result_count != 1:
        parser.error("--document-id is allowed only for a JSON file containing exactly one page")
    if args.page_no is not None and args.document_id is None:
        parser.error("--page-no requires --document-id")

    inserted = existing = pages_seen = 0
    with connect() as conn, conn.cursor() as cur:
        for name, pages in payload.items():
            for result in pages:
                if args.document_id is not None:
                    document_id = args.document_id
                    page_no = args.page_no or int(result["page"])
                else:
                    document_id, page_no = parse_result_name(name, int(result["page"]))
                cur.execute(
                    """SELECT p.width,p.height,d.is_active
                         FROM page p JOIN document d ON d.id=p.document_id
                        WHERE p.document_id=%s AND p.page_no=%s""",
                    (document_id, page_no),
                )
                source = cur.fetchone()
                if source is None:
                    raise ValueError(f"no source page {document_id}:{page_no}")
                width, height, active = source
                if not active:
                    raise ValueError(f"document {document_id} is not active")
                blocks, text, confidence, word_count = _scaled_blocks(
                    result.get("blocks", []), result["image_bbox"],
                    float(width), float(height),
                )
                image_width = float(result["image_bbox"][2])
                dpi = max(1, round(image_width / float(width) * 72))
                pages_seen += 1
                cur.execute(
                    """SELECT id FROM page_ocr_candidate
                        WHERE document_id=%s AND page_no=%s AND engine=%s
                          AND text=%s ORDER BY id DESC LIMIT 1""",
                    (document_id, page_no, ENGINE, text),
                )
                if cur.fetchone():
                    existing += 1
                    continue
                if args.dry_run:
                    print(f"would import {document_id}:{page_no} "
                          f"{word_count} words conf={confidence}")
                    continue
                cur.execute(
                    """INSERT INTO page_ocr_candidate
                       (document_id,page_no,engine,languages,dpi,text,
                        mean_confidence,word_count,blocks,origin_document_id)
                       VALUES (%s,%s,%s,'multilingual-auto',%s,%s,%s,%s,%s::jsonb,%s)""",
                    (document_id, page_no, ENGINE, dpi, text, confidence,
                     word_count, json.dumps(blocks, ensure_ascii=False), document_id),
                )
                inserted += 1
    print(f"Surya pages seen {pages_seen}; inserted {inserted}; already present {existing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
