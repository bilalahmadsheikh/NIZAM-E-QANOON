"""Documents whose PDF stops before the statute does.

A contents gap has two innocent explanations, and a third that no parser fix
reaches. Either the parser missed a section the page prints, or the source
genuinely omits it -- but sometimes the acquired FILE is a partial copy of a
complete statute, and the promised sections are absent from the copy rather than
from the law.

The Nawab Shaheed Ghous Bakhsh Raisani Memorial Hospital Act, 2012 is the worked
example. The Balochistan Code holds it as three pages that stop during section
5, while its own contents lists sixteen. No re-parse recovers section 6; the
nine-page official Gazette does, and ``recover_acquisition.py --alternate-for``
landed it.

Recording those gaps as ``absent_in_source`` would assert something false about
the statute -- that the legislature never enacted the section -- on evidence
that only shows the file is short. So they are held out, and this finds them.

AS BUILT, 20 Sep 2026: THE FIRST VERSION WAS WRONG IN BOTH DIRECTIONS.

The three tests it shipped with are kept below as history because the failure
is instructive: each measured truncation through the PROVISION TREE, and the
tree is the thing under suspicion.

    1. The contents promises a highest label the tree never reaches, and the
       last provision sits on the document's last page.
    2. Every gap sits ABOVE the highest label the tree holds.
    3. The last real line does not end a sentence.

Two false negatives and one false positive were found by reading pages.

FALSE NEGATIVE -- document 127, the Balochistan Witness Protection Act, 2016.
Its body stops inside section 2's definitions on page 4; sections 3 to 29 were
never printed in the copy we hold. Pages 6 and 7 print the Schedule, a list of
fifteen offences numbered 1 to 15. The segmenter bound the contents headings to
those schedule items, so the tree reports "section 3: Application of the Act and
overriding effect" whose text is the single word "Murder." top_held therefore
read 15, not 2; the last provision landed on page 6 of 7, so test 1 failed; and
the gaps 3..15 sat BELOW the false ceiling, so test 2 failed too. A tree-derived
ceiling cannot measure a document whose tree is the defect.

FALSE NEGATIVE -- document 2205, the Sind Public Conveyances Act, 1920. Its text
stops inside section 20(3), "...for the information of any hirer of, or
passenger travelling in, the conveyance", with no terminal stop. Test 3 should
have caught it, and did not: the last block on the last page is the page's
FOOTNOTE apparatus, "1. Ins. by Sind 7 of 1928, s. 6. ...", which ends in a
full stop. The tail test read the apparatus, not the law.

FALSE POSITIVE -- document 3291, the Tariff Standards & Procedure Rules, 1998.
It is complete: rule 27 ends "...as to why the fine may not be imposed.", then
the Secretary's signature block, then footnotes. Its contents prints 31/32/33
where its body prints 25/26/27 -- a numbering offset, not a missing tail. It was
flagged because the last block is a footnote ending in a curly closing quote,
which the ASCII terminator class did not contain.

WHAT REPLACES THEM. Everything is now read from the TEXT BLOCKS and the
document's own character count, which are source evidence, and never from the
provision tree.

    ACCUSING SIGNAL 1 -- the body stops mid-sentence. The tail test walks
    backwards to the last block that is CONTINUING LEGAL PROSE: long enough,
    dense enough in ordinary statutory function words, not the editorial
    footnote apparatus, and not the printing house's colophon. Then it asks
    whether that block ends a sentence, with a Unicode terminator set, so a
    curly quote closes one. For 2205 that block is section 20(3) and it does not
    end; for 3291 it is rule 27(2) and it does.

    ACCUSING SIGNAL 2 -- the file is too thin for what it promises. A contents
    list of thirty sections over 5,436 characters is not holding thirty
    sections. The floor is the corpus's own first percentile of characters per
    substantive contents entry, recomputed on every run and printed with the
    result -- never a number frozen into this file. Entries the contents itself
    marks omitted or repealed are left out of the denominator: they print one
    line each, and counting them reported the Lac Cess Act, 1930 (8 of 12
    sections omitted) as truncated when it is whole. 127 sits at 181 against a
    floor of 421.

    SUPPRESSING SIGNAL -- the body ceiling. Section openers are read from the
    blocks themselves, outside the contents region (every contents entry in this
    corpus retains its exact source block), and cut into ascending runs: a later
    run that restarts at a low number and climbs DENSELY is a Schedule, a Form
    or an Annexure. A body that reaches the top label its contents promises is
    proof the file is not short, and the document is dropped.

    The ceiling only ever suppresses. It was an accusing signal in the first
    draft and had to be demoted: on long statutes the run breaks at the first
    schedule table printed mid-document, so the Income Tax Ordinance, 2001 --
    822 pages, 2.0m characters -- read as holding 26 of its 242 promised
    sections and was reported as truncated.

A document is reported when it has contents entries the tree never satisfied,
its body ceiling is below the promise, and either accusing signal fires.

WHAT IT STILL CANNOT DO. It is a queue, not an adjudication. A statute that ends
in a FORM or a table can still defeat the prose test, and a document whose
openers are typeset in a way this cannot read is measured by nothing -- those
are counted and named separately rather than reported as 0% held. Read the last
pages before calling anything truncated -- and even then, only an independent
official copy settles it, which is the point: the answer to a truncated
acquisition is another acquisition, not another parse.

Reads only. It writes nothing and adjudicates nothing.

    python tools/find_truncated_acquisitions.py [--show N] [--json PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field

from nizam.storage.db import connect
from nizam.workers.verify_ocr import LEGAL, WORD

# A sentence ends with one of these. The first version listed ASCII only and
# lost every document typeset with curly quotes -- 3291 was flagged because
# its last line ended in U+201D.
TERMINATORS = ".;:!?)]}\"'’”»…؟۔‐–—-"

# The editorial apparatus at the foot of a page. These are not the law and they
# say nothing about whether the law stopped: a footnote can end in a clean full
# stop under a section that breaks off mid-clause. Worse, footnote numbering
# restarts on every page, so an unrecognised footnote injects a low label into
# the opener sequence and collapses the body ceiling -- the whole corpus ran at
# 430 hits until "1. Subs. by the Sind Laws ..." stopped reading as section 1.
#
# The verb list is deliberately narrow. "for" and "see" were in the first draft
# and had to come out: a real section opening "1. For the purposes of this Act"
# is not a footnote. So is "1. This Act may be called ...", which is why only
# the gazette's "This Act was passed/published/assented" form is listed.
_FOOTNOTE_VERB = (
    r"(?:subs?|subst|substituted|substitution|ins|inserted|insertion|"
    r"added|addition|omitted|omission|del|deleted|renumbered|re-numbered|"
    r"rep|repealed|ibid|ibidem|vide|now read|"
    r"this (?:act|ordinance|section|rule) was|"
    r"for statement of objects|for the statement of objects|"
    r"printed in the|read as|shall be read|earlier|orig)"
)
FOOTNOTE = re.compile(
    rf"^\s*[*†‡]?\s*\d{{1,3}}\s*[.)\]]?\s*{_FOOTNOTE_VERB}\b",
    re.IGNORECASE)

# A numbered opener: "12.", "16A.", "27)" -- at the head of the block, or on its
# second line where a marginal heading is typeset above it ("Administration of
# Hospital.\n5.\nThe administration and management ...").
OPENER = re.compile(r"^\s*(\d{1,4})\s*[A-Z]?\s*[.)](?:\s|$)")

# The printing house's colophon. It carries enough ordinary words to pass the
# density floor -- "Printed at the Sindh Government Press 7-05-2021 and
# Published by" scores 0.27 -- and it never ends in a stop, so without this it
# reads as a statute breaking off. It is the LAST thing on a complete document,
# which is the opposite of what the tail test is looking for.
IMPRINT = re.compile(
    r"\b(printed (?:at|by|and published)|published by (?:the )?(?:controller|"
    r"manager|director)|government press|printing (?:press|corporation))\b",
    re.IGNORECASE)

# Blocks below these floors are page furniture, marginal headings, table cells
# or signature lines -- never a sentence that the law was in the middle of.
PROSE_MIN_CHARS = 60
PROSE_MIN_WORDS = 10
PROSE_MIN_LEGAL_RATE = 0.12

# A contents list cannot promise a number far beyond the rows it prints. Without
# this bound a trailing year read as a label ("An Act to amend ..., 1972.")
# inflates the promise into the thousands; 30 is slack for suffixed labels.
PROMISE_SLACK = 30

# The second signal is text VOLUME against the promise: a file that prints a
# contents list of thirty sections and holds 5,436 characters cannot be holding
# thirty sections. The threshold is not a number written here -- a criterion
# that encodes today's measurement is a tripwire, not a test -- it is the
# corpus's own first percentile of characters per promised contents entry,
# recomputed on every run and printed with the result.
#
# The first draft used a body/promised LABEL ratio instead and had to be
# withdrawn: on long statutes the opener run breaks at the first schedule table
# printed mid-document, so the Income Tax Ordinance, 2001 -- 822 pages, 2.0m
# characters -- read as holding 26 of 242 promised sections and was reported as
# truncated. Volume does not have that failure mode.
THIN_PERCENTILE = 0.01

# A section the legislature has since omitted or repealed prints as one line:
# "4. *[Omitted]". An Act mostly made of those is thin because the law is thin,
# not because the file is short -- the Lac Cess Act, 1930 (8 of its 12 sections
# omitted) and the Agricultural Produce Cess Act, 1940 (13 of 21) were both
# reported as truncated until the denominator stopped counting them. Both are
# complete: read to the printed "Page 3 of 3" and "Page 4 of 4".
OMITTED_HEADING = r"^\s*[0-9*†]*\s*\[?\s*(omitted|repeal)"


def is_footnote(text: str) -> bool:
    """True when the block is the page's editorial footnote apparatus."""
    return bool(FOOTNOTE.match(text))


