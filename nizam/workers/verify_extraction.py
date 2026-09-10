"""Cross-check what is in the database against the source PDFs, independently.

Document 09a §2 puts poppler-utils on every machine "for quick corpus inspection
and for the extraction cross-check". This is that check: it re-reads each PDF
with `pdftotext` -- a different library, a different codebase, written by
different people -- and compares the result against what PyMuPDF stored.

Two failure modes, and they need different tests:

  LOSS         content in the PDF that never reached the database.
               Character recall: of the characters pdftotext finds, how many are
               present in the stored blocks.

  FABRICATION  content in the database that is not in the PDF -- a decoding bug,
               a mis-mapped font, or blocks duplicated by a bad reading order.
               Character precision, the same comparison in reverse.

Both are needed. Recall alone passes a document that stored a page twice;
precision alone passes one that stored a correct sentence and dropped a page.
Page count is checked separately because losing a whole page can leave both
ratios high.

The comparison is by CHARACTER, not by word, and that distinction is the whole
reason this tool is trustworthy. Pakistani statutes carry superscript amendment
footnote markers flush against the following word: PyMuPDF reads "1Substituted",
pdftotext reads "1" then "Substituted". By word that is one loss and one
fabrication; by character it is a perfect match. The word-level gate flagged 17
of 150 sound documents before this was corrected.

    uv run python -m nizam.workers.verify_extraction --sample 200
    uv run python -m nizam.workers.verify_extraction --all
    uv run python -m nizam.workers.verify_extraction --sha256 e2cd2bb9
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from nizam.storage.db import connect

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))

# CHARACTERS are the gate; tokens are only a hint.
#
# Token comparison cannot distinguish "1Substituted" from "1" + "Substituted",
# and Pakistani statutes are full of superscript amendment footnote markers that
# sit flush against the following word. PyMuPDF attaches them, pdftotext puts
# them on their own line. Measured by tokens that looks like simultaneous loss
# and fabrication; measured by characters it is exactly zero of both. Running the
# token gate alone flagged 17 of 150 sound documents.
MIN_CHAR_RECALL = 0.999
MIN_CHAR_PRECISION = 0.999

# Token agreement is reported because a real reading-order bug would show up here
# first, but it does not fail a document on its own.
TOKEN_HINT_FLOOR = 0.95
VERIFIER = "nizam.verify_extraction/3"

_WORD = re.compile(r"\w+", re.UNICODE)
_WS = re.compile(r"\s+")
_ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def _tokens(text: str) -> collections.Counter:
    """Compare meaning, not typography.

    Case, punctuation and whitespace differ between extractors for reasons that
    are not corruption. Ligatures are folded (NFKC) because pdftotext expands
    "fi" to "f"+"i" and PyMuPDF may not.

    Cf (format) characters are removed for the same reason the character gate
    removes them: pdftotext wraps every Urdu run in U+202A/U+202B/U+202C bidi
    embeddings. Left in, they land inside words and make an identical Urdu
    document score 0.0000 token recall -- which it did, and which read as a
    reading-order fault when nothing was wrong.
    """
    text = unicodedata.normalize("NFKC", text).casefold()
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    return collections.Counter(_WORD.findall(text))


# Hyphens are removed from BOTH sides before comparing. pdftotext de-hyphenates:
# a word broken across a line as "occupa-\ntional" is rejoined and the hyphen
# dropped. We keep it, because it is in the PDF -- so on short documents a single
# line-break hyphen was enough to push precision under the threshold and flag a
# perfectly faithful extraction. Removing them symmetrically cannot mask a loss
# of real content; it can only remove hyphens.
_HYPHENS = str.maketrans("", "", "-‐­")


def _chars(text: str) -> collections.Counter:
    """Characters that carry content, with whitespace and formatting removed.

    Cf (format) characters are dropped from both sides. pdftotext emits U+202B /
    U+202C directional *embeddings* around Urdu runs; we do not store them, and
    Document 08 forbids embeddings in favour of FSI/PDI isolates anyway. They are
    typesetting instructions, not law.
    """
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _WS.sub("", text).translate(_HYPHENS)
    # Format/control/surrogate/private-use/unassigned code points have no stable
    # textual semantics across PDF decoders.  They remain in the stored source
    # extraction and are reviewed through printable-ratio diagnostics, but they
    # cannot prove loss or fabrication against Poppler.
    non_content = {"Cf", "Cc", "Cs", "Co", "Cn"}
    return collections.Counter(c for c in text if unicodedata.category(c) not in non_content)


def _multiset_overlap(a: collections.Counter, b: collections.Counter) -> int:
    return sum((a & b).values())


def _unexplained_extra(stored: str, reference: str, outside_crop: str,
                       ocr_text: str) -> collections.Counter:
    """Stored characters that neither independent decoder nor provenance explains.

    OCR is deliberately not claimed as Poppler-verified: confidence-labelled OCR
    has a different evidentiary basis, so it is removed only from the fabrication
    gate and remains reported separately in the verification detail.
    """
    return ((_chars(stored) - _chars(reference)) - _chars(outside_crop)
            - _chars(ocr_text))


def pdftotext(path: Path) -> str:
    out = subprocess.run(
        ["pdftotext", "-q", "-enc", "UTF-8", str(path), "-"],
        capture_output=True, timeout=300,
    )
    return out.stdout.decode("utf-8", "replace")


def stored_text(cur, document_id: int) -> tuple[str, str, str]:
    cur.execute(
        "SELECT text,inside_cropbox,confidence FROM text_block "
        "WHERE document_id = %s ORDER BY reading_order",
        (document_id,),
    )
    rows = cur.fetchall()
    return ("\n".join(r[0] for r in rows),
            "\n".join(r[0] for r in rows if not r[1]),
            "\n".join(r[0] for r in rows if r[2] is not None))


def attach_decode_evidence(cur, result: dict, document_id: int,
                           sha256: str) -> None:
    """Link a known decoder defect and its latest non-destructive OCR aid."""
    cur.execute(
        """SELECT a.id,a.page_no,a.evidence,c.id,c.engine,c.languages,
                  c.mean_confidence,c.word_count
             FROM extraction_assertion a
             LEFT JOIN LATERAL (
                 SELECT id,engine,languages,mean_confidence,word_count
                   FROM page_ocr_candidate
                  WHERE document_id=%s AND page_no=a.page_no
                  ORDER BY created_at DESC LIMIT 1
             ) c ON true
            WHERE a.sha256=%s AND a.kind='decode_damage' AND a.is_active
            ORDER BY a.asserted_at DESC LIMIT 1""",
        (document_id, sha256),
    )
    damage = cur.fetchone()
    if not damage:
        return
    result["decode_assertion_id"] = damage[0]
    result["ocr_candidate_id"] = damage[3]
    note = (f"known text-layer decode damage on page {damage[1]}: "
            f"{damage[2]}")
    if damage[3] is not None:
        note += (f"; OCR candidate #{damage[3]} {damage[4]} "
                 f"({damage[5]}, confidence {float(damage[6]):.4f}, "
                 f"{damage[7]} words) retained separately")
    result["hints"].append(note)


def check(cur, document_id: int, sha256: str, object_key: str,
          page_count: int, title: str | None) -> dict:
    path = CORPUS_ROOT / object_key
    result = {"document_id": document_id, "sha256": sha256, "title": title,
              "ok": False, "problems": [], "hints": []}
    if not path.exists():
        result["problems"].append("blob missing")
        return result

    mine, outside_crop, ocr_text = stored_text(cur, document_id)
    ref = pdftotext(path)
    attach_decode_evidence(cur, result, document_id, sha256)

    ours_c, theirs_c = _chars(mine), _chars(ref)
    if not theirs_c:
        # pdftotext found nothing but we stored text: not necessarily wrong
        # (they handle some embedded fonts differently), but not verifiable.
        result["problems"].append("pdftotext found no text; cannot cross-check")
        result["recall"] = result["precision"] = None
        return result

    shared_c = _multiset_overlap(ours_c, theirs_c)
    recall = shared_c / sum(theirs_c.values())
    raw_precision = shared_c / sum(ours_c.values()) if sum(ours_c.values()) else 0.0
    # Content intentionally retained outside a publisher crop box is evidence,
    # not decoder fabrication.  Only extras that cannot be accounted for by
    # visibility-flagged blocks participate in the precision gate.
    unexplained_extra = _unexplained_extra(mine, ref, outside_crop, ocr_text)
    precision = ((sum(ours_c.values()) - sum(unexplained_extra.values()))
                 / sum(ours_c.values())) if sum(ours_c.values()) else 0.0
    result["recall"] = round(recall, 5)
    result["precision"] = round(precision, 5)
    result["raw_precision"] = round(raw_precision, 5)
    result["outside_crop_chars"] = sum(_chars(outside_crop).values())
    result["ocr_chars"] = sum(_chars(ocr_text).values())

    ours_t, theirs_t = _tokens(mine), _tokens(ref)
    shared_t = _multiset_overlap(ours_t, theirs_t)
    result["token_recall"] = round(shared_t / max(sum(theirs_t.values()), 1), 4)

    if recall < MIN_CHAR_RECALL:
        missing = theirs_c - ours_c
        sample = ", ".join(repr(c) for c, _ in missing.most_common(6))
        result["problems"].append(
            f"loss: character recall {recall:.5f} < {MIN_CHAR_RECALL} "
            f"({sum(missing.values())} characters missing, e.g. {sample})")
    if precision < MIN_CHAR_PRECISION:
        extra = unexplained_extra
        sample = ", ".join(repr(c) for c, _ in extra.most_common(6))
        cur.execute(
            """SELECT id,page_no,evidence FROM extraction_assertion
                WHERE sha256=%s AND kind='source_content_confirmed' AND is_active
                ORDER BY asserted_at DESC LIMIT 1""",
            (sha256,),
        )
        assertion = cur.fetchone()
        if assertion:
            result["assertion_id"] = assertion[0]
            result["hints"].append(
                f"raw precision {raw_precision:.5f}; source content confirmed "
                f"on page {assertion[1]}: {assertion[2]}")
        else:
            result["problems"].append(
                f"fabrication: character precision {precision:.5f} < {MIN_CHAR_PRECISION} "
                f"({sum(extra.values())} unexplained characters, e.g. {sample})")

    # The token hint is meaningless for Arabic-script text. PyMuPDF returns Urdu
    # with word spaces; pdftotext runs the words together. Neither is wrong --
    # word boundaries in Nastaliq are a rendering decision, not a property of the
    # text -- but it drives token recall to ~0.69 on documents whose characters
    # match at 0.9998. Only the character gate is meaningful there.
    arabic = len(_ARABIC.findall(mine))
    mostly_rtl = arabic > 0.30 * max(sum(ours_c.values()), 1)
    if not mostly_rtl and result["token_recall"] < TOKEN_HINT_FLOOR:
        # Counter overlap contains no positional information, so this cannot
        # prove a reading-order defect.  Keep it as a review hint, never a gate.
        result["hints"].append(
            f"token agreement {result['token_recall']:.4f} is low -- inspect "
            f"tokenisation/order if this document is used for retrieval")
    result["rtl"] = mostly_rtl

    # A whole page can vanish while both ratios stay high, so count pages too.
    info = subprocess.run(["pdfinfo", str(path)], capture_output=True, timeout=60)
    m = re.search(rb"Pages:\s+(\d+)", info.stdout)
    if m:
        real_pages = int(m.group(1))
        if real_pages != page_count:
            result["problems"].append(
                f"page count: PDF has {real_pages}, database has {page_count}")

    result["ok"] = not result["problems"]
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-check the database against the source PDFs")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--sample", type=int, help="check N documents at random")
    g.add_argument("--sha256", nargs="+", metavar="PREFIX",
                   help="check one or more documents by SHA-256 prefix")
    g.add_argument("--document-id", nargs="+", type=int, metavar="ID",
                   help="check exact document revision ids, including retired revisions")
    g.add_argument("--retired-predecessors", action="store_true",
                   help="check every retired revision directly superseded by an active one")
    ap.add_argument("--verbose", action="store_true", help="print every document, not just failures")
    a = ap.parse_args()

    # Lane E4 is excluded by definition. An OCR document is one whose PDF has no
    # usable text layer, so pdftotext has nothing to compare against -- and when
    # it scrapes a few stray characters off a scan, the comparison reports the
    # entire OCR output as fabrication. One document scored 0.007 precision that
    # way. Lane E4 is verified by nizam.workers.verify_ocr instead.
    q = """SELECT d.id, d.sha256, b.object_key, d.page_count,
                  (SELECT s.source_metadata->>'title' FROM source_observation s
                    WHERE s.sha256 = d.sha256 AND s.source_metadata->>'title' IS NOT NULL LIMIT 1)
             FROM document d JOIN blob b ON b.sha256 = d.sha256
            WHERE d.lane <> 'E4'"""
    params: list = []
    if a.document_id:
        q += " AND d.id=ANY(%s)"
        params.append(a.document_id)
    elif a.retired_predecessors:
        q += " AND EXISTS (SELECT 1 FROM document active WHERE active.is_active AND active.supersedes_document_id=d.id)"
    else:
        q += " AND d.is_active"
    if a.sha256:
        q += " AND (" + " OR ".join("d.sha256 LIKE %s" for _ in a.sha256) + ")"
        params.extend(prefix + "%" for prefix in a.sha256)
    elif a.sample:
        q += " ORDER BY random() LIMIT %s"
        params.append(a.sample)
    else:
        q += " ORDER BY d.id"

    with connect() as conn, conn.cursor() as cur:
        cur.execute(q, params)
        rows = cur.fetchall()
        if not rows:
            print("no documents matched", file=sys.stderr)
            return 1
        print(f"cross-checking {len(rows)} document(s) against their PDFs "
              f"with pdftotext\n")

        failures, unverifiable, recalls, precisions = [], 0, [], []
        for n, (doc_id, sha, key, pages, title) in enumerate(rows, 1):
            r = check(cur, doc_id, sha, key, pages, title)
            outcome = ("unverifiable" if r.get("recall") is None
                       else "passed" if r["ok"] else "review")
            cur.execute(
                """INSERT INTO extraction_verification
                    (document_id,verifier,reference_extractor,outcome,char_recall,
                     char_precision,raw_char_precision,token_recall,problems,hints,detail)
                    VALUES (%s,%s,'poppler-pdftotext',%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)""",
                (doc_id, VERIFIER, outcome, r.get("recall"), r.get("precision"),
                 r.get("raw_precision"), r.get("token_recall"),
                 json.dumps(r.get("problems", []), ensure_ascii=False),
                 json.dumps(r.get("hints", []), ensure_ascii=False),
                 json.dumps({"outside_crop_chars": r.get("outside_crop_chars", 0),
                             "ocr_chars": r.get("ocr_chars", 0),
                             "assertion_id": r.get("assertion_id"),
                             "decode_assertion_id": r.get("decode_assertion_id"),
                             "ocr_candidate_id": r.get("ocr_candidate_id")},
                            ensure_ascii=False)),
            )
            cur.execute("UPDATE document SET verification_state=%s WHERE id=%s",
                        ("passed" if outcome == "passed" else "review", doc_id))
            if r.get("recall") is None:
                unverifiable += 1
            else:
                recalls.append(r["recall"]); precisions.append(r["precision"])
            if not r["ok"] and r.get("recall") is not None:
                failures.append(r)
                print(f"  FAIL  #{doc_id} {sha[:12]} {(title or '')[:44]}")
                for p in r["problems"]:
                    print(f"          {p}")
                for hint in r.get("hints", []):
                    print(f"          NOTE: {hint}")
            elif a.verbose:
                print(f"  ok    #{doc_id} {sha[:12]} char_recall={r['recall']} "
                      f"char_precision={r['precision']} tokens={r.get('token_recall')} "
                      f"{(title or '')[:38]}")
            if n % 250 == 0:
                print(f"  ... {n}/{len(rows)}", flush=True)

    checked = len(recalls)
    print()
    print(f"checked        {len(rows)}")
    print(f"verifiable     {checked}   (pdftotext produced text)")
    print(f"unverifiable   {unverifiable}")
    print(f"failed         {len(failures)}")
    if checked:
        print(f"mean char recall    {sum(recalls)/checked:.5f}   (of the PDF's characters, how many we stored)")
        print(f"mean char precision {sum(precisions)/checked:.5f}   (of our characters, how many are in the PDF)")
        print(f"worst char recall   {min(recalls):.5f}")
        print(f"worst char precision {min(precisions):.5f}")
        perfect = sum(1 for r in recalls if r >= 0.99999)
        print(f"character-perfect   {perfect}/{checked}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
