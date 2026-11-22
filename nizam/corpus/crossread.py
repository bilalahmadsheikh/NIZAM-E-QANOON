"""Two independent OCR readings of the same pages, compared -- the lane-E4 counterpart of lane E2's second library.

D-114: a scan is released from Google Document AI's reading; Tesseract reads the same pages on the laptop. Two engines
that share no model agreeing on a page is evidence that the page says what the release says, of the same kind as
pdftotext agreeing with PyMuPDF over a text layer (docs/02 §4, nizam.workers.verify_extraction). Where they disagree,
the page is named for a page read; it is not averaged away.

Per page, two measures over the page's letters and digits (casefolded, NFKC, so ligatures and full-width forms count
once):

  RECALL     the share of the second reader's characters the release reading also has (multiset overlap) -- catches
             a release reading that dropped a line, a column or a footnote the second reader saw;
  PRECISION  the share of the release reading's characters the second reader also has -- catches invented text.

and one over word order: ordered word-bigram precision of the release reading against the second reader, which catches
two columns interleaved or a block moved, which character counts cannot see.

A page where the second reader saw almost nothing (fewer than MIN_REFERENCE_CHARS) is not compared: a blank or
image-only page cannot vote. Pure; no database.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Provisional (D-114): fixed before any Document AI output was seen, from the measured floor of Tesseract on clean
# printed scans (mean word confidence .88-.95 on the first AJK sample, 22 Nov 2026). Recalibrated once, on dev pages
# that were page-read, and the change logged; never tuned per document.
MIN_PAGE_RECALL = 0.90
MIN_PAGE_PRECISION = 0.90
MIN_DOC_BIGRAM_PRECISION = 0.70
MIN_REFERENCE_CHARS = 80

_KEEP = re.compile(r"[^\w]|_", re.UNICODE)
_WORD = re.compile(r"\w+", re.UNICODE)


def _chars(text: str) -> Counter:
    return Counter(_KEEP.sub("", unicodedata.normalize("NFKC", text).casefold()))


def _bigrams(text: str) -> Counter:
    words = _WORD.findall(unicodedata.normalize("NFKC", text).casefold())
    return Counter(zip(words, words[1:]))


def _overlap(a: Counter, b: Counter) -> int:
    return sum(min(n, b[k]) for k, n in a.items())


def compare_pages(release: list[str], second: list[str]) -> dict:
    """Compare two page-aligned readings. Returns per-page measures, the pages that disagree, and a verdict."""
    if len(release) != len(second):
        return {"verdict": "page count differs", "pages": [], "disagree": [],
                "release_pages": len(release), "second_pages": len(second)}
    pages, disagree = [], []
    rel_bi_total = rel_bi_shared = 0
    for n, (mine, theirs) in enumerate(zip(release, second), 1):
        a, b = _chars(mine), _chars(theirs)
        ref = sum(b.values())
        if ref < MIN_REFERENCE_CHARS:
            pages.append({"page": n, "compared": False, "second_chars": ref, "release_chars": sum(a.values())})
            continue
        shared = _overlap(a, b)
        recall = shared / ref
        precision = shared / sum(a.values()) if a else 0.0
        ba, bb = _bigrams(mine), _bigrams(theirs)
        rel_bi_total += sum(ba.values())
        rel_bi_shared += _overlap(ba, bb)
        row = {"page": n, "compared": True, "recall": round(recall, 4), "precision": round(precision, 4)}
        pages.append(row)
        if recall < MIN_PAGE_RECALL or precision < MIN_PAGE_PRECISION:
            disagree.append(n)
    compared = [p for p in pages if p["compared"]]
    bigram_precision = rel_bi_shared / rel_bi_total if rel_bi_total else None
    problems = []
    if not compared:
        problems.append("no page the second reader could read")
    if disagree:
        problems.append(f"pages disagree: {', '.join(map(str, disagree[:20]))}{' ...' if len(disagree) > 20 else ''}")
    if bigram_precision is not None and bigram_precision < MIN_DOC_BIGRAM_PRECISION:
        problems.append(f"word order {bigram_precision:.3f}")
    return {"verdict": "agree" if not problems else "; ".join(problems), "pages": pages, "disagree": disagree,
            "compared_pages": len(compared),
            "bigram_precision": None if bigram_precision is None else round(bigram_precision, 4)}


def release_pages(blocks, page_count: int) -> list[str]:
    """A document's blocks as page texts, in reading order (the shape second_read.py stores)."""
    pages = ["" for _ in range(page_count)]
    for b in sorted(blocks, key=lambda b: b.reading_order):
        pages[b.page_no - 1] += ("\n" if pages[b.page_no - 1] else "") + b.text
    return pages
