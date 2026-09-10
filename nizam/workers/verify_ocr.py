"""Verify lane E4 output — Document 02 §4: "legal-token checks plus human review
below threshold".

Lane E2 is verified by re-reading the PDF with a second library. That is not
available here: an E4 document is one whose PDF has no text layer at all, so
there is nothing independent to compare against. What can be checked is whether
what came out *reads like a statute*.

Three signals, and they catch different failures:

  CONFIDENCE     tesseract's own mean word confidence. Catches a bad scan.
  LEGAL TOKENS   the share of words that are ordinary statutory vocabulary.
                 Catches confident nonsense -- OCR will read a smudge as a
                 word and be sure about it.
  YIELD          words per page. Catches a page that was skipped or came back
                 nearly empty while the rest of the document looked fine.

A document failing any of them is not deleted. It is reported for human review,
which is what §4 asks for: OCR output is evidence of a different quality from a
text layer, and the corpus records which is which rather than pretending they
are the same.

    uv run python -m nizam.workers.verify_ocr
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys

from nizam.storage.db import connect

MIN_CONFIDENCE = 0.70
MIN_LEGAL_RATE = 0.25
MIN_WORDS_PER_PAGE = 40
VERIFIER = "nizam.verify_ocr/4"

# The same small vocabulary used to score the corpus: function words and
# statutory furniture that appear in essentially every English-language Act.
LEGAL = {
    "section", "sections", "sub", "act", "acts", "shall", "may", "any", "the",
    "of", "and", "or", "in", "to", "be", "is", "by", "for", "with", "under",
    "provided", "provisions", "provision", "government", "person", "persons",
    "order", "rules", "rule", "notification", "ordinance", "chapter", "clause",
    "punishment", "court", "power", "powers", "authority", "date", "year",
    "prescribed", "manner", "purpose", "purposes", "case", "law", "made",
}
WORD = re.compile(r"[a-z]{2,}")


def _words_per_page(recorded_words: object, pages: int) -> float:
    """Use Tesseract's script-independent accepted-word count for yield."""
    try:
        count = int(recorded_words or 0)
    except (TypeError, ValueError):
        count = 0
    return count / pages if pages else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify OCR output (full and mixed-page)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--document-id", nargs="+", type=int, metavar="ID",
                    help="verify exact OCR revision ids, including retired revisions")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure without appending verification evidence")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT d.id, d.sha256, d.page_count, d.char_count, d.printable_ratio,
                   d.language, d.pdf_metadata->>'ocr_words',
                   COALESCE(
                     (SELECT i.short_title FROM instrument i
                       WHERE i.document_id=d.id AND i.is_active
                       ORDER BY i.id LIMIT 1),
                     (SELECT s.source_metadata->>'title' FROM source_observation s
                       WHERE s.sha256 = d.sha256
                         AND s.source_metadata->>'title' IS NOT NULL LIMIT 1)),
                   d.lane,d.extractor_config,d.pdf_metadata->>'ocr_language'
              FROM document d
             WHERE (%s::boolean OR d.is_active) AND (d.lane = 'E4' OR EXISTS (
                       SELECT 1 FROM text_block b
                        WHERE b.document_id=d.id AND b.confidence IS NOT NULL))
               AND (%s::bigint[] IS NULL OR d.id=ANY(%s::bigint[]))
             ORDER BY d.printable_ratio""",
            (bool(a.document_id), a.document_id, a.document_id))
        docs = cur.fetchall()
        if not docs:
            print("no OCR documents to verify")
            return 0

        print(f"verifying {len(docs)} OCR-bearing document(s)\n")
        confs, rates, flagged = [], [], []

        for (doc_id, sha, pages, chars, conf, lang, words, title, lane,
             extractor_config, ocr_language) in docs:
            sparse_page_nos: list[int] = []
            confirmed_sparse_page_nos: list[int] = []
            table_source_review_id: int | None = None
            if lane == "E3":
                mixed = (extractor_config or {}).get("mixed_ocr", {})
                candidate_ids = [int(v) for v in mixed.get("candidate_ids", [])]
                cur.execute(
                    """SELECT page_no,word_count,mean_confidence
                         FROM page_ocr_candidate WHERE id=ANY(%s)
                         ORDER BY page_no,id""",
                    (candidate_ids,),
                )
                candidates = cur.fetchall()
                pages = len({row[0] for row in candidates})
                words = sum(row[1] for row in candidates)
                conf = (sum(float(row[2]) * row[1] for row in candidates)
                        / words if words else 0)
                sparse_page_nos = sorted({row[0] for row in candidates
                                          if row[1] < MIN_WORDS_PER_PAGE})
                if sparse_page_nos:
                    cur.execute(
                        """SELECT DISTINCT page_no FROM extraction_assertion
                            WHERE sha256=%s AND is_active
                              AND kind='source_content_confirmed'
                              AND detail->>'purpose'='ocr-sparse-page'
                              AND page_no=ANY(%s)""",
                        (sha, sparse_page_nos),
                    )
                    confirmed_sparse_page_nos = sorted(row[0]
                                                       for row in cur.fetchall())
                ocr_language = mixed.get("languages")
                text_where = " AND confidence IS NOT NULL"
            else:
                text_where = ""
            cur.execute(f"""SELECT coalesce(string_agg(text, ' ' ORDER BY reading_order), '')
                              FROM text_block WHERE document_id=%s{text_where}""",
                        (doc_id,))
            text = cur.fetchone()[0].lower()
            toks = WORD.findall(text)
            rate = (sum(1 for t in toks if t in LEGAL) / len(toks)) if toks else 0.0
            # `WORD` deliberately measures English legal vocabulary, so it
            # cannot also measure yield for Urdu/Sindhi. The OCR worker already
            # records Tesseract's script-independent accepted word count.
            per_page = _words_per_page(words, pages)
            conf = float(conf or 0)

            problems = []
            if conf < MIN_CONFIDENCE:
                problems.append(f"confidence {conf:.3f}")
            # Urdu output is not scored against an English vocabulary.
            english_only = (ocr_language in ("eng", "en")
                            or (not ocr_language and lang == "en"))
            if english_only and rate < MIN_LEGAL_RATE:
                cur.execute(
                    """SELECT id FROM extraction_assertion
                        WHERE sha256=%s AND page_no IS NULL AND is_active
                          AND kind='source_content_confirmed'
                          AND detail->>'purpose'='ocr-table-document'
                        ORDER BY asserted_at DESC,id DESC LIMIT 1""",
                    (sha,),
                )
                reviewed = cur.fetchone()
                table_source_review_id = reviewed[0] if reviewed else None
            if (english_only and rate < MIN_LEGAL_RATE
                    and table_source_review_id is None):
                problems.append(f"legal-token rate {rate:.3f}")
            sparse_source_confirmed = (
                bool(sparse_page_nos)
                and sparse_page_nos == confirmed_sparse_page_nos
            )
            if per_page < MIN_WORDS_PER_PAGE and not sparse_source_confirmed:
                problems.append(f"{per_page:.0f} words/page")

            confs.append(conf)
            if english_only:
                rates.append(rate)
            if problems:
                flagged.append((doc_id, sha, conf, rate, per_page, title, problems))
            elif a.verbose:
                print(f"  ok    #{doc_id:<5} conf={conf:.3f} legal={rate:.3f} "
                      f"{per_page:>5.0f} w/pg  {(title or '')[:44]}")

            outcome = "review" if problems else "passed"
            if not a.dry_run:
                cur.execute(
                    """INSERT INTO extraction_verification
                        (document_id,verifier,reference_extractor,outcome,
                         problems,detail)
                        VALUES (%s,%s,'tesseract-confidence+legal-token+yield',
                                %s,%s::jsonb,%s::jsonb)""",
                    (doc_id, VERIFIER, outcome,
                     json.dumps(problems, ensure_ascii=False),
                     json.dumps({"mean_confidence": conf,
                                 "legal_token_rate": round(rate, 6),
                                 "words_per_page": round(per_page, 3),
                                 "ocr_pages": pages,
                                 "ocr_words": int(words or 0),
                                 "ocr_language": ocr_language,
                                 "document_lane": lane,
                                 "sparse_page_nos": sparse_page_nos,
                                 "source_confirmed_sparse_page_nos":
                                     confirmed_sparse_page_nos,
                                 "table_source_review_assertion_id":
                                     table_source_review_id},
                                ensure_ascii=False)),
                )
                cur.execute("UPDATE document SET verification_state=%s WHERE id=%s",
                            (outcome, doc_id))

        for doc_id, sha, conf, rate, per_page, title, problems in flagged:
            print(f"  REVIEW #{doc_id:<5} {sha[:12]}  {'; '.join(problems)}")
            print(f"           {(title or '(untitled)')[:66]}")

        print()
        print(f"OCR-bearing docs {len(docs)}")
        print(f"needing review   {len(flagged)}")
        print(f"mean confidence  {statistics.mean(confs):.4f}")
        print(f"median           {statistics.median(confs):.4f}")
        print(f"worst            {min(confs):.4f}")
        print(f"above 0.90       {sum(1 for c in confs if c >= 0.90)}/{len(confs)}")
        print(f"above 0.80       {sum(1 for c in confs if c >= 0.80)}/{len(confs)}")
        if rates:
            print(f"mean legal-token {statistics.mean(rates):.4f}  "
                  f"(English documents; the clean-text corpus averages ~0.42)")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
