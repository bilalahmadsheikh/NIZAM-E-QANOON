"""Detect printable-but-garbled text layers using language plausibility.

Printable-ratio catches broken Unicode, while the sequence verifier catches
decoder disagreement. Neither alone proves that readable English survived.
This verifier measures ordinary statutory/function-word density for
Latin-dominant documents and records replacement glyphs for every script.
Schedules, appendices and tabular notifications can dominate a perfectly valid
law, so a low whole-document rate is corroborated against the three strongest
substantive pages before it becomes a review.  A clean cover page alone is not
enough to hide damaged body text.
It is a review gate, never a deletion rule.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics

from nizam.storage.db import connect
from nizam.workers.verify_ocr import LEGAL, WORD

VERIFIER = "nizam.verify_text_quality/2"
MIN_TOKENS = 100
MIN_LEGAL_RATE = 0.15
NARRATIVE_PAGES = 3
_ARABIC = re.compile(r"[\u0600-\u06ff]")
_LATIN = re.compile(r"[A-Za-z]")


def _legal_rate(text: str) -> tuple[int, float]:
    tokens = WORD.findall(text.casefold())
    rate = sum(token in LEGAL for token in tokens) / len(tokens) if tokens else 0.0
    return len(tokens), rate


def score(text: str, page_texts: list[str] | None = None) -> dict:
    token_count, legal_rate = _legal_rate(text)
    latin = len(_LATIN.findall(text))
    arabic = len(_ARABIC.findall(text))
    latin_dominant = latin >= max(100, arabic * 2)
    eligible_page_rates = sorted(
        (rate for page in (page_texts or [])
         for count, rate in [_legal_rate(page)] if count >= MIN_TOKENS),
        reverse=True,
    )
    corroborating = eligible_page_rates[:min(NARRATIVE_PAGES,
                                              len(eligible_page_rates))]
    # The weakest of the three strongest pages is the corroboration floor.  In
    # other words, a long document needs three plausible narrative pages; one
    # clean cover cannot mask printable garbage in the body.
    narrative_rate = min(corroborating) if corroborating else legal_rate
    problems = []
    if "\ufffd" in text:
        problems.append(f"{text.count(chr(0xfffd))} replacement glyphs")
    if (latin_dominant and token_count >= MIN_TOKENS
            and legal_rate < MIN_LEGAL_RATE and narrative_rate < MIN_LEGAL_RATE):
        problems.append(
            f"legal/function-word rate {legal_rate:.3f} and "
            f"narrative-page floor {narrative_rate:.3f}<{MIN_LEGAL_RATE}"
        )
    return {"tokens": token_count, "latin_chars": latin, "arabic_chars": arabic,
            "latin_dominant": latin_dominant, "legal_rate": round(legal_rate, 6),
            "eligible_text_pages": len(eligible_page_rates),
            "narrative_page_floor": round(narrative_rate, 6),
            "replacement_glyphs": text.count("\ufffd"), "problems": problems}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--document-id", nargs="+", type=int)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure without appending verification evidence")
    args = ap.parse_args()
    if not args.all and not args.document_id:
        ap.error("use --all or --document-id")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT d.id,d.sha256,coalesce(x.full_text,''),
                      coalesce(x.page_texts,ARRAY[]::text[])
                 FROM document d
                 LEFT JOIN LATERAL (
                   SELECT string_agg(p.page_text,' ' ORDER BY p.page_no) full_text,
                          array_agg(p.page_text ORDER BY p.page_no) page_texts
                     FROM (
                       SELECT b.page_no,
                              string_agg(b.text,' ' ORDER BY b.reading_order) page_text
                         FROM text_block b
                        WHERE b.document_id=d.id AND b.confidence IS NULL
                        GROUP BY b.page_no
                     ) p
                 ) x ON true
                WHERE d.is_active AND d.lane<>'E4'
                  AND (%s::bigint[] IS NULL OR d.id=ANY(%s::bigint[]))
                ORDER BY d.id""",
            (args.document_id, args.document_id),
        )
        rows = cur.fetchall()
        flagged = []
        rates = []
        printed = 0
        for document_id, sha, text, page_texts in rows:
            result = score(text, page_texts)
            if result["latin_dominant"] and result["tokens"] >= MIN_TOKENS:
                rates.append(result["legal_rate"])
            outcome = "review" if result["problems"] else "passed"
            if not args.dry_run:
                cur.execute(
                    """INSERT INTO extraction_verification
                        (document_id,verifier,reference_extractor,outcome,problems,detail)
                        VALUES (%s,%s,'statutory-language-plausibility',%s,%s::jsonb,%s::jsonb)""",
                    (document_id, VERIFIER, outcome,
                     json.dumps(result["problems"], ensure_ascii=False),
                     json.dumps({k: v for k, v in result.items() if k != "problems"},
                                ensure_ascii=False)),
                )
            if result["problems"]:
                flagged.append((document_id, sha, result))
                if not args.dry_run:
                    cur.execute("UPDATE document SET verification_state='review' WHERE id=%s",
                                (document_id,))
                if printed < 50:
                    print(f"  REVIEW #{document_id} {sha[:12]}: "
                          f"{'; '.join(result['problems'])}")
                    printed += 1
            elif args.verbose:
                print(f"  ok #{document_id} legal={result['legal_rate']:.3f} "
                      f"tokens={result['tokens']}")

    print(f"checked {len(rows)}; review {len(flagged)}")
    if rates:
        print(f"Latin statutory-language rate: mean {statistics.mean(rates):.4f}, "
              f"median {statistics.median(rates):.4f}, worst {min(rates):.4f}")
    if len(flagged) > printed:
        print(f"review details shown {printed}/{len(flagged)}")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