def legal_rate(text: str) -> float:
    """Share of ordinary statutory/function words, as verify_text_quality uses."""
    tokens = WORD.findall(text.casefold())
    if not tokens:
        return 0.0
    return sum(token in LEGAL for token in tokens) / len(tokens)


def is_prose(text: str) -> bool:
    """True when the block is continuing legal prose, not apparatus or a table."""
    stripped = text.strip()
    if len(stripped) < PROSE_MIN_CHARS:
        return False
    if is_footnote(stripped):
        return False
    if IMPRINT.search(stripped[:120]):
        return False
    if len(WORD.findall(stripped.casefold())) < PROSE_MIN_WORDS:
        return False
    return legal_rate(stripped) >= PROSE_MIN_LEGAL_RATE


def ends_a_sentence(text: str) -> bool:
    """True when the block's last real character closes a sentence."""
    tail = text.rstrip()
    return bool(tail) and tail[-1] in TERMINATORS


def opener_label(text: str) -> int | None:
    """The section number this block opens, or None.

    The label may head the block or sit on its second line, where a marginal
    heading is printed above it ("Administration of Hospital." then "5." then
    the section's text). A footnote that happens to start with a number is not
    an opener -- and the footnote test must see the WHOLE line, not just the
    number, because "1." and "1. Subs. by ..." are the same first line until
    the newline is collapsed.
    """
    lines = [line for line in text.splitlines() if line.strip()][:2]
    for position in range(len(lines)):
        candidate = re.sub(r"\s+", " ", " ".join(lines[position:])).strip()
        if is_footnote(candidate):
            continue
        found = OPENER.match(candidate)
        if found:
            return int(found.group(1))
    return None


