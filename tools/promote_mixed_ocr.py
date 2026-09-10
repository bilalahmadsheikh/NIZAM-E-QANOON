"""Promote accepted mixed-page OCR candidates into a new hybrid revision.

Only text-empty pages are eligible. The previous document, pages and blocks are
retired but retained; OCR blocks carry confidence and their page lane is E4.
"""
from __future__ import annotations

import argparse

from nizam.corpus.extract import _printable_ratio
from nizam.shared.corpus_types import ExtractedBlock, ExtractedDocument, ExtractedPage
from nizam.storage import corpus_write
from nizam.storage.db import connect


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-confidence", type=float, default=0.70)
    ap.add_argument("--min-words", type=int, default=3)
    ap.add_argument("--languages", default="urd+eng")
    args = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT DISTINCT d.id
                 FROM document d JOIN page p ON p.document_id=d.id
                 JOIN document cd ON cd.sha256=d.sha256
                 JOIN page_ocr_candidate c
                   ON c.document_id=cd.id AND c.page_no=p.page_no
                WHERE d.is_active AND d.lane='E3' AND p.char_count=0
                  AND c.languages=%s AND c.word_count>=%s
                  AND c.mean_confidence>=%s ORDER BY d.id""",
            (args.languages, args.min_words, args.min_confidence),
        )
        document_ids = [row[0] for row in cur.fetchall()]

    print(f"hybrid revisions: {len(document_ids)} documents")
    for old_id in document_ids:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT sha256,language,publication_role,page_count,char_count,
                          printable_ratio,empty_pages,extractor,extractor_config,
                          pdf_metadata
                     FROM document WHERE id=%s AND is_active FOR SHARE""",
                (old_id,),
            )
            row = cur.fetchone()
            if row is None:
                continue
            (sha, language, role, page_count, char_count, printable_ratio,
             empty_pages, extractor, config, metadata) = row
            cur.execute(
                """SELECT page_no,width,height,char_count,lane,crop_box,media_box
                     FROM page WHERE document_id=%s ORDER BY page_no""", (old_id,))
            page_rows = cur.fetchall()
            cur.execute(
                """SELECT page_no,block_no,reading_order,x0,y0,x1,y1,text,
                          script,confidence,inside_cropbox
                     FROM text_block WHERE document_id=%s
                     ORDER BY reading_order""", (old_id,))
            source_blocks = cur.fetchall()
            cur.execute(
                """SELECT DISTINCT ON (c.page_no) c.page_no,c.id,c.engine,c.dpi,
                          c.mean_confidence,c.word_count,c.blocks
                     FROM page_ocr_candidate c
                     JOIN document cd ON cd.id=c.document_id
                     JOIN document active ON active.id=%s AND active.sha256=cd.sha256
                     JOIN page p ON p.document_id=active.id AND p.page_no=c.page_no
                    WHERE p.char_count=0
                      AND c.languages=%s AND c.word_count>=%s
                      AND c.mean_confidence>=%s
                    ORDER BY c.page_no,c.created_at DESC,c.id DESC""",
                (old_id, args.languages, args.min_words, args.min_confidence),
            )
            candidates = {r[0]: r[1:] for r in cur.fetchall()}

        by_page: dict[int, list[ExtractedBlock]] = {}
        for r in source_blocks:
            by_page.setdefault(r[0], []).append(ExtractedBlock(
                page_no=r[0], block_no=r[1], reading_order=0,
                x0=float(r[3]), y0=float(r[4]), x1=float(r[5]), y1=float(r[6]),
                text=r[7], script=r[8], confidence=(float(r[9]) if r[9] is not None else None),
                inside_cropbox=r[10],
            ))
        promoted_chars: dict[int, int] = {}
        candidate_ids: list[int] = []
        for page_no, (candidate_id, _engine, _dpi, candidate_confidence,
                      _words, blocks) in candidates.items():
            candidate_ids.append(candidate_id)
            page_blocks = []
            for b in blocks:
                x0, y0, x1, y1 = b["bbox"]
                page_blocks.append(ExtractedBlock(
                    page_no=page_no, block_no=int(b["block_no"]), reading_order=0,
                    x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1),
                    text=b["text"], script=b.get("script"),
                    confidence=(float(b["confidence"])
                                if b.get("confidence") is not None
                                else float(candidate_confidence)),
                    inside_cropbox=True,
                ))
            by_page[page_no] = page_blocks
            promoted_chars[page_no] = sum(len(b.text) for b in page_blocks)

        blocks_out: list[ExtractedBlock] = []
        order = 0
        for page_no in range(1, page_count + 1):
            for b in by_page.get(page_no, []):
                blocks_out.append(ExtractedBlock(
                    page_no=b.page_no, block_no=b.block_no, reading_order=order,
                    x0=b.x0, y0=b.y0, x1=b.x1, y1=b.y1, text=b.text,
                    script=b.script, confidence=b.confidence,
                    inside_cropbox=b.inside_cropbox,
                ))
                order += 1

        pages_out = [ExtractedPage(
            page_no=r[0], width=float(r[1]), height=float(r[2]),
            char_count=promoted_chars.get(r[0], r[3]),
            lane="E4" if r[0] in promoted_chars else r[4],
            crop_box=tuple(float(v) for v in r[5]) if r[5] else None,
            media_box=tuple(float(v) for v in r[6]) if r[6] else None,
        ) for r in page_rows]
        config = dict(config or {})
        config["mixed_ocr"] = {
            "languages": args.languages, "min_confidence": args.min_confidence,
            "min_words": args.min_words, "candidate_ids": candidate_ids,
        }
        metadata = dict(metadata or {})
        metadata["mixed_ocr_pages"] = sorted(promoted_chars)
        metadata["mixed_ocr_candidate_ids"] = candidate_ids
        exact_text = "".join(b.text for b in blocks_out)
        exact_char_count = len(exact_text)
        exact_printable_ratio = round(_printable_ratio(exact_text), 4)
        doc = ExtractedDocument(
            sha256=sha, language=language, publication_role=role,
            page_count=page_count, char_count=exact_char_count,
            printable_ratio=exact_printable_ratio,
            empty_pages=empty_pages - len(promoted_chars), lane="E3",
            extractor=f"{extractor}+tesseract-mixed-page",
            extractor_config=config, pdf_metadata=metadata,
            pages=pages_out, blocks=blocks_out,
        )
        new_id = corpus_write.save_document(doc)
        corpus_write.record_attempt(
            sha, doc.extractor, "extracted", lane="E3", document_id=new_id,
            detail={"supersedes_document_id": old_id,
                    "promoted_pages": sorted(promoted_chars),
                    "candidate_ids": candidate_ids,
                    "promoted_chars": sum(promoted_chars.values())},
        )
        print(f"  {old_id} -> {new_id}: pages={len(promoted_chars)} "
              f"chars={sum(promoted_chars.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
