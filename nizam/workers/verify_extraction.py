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


def pdftotext(path: Path, *, layout: bool = False) -> str:
    cmd = ["pdftotext", "-q"]
    if layout:
        cmd.append("-layout")
    out = subprocess.run(
        cmd + ["-enc", "UTF-8", str(path), "-"],
        capture_output=True, timeout=300,
    )
    return out.stdout.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Repaired-reference fallback (agent JE, doc 4608; owner export l q1/q2, lead
# decision 15 Oct 2026).
#
# Poppler cannot open a blob whose cross-reference table is broken ("Couldn't
# find trailer dictionary"), so the independent check has nothing to compare
# and the document stays `unverifiable` for ever, however its text was
# reviewed.  MuPDF rebuilds the xref of the SAME bytes on open; Poppler can
# then read the rebuilt copy.  The rebuilt copy is a temporary file: it is
# never stored, never becomes the corpus text, and the comparison still runs
# Poppler -- a different library from the one that produced the stored text.
#
# The fallback is narrow on purpose:
#   * only when Poppler reads NO text from the blob, and
#   * only when the blob carries an ACTIVE `decode_damage` assertion -- a
#     reviewed, human statement that the file itself is damaged.
# A blob Poppler reads normally never takes this path; nor does an undamaged
# blob Poppler fails on for some other reason.  The result records which
# reference was used (`reference_extractor`, `detail.reference_repair`).
#
# A rebuilt reference of a damaged file is not perfect evidence: Poppler reads
# broken glyphs as stray characters ('μ', combining marks), and the stored
# layer may lack characters the damaged font hides from it.  Those page-local
# differences are accepted ONLY through page-scoped `source_content_confirmed`
# assertions with detail.purpose = 'repaired-reference-difference', each
# listing the exact strings: `missing_strings` (printed in the reference page,
# absent from the stored page) and `extra_strings` (in the stored page, absent
# from the reference page), bound to the reference page's text by
# `reference_page_sha256`.  Every listed string must occur in that page; a
# stale or wrong assertion credits nothing and the gate fails as before.
# Nothing else is waived: an unlisted difference still fails the gate.
REPAIRED_REFERENCE_EXTRACTOR = "poppler-pdftotext+mupdf-xref-rebuild"
REPAIRED_REFERENCE_PURPOSE = "repaired-reference-difference"


def active_decode_damage(cur, sha256: str) -> int | None:
    """The newest active `decode_damage` assertion on this blob, if any."""
    cur.execute(
        """SELECT id FROM extraction_assertion
            WHERE sha256=%s AND kind='decode_damage' AND is_active
            ORDER BY asserted_at DESC, id DESC LIMIT 1""",
        (sha256,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def rebuilt_reference(path: Path, *, layout: bool = False) -> str:
    """Poppler's text of a MuPDF xref-rebuilt copy of the same bytes ('' when MuPDF cannot open it).

    The copy lives in a temporary directory for the length of one pdftotext
    run.  Its bytes are not deterministic (MuPDF writes a fresh /ID), its text
    is, so evidence binds to the text (`reference_page_sha256`)."""
    import tempfile
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - the extractor dependency
        return ""
    pymupdf.TOOLS.mupdf_display_errors(False)
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt = Path(tmp) / "rebuilt.pdf"
        try:
            doc = pymupdf.open(str(path))
            try:
                doc.save(str(rebuilt))
            finally:
                doc.close()
        except Exception:
            return ""
        return pdftotext(rebuilt, layout=layout)


def reference_pages(text: str) -> list[str]:
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def page_text_sha256(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chars_of_strings(strings) -> collections.Counter:
    total = collections.Counter()
    for s in strings:
        total += _chars(s)
    return total


def _occurs(needle: str, haystack: str) -> bool:
    """`needle` printed in `haystack`, compared in the verifier's own character view (whitespace, hyphens and
    format characters do not count), so a string listed from a page is found however the page wraps it."""
    n = "".join(_chars_sequence(needle))
    return bool(n) and n in "".join(_chars_sequence(haystack))


def _chars_sequence(text: str) -> list[str]:
    """`_chars` as a sequence: the same normalisation, order kept."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _WS.sub("", text).translate(_HYPHENS)
    non_content = {"Cf", "Cc", "Cs", "Co", "Cn"}
    return [c for c in text if unicodedata.category(c) not in non_content]


def credited_page_differences(stored_by_page: dict[int, str], ref_pages: list[str],
                              assertions: list[tuple[int, int, dict]]) -> dict:
    """Validate page-scoped repaired-reference assertions and return what they credit.

    `assertions` are (id, page_no, detail).  An assertion credits only if its
    page exists, `reference_page_sha256` equals that page's reference text,
    and every missing string occurs in the reference page and every extra
    string in the stored page.  Returns {'missing': Counter, 'extra': Counter,
    'used': [ids], 'rejected': [(id, reason)]}."""
    missing, extra = collections.Counter(), collections.Counter()
    used, rejected = [], []
    for aid, page_no, detail in assertions:
        if not isinstance(detail, dict) or detail.get("purpose") != REPAIRED_REFERENCE_PURPOSE:
            continue
        if page_no is None or not (1 <= page_no <= len(ref_pages)):
            rejected.append((aid, "page outside the reference")); continue
        ref = ref_pages[page_no - 1]
        stored = stored_by_page.get(page_no, "")
        if detail.get("reference_page_sha256") != page_text_sha256(ref):
            rejected.append((aid, "reference page text changed")); continue
        miss = detail.get("missing_strings") or []
        ext = detail.get("extra_strings") or []
        if not (isinstance(miss, list) and isinstance(ext, list) and (miss or ext)
                and all(isinstance(s, str) and s.strip() for s in miss + ext)):
            rejected.append((aid, "malformed string lists")); continue
        if not all(_occurs(s, ref) for s in miss):
            rejected.append((aid, "a missing string is not printed in the reference page")); continue
        if not all(_occurs(s, stored) for s in ext):
            rejected.append((aid, "an extra string is not in the stored page")); continue
        missing += _chars_of_strings(miss)
        extra += _chars_of_strings(ext)
        used.append(aid)
    return {"missing": missing, "extra": extra, "used": used, "rejected": rejected}


def repaired_reference_assertions(cur, sha256: str) -> list[tuple[int, int, dict]]:
    cur.execute(
        """SELECT id,page_no,detail FROM extraction_assertion
            WHERE sha256=%s AND kind='source_content_confirmed' AND is_active
              AND page_no IS NOT NULL AND detail->>'purpose'=%s
            ORDER BY page_no, id""",
        (sha256, REPAIRED_REFERENCE_PURPOSE),
    )
    return [(r[0], r[1], r[2] if isinstance(r[2], dict) else json.loads(r[2])) for r in cur.fetchall()]


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

    # Repaired-reference fallback: see the note above `REPAIRED_REFERENCE_EXTRACTOR`.
    repaired = False
    if not _chars(ref):
        damage_id = active_decode_damage(cur, sha256)
        if damage_id is not None:
            rebuilt = rebuilt_reference(path)
            if _chars(rebuilt):
                ref, repaired = rebuilt, True
                result["reference_extractor"] = REPAIRED_REFERENCE_EXTRACTOR
                result["reference_repair"] = {
                    "method": "mupdf-xref-rebuild", "decode_assertion_id": damage_id,
                    "reference_page_sha256": [page_text_sha256(p) for p in reference_pages(rebuilt)]}
                result["hints"].append(
                    "Poppler cannot open the blob (decode damage asserted, #%d); compared against Poppler's text "
                    "of a MuPDF xref-rebuilt copy of the same bytes" % damage_id)

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

    credit = None
    if repaired and (recall < MIN_CHAR_RECALL or precision < MIN_CHAR_PRECISION):
        stored_by_page: dict[int, str] = {}
        cur.execute("SELECT page_no,text FROM text_block WHERE document_id=%s ORDER BY reading_order",
                    (document_id,))
        for page_no, text in cur.fetchall():
            stored_by_page[page_no] = stored_by_page.get(page_no, "") + text + "\n"
        credit = credited_page_differences(stored_by_page, reference_pages(ref),
                                           repaired_reference_assertions(cur, sha256))
        result["repaired_reference_assertion_ids"] = credit["used"]
        if credit["rejected"]:
            result["hints"].append("repaired-reference assertions not applied: " + "; ".join(
                f"#{aid} {why}" for aid, why in credit["rejected"]))

    if recall < MIN_CHAR_RECALL:
        missing = theirs_c - ours_c
        credited_recall = None
        if credit is not None:
            # Only the exact strings page-scoped assertions list are credited, never more than is missing.
            left = missing - credit["missing"]
            credited_recall = (sum(theirs_c.values()) - sum(left.values())) / sum(theirs_c.values())
            result["credited_recall"] = round(credited_recall, 5)
        if credited_recall is not None and credited_recall >= MIN_CHAR_RECALL:
            # As `char_precision` already stores the gate value (crop/OCR provenance removed) beside
            # `raw_char_precision`, `char_recall` stores the gate value and the raw measure goes to the detail.
            result["raw_recall"] = round(recall, 5)
            result["recall"] = round(credited_recall, 5)
            result["hints"].append(
                f"raw character recall {recall:.5f}; the {sum(missing.values())} missing characters are the "
                f"reviewed repaired-reference differences of assertion(s) {credit['used']}")
        else:
            left = missing if credit is None else missing - credit["missing"]
            sample = ", ".join(repr(c) for c, _ in left.most_common(6))
            result["problems"].append(
                f"loss: character recall {recall:.5f} < {MIN_CHAR_RECALL} "
                f"({sum(left.values())} characters missing, e.g. {sample})")
    if precision < MIN_CHAR_PRECISION and credit is not None:
        # The generic page-agnostic `source_content_confirmed` waiver below is NOT used against a repaired
        # reference: only the exact extra strings the page-scoped assertions list are credited.
        left = unexplained_extra - credit["extra"]
        credited_precision = ((sum(ours_c.values()) - sum(left.values())) / sum(ours_c.values())
                              if sum(ours_c.values()) else 0.0)
        result["credited_precision"] = round(credited_precision, 5)
        if credited_precision >= MIN_CHAR_PRECISION:
            result["precision"] = round(credited_precision, 5)
            result["hints"].append(
                f"character precision {precision:.5f}; the unexplained characters are the reviewed "
                f"repaired-reference differences of assertion(s) {credit['used']}")
        else:
            sample = ", ".join(repr(c) for c, _ in left.most_common(6))
            result["problems"].append(
                f"fabrication: character precision {precision:.5f} < {MIN_CHAR_PRECISION} "
                f"({sum(left.values())} unexplained characters, e.g. {sample})")
    elif precision < MIN_CHAR_PRECISION:
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
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)""",
                (doc_id, VERIFIER, r.get("reference_extractor", "poppler-pdftotext"), outcome,
                 r.get("recall"), r.get("precision"),
                 r.get("raw_precision"), r.get("token_recall"),
                 json.dumps(r.get("problems", []), ensure_ascii=False),
                 json.dumps(r.get("hints", []), ensure_ascii=False),
                 json.dumps({"outside_crop_chars": r.get("outside_crop_chars", 0),
                             "ocr_chars": r.get("ocr_chars", 0),
                             "assertion_id": r.get("assertion_id"),
                             "decode_assertion_id": r.get("decode_assertion_id"),
                             "ocr_candidate_id": r.get("ocr_candidate_id"),
                             # repaired-reference fallback (agent JE, doc 4608): present only when used
                             **({"reference_repair": r["reference_repair"],
                                 "repaired_reference_assertion_ids": r.get("repaired_reference_assertion_ids", []),
                                 "raw_char_recall": r.get("raw_recall"),
                                 "credited_recall": r.get("credited_recall"),
                                 "credited_precision": r.get("credited_precision")}
                                if r.get("reference_repair") else {})},
                            ensure_ascii=False)),
            )
            cur.execute("UPDATE document SET verification_state=%s WHERE id=%s",
                        ("passed" if outcome == "passed" else "review", doc_id))
            # Commit per document. This loop used to run as one transaction
            # that committed only when `with connect()` exited, so a full
            # `--all` pass -- hours over ~4,500 documents -- kept nothing if it
            # was interrupted. On 21 Sep 2026 a run reached 4,000 of 4,499 with
            # no mismatch and none of it survived. The audit reads the LATEST
            # row per document (criteria.sql, DISTINCT ON document_id ORDER BY
            # verified_at DESC), so a partial pass is safe: documents it
            # reached are refreshed, the rest keep their previous verification.
            # The pdftotext check dominates the runtime; the commit is noise.
            conn.commit()
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