def _restarts(labels: list[int], position: int, ceiling: int) -> bool:
    """True when the label at this position begins a fresh numbering scheme.

    A Schedule, a Form or an Annexure restarts at 1 and climbs DENSELY: 1, 2,
    3. An unrecognised footnote also injects a low label, but the labels after
    it rejoin the body's own ascent and skip past it: 1, then 6, 7. Requiring
    the two labels that follow to continue the restart by one apiece separates
    them -- and a low label with nothing dense behind it is noise, not a new
    scheme.
    """
    label = labels[position]
    if label > ceiling:
        return False
    following = labels[position + 1:position + 3]
    if len(following) < 2:
        return False
    return following == [label + 1, label + 2]


def body_ceiling(labels: list[int]) -> int:
    """The top of the body's own ascending run of openers.

    Truncation loses a contiguous tail, so the body is the run that starts the
    document. A run that restarts densely at a low number after it is a
    Schedule, a Form or an Annexure with its own numbering, and its items are
    not sections -- that is exactly what made document 127 read as holding
    fifteen sections when it holds two.
    """
    ceiling = 0
    for position, label in enumerate(labels):
        if label > ceiling:
            ceiling = label
        elif _restarts(labels, position, ceiling):
            break
    return ceiling


def last_prose_block(texts: list[str]) -> str | None:
    """The last block of continuing legal prose, in reading order."""
    for text in reversed(texts):
        if is_prose(text):
            return text
    return None


