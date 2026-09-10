"""OCR-test documents whose printable PDF text is locally distorted.

The sequence verifier catches embedded-font mappings that produce printable
gibberish.  This worker does not assume OCR is better: it compares the current
text and OCR candidate, and promotes only candidates that clear conservative
confidence, yield, coverage and legal-language improvement gates.  The former
text-layer document is retained as an immutable predecessor.
"""
from __future__ import annotations

import argparse
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from nizam.corpus.ocr import ocr_pdf
from nizam.storage import corpus_write
from nizam.storage.db import connect
from nizam.workers.verify_ocr import LEGAL, WORD

ROOT = Path(__import__("os").environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))


def _legal_rate(text: str) -> float:
    tokens = WORD.findall(text.casefold())
    return sum(token in LEGAL for token in tokens) / len(tokens) if tokens else 0.0


def _one(task: tuple[int, str, str, int, float, float]) -> dict:
    document_id, sha, object_key, current_chars, score, current_legal = task
    started = time.time()
    out = {"document_id": document_id, "sha256": sha, "score": score,
           "current_chars": current_chars, "current_legal": current_legal}
    try:
        doc = ocr_pdf((ROOT / object_key).read_bytes(), sha)
        text = " ".join(block.text for block in doc.blocks)
        out.update(doc=doc, ocr_legal=_legal_rate(text),
                   words=int(doc.pdf_metadata.get("ocr_words", 0)),
                   confidence=float(doc.printable_ratio),
                   ms=int((time.time() - started) * 1000))
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:500]
    return out


def _clear_improvement(result: dict) -> tuple[bool, list[str]]:
    doc = result["doc"]
    pages = max(doc.page_count, 1)
    words_per_page = result["words"] / pages
    coverage = doc.char_count / max(result["current_chars"], 1)
    legal_gain = result["ocr_legal"] - result["current_legal"]
    # A severely broken font map can make otherwise good OCR score below the
    # normal 0.80 confidence floor. Permit a labelled review-grade rescue only
    # when several independent signals agree that OCR is materially better.
    severe_rescue = (
        doc.language == "en" and result["ocr_legal"] >= 0.24
        and coverage >= 0.75
        and ((legal_gain >= 0.15
              and ((result["score"] < 0.40 and result["confidence"] >= 0.65)
                   or result["confidence"] >= 0.70))
             or (legal_gain >= 0.10 and coverage >= 1.0
                 and result["confidence"] >= 0.65))
    )
    if severe_rescue:
        return True, ["review-grade severe-font rescue"]
    reasons = []
    if result["confidence"] < 0.80:
        reasons.append(f"confidence {result['confidence']:.3f}<0.80")
    if words_per_page < 20:
        reasons.append(f"yield {words_per_page:.1f}<20 words/page")
    if coverage < 0.50:
        reasons.append(f"character coverage {coverage:.3f}<0.50")
    if doc.language == "en":
        if result["ocr_legal"] < 0.25:
            reasons.append(f"OCR legal rate {result['ocr_legal']:.3f}<0.25")
        if result["ocr_legal"] < result["current_legal"] + 0.05:
            reasons.append(
                f"legal improvement {result['ocr_legal'] - result['current_legal']:.3f}<0.05"
            )
    else:
        arabic = len(re.findall(r"[\u0600-\u06ff]", " ".join(b.text for b in doc.blocks)))
        if arabic < 50:
            reasons.append(f"Urdu/Arabic yield {arabic}<50 characters")
    return not reasons, reasons


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-score", type=float, default=0.60)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--promote-clear", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--document-id", nargs="+", type=int)
    args = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """WITH latest AS (
                   SELECT DISTINCT ON (document_id) document_id,
                          (detail->>'block_five_gram_precision')::numeric score
                     FROM extraction_verification
                    WHERE verifier='nizam.verify_order/3'
                    ORDER BY document_id,verified_at DESC,id DESC)
               SELECT d.id,d.sha256,b.object_key,d.char_count,l.score,
                      coalesce(string_agg(t.text,' ' ORDER BY t.reading_order),'')
                 FROM latest l JOIN document d ON d.id=l.document_id
                 JOIN blob b USING(sha256)
                 LEFT JOIN text_block t ON t.document_id=d.id
                WHERE d.is_active AND d.lane<>'E4' AND l.score<=%s
                  AND (%s::bigint[] IS NULL OR d.id=ANY(%s::bigint[]))
                GROUP BY d.id,d.sha256,b.object_key,d.char_count,l.score
                ORDER BY l.score,d.id""",
            (args.max_score, args.document_id, args.document_id),
        )
        rows = cur.fetchall()
    tasks = [(r[0], r[1], r[2], r[3], float(r[4]), _legal_rate(r[5])) for r in rows]
    if args.limit:
        tasks = tasks[:args.limit]
    print(f"OCR-testing {len(tasks)} severe text-layer document(s)")
    promoted = clear = failed = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_one, task): task for task in tasks}
        for n, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if "error" in result:
                failed += 1
                print(f"  FAIL   #{result['document_id']} {result['error']}", flush=True)
                continue
            ok, reasons = _clear_improvement(result)
            if ok:
                clear += 1
            action = "CLEAR" if ok else "REVIEW"
            if ok and args.promote_clear:
                doc = result["doc"]
                new_id = corpus_write.save_document(doc)
                corpus_write.record_attempt(
                    result["sha256"], doc.extractor, "extracted", lane="E4",
                    document_id=new_id,
                    detail={"recovery": "severe-sequence-distortion",
                            "predecessor_document_id": result["document_id"],
                            "block_five_gram_precision": result["score"],
                            "previous_legal_rate": round(result["current_legal"], 4),
                            "ocr_legal_rate": round(result["ocr_legal"], 4),
                            "ocr_confidence": result["confidence"],
                            "ocr_words": result["words"]},
                    duration_ms=result["ms"],
                )
                promoted += 1
                action = f"PROMOTE->{new_id}"
            doc = result["doc"]
            print(f"  {n:>3}/{len(tasks)} {action:<14} old=#{result['document_id']} "
                  f"score={result['score']:.3f} conf={result['confidence']:.3f} "
                  f"legal={result['current_legal']:.3f}->{result['ocr_legal']:.3f} "
                  f"chars={result['current_chars']}->{doc.char_count}"
                  f"{'  ' + '; '.join(reasons) if reasons else ''}", flush=True)
    print(f"clear={clear} promoted={promoted} review={len(tasks)-clear-failed} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
