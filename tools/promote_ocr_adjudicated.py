"""Promote adjudicated OCR candidates into a new full-OCR revision (lane E4).

`promote_mixed_ocr.py` is the E3 sibling of this tool: it fills text-empty pages
in a document that otherwise has a real text layer. It cannot serve the Q1
documents, because their pages are not empty -- every page carries OCR text that
is simply wrong. Replacing a page that already has text is a different act from
filling one that has none, and it needs a different gate.

That gate is `page_ocr_adjudication`. Confidence ranks the review queue and never
authorises a promotion on its own (migration 0031); a candidate is promoted here
only because a person accepted it. This tool therefore reads decisions, not
scores -- it will refuse a document whose pages are merely high-confidence.

    # what would be promoted, and why
    POSTGRES_DB=nizam_clean uv run python -m tools.promote_ocr_adjudicated

    # actually write the revision
    POSTGRES_DB=nizam_clean uv run python -m tools.promote_ocr_adjudicated --apply

Dry run is the default, unlike the E3 sibling. This rewrites the text of a
document that already has text, so the safe direction is to make the writing
gesture explicit.

Two conventions this tool must honour, both discovered the hard way:

  printable_ratio IS THE OCR CONFIDENCE FOR LANE E4. `nizam/corpus/ocr.py`
  stores the word-weighted mean confidence in `document.printable_ratio`, and
  `nizam/workers/verify_ocr.py` reads that column back as `conf` for E4
  documents -- so Q1's threshold is tested against it, not against
  `avg(text_block.confidence)` (the two differ: 4503 is 0.3484 and 0.3759).
  A revision that wrote a literal printable ratio here would leave Q1 failing
  with pristine text. docs/SCHEMA.md documents only the E1-E3 meaning.

  THE CORPUS IS APPEND-ONLY. `corpus_write.save_document` retires the previous
  revision rather than deleting it (migration 0012), so the Tesseract reading
  survives as evidence for whatever the adjudication decided against.

Promotion changes the text under a segmentation that was built from the old
text, so the run is not finished when this tool exits -- see the closing notes
it prints.
"""
from __future__ import annotations

import argparse
import re

from nizam.shared.corpus_types import ExtractedBlock, ExtractedDocument, ExtractedPage
from nizam.storage import corpus_write
from nizam.storage.db import connect

# Same tokenizer as the candidate importer, so `ocr_words` stays comparable
# across a promotion rather than shifting because the counter changed.
_WORD = re.compile(r"\w+", re.UNICODE)


def weighted_confidence(pairs: list[tuple[str, float | None]]) -> tuple[float, int]:
    """Word-weighted mean confidence over (text, confidence) pairs.

    Returns the mean and the total word count. This is the E4 convention from
    `nizam/corpus/ocr.py`: weight by words rather than by block, so a page of
    one long paragraph is not outvoted by a page of six short captions, and
    count a block with no confidence toward the word total but not toward the
    mean. An empty input is 0.0 rather than an error -- a document with no text
    is a real state the corpus records, not an exception.
    """
    weighted = 0.0
    weighted_words = 0
    total_words = 0
    for text, confidence in pairs:
        words = len(_WORD.findall(text))
        total_words += words
        if confidence is not None:
            weighted += float(confidence) * max(words, 1)
            weighted_words += max(words, 1)
    mean = (weighted / weighted_words) if weighted_words else 0.0
    return mean, total_words

ELIGIBLE = """
SELECT d.id,
       count(DISTINCT p.page_no)                                   AS pages,
       count(DISTINCT acc.page_no)                                 AS accepted_pages
  FROM document d
  JOIN page p ON p.document_id = d.id
  LEFT JOIN (
        SELECT c.document_id, c.page_no
          FROM page_ocr_candidate c
          JOIN LATERAL (
                SELECT decision FROM page_ocr_adjudication a
                 WHERE a.candidate_id = c.id
                 ORDER BY a.decided_at DESC, a.id DESC LIMIT 1
          ) latest ON true
         WHERE latest.decision = 'accepted'
  ) acc ON acc.document_id = d.id AND acc.page_no = p.page_no
 WHERE d.is_active AND d.lane = 'E4'
   AND (%s::bigint[] IS NULL OR d.id = ANY(%s::bigint[]))
 GROUP BY d.id
HAVING count(DISTINCT acc.page_no) > 0
 ORDER BY d.id
"""