@dataclass
class Candidate:
    document_id: int
    instrument_id: str
    title: str
    page_count: int
    char_count: int
    promised_top: int
    entries: int
    substantive_entries: int
    pending_gaps: int
    adjudicated_gaps: int
    thin_floor: float = 0.0
    opener_labels: list[int] = field(default_factory=list)
    tail_texts: list[str] = field(default_factory=list)

    @property
    def body_top(self) -> int:
        return body_ceiling(self.opener_labels)

    @property
    def held_ratio(self) -> float:
        if not self.promised_top:
            return 1.0
        return self.body_top / self.promised_top

    @property
    def chars_per_entry(self) -> float:
        """Text volume against the contents entries that still carry law.

        Entries the contents itself marks omitted or repealed are excluded:
        they print one line each and say nothing about whether the file is
        short.
        """
        if not self.substantive_entries:
            return 0.0
        return self.char_count / self.substantive_entries

    @property
    def too_thin(self) -> bool:
        return (bool(self.thin_floor) and bool(self.substantive_entries)
                and self.chars_per_entry <= self.thin_floor)

    @property
    def tail(self) -> str | None:
        return last_prose_block(self.tail_texts)

    @property
    def stops_mid_sentence(self) -> bool:
        tail = self.tail
        return tail is not None and not ends_a_sentence(tail)

    @property
    def unresolved_entries(self) -> int:
        """Contents entries the tree never satisfied, adjudicated or not.

        A contents list that is fully satisfied is not evidence of anything
        missing, whatever the openers look like -- and an entry already
        adjudicated ``absent_in_source`` is exactly the row this tool exists to
        challenge, so it counts too.
        """
        return self.pending_gaps + self.adjudicated_gaps

    @property
    def openers_read(self) -> bool:
        """False when no opener was recognised at all: nothing was measured."""
        return self.body_top > 0

    @property
    def reasons(self) -> list[str]:
        found = []
        if self.stops_mid_sentence:
            found.append("stops mid-sentence")
        if self.too_thin:
            found.append(f"{self.chars_per_entry:.0f} chars per promised entry")
        return found

    @property
    def truncated(self) -> bool:
        # The body reaching the top label its contents promises is proof the
        # file is not short, whatever the tail looks like -- so body_ceiling is
        # used only to SUPPRESS, never to accuse. That way its known weakness
        # on long statutes cannot invent a truncation.
        # A document whose openers could not be read at all has been measured
        # by nothing: the ceiling is 0 because the typography defeated the
        # reader, not because the law stopped. Those are counted and named
        # separately rather than accused.
        return (self.unresolved_entries > 0
                and self.openers_read
                and self.promised_top > self.body_top
                and bool(self.reasons))


# Live instruments with a numeric contents list, and the promise it prints.
PROMISED = r"""
SELECT i.id::text, i.document_id, coalesce(i.short_title,''), d.page_count,
       d.char_count,
       max((regexp_match(e.printed_label,'^(\d{1,4})'))[1]::int) AS top_promised,
       count(*) AS entries,
       count(*) FILTER (WHERE coalesce(e.printed_heading,'') !~* '{OMITTED}')
         AS substantive_entries,
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id = i.id),
       (SELECT count(DISTINCT a.printed_label) FROM toc_gap_adjudication a
         WHERE a.instrument_id = i.id)
  FROM instrument i
  JOIN document d ON d.id = i.document_id AND d.is_active
  JOIN instrument_toc_entry e ON e.instrument_id = i.id
 WHERE i.is_active AND i.duplicate_of IS NULL
   AND e.printed_label ~ '^\d{1,4}'
 GROUP BY i.id, i.document_id, i.short_title, d.page_count, d.char_count
HAVING count(*) >= 4
"""

