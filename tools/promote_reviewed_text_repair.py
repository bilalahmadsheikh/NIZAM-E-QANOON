"""Promote a narrowly reviewed text repair as a new document revision.

This tool never edits or deletes source evidence. It requires an active quality
assertion, copies every page/block, applies only the explicitly requested
replacement-glyph stripping or block suppression, and lets save_document retain
the former extraction as an immutable predecessor.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nizam.corpus.extract import _printable_ratio
from nizam.shared.corpus_types import ExtractedBlock, ExtractedDocument, ExtractedPage
from nizam.storage import corpus_write
from nizam.storage.db import connect


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--document", type=int, required=True)
    ap.add_argument("--assertion", type=int, required=True)
    ap.add_argument("--strip-replacement", action="store_true")
    ap.add_argument("--drop-block", action="append", default=[], metavar="PAGE:BLOCK")
    ap.add_argument(
        "--replace-json", type=Path,
        help="UTF-8 JSON object mapping PAGE:BLOCK to an exact reviewed replacement",
    )
    args = ap.parse_args()
    drops = {tuple(map(int, value.split(":"))) for value in args.drop_block}
    replacements = {}
    if args.replace_json:
        raw = json.loads(args.replace_json.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not raw:
            ap.error("--replace-json must contain a non-empty JSON object")
        try:
            replacements = {tuple(map(int, key.split(":"))): value
                            for key, value in raw.items()}
        except (AttributeError, TypeError, ValueError):
            ap.error("replacement keys must be PAGE:BLOCK and values must be text")
        if any(not isinstance(value, str) or not value.strip()
               for value in replacements.values()):
            ap.error("replacement values must be non-empty strings")
    if not args.strip_replacement and not drops and not replacements:
        ap.error("request --strip-replacement, --drop-block and/or --replace-json")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT d.sha256,d.language,d.publication_role,d.page_count,d.lane,
                      d.extractor,d.extractor_config,d.pdf_metadata,a.id
                 FROM document d JOIN extraction_assertion a
                   ON a.id=%s AND a.sha256=d.sha256 AND a.is_active
                WHERE d.id=%s AND d.is_active""",
            (args.assertion, args.document),
        )
        row = cur.fetchone()
        if row is None:
            raise SystemExit("active document/assertion pair not found")
        sha, language, role, page_count, lane, extractor, config, metadata, _ = row
        cur.execute(
            """SELECT page_no,width,height,lane,crop_box,media_box
                 FROM page WHERE document_id=%s ORDER BY page_no""",
            (args.document,),
        )
        page_rows = cur.fetchall()
        cur.execute(
            """SELECT page_no,block_no,x0,y0,x1,y1,text,script,confidence,inside_cropbox
                 FROM text_block WHERE document_id=%s ORDER BY reading_order""",
            (args.document,),
        )
        block_rows = cur.fetchall()

    blocks = []
    removed_chars = removed_blocks = replaced_blocks = 0
    seen_replacements = set()
    for r in block_rows:
        if (r[0], r[1]) in drops:
            removed_blocks += 1
            removed_chars += len(r[6])
            continue
        text = r[6]
        locator = (r[0], r[1])
        if locator in replacements:
            text = replacements[locator]
            seen_replacements.add(locator)
            replaced_blocks += 1
        if args.strip_replacement:
            cleaned = text.replace("\ufffd", "")
            removed_chars += len(text) - len(cleaned)
            text = cleaned
        if not text.strip():
            removed_blocks += 1
            continue
        blocks.append(ExtractedBlock(
            page_no=r[0], block_no=r[1], reading_order=len(blocks),
            x0=float(r[2]), y0=float(r[3]), x1=float(r[4]), y1=float(r[5]),
            text=text, script=r[7],
            confidence=float(r[8]) if r[8] is not None else None,
            inside_cropbox=r[9],
        ))
    missing_replacements = set(replacements) - seen_replacements
    if missing_replacements:
        raise SystemExit(
            "replacement block(s) not found: "
            + ", ".join(f"{page}:{block}" for page, block in sorted(missing_replacements))
        )
    chars_by_page = {}
    for block in blocks:
        chars_by_page[block.page_no] = chars_by_page.get(block.page_no, 0) + len(block.text)
    pages = [ExtractedPage(
        page_no=r[0], width=float(r[1]), height=float(r[2]),
        char_count=chars_by_page.get(r[0], 0), lane=r[3],
        crop_box=tuple(float(v) for v in r[4]) if r[4] else None,
        media_box=tuple(float(v) for v in r[5]) if r[5] else None,
    ) for r in page_rows]
    empty_pages = sum(page.char_count == 0 for page in pages)
    if lane == "E2" and empty_pages:
        lane = "E3"
    text = "".join(block.text for block in blocks)
    config = dict(config or {})
    config["reviewed_text_repair"] = {
        "assertion_id": args.assertion,
        "strip_replacement": args.strip_replacement,
        "dropped_blocks": sorted([list(v) for v in drops]),
        "replaced_blocks": sorted([list(v) for v in replacements]),
        "removed_chars": removed_chars,
        "removed_blocks": removed_blocks,
    }
    doc = ExtractedDocument(
        sha256=sha, language=language, publication_role=role,
        page_count=page_count, char_count=len(text),
        printable_ratio=round(_printable_ratio(text), 4),
        empty_pages=empty_pages, lane=lane,
        extractor=f"{extractor}+reviewed-text-repair",
        extractor_config=config, pdf_metadata=dict(metadata or {}),
        pages=pages, blocks=blocks,
    )
    new_id = corpus_write.save_document(doc)
    corpus_write.record_attempt(
        sha, doc.extractor, "extracted", lane=doc.lane, document_id=new_id,
        detail={"recovery": "reviewed-text-repair",
                "predecessor_document_id": args.document,
                "assertion_id": args.assertion,
                "removed_chars": removed_chars,
                "removed_blocks": removed_blocks,
                "replaced_blocks": replaced_blocks},
    )
    print(f"{args.document} -> {new_id}; removed_chars={removed_chars} "
          f"removed_blocks={removed_blocks} replaced_blocks={replaced_blocks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