# The accepted candidate for each page. A page may only have one -- two accepted
# readings of the same page is a contradiction the reviewer has to resolve, and
# this tool reports it rather than picking.
ACCEPTED = """
SELECT c.page_no, c.id, c.engine, c.mean_confidence, c.word_count, c.blocks,
       a.id AS adjudication_id, a.decided_by
  FROM page_ocr_candidate c
  JOIN LATERAL (
        SELECT id, decision, decided_by FROM page_ocr_adjudication a
         WHERE a.candidate_id = c.id
         ORDER BY a.decided_at DESC, a.id DESC LIMIT 1
  ) a ON true
 WHERE c.document_id = %s AND a.decision = 'accepted'
 ORDER BY c.page_no, c.id
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Promote accepted OCR candidates into a new E4 revision")
    ap.add_argument("--document-id", nargs="+", type=int, metavar="ID",
                    help="restrict to these active document ids")
    ap.add_argument("--apply", action="store_true",
                    help="write the revisions; without it this only reports")
    ap.add_argument("--allow-partial", action="store_true",
                    help="promote a document where only some pages were "
                         "accepted, keeping the stored text for the rest")
    args = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(ELIGIBLE, (args.document_id, args.document_id))
        eligible = cur.fetchall()

    if not eligible:
        print("no documents have accepted OCR candidates.\n"
              "Adjudicate first -- v_ocr_adjudication_queue is the worklist, and\n"
              "v_ocr_adjudication_evidence shows the stored text beside the\n"
              "candidate for each page.")
        return 0

    promoted = skipped = 0
    for old_id, pages, accepted_pages in eligible:
        partial = accepted_pages < pages
        if partial and not args.allow_partial:
            print(f"  {old_id}: SKIP -- {accepted_pages}/{pages} pages accepted "
                  f"(use --allow-partial to promote anyway)")
            skipped += 1
            continue

        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT sha256,language,publication_role,page_count,
                          empty_pages,extractor,extractor_config,pdf_metadata
                     FROM document WHERE id=%s AND is_active FOR SHARE""",
                (old_id,))
            row = cur.fetchone()
            if row is None:
                continue
            (sha, language, role, page_count, empty_pages,
             extractor, config, metadata) = row
            cur.execute(
                """SELECT page_no,width,height,char_count,lane,crop_box,media_box
                     FROM page WHERE document_id=%s ORDER BY page_no""", (old_id,))
            page_rows = cur.fetchall()
            cur.execute(
                """SELECT page_no,block_no,x0,y0,x1,y1,text,script,confidence,
                          inside_cropbox
                     FROM text_block WHERE document_id=%s
                     ORDER BY reading_order""", (old_id,))
            stored_blocks = cur.fetchall()
            cur.execute(ACCEPTED, (old_id,))
            accepted = cur.fetchall()

        # Two accepted readings of one page is a contradiction, not a choice.
        seen: dict[int, int] = {}
        conflict = False
        for page_no, candidate_id, *_ in accepted:
            if page_no in seen:
                print(f"  {old_id}: SKIP -- page {page_no} has two accepted "
                      f"candidates ({seen[page_no]} and {candidate_id}); "
                      f"a reviewer must reject one")
                conflict = True
            seen[page_no] = candidate_id
        if conflict:
            skipped += 1
            continue

        by_page: dict[int, list[ExtractedBlock]] = {}
        for (page_no, block_no, x0, y0, x1, y1, text, script,
             confidence, inside) in stored_blocks:
            by_page.setdefault(page_no, []).append(ExtractedBlock(
                page_no=page_no, block_no=block_no, reading_order=0,
                x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1),
                text=text, script=script,
                confidence=(float(confidence) if confidence is not None else None),
                inside_cropbox=inside,
            ))

        promoted_chars: dict[int, int] = {}
        candidate_ids: list[int] = []
        adjudication_ids: list[int] = []
        deciders: set[str] = set()
        engines: set[str] = set()
        for (page_no, candidate_id, engine, mean_confidence, _words, blocks,
             adjudication_id, decided_by) in accepted:
            candidate_ids.append(candidate_id)
            adjudication_ids.append(adjudication_id)
            deciders.add(decided_by)
            engines.add(engine)
            page_blocks = []
            for b in blocks:
                x0, y0, x1, y1 = b["bbox"]
                page_blocks.append(ExtractedBlock(
                    page_no=page_no, block_no=int(b["block_no"]), reading_order=0,
                    x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1),
                    text=b["text"], script=b.get("script"),
                    confidence=(float(b["confidence"])
                                if b.get("confidence") is not None
                                else float(mean_confidence)),
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

        # The E4 confidence convention: word-weighted mean over every block that
        # carries one, written to printable_ratio because that is where
        # verify_ocr reads it. Weighting by words rather than by block matches
        # nizam/corpus/ocr.py, so a promoted revision is comparable with an
        # originally-OCR'd one.
        mean_confidence, ocr_words = weighted_confidence(
            [(b.text, b.confidence) for b in blocks_out])

        exact_text = "".join(b.text for b in blocks_out)
        pages_out = [ExtractedPage(
            page_no=r[0], width=float(r[1]), height=float(r[2]),
            char_count=promoted_chars.get(r[0], r[3]),
            lane=r[4],
            crop_box=tuple(float(v) for v in r[5]) if r[5] else None,
            media_box=tuple(float(v) for v in r[6]) if r[6] else None,
        ) for r in page_rows]

        config = dict(config or {})
        config["ocr_promotion"] = {
            "candidate_ids": candidate_ids,
            "adjudication_ids": adjudication_ids,
            "supersedes_document_id": old_id,
            "partial": partial,
        }
        metadata = dict(metadata or {})
        metadata["ocr_words"] = ocr_words
        metadata["ocr_promoted_pages"] = sorted(promoted_chars)
        metadata["ocr_promotion_candidate_ids"] = candidate_ids

        new_extractor = "+".join(sorted(engines)) or extractor
        doc = ExtractedDocument(
            sha256=sha, language=language, publication_role=role,
            page_count=page_count, char_count=len(exact_text),
            printable_ratio=round(min(max(mean_confidence, 0.0), 1.0), 4),
            empty_pages=empty_pages, lane="E4",
            extractor=new_extractor,
            extractor_config=config, pdf_metadata=metadata,
            pages=pages_out, blocks=blocks_out,
        )

        if not args.apply:
            print(f"  {old_id}: would promote {len(promoted_chars)}/{pages} pages, "
                  f"conf -> {doc.printable_ratio}, {ocr_words} words, "
                  f"{len(blocks_out)} blocks, decided by "
                  f"{', '.join(sorted(deciders))}")
            promoted += 1
            continue

        new_id = corpus_write.save_document(doc)
        corpus_write.record_attempt(
            sha, doc.extractor, "extracted", lane="E4", document_id=new_id,
            detail={"supersedes_document_id": old_id,
                    "promoted_pages": sorted(promoted_chars),
                    "candidate_ids": candidate_ids,
                    "adjudication_ids": adjudication_ids,
                    "promoted_chars": sum(promoted_chars.values()),
                    "confidence": float(doc.printable_ratio)},
        )
        print(f"  {old_id} -> {new_id}: {len(promoted_chars)}/{pages} pages, "
              f"conf {doc.printable_ratio}, {ocr_words} words")
        promoted += 1

    verb = "would promote" if not args.apply else "promoted"
    print(f"\n{verb} {promoted} document(s); skipped {skipped}")
    if args.apply and promoted:
        print(
            "\nThe promotion is not the whole job. The new revision carries new\n"
            "text under a segmentation built from the old text, so:\n"
            "  1. re-run verify_ocr over the promoted ids to refresh the verdict\n"
            "  2. re-segment them -- provisions still point at the retired blocks\n"
            "  3. ./nz audit-clean, and expect Q1 to move only after both")
    elif not args.apply:
        print("dry run -- nothing written. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
