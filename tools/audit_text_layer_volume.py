"""Does this document's text layer actually hold the law, or only its furniture?

EMPTINESS IS THE WRONG QUESTION. Extraction rejects a PDF with no text at all
(``extract.py``: "no text layer at all -- this is lane E4"), and lane E3 exists
for a document with *some* blank pages. Neither asks the question that matters:
a scanned Act can carry a perfectly printable text layer on every page that
holds nothing but the scanner's branding, a portal stamp, or the running header
repeated fifteen times. Character count says the document is full. Reading it
says the law was never captured.

``extract.py`` already screens for the extreme form of this --
``_is_repeated_sparse_overlay``, which is what routed document 4573 (the Sindh
Essential Commodities Act, every page stamped "CamScanner") to OCR on 3 Sep
2026, rejecting its text layer with "repeated sparse text-layer overlay across
15 pages". So the corpus does NOT hold 4573 as a CamScanner document: it holds
the OCR, 24,700 characters of real statute.

But that screen is deliberately conjunctive -- at least 3 pages, median page
text at most 32 compact characters, mean at most 40, and one signature
dominating 80% of pages -- so it only catches an overlay that is BOTH tiny AND
near-identical everywhere. A text layer of a few hundred characters a page,
made of a running header that varies with the page number and a folio, clears
every one of those bounds and still contains no law.

WHAT THIS MEASURES INSTEAD. Volume of SUBSTANTIVE text, page by page.

    1. Page furniture is identified and subtracted. A short block whose text
       repeats across most of the document's pages is a running header, a
       footer, a portal stamp or scanner branding -- never a provision. Only
       SHORT blocks qualify: a long block that repeats is a genuinely repeated
       passage, and subtracting it would hide real text.

    2. What is left is the page's substantive word count, and a page is USABLE
       when that reaches the floor already accepted for an OCR page elsewhere
       in this corpus -- ``verify_ocr.MIN_WORDS_PER_PAGE``, 40 words.

    3. A document fails when NO page is usable: every page, after its furniture
       is removed, yields less than one sentence of law. That is the honest
       replacement for "is it empty" -- it is a claim about what can be read,
       not about whether bytes exist.

The per-page fractions are reported alongside so a partial failure -- a
document whose middle twenty pages give nothing while its cover gives plenty --
is visible without being asserted as a whole-document verdict.

Reads only. It writes nothing and adjudicates nothing.

    python tools/audit_text_layer_volume.py [--show N] [--json PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field

from nizam.storage.db import connect
from nizam.workers.verify_ocr import MIN_WORDS_PER_PAGE

# A block long enough to be law is never page furniture, however often it
# repeats. Running headers, folios, stamps and scanner branding are all short.
FURNITURE_MAX_WORDS = 25

# How much of the document a short block must appear on before it is furniture
# rather than a passage that happens to recur. Two pages is not a pattern.
FURNITURE_PAGE_FRACTION = 0.6
FURNITURE_MIN_PAGES = 3

_DIGITS = re.compile(r"\d+")
_SPACES = re.compile(r"\s+")


def signature(head: str) -> str:
    """Comparable identity for a block, ignoring the page number it carries.

    ``extract.py`` normalises the same way for its routing decision: a running
    header that counts "Page 3 of 35" is the same furniture as one counting
    "Page 4 of 35".
    """
    return _DIGITS.sub("#", _SPACES.sub(" ", head).strip().casefold())


def find_furniture(blocks: list[tuple[int, str, int]], pages: int) -> set[str]:
    """Signatures of the short blocks that repeat across most of the document.

    ``blocks`` is (page_no, block head, word count).
    """
    if pages < FURNITURE_MIN_PAGES:
        return set()
    seen: dict[str, set[int]] = {}
    for page_no, head, words in blocks:
        if words > FURNITURE_MAX_WORDS:
            continue
        seen.setdefault(signature(head), set()).add(page_no)
    floor = max(FURNITURE_MIN_PAGES, pages * FURNITURE_PAGE_FRACTION)
    return {sig for sig, on in seen.items() if len(on) >= floor}


def substantive_words(blocks: list[tuple[int, str, int]],
                      furniture: set[str]) -> dict[int, int]:
    """Words per page once the furniture is subtracted."""
    per_page: dict[int, int] = {}
    for page_no, head, words in blocks:
        contributes = 0 if (words <= FURNITURE_MAX_WORDS
                            and signature(head) in furniture) else words
        per_page[page_no] = per_page.get(page_no, 0) + contributes
    return per_page


@dataclass
class Measurement:
    document_id: int
    page_count: int
    lane: str
    char_count: int
    title: str = ""
    blocks: list[tuple[int, str, int]] = field(default_factory=list)

    @property
    def furniture(self) -> set[str]:
        return find_furniture(self.blocks, self.page_count)

    @property
    def per_page(self) -> dict[int, int]:
        return substantive_words(self.blocks, self.furniture)

    @property
    def usable_pages(self) -> int:
        return sum(1 for words in self.per_page.values()
                   if words >= MIN_WORDS_PER_PAGE)

    @property
    def usable_fraction(self) -> float:
        return self.usable_pages / self.page_count if self.page_count else 0.0

    @property
    def substantive_total(self) -> int:
        return sum(self.per_page.values())

    @property
    def fails(self) -> bool:
        """No page anywhere in the document yields a readable amount of law."""
        return self.usable_pages == 0


BLOCKS = r"""
SELECT b.document_id, b.page_no, left(btrim(b.text), 80),
       coalesce(array_length(
           regexp_split_to_array(btrim(b.text), '\s+'), 1), 0)
  FROM text_block b
  JOIN document d ON d.id = b.document_id AND d.is_active
 WHERE btrim(b.text) <> ''
 ORDER BY b.document_id, b.reading_order
