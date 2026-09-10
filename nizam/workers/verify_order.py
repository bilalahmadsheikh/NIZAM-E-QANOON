"""Does the stored text say the same thing, in the same order?

`verify_extraction` compares CHARACTER multisets. That is the right test for
loss and fabrication -- it proves no content vanished and none was invented --
and it is blind to exactly one thing: **order**.

    "the dog bit the man"  and  "the man bit the dog"

have identical character multisets, identical word multisets, and completely
different meanings. A reading-order bug, a two-column page read straight across,
or a footnote spliced into the middle of a section would all pass a multiset
check and produce nonsense.

This checks sequence page-locally, because PDF decoders legitimately disagree
about where headers, marginal headings and columns sit in one global stream.
Comparing the whole document as one string therefore creates false alarms.

  ORDERED TRIPLES Three lexical words in stored order must occur within a
                  one-token window on the same independently decoded page.
                  This remains sensitive to transposition but tolerates a
                  decoder moving a superscript footnote marker into the run.

  BLOCK 5-GRAMS   Exact five-word runs are retained as a stricter diagnostic.
                  They are too brittle to gate by themselves: one differently
                  placed footnote number destroys five otherwise correct runs.

  SENTENCE COVER  For each sufficiently long source sentence, how many of its
                  five-word runs survive inside stored blocks on that page.
                  This answers whether the sentence pattern survived without
                  assuming identical line or block breaks.

Run after verify_extraction, not instead of it: this cannot see a page that was
dropped entirely, and that one can.

    uv run python -m nizam.workers.verify_order --sample 200
    uv run python -m nizam.workers.verify_order --all
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import statistics
import subprocess
import sys
import unicodedata
from pathlib import Path

from nizam.storage.db import connect

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))

# The release gate uses lexical ordered triples with one reference-side skip.
# Pure numeric tokens are checked by the character-completeness verifier and
# later by structural/citation gates; excluding them here prevents a superscript
# footnote location disagreement from masquerading as reordered legal prose.
# Keep the established 0.80 review floor, now applied to the insertion-tolerant
# metric. Retained known-bad predecessor #4024 scores 0.761, while direct-source
# checked document #4422 scores 0.999 (the brittle old metric scored 0.044).
MIN_ORDERED_TRIGRAM_PRECISION = 0.80
MIN_SENTENCE_COVERAGE = 0.85
MIN_REFERENCE_LEXICAL_WORDS = 6
VERIFIER = "nizam.verify_order/6"

_WORD = re.compile(r"\w+", re.UNICODE)
_HYPHENS = str.maketrans("", "", "-‐­")
# Legal prose is full of "s. 302", "No. 45", "Art. 8" -- splitting on every full
# stop would shred it. Require the following character to look like a new
# sentence: whitespace then an capital or a digit-with-parenthesis.
_SENTENCE = re.compile(r"(?<=[.;:])\s+(?=[A-Z0-9(])")


def words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold().translate(_HYPHENS)
    return _WORD.findall(text)


def ngrams(ws: list[str], n: int) -> collections.Counter:
    return collections.Counter(tuple(ws[i:i + n]) for i in range(len(ws) - n + 1))


def lexical_words(text: str) -> list[str]:
    """Words carrying letters; omit movable page/footnote number furniture.

    PDF decoders disagree on whether a superscript marker touching a word is
    `1Substituted` or `1` + `Substituted`. For sequence only, strip edge digits
    from alphanumeric words. The character verifier still checks every digit,
    and the legal-tree gate separately checks provision labels.
    """
    out = []
    for word in words(text):
        if not any(ch.isalpha() for ch in word):
            continue
        word = re.sub(r"^\d+|\d+$", "", word)
        if word:
            out.append(word)
    return out


# ---------------------------------------------------------------- script
# Whitespace is a reliable word boundary in Latin script. In the Arabic-derived
# scripts -- Urdu, Sindhi, Arabic -- it is not: the same visible line is
# tokenised completely differently by two decoders. Poppler emits
# "دنسھآرڈسننیربمن" as one token where PyMuPDF gives "دنسھ آرڈسننی ربمن", and a
# word-trigram comparison then scores near zero on text that is in fact correct.
#
# Measured on the two documents this rule was written for:
#
#   doc 4304   word-trigram 0.1576   character-trigram 0.9529   char recall 0.9998
#   doc 3842   word-trigram 0.1290   character-trigram 0.8594   char recall 0.9997
#
# The content is the same and the order is substantially right; only the unit of
# comparison was wrong. For such documents the stable unit is the CHARACTER, and
# the bidirectional control marks Poppler inserts must be removed first or they
# appear as spurious tokens in every gram.
_ARABIC_BLOCKS = (
    (0x0600, 0x06FF),   # Arabic
    (0x0750, 0x077F),   # Arabic Supplement
    (0x08A0, 0x08FF),   # Arabic Extended-A
    (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
)
# Explicit bidi controls plus the soft hyphen: formatting, never content.
_BIDI = dict.fromkeys(
    [0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
     0x2066, 0x2067, 0x2068, 0x2069, 0x00AD], None)
# Above this share of letters, treat the document as connected-script.
MIN_CONNECTED_SCRIPT_SHARE = 0.30


def connected_script_share(text: str) -> float:
    """Fraction of letters drawn from an Arabic-derived block."""
    letters = arabic = 0
    for ch in text:
        if not ch.isalpha():
            continue
        letters += 1
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in _ARABIC_BLOCKS):
            arabic += 1
    return arabic / letters if letters else 0.0


def script_characters(text: str) -> list[str]:
    """Every non-space character, bidi controls removed, order preserved."""
    text = unicodedata.normalize("NFKC", text).translate(_BIDI)
    return [ch for ch in text if not ch.isspace()]


def ordered_skip_trigrams(ws: list[str], max_skip: int = 1) -> collections.Counter:
    """Ordered triples allowing up to `max_skip` reference tokens per gap."""
    out: collections.Counter = collections.Counter()
    width = max_skip + 2
    for i in range(len(ws)):
        for j in range(i + 1, min(len(ws), i + width)):
            for k in range(j + 1, min(len(ws), j + width)):
                out[(ws[i], ws[j], ws[k])] += 1
    return out


def sentences(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    out = []
    for s in _SENTENCE.split(text):
        s = s.strip().casefold().translate(_HYPHENS)
        # short fragments are page furniture, numbering and headings; they match
        # trivially and would flatter the score
        if len(_WORD.findall(s)) >= 6:
            out.append(re.sub(r"\W+", " ", s).strip())
    return out


def pdftotext(path: Path, *, layout: bool = False) -> str:
    cmd = ["pdftotext", "-q"]
    if layout:
        cmd.append("-layout")
    cmd += ["-enc", "UTF-8", str(path), "-"]
    r = subprocess.run(cmd,
                       capture_output=True, timeout=300)
    return r.stdout.decode("utf-8", "replace")


def _score_reference(by_page: dict[int, list[str]], reference_pages: list[str]) -> dict:
    # Choose the comparison unit from the script, not from preference. See
    # connected_script_share: in Nastaliq the two decoders disagree on where
    # words begin, so words are not a stable unit and characters are.
    sample = " ".join(reference_pages) + " " + " ".join(
        b for blocks in by_page.values() for b in blocks)
    connected = connected_script_share(sample)
    use_characters = connected >= MIN_CONNECTED_SCRIPT_SHARE

    stored_grams = collections.Counter()
    reference_grams = collections.Counter()
    stored_ordered = collections.Counter()
    reference_ordered = collections.Counter()
    sentence_scores: list[float] = []
    for page_no in range(1, max(len(reference_pages), max(by_page, default=0)) + 1):
        source = reference_pages[page_no - 1] if page_no <= len(reference_pages) else ""
        source_grams = ngrams(words(source), 5)
        reference_grams.update(source_grams)
        reference_ordered.update(
            ordered_skip_trigrams(script_characters(source)) if use_characters
            else ordered_skip_trigrams(lexical_words(source)))
        page_stored = collections.Counter()
        page_ordered = collections.Counter()
        for block in by_page.get(page_no, []):
            page_stored.update(ngrams(words(block), 5))
            page_ordered.update(ngrams(
                script_characters(block) if use_characters
                else lexical_words(block), 3))
        stored_grams.update(page_stored)
        stored_ordered.update(page_ordered)
        for sentence in sentences(source):
            sentence_words = words(sentence)
            if len(sentence_words) < 10:
                continue
            grams = ngrams(sentence_words, 5)
            sentence_scores.append(
                sum((grams & page_stored).values()) / max(sum(grams.values()), 1)
            )

    shared = sum((stored_grams & reference_grams).values())
    precision = shared / max(sum(stored_grams.values()), 1)
    recall = shared / max(sum(reference_grams.values()), 1)
    ordered_shared = sum((stored_ordered & reference_ordered).values())
    ordered_precision = ordered_shared / max(sum(stored_ordered.values()), 1)
    intact = (sum(1 for score in sentence_scores if score >= MIN_SENTENCE_COVERAGE)
              / len(sentence_scores)) if sentence_scores else None
    return {
        "block_five_gram_precision": round(precision, 4),
        "page_five_gram_recall": round(recall, 4),
        "ordered_trigram_precision": round(ordered_precision, 4),
        "ordered_trigrams_checked": sum(stored_ordered.values()),
        "comparison_unit": "character" if use_characters else "word",
        "connected_script_share": round(connected, 4),
        "sentences_checked": len(sentence_scores),
        "sentence_match": round(intact, 4) if intact is not None else None,
        "mean_sentence_coverage": (round(statistics.mean(sentence_scores), 4)
                                   if sentence_scores else None),
    }


def _page_scores(by_page: dict[int, list[str]], reference_pages: list[str]) -> list[dict]:
    """Expose the same metric page-by-page for auditable diagnostics."""
    out = []
    for page_no in range(1, len(reference_pages) + 1):
        score = _score_reference(
            {page_no: by_page.get(page_no, [])},
            ([""] * (page_no - 1)) + [reference_pages[page_no - 1]],
        )
        stored = collections.Counter()
        unit = (script_characters if score.get("comparison_unit") == "character"
                else lexical_words)
        for block in by_page.get(page_no, []):
            stored.update(ngrams(unit(block), 3))
        reference = ordered_skip_trigrams(unit(reference_pages[page_no - 1]))
        unmatched = stored - reference
        joiner = "" if score.get("comparison_unit") == "character" else " "
        score["unmatched_sample"] = [joiner.join(gram) for gram in list(unmatched)[:8]]
        out.append({"page_no": page_no, **score})
    return out


def check(cur, doc_id: int, object_key: str, title: str | None,
          *, include_page_scores: bool = False) -> dict | None:
    path = CORPUS_ROOT / object_key
    if not path.exists():
        return {"document_id": doc_id, "title": title,
                "unverifiable_reason": "source blob is missing on disk"}
    # OCR-bearing blocks in a mixed E3 document have no Poppler text-layer
    # counterpart by definition. They are verified by verify_ocr; including
    # them here falsely labels a successful page recovery as reordered text.
    cur.execute("SELECT page_no,text FROM text_block WHERE document_id=%s "
                "AND confidence IS NULL ORDER BY reading_order",
                (doc_id,))
    by_page: dict[int, list[str]] = {}
    for page_no, text in cur.fetchall():
        by_page.setdefault(page_no, []).append(text)
    references = []
    for mode, layout in (("reading", False), ("physical-layout", True)):
        theirs_raw = pdftotext(path, layout=layout)
        reference_pages = theirs_raw.split("\f")
        if reference_pages and not reference_pages[-1].strip():
            reference_pages.pop()
        references.append((mode, theirs_raw, reference_pages))
    best_words = max(len(lexical_words(raw)) for _, raw, _ in references)
    if best_words < MIN_REFERENCE_LEXICAL_WORDS:
        stored_short = [lexical_words(" ".join(by_page.get(page_no, [])))
                        for page_no in range(1, max(by_page, default=0) + 1)]
        for mode, _, reference_pages in references:
            reference_short = [lexical_words(page) for page in reference_pages]
            # Page-exact equality plus the independent character gate is strong
            # evidence for a short repeal notice; a 100-word cutoff used to call
            # even exact 28-character documents unverifiable.
            if stored_short == reference_short and any(stored_short):
                return {
                    "document_id": doc_id, "title": title,
                    "reference_mode": mode, "alternate_modes": {mode: 1.0},
                    "ordered_trigram_precision": 1.0,
                    "ordered_trigrams_checked": 0,
                    "block_five_gram_precision": 1.0,
                    "page_five_gram_recall": 1.0,
                    "sentences_checked": 0, "sentence_match": None,
                    "mean_sentence_coverage": None,
                    "short_exact_sequence": True, "problems": [],
                }
        return {"document_id": doc_id, "title": title,
                "unverifiable_reason":
                    f"pdftotext produced fewer than {MIN_REFERENCE_LEXICAL_WORDS} "
                    "lexical words; too little independent sequence evidence"}

    scored = [(mode, _score_reference(by_page, pages))
              for mode, _, pages in references]
    mode, res = max(scored, key=lambda item: (
        item[1]["ordered_trigram_precision"],
        item[1]["block_five_gram_precision"],
    ))
    res.update(document_id=doc_id, title=title, reference_mode=mode,
               alternate_modes={m: s["ordered_trigram_precision"]
                                for m, s in scored})
    if include_page_scores:
        chosen_pages = next(pages for m, _, pages in references if m == mode)
        res["page_scores"] = _page_scores(by_page, chosen_pages)

    problems = []
    if res["ordered_trigram_precision"] < MIN_ORDERED_TRIGRAM_PRECISION:
        problems.append(
            f"ordered-trigram precision {res['ordered_trigram_precision']:.3f}"
        )
    # Sentence coverage is intentionally diagnostic. Different block boundaries
    # split a correct sentence differently and should not fail a document. The
    # within-block precision gate catches severe local distortion without that
    # ambiguity.
    res["problems"] = problems
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify word order and sentence integrity")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--sample", type=int)
    g.add_argument("--sha256")
    g.add_argument("--document-id", nargs="+", type=int)
    g.add_argument("--review-only", action="store_true",
                   help="recheck documents whose newest order evidence is not passed")
    ap.add_argument("--lane", help="restrict to E2, E3 or E4")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--debug-pages", action="store_true",
                    help="print page-local scores (never persisted as evidence)")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure without appending verification evidence")
    a = ap.parse_args()

    sql = """SELECT d.id, b.object_key,
                    COALESCE(
                      (SELECT i.short_title FROM instrument i
                        WHERE i.document_id=d.id AND i.is_active
                        ORDER BY i.id LIMIT 1),
                      (SELECT s.source_metadata->>'title' FROM source_observation s
                        WHERE s.sha256=d.sha256
                          AND s.source_metadata->>'title' IS NOT NULL LIMIT 1))
               FROM document d JOIN blob b ON b.sha256 = d.sha256"""
    params: list = []
    # Only current text-layer expressions are comparable with pdftotext.
    # Historical revisions remain available through the extraction verifier's
    # explicit --document-id mode, but must not inflate a corpus-wide result.
    where = (["d.lane <> 'E4'"] if a.document_id
             else ["d.is_active", "d.lane <> 'E4'"])
    if a.lane:
        where.append("d.lane = %s"); params.append(a.lane)
    if a.sha256:
        where.append("d.sha256 LIKE %s"); params.append(a.sha256 + "%")
    if a.document_id:
        where.append("d.id = ANY(%s)"); params.append(a.document_id)
    if a.review_only:
        where.append("(SELECT v.outcome FROM extraction_verification v "
                     "WHERE v.document_id=d.id AND v.verifier LIKE "
                     "'nizam.verify_order/%%' ORDER BY v.verified_at DESC,v.id DESC "
                     "LIMIT 1) <> 'passed'")
    if where:
        sql += " WHERE " + " AND ".join(where)
    if a.sample:
        sql += " ORDER BY random() LIMIT %s"; params.append(a.sample)
    else:
        sql += " ORDER BY d.id"

    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        print(f"checking word order and sentence integrity on {len(rows)} document(s)\n")

        results, flagged = [], []
        printed_flags = 0
        for i, (doc_id, key, title) in enumerate(rows, 1):
            r = check(cur, doc_id, key, title,
                      include_page_scores=a.debug_pages)
            if r is None:  # defensive: check() should always return evidence
                continue
            if r.get("unverifiable_reason"):
                if not a.dry_run:
                    cur.execute(
                        """INSERT INTO extraction_verification
                        (document_id,verifier,reference_extractor,outcome,problems,detail)
                        VALUES (%s,%s,'poppler-pdftotext-sequence','unverifiable',
                                %s::jsonb,%s::jsonb)""",
                        (doc_id, VERIFIER,
                         json.dumps([r["unverifiable_reason"]]),
                         json.dumps({"reason": r["unverifiable_reason"]})),
                    )
                flagged.append(r)
                continue
            results.append(r)
            outcome = "review" if r["problems"] else "passed"
            if not a.dry_run:
                cur.execute(
                    """INSERT INTO extraction_verification
                    (document_id,verifier,reference_extractor,outcome,
                     token_recall,problems,detail)
                    VALUES (%s,%s,'poppler-pdftotext-sequence',%s,%s,%s::jsonb,%s::jsonb)""",
                     (doc_id, VERIFIER, outcome, r["ordered_trigram_precision"],
                      json.dumps(r["problems"], ensure_ascii=False),
                      json.dumps({k: v for k, v in r.items()
                                  if k not in ("document_id", "title", "problems",
                                               "page_scores")},
                                 ensure_ascii=False)),
                )
                if r["problems"]:
                    cur.execute("UPDATE document SET verification_state='review' WHERE id=%s",
                                (doc_id,))
            if r["problems"]:
                flagged.append(r)
                if printed_flags < 50:
                    print(f"  FLAG  #{doc_id} {(title or '')[:44]}")
                    print(f"          {'; '.join(r['problems'])}  "
                          f"exact block5 {r['block_five_gram_precision']:.3f}  "
                          f"reference={r['reference_mode']}")
                    printed_flags += 1
                if a.debug_pages:
                    for page in r.get("page_scores", []):
                        print(f"          page {page['page_no']}: "
                              f"order3p={page['ordered_trigram_precision']:.3f} "
                              f"block5p={page['block_five_gram_precision']:.3f} "
                              f"page5r={page['page_five_gram_recall']:.3f} "
                              f"triples={page['ordered_trigrams_checked']}")
                        if page.get("unmatched_sample"):
                            print("            unmatched: " +
                                  " | ".join(page["unmatched_sample"]))
            elif a.verbose:
                print(f"  ok    #{doc_id} order3p={r['ordered_trigram_precision']:.3f} "
                      f"block5p={r['block_five_gram_precision']:.3f} "
                      f"page5r={r['page_five_gram_recall']:.3f} "
                      f"sent={r['sentence_match']}")
            if i % 250 == 0:
                print(f"  ... {i}/{len(rows)}", flush=True)

    if not results:
        print("nothing comparable")
        return 0
    precisions = [r["ordered_trigram_precision"] for r in results]
    exact_five = [r["block_five_gram_precision"] for r in results]
    recalls = [r["page_five_gram_recall"] for r in results]
    sen = [r["sentence_match"] for r in results if r["sentence_match"] is not None]

    print()
    print(f"documents compared   {len(results)}")
    print(f"flagged              {len(flagged)}")
    if len(flagged) > printed_flags:
        print(f"flag details shown   {printed_flags}/{len(flagged)}")
    print()
    print(f"ordered-trigram precision mean {statistics.mean(precisions):.4f}   median "
          f"{statistics.median(precisions):.4f}   worst {min(precisions):.4f}")
    print(f"exact block 5-gram diagnostic mean {statistics.mean(exact_five):.4f}   median "
          f"{statistics.median(exact_five):.4f}   worst {min(exact_five):.4f}")
    print(f"page 5-gram recall     mean {statistics.mean(recalls):.4f}   median "
          f"{statistics.median(recalls):.4f}   worst {min(recalls):.4f}")
    if sen:
        print(f"sentences verbatim   mean {statistics.mean(sen):.4f}   median "
              f"{statistics.median(sen):.4f}   worst {min(sen):.4f}")
    print()
    print(f"near-perfect block order {sum(1 for x in precisions if x >= 0.999)}/{len(precisions)}")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