# The corpus's own floor for text volume against the promise, recomputed every
# run so that no measurement is frozen into the criterion.
THIN_FLOOR = r"""
WITH per_instrument AS (
  SELECT d.char_count::numeric
         / count(*) FILTER (WHERE e.printed_label ~ '^\d{1,4}'
                              AND coalesce(e.printed_heading,'') !~* '{OMITTED}')
           AS chars_per_entry
    FROM instrument i
    JOIN document d ON d.id = i.document_id AND d.is_active
    JOIN instrument_toc_entry e ON e.instrument_id = i.id
   WHERE i.is_active AND i.duplicate_of IS NULL
   GROUP BY i.id, d.char_count
  HAVING count(*) FILTER (WHERE e.printed_label ~ '^\d{1,4}'
                            AND coalesce(e.printed_heading,'') !~* '{OMITTED}') >= 4
)
SELECT percentile_cont(%s) WITHIN GROUP (ORDER BY chars_per_entry), count(*)
  FROM per_instrument
"""

PROMISED = PROMISED.replace("{OMITTED}", OMITTED_HEADING)
THIN_FLOOR = THIN_FLOOR.replace("{OMITTED}", OMITTED_HEADING)

# Blocks that could open a numbered provision, outside the contents region.
#
# A contents page is one where the contents entries account for most of the
# blocks; a lone entry mis-anchored into the body does not make the body page a
# contents page, and must not delete a real opener from the run.
OPENERS = r"""
WITH toc AS (
  SELECT e.source_block_id, b.document_id, b.page_no
    FROM instrument_toc_entry e
    JOIN instrument i ON i.id = e.instrument_id AND i.is_active
    JOIN text_block b ON b.id = e.source_block_id
), page_blocks AS (
  SELECT document_id, page_no, count(*) AS blocks
    FROM text_block GROUP BY 1,2
), contents_page AS (
  SELECT t.document_id, t.page_no
    FROM toc t JOIN page_blocks p
      ON p.document_id = t.document_id AND p.page_no = t.page_no
   GROUP BY t.document_id, t.page_no, p.blocks
  HAVING count(*) >= 3 AND count(*)::float / p.blocks >= 0.4
)
SELECT b.document_id, b.reading_order, left(b.text, 160)
  FROM text_block b
  JOIN document d ON d.id = b.document_id AND d.is_active
 WHERE btrim(b.text) ~ '^[^\n]{0,80}\n?\s*\d{1,4}\s*[A-Z]?\s*[.)]'
   AND NOT EXISTS (SELECT 1 FROM contents_page c
                    WHERE c.document_id = b.document_id AND c.page_no = b.page_no
                      AND EXISTS (SELECT 1 FROM toc t WHERE t.source_block_id = b.id))
 ORDER BY b.document_id, b.reading_order
"""

# The tail of every live document: enough blocks to walk back past a page
# footer, a signature block and the footnote apparatus.
TAIL = r"""
SELECT document_id, reading_order, text FROM (
  SELECT b.document_id, b.reading_order, b.text,
         row_number() OVER (PARTITION BY b.document_id
                            ORDER BY b.reading_order DESC) AS rn
    FROM text_block b
    JOIN document d ON d.id = b.document_id AND d.is_active) t
 WHERE rn <= 16
 ORDER BY document_id, reading_order
"""