"""

DOCUMENTS = r"""
SELECT d.id, d.page_count, d.lane::text, d.char_count,
       coalesce((SELECT i.short_title FROM instrument i
                  WHERE i.document_id = d.id AND i.is_active
                  ORDER BY i.id LIMIT 1), '')
  FROM document d WHERE d.is_active ORDER BY d.id
"""


def collect(conn, only: set[int] | None = None) -> list[Measurement]:
    with conn.cursor() as cur:
        cur.execute(DOCUMENTS)
        docs = {row[0]: Measurement(document_id=row[0], page_count=row[1],
                                    lane=row[2], char_count=row[3], title=row[4])
                for row in cur if only is None or row[0] in only}
    with conn.cursor(name="text_layer_blocks") as cur:
        cur.itersize = 20000
        cur.execute(BLOCKS)
        for document_id, page_no, head, words in cur:
            found = docs.get(document_id)
            if found is not None:
                found.blocks.append((page_no, head, words))
    return sorted(docs.values(), key=lambda m: (m.usable_fraction, m.document_id))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=40)
    ap.add_argument("--json", help="write the failing documents here")
    ap.add_argument("--document-id", nargs="+", type=int,
                    help="explain these documents whatever the verdict")
    args = ap.parse_args()

    with connect() as conn:
        rows = collect(conn)

    failing = [row for row in rows if row.fails]
    by_lane: dict[str, int] = {}
    for row in failing:
        by_lane[row.lane] = by_lane.get(row.lane, 0) + 1

    print(f"active documents measured: {len(rows)}")
    print(f"usable page floor: {MIN_WORDS_PER_PAGE} substantive words "
          f"(verify_ocr.MIN_WORDS_PER_PAGE)")
    print(f"documents where NO page yields that: {len(failing)}"
          + (f"  ({', '.join(f'{lane} {n}' for lane, n in sorted(by_lane.items()))})"
             if by_lane else ""))
    thin = [row for row in rows if not row.fails and row.usable_fraction < 0.25]
    print(f"documents where fewer than a quarter of pages do (reported, not "
          f"failed): {len(thin)}")
    print()
    print(f"{'doc':>6} {'pages':>5} {'lane':>4} {'usable':>6} {'chars':>8} "
          f"{'subst.words':>11}  title")
    for row in failing[:args.show]:
        print(f"{row.document_id:>6} {row.page_count:>5} {row.lane:>4} "
              f"{row.usable_pages:>6} {row.char_count:>8} "
              f"{row.substantive_total:>11}  {row.title[:44]}")
    if len(failing) > args.show:
        print(f"  ... and {len(failing) - args.show} more")

    if thin:
        print("\nthin, not failed -- fewer than a quarter of pages usable:\n")
        print(f"{'doc':>6} {'pages':>5} {'lane':>4} {'usable':>6} {'chars':>8} "
              f"{'subst.words':>11}  title")
        for row in thin[:args.show]:
            print(f"{row.document_id:>6} {row.page_count:>5} {row.lane:>4} "
                  f"{row.usable_pages:>6} {row.char_count:>8} "
                  f"{row.substantive_total:>11}  {row.title[:44]}")

    for doc in args.document_id or []:
        row = next((r for r in rows if r.document_id == doc), None)
        if row is None:
            print(f"\ndocument {doc}: not active", file=sys.stderr)
            continue
        print(f"\ndocument {doc}  {row.title}")
        print(f"  {row.page_count} pages, lane {row.lane}, "
              f"{row.char_count} characters")
        print(f"  furniture signatures subtracted: {len(row.furniture)}")
        for sig in sorted(row.furniture)[:6]:
            print(f"    {sig[:72]!r}")
        pages = sorted(row.per_page.items())
        print(f"  substantive words per page: "
              f"{[words for _page, words in pages][:20]}")
        print(f"  usable pages {row.usable_pages} of {row.page_count} "
              f"({row.usable_fraction:.0%})")
        print(f"  verdict: {'FAILS -- no page yields readable law' if row.fails else 'passes'}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump([{
                "document_id": row.document_id,
                "page_count": row.page_count,
                "lane": row.lane,
                "char_count": row.char_count,
                "substantive_words": row.substantive_total,
                "usable_pages": row.usable_pages,
                "title": row.title,
            } for row in failing], handle, ensure_ascii=False, indent=1)
        print(f"\nwrote {len(failing)} rows to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