def collect(conn) -> tuple[list[Candidate], float, int]:
    with conn.cursor() as cur:
        cur.execute(THIN_FLOOR, (THIN_PERCENTILE,))
        floor, measured = cur.fetchone()
        floor = float(floor or 0.0)

        cur.execute(PROMISED)
        by_doc: dict[int, Candidate] = {}
        for (iid, doc, title, pages, chars, top,
             entries, substantive, pending, adjudicated) in cur:
            if top is None or top > entries + PROMISE_SLACK:
                continue
            # One live instrument per document is the norm; where a document
            # carries several, the one promising most is the one at risk.
            held = by_doc.get(doc)
            if held is None or top > held.promised_top:
                by_doc[doc] = Candidate(
                    document_id=doc, instrument_id=iid, title=title,
                    page_count=pages, char_count=chars, promised_top=top,
                    entries=entries, substantive_entries=substantive,
                    pending_gaps=pending, adjudicated_gaps=adjudicated,
                    thin_floor=floor)

        cur.execute(OPENERS)
        for doc, _order, text in cur:
            row = by_doc.get(doc)
            if row is None:
                continue
            label = opener_label(text)
            if label is not None:
                row.opener_labels.append(label)

        cur.execute(TAIL)
        for doc, _order, text in cur:
            row = by_doc.get(doc)
            if row is not None:
                row.tail_texts.append(text)

    return (sorted(by_doc.values(),
                   key=lambda r: (r.chars_per_entry, -r.promised_top)),
            floor, measured)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=40)
    ap.add_argument("--json", help="write the full hit list here")
    ap.add_argument("--document-id", nargs="+", type=int,
                    help="explain these documents whatever the verdict")
    args = ap.parse_args()

    with connect() as conn:
        rows, floor, measured = collect(conn)

    hits = [row for row in rows if row.truncated]
    unreadable = [row for row in rows
                  if not row.openers_read and row.unresolved_entries > 0]
    print(f"live instruments with a numeric contents list: {len(rows)} "
          f"(volume floor measured over {measured})")
    print(f"thin floor: {floor:.0f} characters per promised contents entry "
          f"(corpus {THIN_PERCENTILE:.0%} percentile, recomputed this run)")
    print(f"documents whose body stops short of what their contents promises: "
          f"{len(hits)}")
    print(f"contents gaps still pending in them: "
          f"{sum(row.pending_gaps for row in hits)}; labels already "
          f"adjudicated in them: {sum(row.adjudicated_gaps for row in hits)}")
    print(f"documents with unresolved entries whose openers could not be read "
          f"at all (measured by nothing, NOT counted above): {len(unreadable)}")
    print("\ncandidates for a complete official copy, NOT for "
          "absent_in_source. READ THE LAST PAGES BEFORE BELIEVING ANY ROW:\n")
    print(f"{'doc':>6} {'pages':>5} {'promised':>8} {'body':>5} {'ch/ent':>7} "
          f"{'pend':>5} {'adjd':>5}  {'why':<42}  title")
    for row in hits[:args.show]:
        print(f"{row.document_id:>6} {row.page_count:>5} {row.promised_top:>8} "
              f"{row.body_top:>5} {row.chars_per_entry:>7.0f} "
              f"{row.pending_gaps:>5} {row.adjudicated_gaps:>5}  "
              f"{'; '.join(row.reasons)[:42]:<42}  {row.title[:30]}")
    if len(hits) > args.show:
        print(f"  ... and {len(hits) - args.show} more")

    for doc in args.document_id or []:
        row = next((r for r in rows if r.document_id == doc), None)
        if row is None:
            print(f"\ndocument {doc}: no live instrument with a numeric "
                  f"contents list", file=sys.stderr)
            continue
        tail = row.tail
        print(f"\ndocument {doc}  {row.title}")
        print(f"  promised top {row.promised_top} from {row.entries} entries")
        print(f"  body ceiling {row.body_top} from openers "
              f"{row.opener_labels[:24]}")
        print(f"  body reaches {row.held_ratio:.0%} of the promise; "
              f"{row.char_count} chars = {row.chars_per_entry:.0f} per entry "
              f"against a floor of {row.thin_floor:.0f}")
        print(f"  pending gaps {row.pending_gaps}; labels adjudicated "
              f"{row.adjudicated_gaps}")
        print(f"  last prose block: "
              f"{(tail or '(none)')[-110:]!r}")
        print(f"  verdict: {'TRUNCATED -- ' + '; '.join(row.reasons) if row.truncated else 'not truncated'}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump([{
                "document_id": row.document_id,
                "instrument_id": row.instrument_id,
                "title": row.title,
                "page_count": row.page_count,
                "promised_top": row.promised_top,
                "entries": row.entries,
                "body_top": row.body_top,
                "held_ratio": round(row.held_ratio, 4),
                "char_count": row.char_count,
                "chars_per_entry": round(row.chars_per_entry, 1),
                "thin_floor": round(row.thin_floor, 1),
                "pending_gaps": row.pending_gaps,
                "adjudicated_gaps": row.adjudicated_gaps,
                "reasons": row.reasons,
                "last_prose_block": (row.tail or "")[-300:],
            } for row in hits], handle, ensure_ascii=False, indent=1)
        print(f"\nwrote {len(hits)} rows to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
