"""L1 segmentation — Document 02 §5: parse the law, not arbitrary token windows.

    §5.1 Parse headings and labels with a jurisdiction-aware grammar: section 3,
    3-A, 3AA, (1), (a), (i), provisos, explanations, illustrations and schedules.
    Indentation and coordinates are evidence, not truth; numbering, punctuation,
    font changes and table-of-contents reconciliation vote together.

Pure: blocks in, a provision tree out. No database, no filesystem, no network.

THE TABLE OF CONTENTS IS THE GROUND TRUTH
-----------------------------------------
2,855 of the 4,589 documents in this corpus print their own list of sections.
That list is not boilerplate to strip: it is the document telling us what its
sections are and what each one is called. It is used three ways here.

  * as a BOUNDARY.  The contents end where the numbering falls back to 1. That
    is how the body is located -- far more reliably than looking for enacting
    words, which are phrased a dozen different ways.
  * as a HEADING SOURCE.  A body block reads "302. Punishment of qatl-i-amd.
    Whoever commits qatl-e-amd shall...". Splitting the heading from the text by
    punctuation alone is guesswork; the contents entry says the heading is
    exactly "Punishment of qatl-i-amd", so the split is known rather than
    inferred.
  * as an ACCEPTANCE TEST.  Every section the contents promises must appear in
    the body. Agreement below the threshold is a segmentation defect, and doc
    02 §8 says nothing reaches retrieval because a script finished.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
Amendment resolution, commencement, repeal and the typed edges of doc 03b §1.1
all need evidence from outside the document -- gazette notifications and
judgments. Segmentation produces the structure those edges will later attach to;
it does not guess at them.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass, field

# ---------------------------------------------------------------- the grammar
#
# Ordered: the first pattern that matches wins, so the more specific forms come
# first. Every one of these was measured against the corpus before being written
# -- the shares are from a 400,000-block survey, so the grammar is shaped by what
# Pakistani statutes actually do rather than by what a generic parser expects.

# A superscript amendment marker often precedes the label. Measured forms in
# this corpus: "1[302A." (bracketed insertion), "*273." (asterisk footnote) and
# the bare fused digit "1366." which is footnote 1 on section 366 -- PyMuPDF
# concatenates a superscript with the character after it, the same behaviour that
# produced "1Substituted" during extraction verification.
#
# The bracket and asterisk forms are stripped here. The FUSED form cannot be
# stripped by pattern alone -- "1366" is indistinguishable from a real section
# 1366 -- so it is resolved against the contents list in _repair_label(), which
# is precisely the "table-of-contents reconciliation" vote doc 02 §5.1 asks for.
# Consolidated official editions can carry hundreds of amendment notes.  The
# Sales Tax Act 1990 reaches markers 189--192 before sections 3A--3B, rendered
# as ``189[3A.`` by PyMuPDF.  Limiting the superscript to two digits therefore
# turned the marker into a fictitious section prefix and made the real section
# unreachable.  Four digits is deliberately bounded and the opening bracket
# plus a complete provision label below are still required, so ordinary large
# section numbers are not stripped.
_AMEND_PREFIX = (
    r"(?:(?:\d{1,4}\s*)?\[\s*[\"\u201c\u2018']?\s*|[*\u2020\u2021]\s*)?"
)

RULES: list[tuple[str, str, re.Pattern]] = [
    # PART / CHAPTER headings. 1.36% of blocks.
    ("part",    "part",    re.compile(
        r"^\s*PART(?:\s+|\s*[-\u2013\u2014]\s*)([IVXLC\d]+[A-Z]?)"
        r"\s*[.\-\u2013\u2014:]?\s*(.*)$", re.I | re.S)),
    # A small set of Pakistani regulations call their top-level divisions
    # ``SECTION - IV`` and restart ordinary Arabic numbering inside each one.
    # Treating SECTION only as an Arabic provision leaves those restarts under
    # the preceding provision (observation 4725 nested Accounting Policy under
    # regulation 9). Roman numerals make this form unambiguously structural;
    # store it as the schema's part-like container rather than inventing an
    # Arabic section label from the contents-page running index.
    ("part",    "part",    re.compile(
        r"^\s*SECTION\s*[-\u2013\u2014:]\s*([IVXLC]+)"
        r"\s*[.\-\u2013\u2014:]?\s*(.*)$", re.I | re.S)),
    ("chapter", "chapter", re.compile(
        r"^\s*CHAPTER(?:\s+|\s*[-\u2013\u2014]\s*)([IVXLC\d]+[A-Z]?)"
        r"\s*[.\-\u2013\u2014:]?\s*(.*)$", re.I | re.S)),
    ("form", "form", re.compile(
        r"^\s*(FORM(?:\s+(?:NO\.?\s*)?[A-Z0-9IVXLC()./-]+)?)"
        r"\s*[.\-:]?\s*(.*)$", re.I | re.S)),
    ("appendix", "appendix", re.compile(
        r"^\s*((?:APPENDIX|APPENDICES)(?:\s+[A-Z0-9IVXLC()./-]+)?)"
        r"\s*[.\-:]?\s*(.*)$", re.I | re.S)),
    ("annexure", "annexure", re.compile(
        r"^\s*((?:ANNEXURE|ANNEX)(?:\s+[A-Z0-9IVXLC()./-]+)?)"
        r"\s*[.\-:]?\s*(.*)$", re.I | re.S)),
    ("order", "order", re.compile(
        r"^\s*(ORDER\s+[IVXLC\d]+[A-Z]?)\s*[.\-:]?\s*(.*)$",
        re.I | re.S)),
    # Official Pakistani PDFs sometimes letter-space display headings. Missing
    # this explicit container promotes its numbered table rows to competing
    # top-level sections. Require whitespace between every letter so normal
    # prose containing the word "schedule" continues to use the rule below.
    ("schedule", "schedule", re.compile(
        r"^\s*((?:THE\s+)?(?:FIRST\s+|SECOND\s+|THIRD\s+|FOURTH\s+|"
        r"FIFTH\s+|SIXTH\s+|SEVENTH\s+|[IVXLC\d]+\s+)?"
        r"S\s+C\s+H\s+E\s+D\s+U\s+L\s+E)\s*[.\-:]?\s*(.*)$",
        re.I | re.S)),
    # The ordinal is more commonly printed after the word (``SCHEDULE II``).
    # Capture it in the label rather than as trailing prose; otherwise the
    # short Roman numeral looks like a run-on fragment and the second schedule
    # is silently appended to the first.
    ("schedule", "schedule", re.compile(
        r"^\s*((?:THE\s+)?SCHEDULE\s*[-–—]?\s*"
        r"(?:[IVXLC]+|\d+|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH))"
        r"\s*[.\-–—:]?\s*(.*)$", re.I | re.S)),
    ("schedule", "schedule", re.compile(
        r"^\s*(?:THE\s+)?((?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|[IVXLC\d]+)?\s*SCHEDULE)\s*[.\-–—:]?\s*(.*)$",
        re.I | re.S)),
    # Qualifiers, which attach to whatever they follow rather than opening a new
    # branch. Doc 03b §1.1: "never a proviso without what it qualifies".
    ("proviso",      "proviso",      re.compile(r"^\s*(Provided)\b\s*(.*)$", re.S)),
    ("explanation",  "explanation",  re.compile(r"^\s*" + _AMEND_PREFIX + r"(Explanations?(?:\s*[IVX\d]+)?)\s*[.\-–—:]?\s*(.*)$", re.I | re.S)),
    ("illustration", "illustration", re.compile(r"^\s*(Illustrations?)\s*[.\-–—:]?\s*(.*)$", re.I | re.S)),
    ("exception",    "explanation",  re.compile(r"^\s*(Exceptions?(?:\s*[IVX\d]+)?)\s*[.\-–—:]?\s*(.*)$", re.I | re.S)),
    # Rules and regulations are directly citable provisions even when the
    # publisher prints the word before the number (``Rule 690.``). Treat them
    # as section-kind until the model grows distinct kinds. Terminal
    # punctuation prevents matching prose references such as "under rule 2".
    ("section", "section", re.compile(
        r"^\s*(?:Rules?|Regulations?)\s*"
        r"(\d{1,4}(?:\s*\.\s*\d{1,4}){0,4}\s*-?\s*[A-Z]{0,3})"
        r"\s*[.\-:]\s*(.*)$", re.I | re.S)),
    # Numbered units. Hierarchical regulation/rule labels must precede the
    # ordinary section form.  Building regulations in the corpus cite units as
    # ``10.3`` and ``10.3.3`` (often without a final separator); treating the
    # first dot as the end of label turns every one into a second "section 10"
    # and the collision repair then buries real, citable text as a table row.
    # Keep the printed compound label intact.  It remains a section-kind citable
    # unit until the schema grows a distinct regulation/rule provision kind.
    ("section",    "section",    re.compile(
        r"^\s*" + _AMEND_PREFIX
        + r"(\d{1,4}(?:\s*\.\s*\d{1,4}){1,4}"
          r"(?:[A-Z]{1,3}|\s*[-\u2013]\s*[A-Z]{1,3})?)"
          r"(?:\s*[.â€“â€”:]\s*|\s+)(.*)$", re.S)),
    # An omitted provision may be printed wholly inside amendment brackets:
    # ``506[33A***].`` in the official Sales Tax Act. The stars are the body,
    # not part of the citation label.
    ("section",    "section",    re.compile(
        r"^\s*" + _AMEND_PREFIX
        + r"(\d{1,4}\s*[-–]?\s*[A-Z]{0,3})\s*\*+\s*\]\s*\.\s*(.*)$",
        re.S)),
    # Simple section forms, then the bracketed sub-levels.
    # "302." / "302A." / "302-A."  -- 20.5% of blocks
    ("section",    "section",    re.compile(r"^\s*" + _AMEND_PREFIX + r"(\d{1,4}\s*[-–]?\s*[A-Z]{0,3})\s*\.\s*(.*)$", re.S)),
    ("article",    "article",    re.compile(r"^\s*(?:Article|ARTICLE)\s+(\d{1,4}[A-Z]?)\s*[.\-–—:]?\s*(.*)$", re.S)),
    # "(1)" -- 10.1%.  Romanettes are checked before letters because "(i)" and
    # "(v)" are valid in both alphabets and roman numbering nests deeper.
    ("subsection", "subsection", re.compile(r"^\s*" + _AMEND_PREFIX + r"\(\s*(\d{1,3}[A-Z]?)\s*\)\s*(.*)$", re.S)),
    ("romanette",  "clause",     re.compile(r"^\s*" + _AMEND_PREFIX + r"\(\s*((?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)\s*(.*)$", re.S)),
    ("clause",     "clause",     re.compile(r"^\s*" + _AMEND_PREFIX + r"\(\s*([a-z]{1,2})\s*\)\s*(.*)$", re.S)),
]

# Depth in the tree. A qualifier has no depth of its own -- it hangs off the
# provision above it, whatever that is.
DEPTH = {"part": 1, "chapter": 2, "schedule": 2,
         "form": 2, "appendix": 2, "annexure": 2, "order": 3,
         "section": 3, "article": 3,
         "subsection": 4, "clause": 5}
QUALIFIERS = {"proviso", "explanation", "illustration", "preamble"}
# structural containers: they carry a heading, not enacted text of their own
_AUXILIARY_KINDS = {"schedule", "form", "appendix", "annexure", "order"}
_HEADING_KINDS = {"part", "chapter"} | _AUXILIARY_KINDS

# Page furniture that is not law.
#
# PDFs letter-space their footers, so "15 | P a g e" arrives with a space
# between every character and does not match a naive /Page \d+ of \d+/. Measured
# over this corpus: 14,402 blocks print "Page N of M", 3,558 print "N | P a g e"
# and 169 print "Page N". Missing the latter two cost real structure -- a footer
# ending in a lowercase "e" reads as an unfinished sentence, so the division
# heading printed just below it was taken for a continuation of it, and the
# Upper Swat Development Authority Act lost both of its schedules that way.
#
# Matching is done on the text with all whitespace and bars removed, which makes
# the letter-spacing irrelevant.
_PAGE_FOOTER = re.compile(r"^(?:page\d{1,4}of\d{1,4}|\d{1,4}page|page\d{1,4})$", re.I)
_FOOTER_STRIP = re.compile(r"[\s|\u00a0]+")


def _is_running_header(text: str) -> bool:
    """Is this block a page header or footer rather than part of the document?"""
    flat = _FOOTER_STRIP.sub("", text)
    return bool(flat) and len(flat) <= 24 and bool(_PAGE_FOOTER.match(flat))
_FOOTNOTE = re.compile(
    r"^\s*\d{1,2}\s*(?:"
    r"[.:-]?\s*(?:Substituted|Subs|Inserted|Ins|Added|Ibid|"
    r"(?:A\s+)?New\s+(?:sub[- ]?)?section)\b|"
    r"S\.?\s*No\.?\s*.{0,40}\b(?:substituted|inserted|omitted|deleted)\b|"
    r"[.:-]?\s*For\b.{0,120}\b(?:Gazette|statement|report)\b|"
    r"S\.?\s*\d{1,4}[A-Z]?\s*,?\s*"
      r"(?:ins|inserted|subs|substituted|omitted|deleted)\b|"
    r"(?:Omitted|Deleted|Del|Repealed|Rep|"
    r"This\s+Act\s+was\s+(?:assented|published))\b)", re.I)
_SOURCE_HISTORY_START = re.compile(
    r"^\s*\d{1,2}\s*[.:-]?\s*For\s+Statement\s+of\s+Objects?\s+and\s+Reasons?\b",
    re.I,
)
_PUNCTUATED_AMENDMENT_FOOTNOTE = re.compile(
    r"^\s*\d{1,3}\s*[.:-]\s*\n\s*"
    r"In\s+(?:Sections?|Rules?|Articles?)\b.{0,220}"
    r"\b(?:substitut(?:ed|ion)|insert(?:ed|ion)|omit(?:ted|ssion)|amend(?:ed|ment))\b",
    re.I | re.S,
)
_FOOTNOTE_MARKER_LINE = re.compile(r"^\s*\d{1,3}\s*[.:]?\s*$")


def _footnote_markers_only(text: str) -> bool:
    """A block holding nothing but footnote marker numbers, one per line.

    Tested line by line rather than with the single pattern this replaces --
    ``^\\s*\\d{1,3}\\s*[.:]?\\s*(?:\\n\\s*\\d{1,3}\\s*[.:]?\\s*)+$`` -- because
    ``\\s`` matches a newline, so the leading ``\\s*`` and the repeated group's
    ``\\n\\s*`` can both claim the same one. Where most lines match and one does
    not, proving the overall failure means trying every way to divide that
    whitespace, which is exponential in the number of lines.

    It is not hypothetical. Document 3912, the Punjab Contributory Provident
    Fund Rules, carries an 808-character contribution table of 132 numeric
    lines; 97 are one to three digits and 35 are four, so the answer is False
    and the pattern had not produced it after five minutes -- long enough that
    re-segmenting that document could not complete. Splitting on newlines first
    makes each line independent, so the check is linear and returns the same
    answer.
    """
    lines = [line for line in text.split("\n") if line.strip()]
    return len(lines) >= 2 and all(_FOOTNOTE_MARKER_LINE.match(line)
                                   for line in lines)
_PREAMBLE = re.compile(r"^\s*(Preamble|WHEREAS)\b", re.I)
_CONTENTS = re.compile(
    r"^\s*(?:"
    r"C\s*O\s*N\s*T\s*E\s*N\s*T\s*S"
    r"|TABLE\s+OF\s+CONTENTS"
    r"|ARRANGEMENT\s+OF\s+(?:SECTIONS|RULES|ARTICLES)"
    r")\b", re.I)
_WS = re.compile(r"\s+")

# A contents entry whose heading is just "Schedule IV" is pointing at a schedule,
# not describing a section. Statutes number schedules in the same run as
# sections -- "25. Schedule I", "26. Schedule II" -- so reconciling those against
# body sections marks every schedule as a missing section. They are counted
# separately.
_TOC_SCHEDULE = re.compile(r"^\s*(the\s+)?[IVXLC\d]*\s*schedule\b", re.I)
_TOC_PART = re.compile(
    r"^\s*part(?:\s+|\s*[-\u2013\u2014]\s*)([IVXLC\d]+[A-Z]?)\b", re.I,
)
_NUMBERED_TABLE_HEADER = re.compile(r"\bS\.?\s*No\.?\b", re.I)
_TABLE_COLUMN_ORDINAL = re.compile(r"\(\s*(\d{1,2})\s*\)")


def _is_numbered_table_header(text: str) -> bool:
    """Recognise a source-printed serial-number table header.

    ``S. No.`` alone occurs in prose and amendment apparatus, so it is not
    sufficient.  Requiring at least two distinct parenthesised column ordinals
    identifies the actual table grid while remaining independent of portal-
    specific coordinates and column names.
    """
    value = _norm(text)
    columns = set(_TABLE_COLUMN_ORDINAL.findall(value))
    return bool(_NUMBERED_TABLE_HEADER.search(value)) and len(columns) >= 2

# A long printed contents can itself contain nested Order/rule numbering.  Its
# repeated 1..N runs may score like a body boundary even though the enactment
# begins much later.  An explicit enacting formula is stronger source evidence
# than that numeric hypothesis and lets us locate the first provision after it.
_ENACTING_FORMULA = re.compile(
    r"\b(?:WHEREAS\b|IT\s+IS\s+HEREBY\s+ENACTED\b|BE\s+IT\s+ENACTED\b|"
    r"THE\s+FOLLOWING\s+ACT\s+OF\s+(?:PARLIAMENT|THE\s+LEGISLATURE)\b|"
    r"(?:IS\s+PLEASED\s+TO\s+)?MAKE\s+THE\s+FOLLOWING\s+RULES\b)",
    re.I)


# A line ending in a lowercase word, a comma, semicolon, colon or dash has not
# finished its sentence -- whatever follows continues it. Doc 02 5.1: "numbering,
# punctuation, font changes and table-of-contents reconciliation vote together".
# This is punctuation casting its vote.
_UNFINISHED = re.compile(r"[a-z,;:\-\u2013\u2014\u201c\"(]$")


# What follows a real division heading is a heading, a numeral, or nothing --
# never a lowercase word. "Schedule, on every person who receives a return on
# investment in sukuks" is a sentence that happens to break at a line, and the
# Income Tax Ordinance breaks exactly there.
_RUNS_ON = re.compile(r"^[\s.;,:\-–—]*[a-z]")


def _runs_on(rest: str) -> bool:
    """Does the text after a heading's label continue a sentence?"""
    return bool(rest) and bool(_RUNS_ON.match(rest))


def _continues_previous(prev: str | None) -> bool:
    """Is this text the tail of the previous line's sentence?

    The question matters for PART / CHAPTER / SCHEDULE, because statutes refer to
    their own divisions constantly:

        (zzl) "Game animal" means a wild animal included in
        Schedule- I, which may be hunted under a valid licence;

    A layout engine breaks that at the line, so the second block *starts* with
    "Schedule- I" and the grammar sees a schedule heading. Opening one there
    latches every following section inside it: measured over this corpus that
    single misreading re-parented 2,409 provisions across 31 documents, and in
    the Balochistan Wildlife Act it buried sections 3 to 96.

    A real heading follows a finished sentence, a page header, or nothing.
    """
    if not prev:
        return False
    tail = prev.rstrip()
    return bool(tail) and bool(_UNFINISHED.search(tail))


def _norm(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFC", text)).strip()


# Many Pakistani statutes head their contents list with the bare column name
# rather than the word CONTENTS:
#
#     [2nd April, 1991]
#     Preamble
#     Sections
#     1.  Short title and commencement.
#
# Without it the Canal and Drainage (Extension to Rohri Canal Area) Act, 1991
# prints a four-entry contents list that scores 1.000 against its body and is
# still rejected, because the final guard wants either a marker or five entries.
# Its four contents lines then became sections, and the real sections 1-4 were
# demoted to clauses beside them.
#
# Deliberately strict: the line must be that word and nothing else, so a
# sentence mentioning sections cannot pass. `_CONTENTS` stays as it is -- this
# is weaker evidence and is kept visibly separate from the printed word
# CONTENTS.
# ``c\s*o\s*n\s*t\s*e\s*n\s*t\s*s?`` also appears here rather than in _CONTENTS
# because of the singular: the Sind Civil Servants Ordinance, 1973 heads its
# list ``C O N T E N T``, and _CONTENTS requires the trailing S. Loosening it
# there would let a body line beginning "Content of the application ..." count
# as a marker; requiring the WHOLE line to be the word cannot.
_CONTENTS_COLUMN_HEADER = re.compile(
    r"^\s*(?:c\s*o\s*n\s*t\s*e\s*n\s*t\s*s?"
    r"|sections?|rules?|articles?|regulations?|clauses?)\s*[.:]?\s*$",
    re.I)


def _has_contents_marker(text: str) -> bool:
    """Find a printed contents marker even when it shares a PDF text block.

    The KP Forest Ordinance prints its title, citation and ``CONTENTS`` in one
    layout block; several Sindh PDFs letter-space it as ``C O N T E N T S``.
    Matching only the start of the block therefore discarded positive source
    evidence that is plainly visible on the rendered page.
    """
    return any(_CONTENTS.match(line) or _CONTENTS_COLUMN_HEADER.match(line)
               for line in text.splitlines())


@dataclass
class Node:
    kind: str                    # provision_kind
    label: str
    heading: str | None = None
    marginal_note: str | None = None
    operation: str = "original"
    amendment_note: str | None = None
    amended_by_id: str | None = None
    toc_disposition_assertion_id: int | None = None
    text_parts: list[str] = field(default_factory=list)
    depth: int = 0
    first_page: int | None = None
    last_page: int | None = None
    first_block: int | None = None
    children: list["Node"] = field(default_factory=list)
    parent: "Node | None" = None
    blocks: list[int] = field(default_factory=list)   # every block that fed this node

    @property
    def text(self) -> str:
        return _norm(" ".join(self.text_parts))


@dataclass
class Segmentation:
    root: Node
    toc: dict[str, str]                 # section label -> heading, from the contents
    body_starts_page: int
    toc_found: bool
    matched: int = 0
    missing: list[str] = field(default_factory=list)   # promised by contents, absent from body
    extra: list[str] = field(default_factory=list)     # in the body, not in the contents
    schedules_promised: int = 0
    schedules_found: int = 0
    repeated_labels_demoted: int = 0
    repeated_label_decisions: list = field(default_factory=list)
    schedule_sections_retyped: int = 0
    detached_heading_bodies_merged: int = 0
    marginal_notes_split: int = 0
    toc_dispositions_materialised: int = 0
    curation_patches_applied: int = 0
    # block id -> (role, node or None). Every block in the document appears here
    # exactly once; see docs/CORPUS-CRITERIA.md C4/C5.
    block_roles: dict = field(default_factory=dict)
    # The printed contents list, in printed order, each entry carrying the node
    # the body walk produced for it -- or None, which is the gap the document
    # itself proves exists. Written to instrument_toc_entry (migration 0011).
    toc_entries: list = field(default_factory=list)

    @property
    def agreement(self) -> float:
        total = len(self.toc)
        return (self.matched / total) if total else 0.0

    def flatten(self) -> list[Node]:
        out: list[Node] = []

        def walk(n: Node):
            for c in n.children:
                out.append(c)
                walk(c)
        walk(self.root)
        return out


# A cell in a numeric table is not a section. A pay scale prints
# "3100 240 1030 30 14. 3565 275 1181 30", a pesticide schedule prints
# "05 0.05 Carbosulfan Rice 0.2", a tariff prints "9822.2000, 9822.3000" -- and
# a block starting at any of those matches the section rule exactly. The
# remainder tells them apart: enacted text never opens with eight characters of
# digits and punctuation. _INNER already refuses to cut mid-block for this
# reason; this applies the same judgement at a block start.
_NUMERIC_RUN = re.compile(r"^[0-9][0-9\s.,%/()\u2013-]{7,}")
_DOTTED_VALUE_REST = re.compile(
    r"^(?:%|percent\b|paisa\b|rupees?\b|rs\.?\b|pkr\b|kg\b|grams?\b|"
    r"litres?\b|meters?\b|others?\b)", re.I)
_YEAR_TITLE_LINE = re.compile(
    r"^(?:18|19|20)\d{2}\s*\.\s*(?:$|\(?\s*(?:THE\s+)?(?:WEST\s+PAKISTAN\s+|"
    r"KHYBER\s+PAKHTUNKHWA\s+|SINDH?\s+|PUNJAB\s+|BALOCHISTAN\s+)?"
    r"(?:ACT|ORDINANCE)\s+NO\b)", re.I | re.S)


def classify(text: str) -> tuple[str, str, str] | None:
    """Return (rule_name, label, remainder), or None for continuation prose."""
    head = text[:200]
    for name, kind, pat in RULES:
        m = pat.match(head)
        if m:
            label = _norm(m.group(1))
            rest = text[m.start(2):] if m.lastindex and m.lastindex >= 2 else ""
            if kind == "section" and "." in label:
                first = re.match(r"\d+", label.replace(" ", ""))
                # Decimal rates and tariff headings are quantities, not legal
                # hierarchy.  They were the few regressions revealed by the
                # compound-label repair (e.g. ``1.5 Percent`` and
                # ``9812.7900 Others``).
                if ((first and int(first.group()) in {0}
                     or first and int(first.group()) >= 1000)
                        or _DOTTED_VALUE_REST.match(rest.lstrip())):
                    return None
            if kind == "section" and re.match(r"^0(?:\D|$)", label):
                return None
            if kind == "section" and _YEAR_TITLE_LINE.match(text):
                return None
            if kind in ("section", "article") and _NUMERIC_RUN.match(rest.lstrip()):
                return None
            return kind, label, rest
    return None


# ------------------------------------------------------- block sub-division
#
# Doc 02 §5.1: "Indentation and coordinates are evidence, not truth." A PyMuPDF
# block is a typographic unit -- text grouped by visual proximity -- and it has
# no relationship to where one provision ends and the next begins. A single
# block on page 4 of the Abaseen Construction Ordinance holds the tail of
# section 5's clause (c), the whole of section 6, and the opening of section 7.
#
# So the grammar is applied to every plausible provision START inside a block,
# not only to the first character of it.
#
# The guard against false splits is deliberately strict, because splitting mid
# sentence would fabricate a provision that does not exist -- a worse failure
# than missing one. A candidate must be preceded by a sentence ending or a line
# break, AND be a form that opens a provision.
_INNER = re.compile(
    r"(?:(?<=[.;:—\-])\s+|(?<=\n)[ \t\u00a0]*)"          # after sentence end or newline
    r"(?="                                                 # followed by...
    r"(?:\d{1,4}\s*)?\[\s*[\"“‘']?\s*\d{1,4}\s*[-–]?\s*[A-Z]{0,3}\s*\.\s*(?:[A-Z(*\"“]|\d{1,4}\s*\[)" # 3[19-B. / 1[“6-A.
    r"|(?:\d{1,4}\s*)?\[\s*\d{1,4}\s*[-–]\s*[A-Z]{1,3}\s*\]\s*\.\s*[A-Z]" # 7[3-A]. Notices
    r"|(?:\d{1,4}\s*)?\[\s*Sections?\s+\d{1,4}[A-Z]{0,3}\s*\." # 1[Section 10.
    r"|(?:\d{1,4}\s*)?\[\s*\d{1,4}[A-Z]{1,3}\s*\n\s*[A-Z]" # 697[72A newline Heading
    r"|(?:\d{1,4}\s*)?\[\s*[lI]\d{1,3}[A-Z]{0,3}\s*\.\s*[A-Z]" # 3[l35A. OCR glyph
    r"|\d{5,8}[A-Z]{0,3}\s*\.\s+[A-Z(]"                    # 52337A. TOC-proved fused marker
    r"|\d{1,4}\s*[-–]?\s*[A-Z]{0,3}\s*\.\s+[A-Z(*]"       # 302. heading / 42. ***
    # ``21.(1)`` -- the first subsection set tight against the number,
    # with no space after the period. Every alternative above requires
    # that space, so this opener stayed inside the previous section's
    # block and the section did not exist.
    r"|\d{1,4}\s*[-–]?\s*[A-Z]{0,3}\s*\.\s*\(\s*\d{1,3}[A-Z]?\s*\)\s*[A-Za-z]"
    # Consolidations keep repealed/omitted provisions as directly citable
    # placeholders, commonly ``3. [Repeal.]``. When PyMuPDF fuses that line
    # to the preceding provision, the opening bracket used to make the label
    # unreachable. Restrict this boundary to explicit disposition words: a
    # generic ``3. [`` is too common in amendment notes and statutory tables.
    r"|\d{1,4}\s*[-–]?\s*[A-Z]{0,3}\s*\.\s+\[\s*"
      r"(?:Repeal(?:ed)?|Omitted|Deleted)\b"
    r"|\d{1,4}\s*-?\s*[A-Z]{0,3}\s*\.\s+\d{1,4}\s*\[" # 7. 1[(1)
    r"|\d{1,4}\s*-?\s*[A-Z]{0,3}\s*\.\s+[\"“]"       # 2. \"definition\"
    r"|\(\s*\d{1,3}[A-Z]?\s*\)\s*[A-Za-z]"                # (2) text
    r"|Provided\b"
    r"|Explanations?\b"
    r"|Illustrations?\b"
    r")")

# A publisher may place consecutive ``Rule N.`` paragraphs in one typographic
# block. Cut only when the prefix begins a new extracted line: prose references
# to "rule 2" remain untouched, while ``Rule 820. ...\nRule 821.- ...`` becomes
# two directly citable units.
_INNER_RULE = re.compile(
    r"(?<=\n)[ \t\u00a0]*"
    r"(?=(?:Rules?|Regulations?)\s*\d{1,4}(?:\s*\.\s*\d{1,4}){0,4}"
    r"\s*-?\s*[A-Z]{0,3}\s*[.\-:])",
    re.I)

# OCR layout engines preserve a printed list as one ``ListGroup`` block.  The
# HTML-to-text candidate is still source-faithful, but clauses ``(a)`` through
# ``(m)`` then sit inside one typographic block and only the first becomes a
# node.  Expose alphabetic/romanette starts under the same conservative guard
# as numeric inner units: a source line break or preceding list punctuation.
# This does not match prose references such as ``under clause (b)``.
_INNER_ALPHA = re.compile(
    r"(?:(?<=[.;:\u2014\-])\s+|(?<=\n)[ \t\u00a0]*)"
    r"(?=\(\s*(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)\s*"
    r"[A-Za-z\"\u201c\u2018])",
    re.I,
)

# Editorial source histories are occasionally fused to the final operative
# clause in the same extracted block. Expose the canonical ``For Statement of
# Objects and Reasons`` marker as its own unit so it and the continuation below
# can be assigned to apparatus without swallowing the preceding law.
_INNER_SOURCE_NOTE = re.compile(
    r"(?<=\n)[ \t\u00a0]*"
    r"(?=\d{1,2}\s*[.:-]?\s*For\s+Statement\s+of\s+Objects?\s+and\s+Reasons?\b)",
    re.I,
)

# A source-proved section can omit the full stop after its number while still
# beginning on a new extracted line (Sindh High Court Rules: ``13  Efficiency
# and Discipline:``). This pattern only exposes the candidate boundary. The
# body classifier still requires exact next-label and TOC-heading agreement,
# so numeric table rows split here remain ordinary continuation text.
_INNER_BARE = re.compile(
    r"(?<=\n)[ \t\u00a0]*"
    r"(?=\d{1,4}(?:[ \t]*[-\u2013\u2014][ \t]*[A-Z]{1,3}|[A-Z]{0,3})"
    r"[ \t\u00a0]{2,}[A-Z])",
)


# A division heading fused with page furniture is unreachable at a block start.
# The Khyber Pakhtunkhwa local-government Act prints
#
#     15 | P a g e
#     Schedule-I
#     [see section 7(1)]
#
# as ONE block, so "Schedule-I" is never at position 0 and the schedule is never
# opened -- after which its penalty table's rows (13., 14., 15. ...) become
# top-level sections of the Act and collide with the real sections 13 to 18.
# 259 blocks across 127 documents carry a division heading this way.
_INNER_DIV = re.compile(
    r"(?<=\n)[ \t\u00a0]*"
    r"(?=(?:THE\s+)?"
    # A four-digit year after ``Order`` is ordinarily a citation embedded in
    # prose (``Freezing and Seizure) Order 2019, published ...``), not a nested
    # structural heading.  Let a block-start title remain classifiable, but do
    # not manufacture an inner Order node merely because a wrapped citation
    # begins a new extracted line (document 3180, block 321097).
    r"(?:PART|CHAPTER|SCHEDULE|FORM|APPENDIX|APPENDICES|ANNEX|ANNEXURE|"
    r"ORDER\s+(?!(?:18|19|20)\d{2}\b)[IVXLC0-9]+"
    r"|(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)"
    r"[\s-]*SCHEDULE"
    r"|[IVXLC0-9]+[\s-]*SCHEDULE)\b)",
    re.I)


# A marginal heading fused ahead of its own section hides the section entirely.
# PyMuPDF emits the heading, the number and the text as one block, so section 27
# of the Balochistan Education Foundation Act is appended to section 26 and
# leaves the corpus.
#
# This is deliberately a rule about the START of a block, not a general internal
# cut. Tried as an _INNER alternative it also fired inside footnote runs -- a
# line of amendment notes offers the same number-dot-superscript shape -- and
# shredded them into fabricated sections.
_FUSED_MARGIN_PREFIX = re.compile(
    r"^([A-Z][^\n]{2,60}?\.)\s*\n\s*(\d{1,4}\s*[-–]?\s*[A-Z]{0,3}\s*\.\s*"
    r"(?:\d{1,3}(?=[A-Z])|[A-Z(*]).*)$",
    re.S,
)


def subdivide(text: str) -> list[str]:
    """Cut one block at internal provision starts. Returns >= 1 piece.

    There is no minimum length. A 60-character floor used to stand here on the
    theory that a short block cannot hold two provisions; measured against the
    corpus it silently merged 1,754 blocks, among them
    "1. Short title and commencement. \n2. Repeal." -- two sections read as one.
    _INNER is the guard, and it is a strict one: a cut needs a sentence ending or
    a line break *and* a form that opens a provision.
    """
    fused = _FUSED_MARGIN_PREFIX.match(text)
    if fused and not _FOOTNOTE.match(text):
        return [fused.group(1)] + subdivide(fused.group(2))

    raw_cuts = ({m.end() for m in _INNER.finditer(text)}
                | {m.end() for m in _INNER_RULE.finditer(text)}
                | {m.end() for m in _INNER_ALPHA.finditer(text)}
                | {m.end() for m in _INNER_SOURCE_NOTE.finditer(text)}
                | {m.end() for m in _INNER_BARE.finditer(text)}
                | {m.end() for m in _INNER_DIV.finditer(text)})
    # Do not cut a whitespace-padded dotted citation label (``6 . 2 .``) at
    # its internal dot.  A genuine new section may follow a sentence-ending
    # dot, but that sentence does not itself end in a bare number.
    cuts = sorted(c for c in raw_cuts if not (
        (re.search(r"\d[ \t]*\.[ \t]*$", text[:c])
         and re.match(r"\d{1,4}\s*\.", text[c:]))
        # A tariff cell can wrap a currency amount after its abbreviation:
        # ``in excess of Rs.\n1000.\nTen rupees.``.  The amount plus the
        # capitalised rate has exactly the typography of an internal section,
        # but the explicit currency prefix proves it is tabular data. Keep it
        # in the governing amendment instead of fabricating section 1000.
        or (re.search(r"\bRs\.\s*$", text[:c], re.I)
            and re.match(r"\d{1,4}\s*\.", text[c:]))
        # A division word may be the heading of the numbered provision just
        # before it.  Official contents pages commonly extract ``3.\nFORM AND
        # VERIFICATION ...`` as one block.  Cutting at FORM leaves section 3
        # with an empty heading, after which the source entry disappears from
        # the TOC ledger.  Suppress only a division cut immediately following
        # a bare provision label; genuine later ``FORM A`` blocks still split.
        or (re.search(
                r"(?:^|\n)\s*\d{1,4}\s*[-\u2013]?\s*[A-Z]{0,3}\s*\.\s*$",
                text[:c], re.I)
            and re.match(
                r"(?:THE\s+)?(?:PART|CHAPTER|SCHEDULE|FORM|APPENDIX|"
                r"APPENDICES|ANNEX|ANNEXURE|ORDER)\b",
                text[c:], re.I))
        # ``Note. 1. ...`` numbers an explanatory note; it does not open a
        # new section. Keep the printed note attached to its governing rule.
        or re.search(r"\bNotes?\.\s*$", text[:c], re.I)))
    if not cuts:
        return [text]
    pieces, prev = [], 0
    for c in cuts:
        piece = text[prev:c]
        if piece.strip():
            pieces.append(piece)
        prev = c
    tail = text[prev:]
    if tail.strip():
        pieces.append(tail)
    return pieces or [text]


def _is_furniture(text: str, y0: float, page_height: float) -> bool:
    t = text.strip()
    if not t or _is_running_header(t):
        return True
    # Amendment footnotes sit in the bottom margin and restart at 1 on every
    # page. They are evidence about the law, not the law, and they wreck the
    # numbering if fed to the grammar.
    return bool(y0 > page_height * 0.86 and (
        _FOOTNOTE.match(t) or _PUNCTUATED_AMENDMENT_FOOTNOTE.match(t)
    ))


def _section_numbers(blocks: list[dict]) -> list[tuple[int, int, str, str]]:
    """(index, number, label, heading) for every block that opens like a section."""
    out = []
    for i, b in enumerate(blocks):
        # A footnote list in the bottom margin is not a section opener, and
        # letting it look like one corrupts the CONTENTS BOUNDARY, not merely a
        # node. The Khyber Pakhtunkhwa (Restricting the Sale of the Holy Quran)
        # Act, 1939 is the case: its page-2 footnotes read
        #
        #     1. Subs vide the Khyber Pakhtunkhwa Act No. IV of 2011.
        #     2. The word "Province" omitted by W.P. Laws ...
        #
        # so the numbering appeared to restart at 1 there, parse_contents chose
        # that block as where the body resumes, and the Act's real sections --
        # four blocks earlier on the same page -- were swallowed into the
        # contents region. The document ends with zero sections and four gaps.
        #
        # `_is_furniture` already makes this judgement, on position plus the
        # footnote vocabulary; it simply was not consulted here, so apparatus
        # got a vote on where the law begins.
        if _is_furniture(b.get("text") or "", b.get("y0", 0) or 0,
                         b.get("page_height", 792) or 792):
            continue
        for piece in subdivide(b["text"]):
            c = classify(piece)
            if not c or c[0] != "section":
                continue
            label = c[1].replace(" ", "")
            m = re.match(r"^(\d+)", label)
            if m:
                out.append((i, int(m.group(1)), label, _norm(c[2])))
    return out


# A two-column run must be corroborated by the body at this rate before it is
# believed to be a contents list. Genuine ones measure 1.00; the tables that
# broke six documents measured 0.02 to 0.83.
_TWOCOL_MIN_CORROBORATION = 0.90

# Below this, the contents-list hypothesis is refuted rather than imperfect.
# Chosen from the corpus, not from taste -- see the comment in parse_contents.
_TOC_MIN_AGREEMENT = 0.30


# A contents list is often set as a two-column table -- the number in one
# column, the heading in the next -- and a layout engine emits those as two
# lines with no period between them:
#
#     94
#     Power of Garrison Commander on reference under section 93.
#
# The body always prints "94." with the period, so this form is never trusted to
# create a provision. It is used for one purpose only: finding where the
# contents list ends. Without it the Cantonments Ordinance's 302-entry contents
# list was invisible, the body was mistaken for it, and 218 sections were lost.
_TWOCOL = re.compile(
    r"(?:^|\n)[ \t\u00a0]*(\d{1,4}\s*[-\u2013]?\s*[A-Z]{0,3})[ \t\u00a0]*\n"
    # A consolidated contents list can preserve an expressly omitted provision
    # as ``16\n[Omitted]``.  The opening bracket made those real printed rows
    # invisible because the ordinary heading branch deliberately starts with a
    # capital letter.  Admit only the closed, bare disposition placeholder here;
    # broad bracketed text would turn schedules and amendment apparatus into TOC
    # entries.
    r"[ \t\u00a0]*((?:[A-Z][^\n]{2,110})|"
    r"(?:\[\s*(?:Omitted|Deleted|Repealed)\s*\.?\s*\])|"
    r"(?:\*+\s*\]?\s*(?:Omitted|Deleted|Repealed)\s*\.?))", re.M | re.I)
# Amendment footnotes wear the same shape -- "1\nInserted by the Finance Act,
# 2003" -- and restart on every page. They are evidence about the law, not a
# contents list.
_AMEND_NOTE = re.compile(
    r"^\s*(Subs|Ins|Inserted|Substituted|Added|Omitted|Deleted|Rep|Repealed|Ibid|"
    r"New|Clause|The\s+(word|words|figure|figures|comma|full)|Section|Sub-section)\b",
    re.I)


# A contents row that is itself a disposition placeholder:
# "4 [Repealed.]", "56 [Omitted]", "93 Repealed."
_DISPOSITION_ROW = re.compile(
    r"^\s*[\[(]?\s*(?:omitted|deleted|repealed)\b", re.I)


def _twocol_run(blocks: list[dict],
                dotted: set[str] | None = None) -> list[tuple[int, int, str, str]]:
    """Contents entries printed as a two-column table, if there is a run of them.

    A single match means nothing -- a footnote looks identical. What identifies a
    contents list is that its numbers ASCEND over a long stretch, which is
    exactly what a page-restarting footnote never does.

    Ascending is necessary and not sufficient. Statutes are full of ascending
    two-column tables that are not contents lists at all, and trusting them cost
    six documents their entire structure:

        doc 4345   1 Arzani.  2 Agroia.  3 Alhan.        a list of villages
        doc 4410   1 Company Title  2 Location           table column headers
        doc 2133   1 Agrotis spp.  2 Aleurocanthus       a schedule of pests
        doc 2616   1 Chairman(BPS-20)  2 Consultant      a staffing schedule

    The test that separates them is what a contents list IS: a summary of
    sections that exist. Nearly every label in a real one reappears in the body
    as a numbered section with its period. Measured over this corpus, genuine
    two-column contents lists overlap the body's section labels at 1.00, while
    the four tables above score 0.02, 0.17, 0.62 and 0.83.
    """
    hits: list[tuple[int, int, str, str]] = []
    for i, b in enumerate(blocks):
        # NOT filtered for furniture here, and that is measured rather than
        # assumed. The ascending-run test this function documents has a hole --
        # a page carrying seven amendment notes numbers them 1 to 7, which
        # ascends exactly like a short contents list -- so the same
        # `_is_furniture` guard that `_section_numbers` now applies was added
        # here too. Over 4,596 documents it changed NOTHING: zero moved. The
        # body-overlap test below already rejects those runs, so the guard was
        # dead code and is not here.
        #
        # The 216 footnote-shaped contents entries in 31 stored instruments are
        # therefore a historical artefact of older parses, not something the
        # current parser still produces.
        for m in _TWOCOL.finditer(b["text"]):
            head = m.group(2).strip()
            # A bare disposition word is still a real contents citation
            # (``31 / Omitted.``). Longer ``Omitted by Act ...`` text is an
            # amendment note and remains excluded.
            if (_AMEND_NOTE.match(head)
                    and not re.fullmatch(
                        r"(?:Omitted|Deleted|Repealed)\s*\.?", head, re.I
                    )):
                continue
            label = m.group(1).replace(" ", "")
            n = re.match(r"^(\d+)", label)
            if n:
                hits.append((i, int(n.group(1)), label, _norm(head)))

    def order_key(value: str) -> tuple[int, str]:
        match = re.match(
            r"^(\d{1,4})(?:\s*[-\u2013]?\s*([A-Z]{1,3}))?$",
            value.replace(" ", ""),
            re.I,
        )
        return ((int(match.group(1)), (match.group(2) or "").casefold())
                if match else (-1, ""))

    best: list[tuple[int, int, str, str]] = []
    run: list[tuple[int, int, str, str]] = []
    for h in hits:
        if run and order_key(h[2]) <= order_key(run[-1][2]):
            if len(run) > len(best):
                best = run
            run = []
        run.append(h)
    if len(run) > len(best):
        best = run
    if len(best) < 8:
        return []

    if dotted is None:
        dotted = {lbl for _, _, lbl, _ in _section_numbers(blocks)}
    # A contents row that IS a disposition placeholder -- "4 [Repealed.]",
    # "56 [Omitted]" -- cannot corroborate against the body's dotted numbering,
    # because the whole point of it is that no such section is in the body. It
    # therefore has no business in the denominator of a test that asks how much
    # of this list the body confirms: keeping it there penalises a contents list
    # for being accurate about its own repeals.
    #
    # The Registration Act, 1908 is the case. Its five-page contents scores
    # 89/99 = 0.899 against a 0.90 floor and is rejected by one entry; five of
    # its rows are [Repealed.] placeholders, and without them it is 86/94 =
    # 0.9149. Rejecting it cost the whole Act -- toc_found False, and the body
    # then swallowed into a schedule under Part XV with no citable section at
    # all.
    placeholders = {lbl for _, _, lbl, head in best
                    if _DISPOSITION_ROW.match(head)}
    labels = {lbl for _, _, lbl, _ in best} - placeholders
    if not labels or len(labels & dotted) / len(labels) < _TWOCOL_MIN_CORROBORATION:
        return []
    return best


def parse_contents(blocks: list[dict]) -> tuple[dict[str, str], int, bool]:
    """Read the printed contents and find where the body begins.

    The boundary is chosen by AGREEMENT rather than by the first numbering fall.
    A fall to 1 happens many times in a long statute -- schedules, forms and
    numbered lists all restart -- and the Constitution produced 119 of them, so
    taking the first put the boundary 170 pages into the document.

    Instead every fall is a candidate, and the one kept is the one under which
    the contents and the body agree best. The correct boundary is by definition
    the split that makes the document's own list of sections match the sections
    that follow it; a wrong split destroys that agreement. This is doc 02 §5.1's
    "numbering ... and table-of-contents reconciliation vote together", with the
    votes actually counted.
    """
    nums = _section_numbers(blocks)
    # A statute with three sections still prints a contents list, and missing it
    # still duplicates those three sections -- once from the contents, once from
    # the body. Requiring the numbering to reach 8 before a fall could count made
    # short statutes undetectable by construction: 743 documents print a contents
    # list the parser could not see, and 1,690 instruments ended up carrying a
    # section label twice, which breaks INV-4 outright. The threshold now follows
    # the document's own length.
    peak_needed = 8 if len(nums) > 24 else 2
    # Fold in a two-column contents list where one exists, so the fall from its
    # last entry to the body's first section becomes a visible candidate.
    twocol = _twocol_run(blocks, {lbl for _, _, lbl, _ in nums})
    if twocol:
        seen_at = {(i, lbl) for i, _, lbl, _ in nums}
        nums = sorted(nums + [h for h in twocol if (h[0], h[2]) not in seen_at],
                      key=lambda h: h[0])
    if len(nums) < 4:
        return {}, 0, False

    # A contents marker proves that the *opening* numbered run is a list. A
    # marker found later cannot retroactively turn enacted pages into contents:
    # document 8514 contains one at page 105 after a complete 104-page version,
    # and the old global scan classified those 104 pages as its table of
    # contents. Restrict the evidence to the prefix at or before the first
    # section-shaped entry.
    marker_end = min(len(blocks), nums[0][0] + 1)
    saw_marker = any(_has_contents_marker(b["text"])
                     for b in blocks[:marker_end])

    candidates, peak = [], 0
    for idx, n, _, _ in nums:
        if peak >= peak_needed and n <= 2 and idx > 0:
            candidates.append(idx)
        peak = max(peak, n)
    if not candidates:
        return {}, 0, False

    def score(boundary: int) -> tuple[float, dict[str, str]]:
        toc: dict[str, str] = {}
        for idx, _, label, heading in nums:
            if idx >= boundary:
                break
            if label not in toc and heading:
                toc[label] = heading
        if len(toc) < 2:
            return 0.0, toc
        body = {label for idx, _, label, _ in nums if idx >= boundary}
        # A contents list summarises a body. It cannot be longer than the thing
        # it summarises, so a split leaving fewer numbered units after it than
        # before it is upside down -- the body has been read as the contents.
        # Measured over the corpus: below 0.30 agreement, 91 of 116 documents
        # have this shape; above it, 20 of 2,468 do.
        if len(body) < len(toc) * 0.5:
            return 0.0, toc
        # repair fused labels before scoring, or the score punishes the very
        # thing the repair exists to fix
        body = {_repair_label(l, toc) for l in body}
        matched_toc, _ = _reconcile_label_sets(set(toc), body)
        return len(matched_toc) / len(toc), toc

    scored = [(cand,) + score(cand) for cand in candidates[:400]]
    best_score = max((sc for _, sc, _ in scored), default=-1.0)

    # Candidates often tie, and taking the first was arbitrary. The Bolan
    # University Act lists its sections 1-60 and then, still inside the contents,
    # the First Statute's own items 1-33. That inner fall ties with the real
    # boundary on agreement, and preferring it left 33 contents entries in the
    # body as duplicate sections.
    #
    # Two rules settle it. The body must OPEN at the lowest section the contents
    # promises, because a boundary one section too late swallows section 1 into
    # the contents. Among the boundaries that do, take the LAST: a later split
    # scoring no worse consumed only labels the body already had, and that is
    # what more contents looks like.
    def opens_at_first_section(boundary: int, toc: dict[str, str]) -> bool:
        numeric = [int(m.group(1)) for k in toc
                   for m in [re.match(r"^(\d+)", k)] if m]
        if not numeric:
            return True
        for idx, _, label, _ in nums:
            if idx >= boundary:
                m = re.match(r"^(\d+)", _repair_label(label, toc))
                return bool(m) and int(m.group(1)) == min(numeric)
        return False

    def heading_corroboration(boundary: int, toc: dict[str, str]) -> float:
        """How much of an unmarked list repeats as later substantive headings.

        Label overlap alone can make a numbered front table look like contents.
        A real contents list also predicts the words that open the later unit.
        Prefix matching is intentional: a body entry continues from its heading
        into enacted text, while a contents entry stops at the heading.
        """
        later: dict[str, list[str]] = {}
        for idx, _, label, heading in nums:
            if idx < boundary or not heading:
                continue
            key = _repair_label(label, toc).replace(" ", "")
            later.setdefault(key, []).append(_norm(heading).casefold())
        supported = 0
        expected = 0
        for label, heading in toc.items():
            wanted = _norm(heading).casefold().rstrip(".–—- ")
            if not wanted:
                continue
            expected += 1
            if any(actual.startswith(wanted)
                   or wanted.startswith(actual.rstrip(".–—- "))
                   or SequenceMatcher(None, wanted, actual).ratio() >= 0.82
                   for actual in later.get(label, [])):
                supported += 1
        return supported / expected if expected else 0.0

    tied = [(c, sc, toc) for c, sc, toc in scored
            if sc >= best_score - 1e-9 and len(toc) >= 2]
    clean = [t for t in tied if opens_at_first_section(t[0], t[2])]
    pick = (clean or tied)
    if not pick:
        return {}, 0, False
    # Among boundaries that label overlap alone cannot separate, prefer the one
    # whose following headings the contents list actually predicts. Taking the
    # last tied candidate assumes a later boundary means more contents, which is
    # right for a genuine two-page contents list and wrong for a numbered table
    # inside the body: a membership grid restarting at 1 ties on labels alone,
    # yet its rows ("Prime Minister", "Finance Minister") repeat none of the
    # promised headings while the real opening repeats all of them. Position
    # still decides a corroboration tie, so documents the headings cannot
    # separate keep the boundary they had.
    best_idx, best_score, best_toc = max(
        enumerate(pick),
        key=lambda item: (heading_corroboration(item[1][0], item[1][2]), item[0]),
    )[1]

    # Some official gazettes typeset marginal headings in a left column and
    # the numbered operative text in a right column. The body parser then sees
    # only a small fraction of the labels promised by a long contents page, so
    # aggregate agreement alone rejects the real boundary. Three consecutive
    # opening headings, an explicit CONTENTS marker and an enacting formula are
    # stronger source evidence than that low recall. Accept the first numbered
    # block after the formula only when each expected heading is visibly in the
    # same block or the immediately preceding block on the same page.
    if saw_marker and best_score < _TOC_MIN_AGREEMENT:
        formulae = [i for i, block in enumerate(blocks[marker_end:], marker_end)
                    if _ENACTING_FORMULA.search(block["text"])]
        for formula in formulae:
            opening = []
            used_labels: set[str] = set()
            for idx, _, label, _ in nums:
                if idx <= formula:
                    continue
                key = _repair_label(label, best_toc).replace(" ", "")
                if key not in best_toc or key in used_labels:
                    continue
                used_labels.add(key)
                opening.append((idx, key))
                if len(opening) == min(3, len(best_toc)):
                    break
            matched_layout = 0
            for idx, key in opening:
                context = _norm(blocks[idx]["text"])
                if idx > 0 and blocks[idx - 1].get("page_no") == blocks[idx].get("page_no"):
                    context = _norm(blocks[idx - 1]["text"] + " " + context)
                wanted = _norm(best_toc[key]).casefold().rstrip(".â€“â€”- ")
                actual = context.casefold()
                if wanted and (wanted in actual
                               or SequenceMatcher(None, wanted, actual[:len(wanted)]).ratio()
                                  >= 0.82):
                    matched_layout += 1
            if len(opening) >= min(3, len(best_toc)) and matched_layout == len(opening):
                best_idx = opening[0][0]
                best_score = _TOC_MIN_AGREEMENT
                # The boundary and the contents must describe the SAME split.
                # This path replaces the boundary with the opening it found and
                # used to leave `best_toc` as whatever max() had chosen, so the
                # two stopped agreeing: the Essential Personnel (Registration)
                # Ordinance kept a 131-entry contents -- Schedule I's list of
                # occupations, "8 Chemist", "9 Metallurgist", "10 Geologist" --
                # against a boundary at block 27, where its seven printed
                # contents rows end and section 1 begins. 124 of those entries
                # could never match a body of seven sections, and every one of
                # them became a top-level section. Recompute the contents for
                # the boundary actually taken.
                _, best_toc = score(best_idx)
                break

    # The score IS the evidence. A boundary scoring 0.06 is not a contents list
    # read badly -- it is a hypothesis the document refuted, and acting on it
    # costs the whole body: the Punjab Distillery Rules kept 8 sections of 272
    # because 24 pages of enacted text were filed as a contents list. When no
    # candidate clears the floor, the honest answer is that this document prints
    # no contents we can locate, and every block is body.
    if best_score < _TOC_MIN_AGREEMENT or len(best_toc) < 2:
        return {}, 0, False
    # The three returns must agree. `toc_found` used to gate only what was
    # REPORTED, while `boundary` gated what actually happened -- so a document
    # could be cut in half on the strength of a contents list the function did
    # not itself believe in. Documents 4300 and 4410 were truncated at blocks 43
    # and 33 with toc_found False, and lost every provision they had.
    #
    # If the evidence is too thin to claim a contents list, it is too thin to cut
    # the body on.
    # An unmarked contents list is possible, but it must occur at the front of
    # the document. Otherwise any later schedule/form that restarts at 1 can
    # make the entire enacted body look like a high-agreement contents list.
    # The guard is deliberately conservative: rejecting an uncertain TOC keeps
    # every page in the body; accepting a false one removes enacted law from the
    # provision tree. Explicit printed markers are not subject to this fallback.
    last_page = max((int(b.get("page_no", 1)) for b in blocks), default=1)


    def agreement_at(candidate_boundary: int) -> float:
        body_labels = {
            _repair_label(label, best_toc).replace(" ", "")
            for idx, _, label, _ in nums if idx >= candidate_boundary
        }
        return len(set(best_toc) & body_labels) / max(len(best_toc), 1)

    def boundary_preserves_toc(candidate_boundary: int) -> bool:
        # CPC's nested Order contents move costs only 0.0056 agreement; false
        # moves in short Acts collapsed 1.000 to 0.08-0.68.  Do not exchange a
        # strong document-level invariant for a local title resemblance.
        return agreement_at(candidate_boundary) >= best_score - 0.02

    def opening_matches_toc(candidate_boundary: int) -> bool:
        """Does the run immediately after a formula reproduce the TOC?

        Several Acts share a generic section 1 ("Short title"), so one match is
        not evidence. Require the first three to five distinct promised labels
        and their headings to agree. This admits an official Rules notification
        whose title is not repeated nearby, while rejecting an appended,
        unrelated enactment.
        """
        matched = 0
        seen_labels: set[str] = set()
        needed = min(5, len(best_toc))
        promised = list(best_toc)[:needed]
        for idx, _, label, heading in nums:
            if idx < candidate_boundary:
                continue
            if matched >= needed:
                break
            key = _repair_label(label, best_toc).replace(" ", "")
            # Amendment notes and tables may repeat the same small numbers
            # between real opening sections.  They are collisions, not
            # negative evidence.  Seek each promised opening label in order
            # and accept an occurrence only when its local source heading also
            # corroborates the printed contents.
            if key != promised[matched] or key in seen_labels:
                continue
            wanted = _norm(best_toc[key]).casefold().rstrip(".â€“â€”- ")
            # Official two-column Acts can emit a marginal heading beside,
            # immediately before, or immediately after the numbered operative
            # block. `_section_numbers` exposes only the inline tail, so judge
            # the opening run against its same-page layout neighbourhood too.
            # Formula, repeated-title, ordered multi-label, and document-level
            # agreement guards must still concur before the boundary moves.
            page = blocks[idx].get("page_no")
            sources = [heading, blocks[idx].get("text", "")]
            for neighbour in (idx - 1, idx + 1):
                if (0 <= neighbour < len(blocks)
                        and blocks[neighbour].get("page_no") == page):
                    sources.append(blocks[neighbour].get("text", ""))
            actuals = [
                _norm(source).casefold()
                for source in sources if _norm(source)
            ]
            is_match = any(
                wanted in candidate or _heading_supports(candidate, wanted)
                for candidate in actuals
            )
            if not is_match:
                continue
            seen_labels.add(key)
            matched += 1
        minimum = min(3, needed)
        return matched >= minimum

    # Prefer an explicit enactment marker when it proves the numeric boundary
    # stopped inside a long contents list.  Select the first section-shaped
    # block after the formula whose label is one promised by the printed TOC.
    # This fixes the Code of Civil Procedure source, where Orders in the TOC
    # restart at 1 repeatedly and the best numeric split was page 17 although
    # the Act's title/enacting formula and section 1 begin on page 37.
    front_titles = [_norm(b["text"]) for b in blocks[:12]
                    if 12 <= len(_norm(b["text"])) <= 220
                    and not _has_contents_marker(b["text"])
                    and classify(b["text"]) is None]

    def repeats_front_title(marker_index: int) -> bool:
        nearby = [_norm(b["text"]) for b in blocks[max(0, marker_index - 12):marker_index]
                  if 12 <= len(_norm(b["text"])) <= 260]
        return any(
            (len(front) >= 20 and (front.casefold() in near.casefold()
                                   or near.casefold() in front.casefold()))
            or SequenceMatcher(None, front.casefold(), near.casefold()).ratio() >= 0.82
            for front in front_titles for near in nearby)

    marker_indexes = [i for i, block in enumerate(blocks)
                      # The numeric scorer may have skipped the real body and
                      # tied on a later schedule restart. Search after the
                      # printed contents prefix, not only after that provisional
                      # (possibly too-late) boundary.
                      if i >= marker_end
                      and int(block.get("page_no", 1)) <= max(5, int(last_page * 0.20))
                      and _ENACTING_FORMULA.search(block["text"])
                      and (repeats_front_title(i) or saw_marker)]
    if marker_indexes:
        marker = marker_indexes[0]
        explicit = next((idx for idx, _, label, _ in nums
                         if idx > marker
                         and _repair_label(label, best_toc).replace(" ", "")
                             in best_toc), None)
        if (explicit is not None
                and boundary_preserves_toc(explicit)
                and opening_matches_toc(explicit)):
            best_idx = explicit
    else:
        # Some rules omit a WHEREAS/enacting formula.  A repeated opening title
        # still proves the start only when the first promised provision after
        # it contains substantive text beyond the exact TOC heading.  A title
        # running header followed by another contents entry fails this test.
        title_repeats = [i for i in range(marker_end, len(blocks))
                         if int(blocks[i].get("page_no", 1))
                            <= max(5, int(last_page * 0.20))
                         and any(
                             (len(front) >= 20 and
                              (front.casefold() in _norm(blocks[i]["text"]).casefold()
                               or _norm(blocks[i]["text"]).casefold() in front.casefold()))
                             or SequenceMatcher(
                                 None, front.casefold(),
                                 _norm(blocks[i]["text"]).casefold()).ratio() >= 0.82
                             for front in front_titles)]
        for title_index in title_repeats:
            candidate = next(((idx, label, heading)
                              for idx, _, label, heading in nums
                              if idx > title_index
                              and _repair_label(label, best_toc).replace(" ", "")
                                  in best_toc), None)
            if candidate is None:
                continue
            idx, label, heading = candidate
            key = _repair_label(label, best_toc).replace(" ", "")
            expected_heading = _norm(best_toc.get(key, ""))
            actual = _norm(heading)
            if (expected_heading
                    and actual.casefold().startswith(expected_heading.casefold())
                    and len(actual) - len(expected_heading) >= 20
                    and boundary_preserves_toc(idx)):
                best_idx = idx
                break
    # Judge front-matter placement only after the source-evidence corrections
    # above.  A numeric tie can initially choose an inner membership list or a
    # schedule restart inside the body.  Rejecting that provisional boundary
    # before the repeated title/enacting formula gets a vote made the correction
    # below unreachable: document 2552 chose an item list on page 4 and returned
    # ``toc_found=False`` even though its Act restarts, with matching headings,
    # immediately after the enactment on page 3.
    boundary_page = int(blocks[best_idx].get("page_no", 1))
    heading_support = heading_corroboration(best_idx, best_toc)
    # A two-page contents list in a ten-page colonial Act puts the body on page
    # 3, which is 30% of the file and used to fail this guard.  Very high
    # contents/body agreement plus heading repetition independently proves this
    # small-document case.  Known false front tables score at most 0.83.
    implicit_is_front_matter = (
        boundary_page == 1
        or (boundary_page <= 10
            and boundary_page / max(last_page, 1) <= 0.20)
        or (boundary_page <= 3 and best_score >= 0.90
            and heading_support >= 0.80))
    found = bool(best_toc) and (
        saw_marker or (len(best_toc) >= 5 and implicit_is_front_matter))
    if not found:
        return {}, 0, False
    return best_toc, best_idx, True


def _toc_source_entries(blocks: list[dict], boundary: int,
                        toc: dict[str, str]) -> list[dict]:
    """Return every parsed printed entry with its page/block evidence.

    ``toc`` remains a label map because it is useful for heading repair during
    the body walk. It cannot, however, be the stored ground-truth object: a dict
    silently overwrites repeated printed labels. This ordered ledger preserves
    each occurrence and points back to the immutable extracted block, whose
    text and bounding box remain the exact evidence.
    """
    dotted = _section_numbers(blocks)
    twocol = _twocol_run(blocks, {label for _, _, label, _ in dotted})
    # A contents list may cite subprovisions directly (``4(1). Heading``).
    # Keep that printed citation intact in the evidence ledger; the body
    # grammar still parses section 4 and subsection (1) separately.
    compound: list[tuple[int, int, str, str]] = []
    for idx, block in enumerate(blocks[:boundary]):
        for piece in subdivide(block["text"]):
            match = re.match(
                r"^\s*(\d{1,4})\s*\(\s*(\d{1,3}[A-Z]?)\s*\)"
                r"\s*\.\s*(.+)$", piece, re.S,
            )
            if match:
                compound.append((
                    idx, int(match.group(1)),
                    f"{match.group(1)}({match.group(2)})",
                    _norm(match.group(3)),
                ))
    candidates = sorted(dotted + twocol + compound, key=lambda h: h[0])
    out: list[dict] = []
    seen: set[tuple[int, str, str]] = set()
    for idx, _, label, heading in candidates:
        if idx >= boundary:
            break
        block = blocks[idx]
        if _is_furniture(
                block["text"], block.get("y0", 0),
                block.get("page_height", 792) or 792,
        ):
            continue
        compound_label = re.match(r"^(\d{1,4})\(", label)
        if ((label not in toc
             and (compound_label is None
                  or compound_label.group(1) not in toc))
                or not heading):
            continue
        key = (idx, label, heading)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "ordinal": len(out),
            "label": label,
            "heading": heading,
            "source_block_id": block.get("id"),
            "source_page": block.get("page_no"),
        })
    return out


def _repair_label(label: str, toc: dict[str, str],
                  seen: set[str] | None = None,
                  actual_heading: str | None = None) -> str:
    """Undo superscript fusion using the contents list as the arbiter.

    PyMuPDF glues a superscript footnote marker to the number that follows it, so
    section 366 carrying footnote 1 arrives as "1366", and section 500 carrying
    footnote 1 arrives as "1500". Pattern matching cannot tell those from a real
    section 1366, and guessing by magnitude would break any statute that genuinely
    runs past a thousand sections.

    The contents settle it. If the label as read is absent from the contents but
    the label with its leading digit removed is present, the leading digit was a
    footnote marker. If neither is present, nothing is changed -- a repair that
    cannot be corroborated is not made.
    """
    key = label.replace(" ", "")
    if not toc:
        return label
    # Absence from the contents is evidence of fusion only when the label as
    # read is implausible for this document. "1366" is: no statute numbering to
    # 500 has a section 1366, so the leading 1 is a footnote marker. "21" is
    # not, in a document whose own contents runs to 72 -- there the absence
    # says the contents is incomplete, not that the number is wrong.
    #
    # The Sindh mining rules prove the difference. Their contents lists
    # 1,2,4,5,6,7,44,45 ... 72 and nothing between 7 and 44, so rules 21 and 22
    # are missing from it. Read literally, the old test stripped both to 1 and
    # 2, and rule 22 -- "Records, and Reporting by Licensee", printed on page 22
    # with an ordinary bold heading -- stopped being citable at all.
    printed_numbers = [int(entry) for entry in toc if entry.isdigit()]
    highest_printed = max(printed_numbers) if printed_numbers else 0
    # Absence is evidence only where the contents is actually speaking. A list
    # that prints 15 and 17 but not 16 is saying 16 is not a section; a list
    # that jumps from 7 to 44 is saying nothing whatever about 21. Measure the
    # distance to the nearest printed number: the Sindh mining rules' hole
    # around rule 21 is 14 wide, while the Zina Ordinance prints 17 one step
    # from the 16 it omits, and that is the difference between an incomplete
    # contents and a deliberate one.
    nearest_printed = min(
        (abs(number - int(key)) for number in printed_numbers),
        default=None) if key.isdigit() else None
    within_printed_range = (
        key.isdigit() and highest_printed and int(key) <= highest_printed
        and nearest_printed is not None and nearest_printed > 3)
    toc_order = list(toc)
    for strip in (1, 2, 3, 4):
        # A number the document's own contents shows to be in range is a
        # provision number, not a marker glued to a shorter one.
        if within_printed_range and key not in toc:
            break
        if len(key) > strip and key[:strip].isdigit():
            candidate = key[strip:]
            if candidate and candidate[0].isdigit() and candidate in toc:
                # If the full numeric reading continues the body sequence and
                # the stripped label has already occurred, the leading digit
                # is part of the provision number.  This covers an official
                # contents list that omits its own omitted rows: after section
                # 15, body ``16. 2[Omitted.]`` is section 16, not a second 6.
                if (seen is not None and candidate in seen
                        and key.isdigit()):
                    numeric_seen = [
                        int(value) for value in seen if value.isdigit()
                    ]
                    if numeric_seen and int(key) == max(numeric_seen) + 1:
                        continue
                if key in toc:
                    # Ambiguous fusion: CPC page 20 emits footnote 1 + section
                    # 25 as ``125.``, while the same Code also has a genuine
                    # section 125.  First use the independently printed body
                    # heading: this prevents a genuine Railways section 116
                    # ("Altering or defacing pass or ticket") from being
                    # relabelled section 16 merely because omitted section 16
                    # is still unseen.  If headings cannot distinguish the two,
                    # printed order settles it, but a sequence already reaching
                    # the full label wins over stripping it.
                    if actual_heading:
                        exact_support = _heading_supports(
                            actual_heading, toc.get(key))
                        candidate_support = _heading_supports(
                            actual_heading, toc.get(candidate))
                        if exact_support != candidate_support:
                            return candidate if candidate_support else key
                    if seen is None or candidate in seen:
                        continue
                    exact_position = toc_order.index(key)
                    if (exact_position == 0
                            or toc_order[exact_position - 1] in seen):
                        continue
                    position = toc_order.index(candidate)
                    if position == 0 or toc_order[position - 1] not in seen:
                        continue
                return candidate
    return label


def _citation_label_key(label: str) -> str:
    """Normalize citation typography without erasing legal punctuation.

    Pakistani official editions alternate between ``53-A``, ``53A`` and
    ``53 A`` for the same inserted section.  Spaces and dash glyphs are purely
    typographic in that position.  Dots are deliberately preserved: ``2.1``
    must never become section ``21``.
    """
    key = re.sub(r"[\s\-\u2013\u2014]+", "", label).casefold()
    # Contents tables in ten active Sindh documents zero-pad their display
    # numbers (``01`` ... ``09``), while the operative body prints ordinary
    # section labels (``1`` ... ``9``).  Padding is typography, but only for a
    # wholly numeric label: stripping zeroes from an alphanumeric identifier
    # could change a publisher-defined citation.  The callers remain
    # ambiguity-safe and accept a normalized key only when it identifies one
    # unmatched label on each side.
    if key.isdigit() and len(key) > 1 and key.startswith("0"):
        key = key.lstrip("0") or "0"
    return key


def _reconcile_label_sets(promised: set[str], seen: set[str]) -> tuple[set[str], set[str]]:
    """Return matched TOC labels and matched body labels, ambiguity-safe.

    Exact labels win.  A typography-equivalent match is admitted only when the
    normalized key names exactly one still-unmatched label on each side.  This
    makes the rule fail closed if a future source genuinely prints both forms.
    """
    matched_promised = promised & seen
    matched_seen = promised & seen
    promised_by_key: dict[str, list[str]] = {}
    seen_by_key: dict[str, list[str]] = {}
    for label in promised - matched_promised:
        promised_by_key.setdefault(_citation_label_key(label), []).append(label)
    for label in seen - matched_seen:
        seen_by_key.setdefault(_citation_label_key(label), []).append(label)
    for key, promised_labels in promised_by_key.items():
        seen_labels = seen_by_key.get(key, [])
        if len(promised_labels) == 1 and len(seen_labels) == 1:
            matched_promised.add(promised_labels[0])
            matched_seen.add(seen_labels[0])
    return matched_promised, matched_seen


def _toc_label_is_next(label: str, toc: dict[str, str],
                       seen: set[str] | None) -> bool:
    """Require ordered TOC evidence before accepting weak label typography."""
    if seen is None or label not in toc or label in seen:
        return False
    order = list(toc)
    position = order.index(label)
    return position == 0 or order[position - 1] in seen


def _heading_tail_supports(context: str | None, expected: str | None) -> bool:
    """Does any TRAILING part of a collected marginal context support the heading?

    ``previous_heading_context`` walks backwards over up to three blocks and
    joins what it finds, so it can pick up the tail of the PREVIOUS section's
    marginal note along with this one's. The Balochistan Sales Tax on Services
    Act collects ``General Default Surcharge.`` for its section 49, where the
    contents promises ``Default Surcharge`` -- "General" is the end of section
    48's note, sitting in the same column three blocks up.

    ``_heading_supports`` compares from the first word, so one stray leading
    word makes it False, and 41 promised sections stopped being citable for it.
    The detached-heading pass already handles exactly this by trying
    progressively shorter selections of the blocks it collected; this applies
    the same idea to the joined string.

    Only SUFFIXES are tried. Dropping words from the front can only discard a
    neighbour's text; dropping from the back would let an unrelated heading
    match on a shared first word.
    """
    if not context or not expected:
        return False
    words = context.split()
    return any(_heading_supports(" ".join(words[start:]), expected)
               for start in range(len(words)))


def _heading_supports(candidate: str | None, expected: str | None) -> bool:
    """Does source layout text independently support the printed TOC heading?"""
    got = _norm(candidate or "").casefold().strip(" .:-–—")
    want = _norm(expected or "").casefold().strip(" .:-–—")
    # A superscript amendment-note marker can be fused to an omitted heading
    # (body ``2[Omitted.]`` versus contents ``[Omitted]``). It is provenance,
    # not a word in the heading.
    got = re.sub(r"^\d{1,4}\s*(?=\[)", "", got)
    got = re.sub(r"\.\]$", "]", got)
    want = re.sub(r"\.\]$", "]", want)
    if not got or not want:
        return False
    got_words = re.findall(r"[a-z0-9]+", got)
    want_words = re.findall(r"[a-z0-9]+", want)
    common_prefix = 0
    for got_word, want_word in zip(got_words, want_words):
        if got_word != want_word:
            break
        common_prefix += 1
    got_heading = re.split(r"\s*[–—]\s*", got, maxsplit=1)[0]
    # Edit-distance similarity is useful for OCR damage in substantive
    # headings, but unsafe for terse legal labels: ``Topic E`` and ``Topic F``
    # score above 0.82 despite naming different things. Short headings must
    # agree by exact/prefix words; reserve fuzzy corroboration for enough text
    # to make the score discriminative.
    fuzzy_heading = min(len(got_heading), len(want)) >= 12
    fuzzy_full = min(len(got), len(want)) >= 12
    return (got.startswith(want) or want.startswith(got)
            or common_prefix >= 5
            or (fuzzy_heading
                and SequenceMatcher(None, got_heading, want).ratio() >= 0.82)
            or (fuzzy_full and SequenceMatcher(None, got, want).ratio() >= 0.82))


def _opening_toc_hints(blocks: list[dict]) -> tuple[dict[str, str], int]:
    """Recover conservative TOC heading hints when fusion defeats its boundary.

    This does not declare a contents list. It captures only the first numbered
    run after an explicit CONTENTS marker and before the enactment/body restart,
    so geometry-backed marginal-note splitting can repair the evidence that
    :func:`parse_contents` will then judge normally.
    """
    numbers = _section_numbers(blocks)
    if not numbers:
        return {}, 0
    first_number = numbers[0][0]
    markers = [index for index, block in enumerate(blocks[:first_number + 1])
               if _has_contents_marker(block["text"])]
    if not markers:
        return {}, 0
    marker = markers[-1]
    formula = next((index for index, block in enumerate(blocks[marker + 1:], marker + 1)
                    if _ENACTING_FORMULA.search(block["text"])), None)

    body_floor = formula + 1 if formula is not None else 0
    if not body_floor:
        labels_seen: set[str] = set()
        for index, _, label, _ in numbers:
            if index <= marker:
                continue
            key = _citation_label_key(label)
            if key in labels_seen and len(labels_seen) >= 2:
                body_floor = index
                break
            labels_seen.add(key)
    if not body_floor:
        return {}, 0

    hints: dict[str, str] = {}
    seen_keys: set[str] = set()
    for index, _, label, heading in numbers:
        if index <= marker:
            continue
        if index >= body_floor:
            break
        key = _citation_label_key(label)
        if key in seen_keys:
            break
        seen_keys.add(key)
        if heading:
            hints[label.replace(" ", "")] = heading
    return hints, body_floor


def _split_fused_marginal_notes(blocks: list[dict], toc: dict[str, str],
                                body_floor: int) -> int:
    """Split a left-column marginal note fused to its operative section.

    Thresholds are document-relative because the five source portals use
    different page boxes. Text is removed from neither the source block nor the
    corpus ledger: the derived block feeds only the operative tail to the
    numbering grammar and carries the prefix as ``marginal_note`` for storage
    on the resulting provision.
    """
    if not toc:
        return 0
    geometry = sorted(float(block["x0"]) for block in blocks
                      if block.get("x0") is not None and block.get("x1") is not None)
    if len(geometry) < 4:
        return 0
    # percentile_disc(0.10) / percentile_disc(0.50), matching the corpus SQL.
    x_left = geometry[max(0, (len(geometry) + 9) // 10 - 1)]
    x_body = geometry[max(0, (len(geometry) + 1) // 2 - 1)]
    headings_by_key: dict[str, list[tuple[str, str]]] = {}
    for label, heading in toc.items():
        headings_by_key.setdefault(_citation_label_key(label), []).append(
            (label, heading))

    # Never split a later same-numbered schedule/list row when the ordinary
    # body walk can already see the promised section.  Document 1117 proves
    # why this must precede geometry: sections 8--15 are normal right-column
    # openings, followed by a charity-purpose schedule whose rows carry those
    # same numbers and span the page.  Geometry alone split the schedule,
    # moved the body boundary from page 2 to 17, and collapsed 228 provisions
    # to 96.  Fusion is a recovery operation, so it is eligible only for TOC
    # labels that the unsplit body numbering cannot already reconcile.
    body_labels = {
        _repair_label(label, toc, actual_heading=heading).replace(" ", "")
        for _index, _number, label, heading
        in _section_numbers(blocks[body_floor:])
    }
    matched_toc, _matched_body = _reconcile_label_sets(set(toc), body_labels)
    unresolved_keys = {
        _citation_label_key(label) for label in toc if label not in matched_toc
    }
    if not unresolved_keys:
        return 0

    split_count = 0
    for index, block in enumerate(blocks):
        if index < body_floor:
            continue
        x0, x1 = block.get("x0"), block.get("x1")
        if x0 is None or x1 is None:
            continue
        if float(x0) > x_left + 6 or float(x1) <= x_body + 40:
            continue
        text = block["text"]
        for marker in re.finditer(r"(?<!\S)(?=\d{1,4})", text):
            if marker.start() == 0:
                continue
            tail = text[marker.start():]
            decision = _classify_body(tail, toc)
            if decision is None or decision[0] != "section":
                continue
            repaired = _repair_label(decision[1], toc, actual_heading=decision[2])
            if _citation_label_key(repaired) not in unresolved_keys:
                continue
            candidates = headings_by_key.get(_citation_label_key(repaired), [])
            if len(candidates) != 1:
                continue
            expected = candidates[0][1]
            marginal = _norm(text[:marker.start()])
            # Marginal notes are concise headings. This length guard prevents a
            # full-width paragraph that merely cites a later section from being
            # cut even if its opening words resemble a contents heading.
            if (not marginal
                    or len(marginal) > max(80, 2 * len(_norm(expected)) + 20)
                    or not _heading_supports(marginal, expected)):
                continue
            block["text"] = tail
            block["marginal_note"] = marginal
            split_count += 1
            break
    return split_count


def _heading_lead(value: str | None) -> str:
    """The printed marginal-heading phrase before body punctuation."""
    normalized = _norm(value or "").casefold().strip(" .:-–—")
    return re.split(r"\s*[.–—]\s*", normalized, maxsplit=1)[0].strip()


def _schedule_identity(value: str | None) -> str | None:
    """Return the printed ordinal from ``Schedule-I`` / ``SCHEDULE II``.

    A numbered TOC row may use its row number as ``printed_label`` and put the
    actual schedule identity in the heading.  Roman identity is the stable
    join key; row number is not a legal schedule citation.
    """
    normalized = _norm(value or "").casefold()
    match = re.search(
        r"\bschedule\s*[-–—]?\s*(first|second|third|fourth|fifth|sixth|"
        r"seventh|[ivxlc]+|\d+)\b", normalized,
    )
    if not match:
        return None
    names = {
        "first": "i", "second": "ii", "third": "iii", "fourth": "iv",
        "fifth": "v", "sixth": "vi", "seventh": "vii",
    }
    return names.get(match.group(1), match.group(1))


def _explicit_schedule_cross_reference(value: str | None) -> bool:
    """Is this a display schedule heading tied to a provision by the source?

    Some consolidations print no schedule ordinal, but do print a self-contained
    heading such as ``SCHEDULE / STANDING ORDERS [SECTION 2(g)]``. That
    bracketed section reference is independent source evidence of a legal
    schedule boundary, not a prose mention of a schedule.
    """
    normalized = _norm(value or "")
    return bool(
        re.match(r"^(?:THE\s+)?SCHEDULE\b", normalized)
        and re.search(
            r"[\[(]\s*SECTION\s+\d{1,4}[A-Z]?"
            r"(?:\s*\([^)]+\))?\s*[\])]",
            normalized,
            re.I,
        )
    )


def _schedule_rule_reference(value: str | None) -> str | None:
    """Return the rule cited by an unnumbered schedule heading.

    Some official rules have one unnumbered ``Schedule (Under Rule 3)`` while
    their numbered contents row reads ``SCHEDULE- Under Rule -3—PART-I``. The
    rule reference is printed independently in both places and is therefore a
    stronger join key than either the TOC row number or a generic ``Schedule``
    label. No reference means no match; callers also require one candidate.
    """
    normalized = _norm(value or "").casefold()
    match = re.search(
        r"\bunder\s+rules?\s*[-\u2013\u2014]?\s*"
        r"(\d{1,4}(?:\s*[-\u2013\u2014]?\s*[a-z]{1,3})?)\b",
        normalized,
    )
    return _citation_label_key(match.group(1)) if match else None


def _part_identity(value: str | None) -> str | None:
    """Return the printed Part ordinal from spaced or hyphenated headings."""
    match = _TOC_PART.match(_norm(value or ""))
    return match.group(1).casefold() if match else None


def _classify_body(text: str, toc: dict[str, str],
                   seen: set[str] | None = None,
                   previous_heading: str | None = None,
                   ) -> tuple[str, str, str] | None:
    """Classify body text, allowing only TOC-proved fused amendment markers.

    A bare ``52337A.`` could be a table code, so the general grammar continues
    to reject labels longer than four digits. In a body whose printed contents
    promise ``37A``, removing the leading ``523`` is evidence-backed: 523 is
    the superscript amendment note visible on the same source page.
    """
    decision = classify(text)
    if decision is not None:
        return decision

    # Some official consolidations omit the final full stop from a bracketed
    # starred omission (``2[31***]``). Keep this out of the general grammar:
    # the same shape appears in contents tables beside a page number. The
    # document's printed TOC must independently promise the label before it can
    # become a body section.
    starred_undotted = re.match(
        r"^\s*" + _AMEND_PREFIX
        + r"(\d{1,4}[A-Z]{0,3})\s*\*+\s*\]\s*(.*)$",
        text,
        re.S,
    )
    if starred_undotted:
        label = _norm(starred_undotted.group(1)).replace(" ", "")
        if label in toc:
            return "section", label, starred_undotted.group(2)

    # An official print that omits the full stop after the section number:
    #
    #     16 Zone approval criteria.- 2[* * * * * * *]
    #     20 Punishment of bigamy.-Any Hindu marriage solemnized after ...
    #    185D Transfer of cases.- (1) Where more than one Special Judge ...
    #
    # classify() returns None for all of these and ('section', ...) the moment a
    # period is added, so a whole section is lost to one missing character. It
    # is right to reject a bare "N " prefix in the general grammar: the same
    # shape is ordinary prose ("under section 16 Zone approval criteria"), a
    # table row, and a list item. What separates them here is the document's own
    # contents, which is this parser's stated ground truth -- require the label
    # to be promised AND the text after it to open with the heading promised for
    # that label. Corroborated both ways, 18 of these exist in the corpus.
    periodless = re.match(r"^\s*(\d{1,4}(?:\s*-\s*[A-Za-z0-9]{1,3}|[A-Z]{1,3})?)"
                          r"\s+(\S.*)$", text, re.S)
    if periodless:
        label = _norm(periodless.group(1)).replace(" ", "")
        rest = periodless.group(2)
        if label in toc and _heading_supports(rest, toc[label]):
            return "section", label, rest

    # A marginal note fused INLINE, ahead of the number, with no line break:
    #
    #     'Visitation. 10. (1) The Chancellor may cause an inspection or'
    #     'Chancellor. 9. (1) The Governor of Balochistan shall be the ...'
    #     'Power and Function of 4.       The following shall be the powers ...'
    #
    # _FUSED_MARGIN_PREFIX already splits this shape, but only when a NEWLINE
    # separates the note from the number -- the extractor joined these two
    # columns onto one line, so the block opens with prose and classify()
    # returns None. Document 252's section 4 does not exist for that reason.
    #
    # "Power and Function of 4." is also an ordinary sentence fragment, so the
    # typography cannot decide it. The contents can: require the label to be
    # promised and the PREFIX to support the heading promised for that label.
    # 26 blocks in the corpus satisfy both.
    inline_note = re.match(
        r"^([^\n\d][^\n]{2,60}?)\s+(\d{1,4}[A-Za-z-]{0,3})\s*\.\s+(\S.*)$",
        text, re.S)
    if inline_note:
        label = _norm(inline_note.group(2)).replace(" ", "")
        if label in toc and _heading_supports(inline_note.group(1), toc[label]):
            return "section", label, inline_note.group(3)

    # Some official consolidations close the amendment bracket before the
    # provision's full stop (Punjab Electricity Act p.2: ``7[3-A].``).  The
    # general amendment prefix intentionally does not consume that closing
    # bracket, so handle this source-proved form explicitly.
    closed_bracket = re.match(
        r"^\s*\d{1,4}\s*\[\s*(\d{1,4}\s*[-–]\s*[A-Z]{1,3})"
        r"\s*\]\s*\.\s*(.*)$", text, re.S,
    )
    if closed_bracket:
        label = _norm(closed_bracket.group(1)).replace(" ", "")
        if label in toc:
            return "section", label, closed_bracket.group(2)

    # Four Balochistan Acts and one other print their section 1 with a lowercase
    # L where the digit belongs -- "l. (1) This Act may be called ...". The
    # extraction is faithful; the glyph in the source text layer is wrong. No
    # digit means no section opens, so section 1 of those Acts -- its short
    # title, extent and commencement -- is absent from the corpus entirely.
    #
    # This stays out of the general grammar because "(l)" is an ordinary
    # alphabetic clause label. It is admissible only where the document's own
    # contents promises section 1, the text then opens as a section does, and no
    # section 1 has been seen -- so a real clause can never take this path.
    ell_for_one = re.match(r"^\s*l\s*\.\s*((?:\(\s*1\s*\)|[A-Z]).*)$", text, re.S)
    if (ell_for_one and "1" in toc
            and (seen is None or "1" not in seen)):
        return "section", "1", ell_for_one.group(1)

    bracketed_section_word = re.match(
        r"^\s*\d{1,4}\s*\[\s*Sections?\s+"
        r"(\d{1,4}[A-Z]{0,3})\s*\.\s*(.*?)(?:\]\s*)?$",
        text, re.I | re.S,
    )
    if bracketed_section_word:
        label = bracketed_section_word.group(1)
        if label in toc:
            return "section", label, bracketed_section_word.group(2)

    # In columnar statutes a marginal heading may precede a bare numeric label
    # in the same extracted block (``Overriding Effect.\n20\nThe ...``).  A
    # bare number is far too weak on its own: accept it only when it is the next
    # unseen printed TOC entry and either the inline or immediately preceding
    # layout heading independently matches that entry.
    marginal = re.match(
        r"^\s*(.{2,160}?)\n\s*(\d{1,4}(?:\s*[-–]\s*[A-Z]{1,3}|[A-Z]{0,3}))"
        r"\s*\n\s*(.*)$", text, re.S,
    )
    if marginal:
        label = _norm(marginal.group(2)).replace(" ", "")
        if (_toc_label_is_next(label, toc, seen)
                and _heading_supports(marginal.group(1), toc.get(label))):
            return "section", label, marginal.group(3)

    bare = re.match(
        r"^\s*(\d{1,4}(?:\s*[-–]\s*[A-Z]{1,3}|[A-Z]{0,3}))"
        r"\s*\n\s*(.*)$", text, re.S,
    )
    if bare:
        label = _norm(bare.group(1)).replace(" ", "")
        rest = bare.group(2)
        inline_heading = _norm(rest).split(":", 1)[0].split(".", 1)[0]
        promised = toc.get(label)
        heading_agrees = (_heading_supports(inline_heading, promised)
                          or _heading_supports(previous_heading, promised))
        # `_toc_label_is_next` keeps a bare table cell from opening a section,
        # and it is the right default. But it is a CHAIN: one opener the parser
        # misses blocks every section after it, however plainly each is printed.
        # The NEPRA Licensing Regulations lose eleven of twelve that way -- the
        # body prints "1", "3", "4" each alone on a line above its own heading,
        # section 2's opener is fused into the definitions block and section 3's
        # into "PART- II", and from there nothing is ever "next" again.
        #
        # So accept a break in the chain only on the strongest evidence the page
        # can give: the label is one the printed contents promises, it has not
        # been seen, and the heading printed beneath the number is EXACTLY the
        # heading the contents prints against that label -- not merely one that
        # `_heading_supports`, which asks the weaker question of whether the
        # words continue into it.
        exact_promised_heading = bool(
            promised
            and (seen is None or label not in seen)
            and _norm(inline_heading).casefold().rstrip(". ")
                == _norm(promised).casefold().rstrip(". ")
        )
        if heading_agrees and (_toc_label_is_next(label, toc, seen)
                               or exact_promised_heading):
            return "section", label, rest
    # A small number of official gazettes print the label and heading in one
    # block but omit punctuation after the number (``13  Efficiency and
    # Discipline:``). Two or more source whitespace characters distinguish
    # that typography from ordinary prose. Still require the exact next TOC
    # label and a matching printed heading; a bare table cell cannot pass all
    # three tests.
    inline_bare = re.match(
        r"^\s*(\d{1,4}(?:\s*[-\u2013\u2014]\s*[A-Z]{1,3}|[A-Z]{0,3}))"
        r"\s{2,}(.+)$", text, re.S,
    )
    if inline_bare:
        label = _norm(inline_bare.group(1)).replace(" ", "")
        rest = inline_bare.group(2)
        inline_heading = _norm(rest).split(":", 1)[0].split(".", 1)[0]
        if (_toc_label_is_next(label, toc, seen)
                and _heading_supports(inline_heading, toc.get(label))):
            return "section", label, rest
    # Some official consolidations omit the full stop after an inserted label.
    # Accept that typography only when the label has an alphabetic suffix, the
    # next extracted line begins like a heading, and the printed TOC promises
    # the exact label (Sales Tax Act p.117: ``697[72A\n Reference ...``).
    no_stop = re.match(
        r"^\s*(?:\d{1,4}\s*)?\[\s*(\d{1,4}[A-Z]{1,3})\s*\n\s*"
        r"([A-Z].*)$", text, re.S,
    )
    if no_stop and no_stop.group(1) in toc:
        return "section", no_stop.group(1), no_stop.group(2)
    glyph = re.match(
        r"^\s*(?:\d{1,4}\s*)?\[\s*([lI]\d{1,3}[A-Z]{0,3})\s*\.\s*"
        r"(.*)$", text, re.S,
    )
    if glyph:
        repaired = "1" + glyph.group(1)[1:]
        if repaired in toc:
            return "section", repaired, glyph.group(2)
    match = re.match(
        r"^\s*(\d{5,8}[A-Z]{0,3})\s*\.\s*(.*)$", text, re.S,
    )
    if not match:
        return None
    printed = match.group(1)
    repaired = _repair_label(printed, toc)
    if repaired == printed:
        return None
    return "section", repaired, match.group(2)


def _split_heading(rest: str, toc_heading: str | None) -> tuple[str | None, str]:
    """Separate a section's heading from its text.

    With a contents entry this is known, not guessed: the entry IS the heading,
    so it is stripped from the front of the block and what remains is the text.
    Without one, fall back to the first sentence-like span, capped so a long
    opening sentence is never mistaken for a heading.
    """
    body = rest.lstrip(" .—-\t\n")
    if toc_heading:
        flat = _norm(body)
        if flat.lower().startswith(toc_heading.lower()[: max(len(toc_heading) - 2, 8)]):
            return toc_heading, _norm(flat[len(toc_heading):]).lstrip(" .—-")
        # A TOC predicts a heading; it does not authorize inventing that
        # heading on a different numbered object. Dense statutory tables often
        # restart at 1, and copying "Short title" onto row 1 destroys both the
        # row's semantics and the independent evidence needed to distinguish it
        # from the real section 1.
        return None, _norm(body)
    m = re.match(r"^(.{4,110}?)\.\s+(?=[A-Z(])", _norm(body))
    if m:
        return _norm(m.group(1)), _norm(body[m.end():])
    # A marginal note is often emitted as its own block, so there is no body
    # text after the terminal full stop for the rule above to look ahead to.
    # Treat only a short, non-operative phrase as a detached heading.  A terse
    # enacted sentence such as "It shall apply." must remain provision text.
    flat = _norm(body)
    if (flat.endswith(".") and 1 <= len(flat.split()) <= 14
            and len(flat) <= 110
            and not re.search(
                r"\b(?:is|are|was|were|shall|may|must|means|includes?|"
                r"appl(?:y|ies|ied)|extends?|comes?|has|have|had)\b",
                flat, re.I)):
        return flat[:-1].strip(), ""
    return None, _norm(body)


def _apply_curation_patches(blocks: list[dict], patches: list[dict]) -> tuple[list[dict], int]:
    """Apply approved parser-input patches without changing extracted evidence.

    Locators use physical page plus a stable text fragment, not a text_block id,
    so an approved correction survives a non-destructive extraction rebuild.
    Ambiguous or stale locators fail closed instead of touching a guessed block.
    """
    if not patches:
        return blocks, 0
    derived = [dict(block) for block in blocks]
    applied = 0
    for patch in patches:
        matches = [block for block in derived
                   if block.get("page_no") == patch["page_no"]
                   and patch["match_text"].casefold() in block["text"].casefold()]
        if len(matches) != 1:
            raise ValueError(
                f"curation patch {patch.get('id')} matched {len(matches)} blocks; expected 1")
        block = matches[0]
        before = patch["before_text"]
        if block["text"].count(before) != 1:
            raise ValueError(
                f"curation patch {patch.get('id')} before_text is not unique")
        block["text"] = block["text"].replace(before, patch["after_text"], 1)
        applied += 1
    return derived, applied


def segment(blocks: list[dict], curation_patches: list[dict] | None = None,
            toc_dispositions: list[dict] | None = None,
            split_fused_margins: bool = False,
            detect_contents: bool = True,
            force_opening_contents: bool = False) -> Segmentation:
    """Build the provision tree.

    `blocks` are dicts with text, page_no, y0, page_height and id, in reading
    order -- exactly what text_block stores.
    """
    blocks, patches_applied = _apply_curation_patches(
        blocks, curation_patches or [])
    toc_dispositions = toc_dispositions or []
    applied_disposition_ids: set[int] = set()
    # Ask the ordinary boundary detector first. If fused marginal notes have
    # hidden too many body labels for it to accept an otherwise explicit TOC,
    # recover only provisional opening-run hints. After the geometric split the
    # full detector runs again; hints never become corpus facts by themselves.
    toc, boundary, toc_found = (
        parse_contents(blocks) if detect_contents else ({}, 0, False)
    )
    if force_opening_contents and detect_contents and not toc_found and blocks:
        # A source-reviewed embedded expression can own a contents row printed
        # on the package's first page while its body begins many pages later.
        # The ordinary implicit-list guard correctly rejects that geometry in
        # the general corpus.  Supplying an in-memory marker lets the same TOC
        # parser run under explicit caller evidence; the synthetic block is
        # removed from the returned boundary and never enters the ledger.
        marker = dict(blocks[0])
        marker.update({"id": None, "text": "CONTENTS"})
        toc, probe_boundary, toc_found = parse_contents([marker] + blocks)
        boundary = max(0, probe_boundary - 1) if toc_found else 0
    toc_hints, body_floor = (
        (toc, boundary) if toc_found else _opening_toc_hints(blocks)
    )
    marginal_notes_split = (_split_fused_marginal_notes(
        blocks, toc_hints, body_floor) if split_fused_margins else 0)
    if marginal_notes_split:
        toc, boundary, toc_found = parse_contents(blocks)
    printed_toc = _toc_source_entries(blocks, boundary, toc) if toc_found else []
    body = blocks[boundary:] if boundary else blocks
    body_page = body[0]["page_no"] if body else 1

    # A heading printed at the top of every page is a running header, not a
    # structure. The Income Tax Ordinance prints "Chapter I - Preliminary" at the
    # head of every page of Chapter I; taking each at face value produced 498
    # chapters and left 9 sections of 240. A real division heading appears once.
    #
    # Two conditions, because either alone is wrong: the text must REPEAT across
    # pages, and it must sit at the TOP of them. "PART I" legitimately appears in
    # several schedules, so repetition alone would delete real structure.
    seen_at: dict[str, set[int]] = {}
    for b in body:
        t = _norm(b["text"])
        ph = b.get("page_height", 792) or 792
        if t and len(t) <= 120 and b.get("y0", 0) < ph * 0.12:
            seen_at.setdefault(t, set()).add(b["page_no"])
    running_headings = {t for t, pages in seen_at.items() if len(pages) >= 3}

    root = Node(kind="instrument", label="", depth=0)
    stack: list[Node] = [root]
    current: Node = root
    seen: set[str] = set()
    label_nodes: dict = {}          # section label -> the node the body produced
    seg_roles: dict = {}
    in_schedule = False
    schedule_node: Node | None = None
    explicit_table_owner: Node | None = None
    roman_section_division_seen = False
    roman_section_division_nodes: list[Node] = []
    max_before_schedule = 0     # highest section number seen when a schedule opened
    max_prefixed_rule_before_schedule = 0
    detached_heading_bodies_merged = 0
    marginal_note_blocks_attached: set[int] = set()
    source_block_by_id = {block.get("id"): block for block in body}

    # The body column's own left edge, for the two indentation tests below.
    #
    # Those tests ask whether a numbered block sits deeper than the provision
    # that owns it, and they asked it against the OWNER'S first block. In a
    # gazette that sets marginal headings in a left column that is not a
    # baseline: the Balochistan Essential Education Services Act prints section
    # 2 as one fused block, "Definition. 2. In this Act, ...", starting at x0
    # 118 in the margin, while section 3's heading is a SEPARATE margin block
    # and its text starts at 230.5 in the body column. 230.5 >= 118 + 18, so
    # section 3 read as an indented sub-item of section 2 and was demoted to a
    # clause -- printed law, no longer citable at its own number. Reading page 3
    # settled it: "3. (1) The Government may, by notification in the official
    # Gazette, declare any Education Service to be an Essential Service", with
    # the contents' exact heading beside it.
    #
    # So compare against the body column as well. A genuinely indented sub-item
    # clears both edges and is still demoted; a section merely sitting at the
    # normal body margin no longer is. percentile 10/50 of x0, the same pair
    # `_toc_marginal_share` and tools/audit use.
    # Weighting this by CHARACTERS rather than block count was tried and
    # reverted. The reasoning was sound -- a plain median counts a four-word
    # marginal fragment the same as a full paragraph, so in a gazette with a
    # populous heading column it lands between the two columns. It did not
    # help: document 275's weighted figure is 190.0 against a plain 185.5,
    # because that document is not cleanly two-column at all (x0 clusters at
    # 72, 166, 190, 217 and 405). And it cost document 3094 a section, measured
    # 8 -> 7 with a gap appearing. Geometry does not settle these; the printed
    # heading does, which is what the demotion rule below now consults.
    _x0s = sorted(float(block["x0"]) for block in body
                  if block.get("x0") is not None)
    body_column_x0 = (_x0s[max(0, (len(_x0s) + 1) // 2 - 1)]
                      if len(_x0s) >= 4 else None)

    def _indented_past_body(block: dict, owner_block: dict | None) -> bool:
        """Deeper than its owner AND deeper than the body column's left edge."""
        if (owner_block is None or block.get("x0") is None
                or owner_block.get("x0") is None):
            return False
        if block["x0"] < owner_block["x0"] + 18:
            return False
        # No usable geometry: keep the original single-edge behaviour rather
        # than silently turning the test off.
        if body_column_x0 is None:
            return True
        return block["x0"] >= body_column_x0 + 18

    # Each block is cut at its internal provision starts before the grammar runs,
    # so a block holding three sections yields three units rather than one.
    units: list[tuple[dict, str]] = []
    for b in body:
        # Keep an amendment-footnote block whole.  Subdividing first can see
        # the citation fragment ``s. 2. It was provided ...`` as a new section
        # even though the block's fused superscript and amendment verb prove
        # the whole block is apparatus (CPC pages 65, 66 and 85).
        pieces = ([b["text"]] if (
            _FOOTNOTE.match(b["text"])
            or _PUNCTUATED_AMENDMENT_FOOTNOTE.match(b["text"])
            or _footnote_markers_only(b["text"])
        ) else subdivide(b["text"]))
        for piece in pieces:
            units.append((b, piece))

    def preceding_prefixed_rule_number(unit_index: int) -> int:
        """Nearest earlier explicit Rule/Regulation number in source order.

        Nearest is intentional. Editorial amendment notes can mention a much
        larger Rule number earlier on the page; a global maximum would then
        hide an ordinary 77 -> 78 enacted sequence.
        """
        for _, prior_text in reversed(units[:unit_index]):
            match = re.match(
                r"^\s*(?:Rules?|Regulations?)\s*(\d{1,4})\b",
                prior_text,
                re.I,
            )
            if match:
                return int(match.group(1))
        return 0

    # Some official layouts print a marginal heading in a separate, narrow
    # column immediately before the wide operative block. PyMuPDF preserves
    # both but orders the heading first. Treating it as continuation therefore
    # appends section 7's heading to section 6's legal text. Identify these
    # blocks only when four independent facts agree: same page, immediately
    # preceding short blocks, horizontally separate columns, and the combined
    # words match the next numbered provision's printed TOC heading.
    detached_heading_for_body: dict[int, tuple[list[int], str]] = {}
    detached_heading_ids: set[int] = set()
    if toc:
        toc_headings_by_label: dict[str, list[str]] = {}
        for entry in printed_toc:
            key = _citation_label_key(entry.get("label") or "")
            value = _norm(entry.get("heading") or "")
            if value and value not in toc_headings_by_label.setdefault(key, []):
                toc_headings_by_label[key].append(value)
            compound_label = re.match(r"^(\d{1,4})\(", key)
            if compound_label and value not in toc_headings_by_label.setdefault(
                    compound_label.group(1), []):
                toc_headings_by_label[compound_label.group(1)].append(value)

        def horizontally_separate(candidate: dict, provision_block: dict) -> bool:
            candidate_x0 = candidate.get("x0")
            candidate_x1 = candidate.get("x1")
            body_x0 = provision_block.get("x0")
            body_x1 = provision_block.get("x1")
            if None in (candidate_x0, candidate_x1, body_x0, body_x1):
                return False
            return bool(
                candidate_x0 >= body_x1 - 2
                or candidate_x1 <= body_x0 + 2
                # PyMuPDF occasionally combines the operative left column and
                # a different marginal note into one wide block. A narrow
                # right-column block aligned with that row is still separate.
                or (candidate_x0 >= body_x0 + 300
                    and candidate_x1 - candidate_x0 <= 140)
            )

        for body_index, provision_block in enumerate(body):
            provision = next((
                decision
                for piece in subdivide(provision_block["text"])
                for decision in [_classify_body(piece, toc)]
                if decision is not None
                and (decision[0] == "section"
                     or (decision[0] == "subsection"
                         and re.match(r"^\s*\(\s*1\s*\)", decision[2])))
            ), None)
            if provision is None:
                continue
            label = _norm(provision[1]).replace(" ", "")
            expected_headings = toc_headings_by_label.get(
                _citation_label_key(label),
                [toc[label]] if label in toc else [],
            )
            body_id = provision_block.get("id")
            body_x0 = provision_block.get("x0")
            body_x1 = provision_block.get("x1")
            if (not expected_headings or body_id is None
                    or body_x0 is None or body_x1 is None):
                continue
            prior_blocks: list[dict] = []
            for prior in reversed(body[max(0, body_index - 4):body_index]):
                if prior.get("page_no") != provision_block.get("page_no"):
                    break
                value = _norm(prior.get("text") or "")
                if not value:
                    continue
                if (_is_running_header(value)
                        or value in running_headings
                        or _is_furniture(
                            value, prior.get("y0", 0),
                            prior.get("page_height", 792) or 792,
                        )
                        or len(value) > 110
                        or any(classify(piece) is not None
                               for piece in subdivide(prior["text"]))):
                    break
                if not horizontally_separate(prior, provision_block):
                    break
                prior_blocks.append(prior)
            prior_blocks.reverse()
            for start in range(len(prior_blocks)):
                selected = prior_blocks[start:]
                combined = " ".join(_norm(row["text"]) for row in selected)
                supported = [expected for expected in expected_headings
                             if _heading_supports(combined, expected)]
                if len(supported) != 1:
                    continue
                heading_ids = [row["id"] for row in selected
                               if row.get("id") is not None]
                if heading_ids and not any(
                        block_id in detached_heading_ids
                        for block_id in heading_ids):
                    detached_heading_for_body[body_id] = (
                        heading_ids, supported[0],
                    )
                    detached_heading_ids.update(heading_ids)
                break
            if body_id in detached_heading_for_body:
                continue

            # Two-column extraction may emit the right marginal heading after
            # the operative block, sometimes after up to two left-column list
            # items. Accept one short, vertically aligned, separate-column
            # block only when it supports exactly one of the printed headings
            # for this repeated label.
            body_y0 = provision_block.get("y0")
            body_y1 = provision_block.get("y1")
            if body_y0 is None or body_y1 is None:
                continue
            for following in body[body_index + 1:body_index + 5]:
                if following.get("page_no") != provision_block.get("page_no"):
                    break
                value = _norm(following.get("text") or "")
                if (not value or len(value) > 110
                        or _is_running_header(value)
                        or value in running_headings
                        or any(classify(piece) is not None
                               for piece in subdivide(following["text"]))
                        or not horizontally_separate(
                            following, provision_block,
                        )):
                    continue
                candidate_y0 = following.get("y0")
                candidate_y1 = following.get("y1")
                if (candidate_y0 is None or candidate_y1 is None
                        or candidate_y0 > body_y1 + 20
                        or candidate_y1 < body_y0 - 20):
                    continue
                supported = [expected for expected in expected_headings
                             if _heading_supports(value, expected)]
                following_id = following.get("id")
                if (len(supported) == 1 and following_id is not None
                        and following_id not in detached_heading_ids):
                    detached_heading_for_body[body_id] = (
                        [following_id], supported[0],
                    )
                    detached_heading_ids.add(following_id)
                    break

    def mark(block: dict, role: str, node=None):
        """Record a block's role. First writer wins, so a block subdivided into
        several provisions is attributed to the first, and a block already
        classified is never silently reclassified."""
        bid = block.get("id")
        if bid is not None and bid not in seg_roles:
            seg_roles[bid] = (role, node)

    # Schedules follow the body. That single fact decides which "SCHEDULE" is a
    # division and which is a cross-reference, and it is the only test that
    # separates the two correctly: the Income Tax Ordinance names its schedules
    # 271 times mid-sentence, while the Code of Civil Procedure's First Schedule
    # is genuine and carries Order VII rule 11.
    #
    # The marker is the last unit opening a section the contents list promises,
    # counted only while the numbering ASCENDS -- schedule rules restart at 1,
    # so they never extend the body, and the CPC's Orders cannot push the marker
    # to the end of the document.
    last_body_section = -1
    toc_schedule_identities = {
        identity for entry in printed_toc
        for identity in [_schedule_identity(entry.get("heading"))]
        if identity is not None
    }
    if toc:
        highest = 0
        boundary_seen: set[str] = set()
        for i, (_, t) in enumerate(units):
            c = _classify_body(t, toc)
            # A source-labelled schedule with its own statutory cross-reference
            # ends the principal body even when schedule item numbers later
            # climb above the Act's final section. Without this stop, Standing
            # Orders 11--20 make an Act ending at section 10 appear to continue
            # through section 20.
            if (c and c[0] == "schedule" and boundary_seen
                    and _explicit_schedule_cross_reference(t)):
                break
            if not c or c[0] != "section":
                continue
            k = _repair_label(
                c[1], toc, boundary_seen, c[2]
            ).replace(" ", "")
            m = re.match(r"^(\d+)", k)
            if k in toc and m and int(m.group(1)) > highest:
                highest = int(m.group(1))
                last_body_section = i
            if k in toc:
                boundary_seen.add(k)

    def previous_content(idx: int) -> str | None:
        """The last unit that was neither a running header nor a footnote.
        Page furniture interrupts the printed line but not the sentence."""
        for j in range(idx - 1, max(-1, idx - 10), -1):
            t = units[j][1]
            # Page furniture -- a header, a bare page number, a footnote -- is
            # skipped rather than treated as a full stop. A page break
            # interrupts the printed line; it does not end the sentence. The
            # Income Tax Ordinance breaks "...chargeable under the First /
            # Schedule, on every person who..." across exactly such a break.
            if _is_running_header(t) or _norm(t) in running_headings:
                continue
            if not _norm(t) or _norm(t).isdigit():
                continue
            if _is_furniture(t, units[j][0].get("y0", 0),
                             units[j][0].get("page_height", 792) or 792):
                continue
            return t
        return None

    # THE RIGHT-MARGIN LAYOUT: built, measured, and removed.
    #
    # 238 of the 350 documents holding pending contents gaps set their marginal
    # notes to the right of the body, and 753 of the 1,045 gaps sit in them, so
    # this looked like the largest remaining lever. The notes arrive after every
    # body block and the whole column is usually ONE block separated by blank
    # lines, which `previous_heading_context` cannot reach because it scans
    # backwards.
    #
    # A helper was added that collected each page's right-margin lines and asked
    # whether any of them supported the heading the CONTENTS promises for the
    # label -- deliberately not pairing the n-th note with the n-th section,
    # since one un-noted section shifts every pairing after it. It was wired
    # into the Table guard and the demotion guard.
    #
    # Measured over 4,596 documents: 6 move, one improves, none regress, and it
    # costs SIX new demotions to close ONE gap. Net worse under the gate, for
    # real added complexity, so it is not here.
    #
    # The reason it does so little is worth keeping: document 3353, the largest
    # cluster, does not have its sections demoted at all. Its tree anchors
    # section 1 to page 11, where the source prints sections 11 and 12 -- the
    # page anchors themselves are wrong, and no heading evidence repairs that.
    # See docs/RELEASING-THE-BLOCKED-INSTRUMENTS.md.

    def previous_heading_context(idx: int) -> str | None:
        """Collect a short same-page marginal heading split across blocks.

        Balochistan PDFs frequently emit ``Powers to make`` and
        ``regulations.`` as two blocks before the number/body column.  Stop at
        the first provision or long prose block so ordinary preceding text
        cannot corroborate a weak bare number.
        """
        parts: list[str] = []
        page = units[idx][0].get("page_no")
        for j in range(idx - 1, max(-1, idx - 4), -1):
            block, raw = units[j]
            if block.get("page_no") != page:
                break
            value = _norm(raw)
            if not value or _is_running_header(value):
                continue
            if _is_furniture(raw, block.get("y0", 0),
                             block.get("page_height", 792) or 792):
                continue
            if len(value) > 100 or classify(raw) is not None:
                break
            parts.append(value)
        return " ".join(reversed(parts)) if parts else None

    source_history_page: int | None = None
    for idx, (b, text) in enumerate(units):
        # Once a canonical source-history footnote starts, its wrapped
        # continuation may occupy several blocks and lose the superscript
        # marker. It remains apparatus through the end of that physical page.
        if source_history_page == b["page_no"]:
            mark(b, "footnote")
            continue
        if _is_running_header(text):
            mark(b, "running_header")
            continue
        if _is_furniture(text, b.get("y0", 0), b.get("page_height", 792) or 792):
            mark(b, "footnote")
            continue
        # Amendment notes are sometimes set beside the amended line rather
        # than in the bottom margin.  Their fused superscript number (for
        # example ``16Substituted``) must not become section 1625 or 2014.
        # An amending Act states its amendments as its own operative sections,
        # so ``4. In section 15 of the said Act ... shall be substituted`` is
        # the section, not a note about one -- textually identical to the
        # apparatus this pattern exists to catch. The walk has already told the
        # two apart above: a block reached here as the body of a detached
        # marginal heading was matched to a printed contents heading and proved
        # to sit in its own column, which apparatus never is. Prefer that
        # evidence over the text shape, or the marginal heading is left owning
        # nothing and its characters fall out of the ledger (C4/C5).
        if ((_FOOTNOTE.match(text)
                or _PUNCTUATED_AMENDMENT_FOOTNOTE.match(text))
                and b.get("id") not in detached_heading_for_body):
            mark(b, "footnote")
            if _SOURCE_HISTORY_START.match(text):
                source_history_page = b["page_no"]
            continue
        if _footnote_markers_only(text):
            mark(b, "footnote")
            continue

        # A source-labelled TABLE belongs to the provision immediately before
        # it.  Its numbered rows are data, not competing sections of the Act.
        # Keep the heading itself reachable as body text and remember the
        # owning provision until a TOC-proved next section closes the table.
        if (re.fullmatch(r"(?:THE\s+)?TABLE\s*[.:-]?", _norm(text), re.I)
                or _is_numbered_table_header(text)):
            if current is not root:
                owner = current
                while owner is not root and owner.kind in (
                        {"clause"} | QUALIFIERS):
                    owner = owner.parent or root
                if owner is not root:
                    explicit_table_owner = owner
                current.text_parts.append(text)
                current.last_page = b["page_no"]
                current.blocks.append(b.get("id"))
                mark(b, "body", current)
            else:
                mark(b, "preface")
            continue

        if _PREAMBLE.match(text) and not any(c.kind == "preamble" for c in root.children):
            node = Node(kind="preamble", label="Preamble", depth=1,
                        text_parts=[text], first_page=b["page_no"],
                        last_page=b["page_no"], first_block=b.get("id"), parent=root)
            root.children.append(node)
            node.blocks.append(b.get("id"))
            mark(b, "preamble", node)
            current = node
            continue

        heading_context = previous_heading_context(idx)
        c = _classify_body(text, toc, seen, heading_context)
        if not c:
            if b.get("id") in detached_heading_ids:
                mark(b, "heading")
                continue
            # continuation prose: 44.9% of blocks. It belongs to whatever
            # provision is open.
            if current is not root:
                current.text_parts.append(text)
                current.last_page = b["page_no"]
                current.blocks.append(b.get("id"))
                mark(b, "body" if current.kind not in _HEADING_KINDS else "heading", current)
            else:
                # before any provision has opened: title page, gazette line,
                # enacting formula. Akoma Ntoso calls this the preface.
                mark(b, "preface")
            continue

        kind, label, rest = c
        # A small number of official schedules parenthesize a top-level rule
        # number before its first subrule (``(12) (1) ...``), while their own
        # printed contents and aligned marginal heading cite plain rule 12.
        # Promote only inside an open schedule and only when that independent
        # heading evidence names exactly one printed entry for the label.
        if (kind == "subsection" and in_schedule
                and re.match(r"^\s*\(\s*1\s*\)", rest)):
            supported_schedule_headings = [
                entry["heading"] for entry in printed_toc
                if _citation_label_key(entry["label"])
                   == _citation_label_key(label)
                # Deliberately NOT suffix-tolerant, unlike the Table rule
                # below. Extending _heading_tail_supports to this guard and to
                # the (4)-as-section guard was measured over the corpus: 17
                # documents moved, none improved, four regressed, and it
                # produced 17 new demotions and 4 new gaps while creating no
                # sections at all. A promotion rule wants the STRICTER test --
                # it invents a section where the source printed a subsection,
                # so a neighbour's marginal text must not be able to license it.
                and _heading_supports(heading_context, entry.get("heading"))
            ]
            if len(set(supported_schedule_headings)) == 1:
                kind = "section"

        if kind in ("section", "article") and explicit_table_owner is not None:
            table_key = _repair_label(
                label, toc, seen, rest
            ).replace(" ", "")
            expected_heading = toc.get(table_key)
            # The promised heading is not always run into the body text. Where
            # a gazette sets marginal headings, it is a separate block BEFORE
            # the numbered one, which `previous_heading_context` exists to
            # collect -- and which the schedule branch a few lines above already
            # consults. Asking only `rest` therefore fails for exactly the
            # documents that print headings in the margin, and the whole Act
            # after a section declaring a Table becomes rows of that Table.
            # The Balochistan Sales Tax on Services Act is the case: section 48
            # says "column 2 of the Table below", and sections 49 to 62 -- every
            # one printed with its own number and marginal heading -- became
            # clauses of section 48's subsection (2), so 41 promised sections
            # stopped being citable.
            next_promised_section = (
                _toc_label_is_next(table_key, toc, seen)
                and (_heading_supports(rest, expected_heading)
                     or _heading_tail_supports(heading_context,
                                               expected_heading)
                     )
            )
            if next_promised_section:
                explicit_table_owner = None
            else:
                # The row remains individually addressable inside the table,
                # but is deliberately non-citable as a section/article.  Its
                # source block and full text stay in the ordinary reachability
                # ledger; no content is discarded.
                node = Node(
                    kind="clause", label=label, heading=None,
                    depth=explicit_table_owner.depth + 1,
                    text_parts=[_norm(rest)] if rest else [],
                    first_page=b["page_no"], last_page=b["page_no"],
                    first_block=b.get("id"), parent=explicit_table_owner,
                )
                explicit_table_owner.children.append(node)
                node.blocks.append(b.get("id"))
                mark(b, "schedule_row", node)
                current = node
                continue

        # A line-wrapped cross-reference can begin an extracted block with
        # ``Rule 21.`` and look exactly like a provision opener in isolation.
        # Keep it as continuation when the preceding source text is unfinished
        # unless ordered TOC evidence independently says this is the next rule.
        # This retains genuine ``Rule N.`` provisions while preventing a
        # definition ending ``...mentioned in column No. 2 of / Rule 21.``
        # from stealing the later real rule 21.
        prior_content = previous_content(idx)
        prior_lines = [
            _norm(line) for line in (prior_content or "").splitlines()
            if _norm(line)
        ]
        trailing_rule_heading = prior_lines[-1] if prior_lines else ""
        prefixed_rule = re.match(
            r"^\s*(?:Rules?|Regulations?)\s*(\d{1,4})\b", text, re.I,
        )
        prior_prefixed_rule = preceding_prefixed_rule_number(idx)
        sequential_prefixed_rule = bool(
            prefixed_rule
            and int(prefixed_rule.group(1)) == prior_prefixed_rule + 1
        )
        displayed_rule_heading = bool(
            prefixed_rule
            and trailing_rule_heading
            and len(trailing_rule_heading) <= 160
            and trailing_rule_heading.endswith(":")
        )
        if (kind == "section"
                and re.match(r"^\s*(?:Rules?|Regulations?)\s*\d", text, re.I)
                and _continues_previous(prior_content)
                and not displayed_rule_heading
                and not sequential_prefixed_rule
                and not _toc_label_is_next(
                    _norm(label).replace(" ", ""), toc, seen
                )):
            if current is not root:
                current.text_parts.append(text)
                current.last_page = b["page_no"]
                current.blocks.append(b.get("id"))
                mark(b, "body", current)
            else:
                mark(b, "preface")
            continue

        # One official Refugees Act edition visibly prints the next top-level
        # section as ``(4)``.  Parentheses normally mean subsection and remain
        # so unless three independent signals agree: ordered TOC position, an
        # unseen label, and the immediately preceding marginal heading.
        subsection_key = label.replace(" ", "")
        if (kind == "subsection"
                and _toc_label_is_next(subsection_key, toc, seen)
                # Strict by measurement, not by oversight -- see the note on
                # the schedule-rule promotion above.
                and _heading_supports(heading_context,
                                      toc.get(subsection_key))):
            kind, label = "section", subsection_key

        if kind in _HEADING_KINDS and _norm(text) in running_headings:
            # Printed at the top of many pages: furniture, not a division.
            mark(b, "running_header")
            continue

        # A materialised expression does not inherit a compilation's editorial
        # contents page.  Some official notifications nevertheless prove their
        # schedule directly: after several enacted sections and the signature,
        # a new source block starts with the standalone, uppercase display word
        # ``SCHEDULE``.  The first numbered schedule item may share that block.
        # Requiring (1) no TOC, (2) at least two already-opened sections, and
        # (3) an exact uppercase first line keeps ordinary prose references to
        # "the Schedule" on the conservative cross-reference path below.
        unlisted_display_schedule = bool(
            not toc
            and len(seen) >= 2
            and current is not root
            and re.match(
                r"^\s*(?:THE\s+)?SCHEDULE[ \t]*(?:\r?\n|$)",
                b["text"],
            )
        )
        source_proves_schedule = (
            kind == "schedule"
            # The override is only for a display heading that starts its
            # physical source block.  A subdivided mid-sentence reference to
            # Schedule I must continue through the ordinary cross-reference
            # guards below. Uppercase is additional layout evidence used by
            # the official Sindh source that exposed this ambiguity.
            and re.match(r"^\s*(?:THE\s+)?SCHEDULE\b", b["text"])
                is not None
            and (
                _schedule_identity(f"{label} {rest}")
                    in toc_schedule_identities
                or _explicit_schedule_cross_reference(b["text"])
                or unlisted_display_schedule
            )
        )
        if kind in _HEADING_KINDS and not source_proves_schedule and (
                _runs_on(rest)
                or (kind == "schedule" and idx < last_body_section)
                or _continues_previous(previous_content(idx))):
            # A cross-reference to a division, not the division itself.
            if current is not root:
                current.text_parts.append(text)
                current.last_page = b["page_no"]
                current.blocks.append(b.get("id"))
                mark(b, "body" if current.kind not in _HEADING_KINDS else "heading",
                     current)
            else:
                mark(b, "preface")
            continue

        if kind in QUALIFIERS:
            # Attaches to the open enacted provision, never opens an unbounded
            # qualifier branch. Statutes commonly print several provisos or
            # numbered explanations in sequence; they are siblings qualifying
            # the same clause/section, not proviso-within-proviso.
            parent = current if current is not root else root
            while parent is not root and parent.kind in QUALIFIERS:
                parent = parent.parent or root
            node = Node(kind=kind, label=label, depth=parent.depth + 1,
                        text_parts=[rest or text], first_page=b["page_no"],
                        last_page=b["page_no"], first_block=b.get("id"), parent=parent)
            parent.children.append(node)
            node.blocks.append(b.get("id"))
            mark(b, "body", node)
            current = node
            continue

        # Numbered lists inside an enacted provision sometimes use ``1.`` / ``2.``
        # / ``3.`` rather than parentheses.  In isolation those blocks satisfy
        # the section grammar, but the source layout and surrounding prose can
        # prove that they are local list items.  Keep this deliberately narrower
        # than the repeated-label repair below: either (a) a label already used
        # by the Act is followed by the next dotted item in the *same* block, or
        # (b) an indented item continues visibly unfinished prose.  In both cases
        # the candidate must fail to match the independently printed TOC heading.
        # This is the typography used by the definition of ``resident`` in the
        # Sindh Sales Tax on Services Act, including item 3 across pages 10--11.
        if kind == "section" and not in_schedule and current is not root:
            owner = current
            while owner is not root and owner.kind not in {"section", "article"}:
                owner = owner.parent or root
            candidate_key = _repair_label(label, toc, seen, rest).replace(" ", "")
            candidate_number = (
                int(candidate_key) if candidate_key.isdigit() else None
            )
            owner_block = source_block_by_id.get(owner.first_block)
            indented = _indented_past_body(b, owner_block)
            has_next_item = bool(
                candidate_number is not None
                and re.search(
                    rf"(?:^|\s){candidate_number + 1}\s*\.\s+", rest
                )
            )
            # The block's own tail is not the only place the printed heading
            # can be. A gazette that sets marginal notes in a side column puts
            # it in separate blocks, and the detached-heading pass above has
            # already matched those to this block. Document 275 page 3 prints
            # "Tax on motor" (x0 109), then "5. There shall be levied and
            # collected in any area in which" (x0 217), then "vehicles."
            # (x0 130) -- the heading split around the body block it heads.
            # The contents promises exactly "5. Tax on motor vehicles.", the
            # detached pass attached it, and the tail alone still disagreed, so
            # the whole of section 5 became a clause of section 4.
            #
            # Geometry cannot rescue this one: the document's x0 values cluster
            # at 72, 190, 217, 405 and 166, so there is no single body column to
            # measure indentation against. The printed heading is the evidence.
            detached_note = detached_heading_for_body.get(b.get("id"))
            heading_disagrees = not (
                _heading_supports(rest, toc.get(candidate_key))
                or (detached_note is not None
                    and _heading_supports(detached_note[1],
                                          toc.get(candidate_key)))
            )
            if (owner is not root and candidate_key in toc and heading_disagrees
                    and ((candidate_key in seen and has_next_item)
                         or (indented
                             and _continues_previous(previous_content(idx))))):
                kind = "clause"

        # A few official consolidations print section subparts as indented
        # ``2.`` and ``3.`` after an inline ``(1)`` instead of retaining the
        # parentheses.  Do not let those typography-only dots create duplicate
        # top-level sections. Five independent signals are required: an open
        # section whose text visibly starts with (1), same page, deeper source
        # indentation, consecutive subpart numbering, and a heading that does
        # not match the independently printed TOC entry for the same number.
        if kind == "section" and not in_schedule and current is not root:
            owner = current
            while owner is not root and owner.kind not in {"section", "article"}:
                owner = owner.parent or root
            candidate_key = _repair_label(label, toc, seen, rest).replace(" ", "")
            candidate_number = (
                int(candidate_key) if candidate_key.isdigit() else None
            )
            numeric_children = [
                int(child.label) for child in owner.children
                if child.kind == "subsection" and child.label.isdigit()
            ] if owner is not root else []
            expected_number = (
                max(numeric_children) + 1 if numeric_children else 2
            )
            owner_block = source_block_by_id.get(owner.first_block)
            indented = _indented_past_body(b, owner_block)
            if (owner is not root
                    and re.match(r"^\s*\(\s*1\s*\)", owner.text)
                    and owner.first_page == b["page_no"]
                    and indented
                    and candidate_number == expected_number
                    and candidate_key in toc
                    and not _heading_supports(rest, toc.get(candidate_key))):
                depth = owner.depth + 1
                while stack and stack[-1].depth >= depth:
                    stack.pop()
                node = Node(
                    kind="subsection", label=candidate_key, depth=depth,
                    text_parts=[_norm(rest)] if rest else [],
                    first_page=b["page_no"], last_page=b["page_no"],
                    first_block=b.get("id"), parent=owner,
                )
                owner.children.append(node)
                node.blocks.append(b.get("id"))
                mark(b, "body", node)
                stack.append(node)
                current = node
                continue

        # Once a schedule has opened, a numbered item belongs INSIDE it -- it is
        # not section 3 of the Act starting over.
        #
        # It is not discarded, though. The Code of Civil Procedure carries Orders
        # I-LI with their Rules in its First Schedule, and "Order VII Rule 11
        # CPC" is among the most-cited provisions in Pakistani civil practice.
        # Dropping schedule content would delete real, citable law. Instead it is
        # re-parented under the schedule, so it keeps its text and its own path
        # while staying out of the Act's top-level section numbering.
        # An Act has one section 27. A second top-level section bearing a label
        # the body has already used is not law repeating itself -- it is a row of
        # a table printed after the body:
        #
        #   doc 4371  s.27  p25 "Assessment of tax and recovery..."   the section
        #             s.27  p69 "Members of Parliament (Majlis-e-Shoora)..."  a
        #             s.27  p86 "The following services of Pakistan Railways..."
        #                        rate-schedule rows
        #
        # Both of those documents score 1.000 against their own contents list, so
        # the body is right and only the tail is wrong. The test is positional
        # rather than global on purpose: a repeat BEFORE the body has finished is
        # usually a contents entry that leaked, and demoting that would bury the
        # real section instead. Only repeats after the last promised section are
        # demoted, and they keep their text as content of whatever precedes them.
        if (kind in ("section", "article") and not in_schedule
                and last_body_section >= 0 and idx > last_body_section
                and _repair_label(
                    label, toc, seen, rest
                ).replace(" ", "") in seen):
            # Repeated numeric rows are siblings, never a 189-level chain. The
            # old code made each row the parent of the next (`current=node`), so
            # a tariff table produced paths 1,499 bytes deep and broke ltree's
            # GiST page split. Climb out of an open clause/qualifier to the
            # stable provision that owns the trailing table; continuation prose
            # still attaches to the individual row via `current` below.
            roman_parent = next((candidate for candidate in reversed(stack)
                                 if any(candidate is division
                                        for division
                                        in roman_section_division_nodes)), None)
            if roman_parent is not None:
                # Local numbering beneath ``SECTION - Roman`` is a sibling
                # sequence even when a decimal child (3.4) was the immediately
                # preceding unit. Attaching local 4 beneath 3.4 made Budget a
                # child of a bank-reconciliation sentence in observation 4725.
                parent = roman_parent
            else:
                parent = current if current is not root else root
                while (parent is not root
                       and parent.kind in ({"clause"} | QUALIFIERS)):
                    parent = parent.parent or root
            detached_heading = detached_heading_for_body.get(b.get("id"))
            node = Node(kind="clause", label=label,
                        heading=(detached_heading[1]
                                 if detached_heading else None),
                        depth=parent.depth + 1,
                        text_parts=[_norm(rest)] if rest else [],
                        first_page=b["page_no"], last_page=b["page_no"],
                        first_block=b.get("id"), parent=parent)
            parent.children.append(node)
            node.blocks.append(b.get("id"))
            if detached_heading:
                node.blocks[0:0] = detached_heading[0]
                for heading_block_id in detached_heading[0]:
                    seg_roles[heading_block_id] = ("heading", node)
            mark(b, "schedule_row", node)
            current = node
            continue

        if kind in ("section", "article") and in_schedule:
            # ...unless the document itself says otherwise. Two ways it can:
            #
            #   * its contents list names this section, and we have not met it
            #     yet -- a schedule cannot contain a section the Act's own
            #     contents promises, so the schedule we are inside was a false
            #     reading and it ends here;
            #   * there is no contents list, but this number CONTINUES the Act's
            #     section sequence rather than restarting inside a table.
            #
            # Schedule rows restart at 1 (Order VII rule 1, rule 2...), so a
            # label above everything seen before the schedule opened is the body
            # resuming. Without this reset one false schedule silently converts
            # the entire remainder of a statute into table rows: the Balochistan
            # Sale Tax Act kept 10 sections of 101 for exactly that reason.
            key = _repair_label(label, toc, seen, rest).replace(" ", "")
            resumes = False
            if toc and key in toc and key not in seen:
                # Only the body can resume, and the body is over once the last
                # promised section has passed. Without this the Code of Civil
                # Procedure's First Schedule -- which is genuine -- had its
                # Order rules promoted to sections of the Act, because rule 23
                # of an Order shares a label with section 23 of the Code.
                resumes = idx <= last_body_section
            elif (not toc and schedule_node is not None
                  and schedule_node.kind == "schedule"):
                m = re.match(r"^(\d+)", key)
                # Recompute from the immutable source prefix immediately before
                # this candidate. Parser state is deliberately not consulted:
                # it may already be wrong because an earlier auxiliary heading
                # failed to close. The nearest/highest explicit Rule prefix is
                # the independent evidence that Rule 1107 follows Rule 1106.
                source_rule_before = max_prefixed_rule_before_schedule
                # With no contents list, a bare ``8.`` after sections 2--7 is
                # equally likely to be row 8 of a schedule.  A source-printed
                # ``Rule 1107.`` after rules through 1106 is a much stronger
                # resumption signal.  This distinction keeps the Punjab wage
                # tables inside their schedule while letting the Prisons Rules
                # resume after an inserted disciplinary schedule.
                if (m and int(m.group(1)) > source_rule_before
                        # An expressly omitted or OCR-missed rule can leave a
                        # small gap at the resumption point.  Larger jumps stay
                        # inside the schedule and require source review.
                        and int(m.group(1)) <= source_rule_before + 3
                        and re.match(
                            r"^\s*(?:Sections?|Rules?|Regulations?)\s*\d",
                            text, re.I,
                        )):
                    resumes = True
            if resumes:
                # Close the actual auxiliary node, not merely nodes at the
                # incoming provision's depth. A schedule is usually depth 1;
                # the old ``depth >= 3`` unwind left it on the stack, created
                # the resumed Rule beneath it, and the safety post-pass then
                # retyped that Rule to a schedule-row clause.
                closing_schedule = schedule_node
                while stack and stack[-1] is not closing_schedule:
                    stack.pop()
                if stack and stack[-1] is closing_schedule:
                    stack.pop()
                in_schedule, schedule_node = False, None
            else:
                row_container = (stack[-1] if stack and
                                 stack[-1].kind in (
                                     _AUXILIARY_KINDS | {"part", "chapter"}
                                 )
                                 else schedule_node)
                depth = row_container.depth + 1 if row_container else 3
                while stack and stack[-1].depth >= depth:
                    stack.pop()
                parent = stack[-1] if stack else (row_container or root)
                # A numbered row in a schedule table is not a section of the Act.
                # Recording it as one inflates the section count and produces
                # many provisions labelled "1" under one schedule. It is content
                # of the schedule, so it is stored as a clause of it.
                detached_heading = detached_heading_for_body.get(b.get("id"))
                node = Node(kind="clause", label=label,
                            heading=(detached_heading[1]
                                     if detached_heading else None), depth=depth,
                            text_parts=[_norm(rest)] if rest else [],
                            first_page=b["page_no"], last_page=b["page_no"],
                            first_block=b.get("id"), parent=parent)
                parent.children.append(node)
                node.blocks.append(b.get("id"))
                if detached_heading:
                    node.blocks[0:0] = detached_heading[0]
                    for heading_block_id in detached_heading[0]:
                        seg_roles[heading_block_id] = ("heading", node)
                mark(b, "schedule_row", node)
                stack.append(node)
                current = node
                continue

        depth = DEPTH.get(kind, 3)
        # A Schedule can itself be divided into Parts. Globally a Part is a
        # top-level instrument division, but within an open schedule the
        # printed Part I/II headings are children of that schedule, not peers
        # that terminate it.
        if kind == "part" and in_schedule and schedule_node is not None:
            depth = schedule_node.depth + 1
        # unwind to this level's parent
        while stack and stack[-1].depth >= depth:
            stack.pop()
        parent = stack[-1] if stack else root

        heading, body_text = (None, _norm(rest))
        if kind == "section":
            label = _repair_label(label, toc, seen, rest)
            key = label.replace(" ", "")
            # Once a document has entered a ``SECTION - Roman`` division its
            # body numbering is local to that division, while the contents can
            # continue with a separate global display index.  Feeding a global
            # TOC heading into a local same-numbered node would make the later
            # entry linker corroborate evidence that the parser itself copied.
            # Keep those evidence streams independent: infer the local heading
            # from body text and let reconciliation prove (or reject) the link.
            toc_heading = None if roman_section_division_seen else toc.get(key)
            heading, body_text = _split_heading(rest, toc_heading)
            # Many gazette PDFs lay out a marginal heading and operative text
            # in separate columns/blocks.  In reading order this becomes:
            #
            #   1. Short title and commencement.
            #   1. (1) This Act may be called ...
            #
            # They are two source spans of one section, not two citable
            # sections and not a schedule row.  Merge only the immediately
            # open, heading-only section with the same repaired label.  The
            # source blocks remain individually anchored in the role ledger.
            prior = label_nodes.get(key)
            candidate_text = _norm(rest)
            heading_similarity = SequenceMatcher(
                None, _norm(prior.heading or "").casefold(),
                candidate_text.casefold()).ratio() if prior else 0.0
            if (prior is not None and current is prior
                    and prior.kind == "section" and prior.heading
                    and not prior.text
                    and (not candidate_text
                         or candidate_text.startswith("(")
                         or len(candidate_text) >= 18)
                    and (not candidate_text or heading_similarity < 0.88)):
                if candidate_text:
                    prior.text_parts.append(candidate_text)
                block_id = b.get("id")
                if (b.get("marginal_note") and block_id is not None
                        and block_id not in marginal_note_blocks_attached):
                    prior.marginal_note = _norm(b["marginal_note"])
                    marginal_note_blocks_attached.add(block_id)
                prior.last_page = b["page_no"]
                prior.blocks.append(b.get("id"))
                mark(b, "body", prior)
                # A bare repeated ``1.`` is followed by subdivided ``(1)``
                # units from the same block. Keep the real section open so
                # those subsections attach to it.
                if not stack or stack[-1] is not prior:
                    stack.append(prior)
                current = prior
                detached_heading_bodies_merged += 1
                continue
            if not in_schedule:
                seen.add(key)
        elif kind in _HEADING_KINDS:
            heading = _norm(rest) or None
            body_text = ""

        # A Roman ``SECTION - IV`` is a structural division whose children
        # restart at 1. In such documents the contents often uses a separate,
        # globally increasing display index. Remember that numbering regime so
        # entry resolution cannot join unrelated objects on label alone.
        is_roman_section_division = bool(
            kind == "part"
            and re.match(
                r"^\s*SECTION\s*[-\u2013\u2014:]\s*[IVXLC]+", text, re.I,
            )
        )
        if is_roman_section_division:
            roman_section_division_seen = True

        detached_heading = detached_heading_for_body.get(b.get("id"))
        if kind == "section" and not heading and detached_heading:
            heading = detached_heading[1]
        marginal_note = None
        block_id = b.get("id")
        if (kind == "section" and b.get("marginal_note")
                and block_id is not None
                and block_id not in marginal_note_blocks_attached):
            marginal_note = _norm(b["marginal_note"])
            marginal_note_blocks_attached.add(block_id)
        node = Node(kind=kind, label=label, heading=heading,
                    marginal_note=marginal_note, depth=depth,
                    text_parts=[body_text] if body_text else [],
                    first_page=b["page_no"], last_page=b["page_no"],
                    first_block=b.get("id"), parent=parent)
        parent.children.append(node)
        if is_roman_section_division:
            roman_section_division_nodes.append(node)
        node.blocks.append(b.get("id"))
        if kind == "section":
            heading_block_ids = (
                detached_heading[0] if detached_heading else []
            )
            if heading_block_ids:
                node.blocks[0:0] = heading_block_ids
                for heading_block_id in heading_block_ids:
                    seg_roles[heading_block_id] = ("heading", node)
        mark(b, "heading" if kind in _HEADING_KINDS else "body", node)
        if kind == "section" and not in_schedule:
            # First occurrence wins. A label repeats in the body whenever a
            # schedule or a form restarts its numbering, and the later one must
            # not steal the contents entry from the section that bears it.
            label_nodes.setdefault(label.replace(" ", ""), node)
        stack.append(node)
        current = node
        if kind in _AUXILIARY_KINDS:
            in_schedule, schedule_node = True, node
            max_before_schedule = max(
                [0] + [int(m.group(1)) for lbl in seen
                       for m in [re.match(r"^(\d+)", lbl)] if m])
            # Snapshot the source sequence at the auxiliary boundary. Rules
            # printed inside the Schedule may have their own high or restarted
            # numbering and must not redefine where the parent Rules resume.
            max_prefixed_rule_before_schedule = max(
                [0] + [
                    int(match.group(1))
                    for _, prior_text in units[:idx]
                    for match in [re.match(
                        r"^\s*(?:Rules?|Regulations?)\s*(\d{1,4})\b",
                        prior_text,
                        re.I,
                    )]
                    if match
                ]
            )

    # Everything before the body boundary is the contents list, and everything
    # the walk never reached is 'unassigned' -- the defect counter. No block may
    # be absent from this ledger (CORPUS-CRITERIA C4).
    for b in blocks[:boundary] if boundary else []:
        bid = b.get("id")
        if bid is not None and bid not in seg_roles:
            seg_roles[bid] = ("contents", None)
    # A detached marginal heading whose body never became a provision owns
    # nothing, and legal_write refuses to store a heading without one -- so its
    # characters fall out of the ledger and C5 fails. That is the right refusal
    # and the wrong outcome: the words are printed on the page and belong to the
    # provision they head. Give each one the node of the next block that has
    # one, which in a marginal layout is the section the heading sits beside.
    #
    # Document 775 page 7 shows how it arises. "Indemnity." is fused to section
    # 10's text in a single full-width block, so section 10 never opens cleanly,
    # and the NEXT heading -- "Members, officers, / officials not personally",
    # aligned with section 11 -- is left with nothing to attach to.
    ordered = [b.get("id") for b in blocks if b.get("id") is not None]
    for position, bid in enumerate(ordered):
        entry = seg_roles.get(bid)
        if entry is None or entry[0] != "heading" or entry[1] is not None:
            continue
        successor = next((seg_roles[nxt][1] for nxt in ordered[position + 1:]
                          if seg_roles.get(nxt) and seg_roles[nxt][1] is not None),
                         None)
        if successor is not None:
            seg_roles[bid] = ("heading", successor)

    for b in blocks:
        bid = b.get("id")
        if bid is not None and bid not in seg_roles:
            seg_roles[bid] = ("unassigned", None)

    # A section/article below a printed schedule is a schedule rule/row, not a
    # section of the parent Act. A false "body resumes" decision can otherwise
    # promote hundreds of schedule rows when their numbers exceed the Act's
    # highest section. Preserve the nodes and text, but restore their type and
    # ledger role.
    schedule_sections_retyped = 0

    def beneath_schedule(node: Node) -> bool:
        parent = node.parent
        while parent is not None and parent is not root:
            if parent.kind == "schedule":
                return True
            parent = parent.parent
        return False

    def walk_nodes(parent: Node):
        for child in parent.children:
            yield child
            yield from walk_nodes(child)

    all_nodes = list(walk_nodes(root))
    for node in all_nodes:
        if node.kind in {"section", "article"} and beneath_schedule(node):
            node.kind = "clause"
            schedule_sections_retyped += 1
            for bid in node.blocks:
                if bid in seg_roles and seg_roles[bid][1] is node:
                    seg_roles[bid] = ("schedule_row", node)

    # One parent cannot have two citable sections/articles bearing one label:
    # the citation would resolve to both. Numeric table rows, appended forms and
    # compiled instruments commonly restart numbering under a shared inferred
    # container. Preserve every node and child, but type non-canonical siblings
    # as clauses and keep the decision in the adjudication counter.
    # Where the PDF prints contents, its heading selects the canonical occurrence;
    # otherwise the first occurrence is the only non-invented default. Labels
    # under distinct printed Parts/Chapters stay distinct because they have
    # different parents.
    repeated_labels_demoted = 0
    repeated_label_decisions: list[dict] = []
    for parent in [root] + all_nodes:
        sibling_groups: dict[tuple[str, str], list[Node]] = {}
        for node in parent.children:
            if node.kind in {"section", "article"}:
                sibling_groups.setdefault(
                    (node.kind, node.label.replace(" ", "")), []).append(node)
        for (_, key), nodes in sibling_groups.items():
            if len(nodes) < 2:
                continue
            # Heading agreement alone picks the wrong occurrence whenever a
            # document prints its section headings twice -- once in a list and
            # once above the law. The list entry IS the heading, so it scores
            # 1.0; the real section carries the operative text and often no
            # heading at all, so it scores 0.0 and is demoted. The University of
            # Karachi Ordinance loses section after section that way: "48.
            # Repeal and savings." on page 31 is kept and "48. (1) The
            # University of Karachi Ordinance, 1962 ..." on page 45 -- the
            # provision itself -- becomes a clause.
            #
            # A unit carrying no law is not the section, whatever its heading
            # says and whether or not the document prints a contents list. Rank
            # on that first in BOTH branches below; the existing signals decide
            # among units that do carry law, and source order breaks ties.
            def carries_law(candidate: Node) -> int:
                # "Text is non-empty" does not separate them: a contents line
                # "48. Repeal and savings." parses with rest "Repeal and
                # savings.", so the heading IS its whole text. What separates
                # them is text BEYOND the heading.
                if candidate.children:
                    return 1
                body = _norm("".join(candidate.text_parts)).casefold()
                head = _norm(candidate.heading or "").casefold()
                # A node parsed straight out of the contents region often has no
                # heading of its own -- nothing attached one, because its text
                # IS the heading. Then there is nothing to strip, 34 characters
                # of "Sind Act VII of 1879 not to apply." count as law, both
                # occurrences score 1, and source order hands the citation to
                # the contents line. Document 423 loses section 3 that way, and
                # document 956 loses sections 2, 6 and 7.
                #
                # The contents itself supplies the missing heading: it is the
                # promise this label was matched on. Falling back to it makes
                # the contents-line node strip to nothing, which is exactly what
                # it is -- a heading with no law under it.
                if not head:
                    head = _norm(toc.get(key, "")).casefold()
                if head and body.startswith(head.rstrip(". ")):
                    body = body[len(head.rstrip(". ")):]
                return int(len(body.strip(" .—–-")) >= 20)

            expected = _norm(toc.get(key, "")).casefold()
            if expected:
                def heading_score(candidate: Node) -> float:
                    actual = _norm(candidate.heading or "").casefold()
                    return (SequenceMatcher(None, expected, actual).ratio()
                            if actual else 0.0)

                canonical = max(
                    enumerate(nodes),
                    key=lambda pair: (carries_law(pair[1]),
                                      heading_score(pair[1]), -pair[0]))[1]
            else:
                # With no contents list, a source-printed ``Rule 678.`` is
                # stronger identity evidence than a bare ``678.`` previously
                # inferred from a table/list row. The old first-occurrence
                # default kept the bare row citable and demoted the actual Rule
                # in Punjab Prisons Rules. Prefer an explicit block-start legal
                # unit prefix; ties remain source-order stable.
                def explicit_unit_score(candidate: Node) -> int:
                    block = source_block_by_id.get(candidate.first_block) or {}
                    value = block.get("text") or ""
                    return int(bool(re.match(
                        r"^\s*(?:Sections?|Rules?|Regulations?)\s*"
                        + re.escape(candidate.label)
                        + r"\b",
                        value,
                        re.I,
                    )))

                # Same first rank as the contents branch: a unit carrying no
                # law is not the section, whether or not the document prints a
                # contents list to say so.
                canonical = max(
                    enumerate(nodes),
                    key=lambda pair: (carries_law(pair[1]),
                                      explicit_unit_score(pair[1]), -pair[0]),
                )[1]
            if key in label_nodes:
                label_nodes[key] = canonical
            for node in nodes:
                if node is canonical:
                    continue
                repeated_label_decisions.append({
                    "candidate": node,
                    "canonical": canonical,
                    "parent": None if parent is root else parent,
                    "original_kind": node.kind,
                    "printed_label": node.label,
                    "group_size": len(nodes),
                    "group_ordinal": nodes.index(node),
                    "toc_heading": toc.get(key),
                    "candidate_heading_score": (
                        heading_score(node) if expected else None),
                    "canonical_heading_score": (
                        heading_score(canonical) if expected else None),
                    # Whether each occurrence carries text beyond its own
                    # heading. This is the signal canonical selection now ranks
                    # on, and a reviewer needs it: where the kept occurrence
                    # carries law and the demoted one is a bare repeat of the
                    # heading, the heading SCORES will be inverted -- the
                    # heading line matches the contents perfectly and the
                    # provision often has no heading at all -- so a rule reading
                    # only those scores would call the right choice wrong.
                    "canonical_carries_law": bool(carries_law(canonical)),
                    "candidate_carries_law": bool(carries_law(node)),
                })
                node.kind = "clause"
                repeated_labels_demoted += 1
                for bid in node.blocks:
                    if bid in seg_roles and seg_roles[bid][1] is node:
                        seg_roles[bid] = ("schedule_row", node)

    seg = Segmentation(root=root, toc=toc, body_starts_page=body_page,
                       toc_found=toc_found, block_roles=seg_roles,
                       repeated_labels_demoted=repeated_labels_demoted,
                       repeated_label_decisions=repeated_label_decisions,
                       schedule_sections_retyped=schedule_sections_retyped,
                       detached_heading_bodies_merged=detached_heading_bodies_merged,
                       marginal_notes_split=marginal_notes_split,
                       curation_patches_applied=patches_applied)
    if toc:
        # Entries pointing at a schedule are reconciled against the schedules
        # found in the body, not against sections.
        sched_entries = {e["label"] for e in printed_toc
                         if _TOC_SCHEDULE.match(e["heading"] or "")}
        promised = set(toc) - sched_entries
        body_schedules = sum(1 for n in seg.flatten() if n.kind == "schedule")
        seg.schedules_promised = len(sched_entries)
        seg.schedules_found = body_schedules
        matched_promised, matched_seen = _reconcile_label_sets(promised, seen)
        seg.matched = len(matched_promised)
        seg.missing = sorted(promised - matched_promised)[:200]
        seg.extra = sorted(seen - matched_seen)[:200]

        # The contents list as a list, in printed order, each entry carrying the
        # node the body produced for it. Everything above counts; this names.
        # Written to instrument_toc_entry -- migration 0011.
        flat_nodes = seg.flatten()
        node_order = {id(node): ordinal for ordinal, node in enumerate(flat_nodes)}
        nodes_by_citation_key: dict[str, list[Node]] = {}
        for node in flat_nodes:
            # A printed contents entry may name a top-level section/article or
            # a rule/item nested inside an Order, schedule, appendix or form
            # (CPC has 778 entries and dozens of rules numbered 6). Never use
            # label alone when more than one candidate exists: the printed
            # heading or bounded source order must select exactly one body node.
            # A section-level contents row can never be satisfied by an
            # internal subsection merely because the printed number agrees.
            # Rules/items nested under an Order or schedule are represented as
            # clauses and remain eligible, but require heading/order evidence
            # below when label identity alone is insufficient.
            if (node.kind == "subsection" and node.parent is not None
                    and node.parent.kind in {"section", "article", "clause"}):
                compound_key = _citation_label_key(
                    f"{node.parent.label}({node.label})"
                )
                compound_bucket = nodes_by_citation_key.setdefault(
                    compound_key, [],
                )
                if all(existing is not node for existing in compound_bucket):
                    compound_bucket.append(node)
            if node.kind not in {"section", "article", "clause"}:
                continue
            bucket = nodes_by_citation_key.setdefault(
                _citation_label_key(node.label), [])
            if all(existing is not node for existing in bucket):
                bucket.append(node)

        toc_key_counts: dict[str, int] = {}
        for entry in printed_toc:
            key = _citation_label_key(entry["label"])
            toc_key_counts[key] = toc_key_counts.get(key, 0) + 1

        # Some compilations switch from true provision labels to a globally
        # increasing contents index when a Roman ``SECTION`` division begins.
        # Locate that transition from the first TOC heading independently
        # represented by a Roman division (observation 4725: TOC 5 ``Funds``
        # -> body ``SECTION - III / FUNDS``). From that entry onward, even a
        # same-numbered node printed before the division needs heading evidence:
        # pages 5-6 contain unrelated enabling-Ordinance sections 10 and 11.
        roman_global_start_ordinal: int | None = None
        for entry in printed_toc:
            if any(_heading_supports(
                    division.heading or division.text,
                    entry.get("heading"),
                ) for division in roman_section_division_nodes):
                roman_global_start_ordinal = entry["ordinal"]
                break

        def mixed_numbering_entry(entry: dict) -> bool:
            return (roman_global_start_ordinal is not None
                    and entry["ordinal"] >= roman_global_start_ordinal)

        def under_roman_section_division(node: Node) -> bool:
            parent = node.parent
            while parent is not None:
                if any(parent is division
                       for division in roman_section_division_nodes):
                    return True
                parent = parent.parent
            return False

        def toc_node(entry: dict) -> tuple[Node | None, str]:
            entry_label = entry["label"]
            citation_key = _citation_label_key(entry_label)
            candidates = nodes_by_citation_key.get(citation_key, [])
            expected_heading = entry.get("heading")
            compound_entry = bool(re.match(r"^\d{1,4}\(", citation_key))

            def heading_evidence(node: Node) -> str:
                own = node.heading or node.text
                if compound_entry and node.parent is not None:
                    parent = node.parent.heading or node.parent.text
                    return " ".join(value for value in (parent, own) if value)
                return own

            def supports_heading(node: Node) -> bool:
                evidence = _norm(heading_evidence(node)).casefold()
                expected = _norm(expected_heading or "").casefold()
                return bool(expected) and (
                    expected in evidence
                    or _heading_supports(evidence, expected)
                )

            exact_typography = [
                node for node in candidates
                if node.label.replace(" ", "") == entry_label.replace(" ", "")
            ]
            # Preserve the ordinary, strongest case as a direct label match:
            # one printed occurrence and one primary body provision. Repeated
            # labels and nested clauses continue through corroborating heading
            # and order checks below.
            #
            # Count only provisions that could BE the promised section. An S7
            # demotion leaves a clause carrying the same citation key beside the
            # section, and counting it made `len(candidates) == 1` false, so
            # this path was abandoned for a row that had exactly one possible
            # answer. A demoted clause is non-citable by construction -- that is
            # what the demotion decided -- so it can never be what a contents
            # row promising a section refers to.
            #
            # This was costly. As later versions demoted more repeated labels,
            # more contents rows stopped matching: 240 rows that had matched by
            # plain `label` went unmatched, taking 56 instruments out of the
            # release view. Document 140 is the plain case -- sections 2 and 3
            # present, their rows unmatched, and exactly two demotions.
            primary = [node for node in candidates
                       if node.kind in {"section", "article"}]
            if (len(primary) == 1
                    and toc_key_counts[citation_key] == 1
                    and (not mixed_numbering_entry(entry)
                         and not under_roman_section_division(primary[0])
                         or _heading_supports(
                             primary[0].heading or primary[0].text,
                             expected_heading,
                         ))):
                method = "label" if exact_typography else "label_typography"
                return primary[0], method
            exact_heading_matches = [
                node for node in candidates
                if _heading_lead(heading_evidence(node))
                   == _heading_lead(expected_heading)
            ]
            if len(exact_heading_matches) == 1:
                node = exact_heading_matches[0]
                method = ("label_heading_exact" if node in exact_typography
                          else "label_heading_exact_typography")
                return node, method
            heading_matches = [
                node for node in candidates
                if supports_heading(node)
            ]
            if len(heading_matches) == 1:
                node = heading_matches[0]
                method = ("label_heading" if node in exact_typography
                          else "label_heading_typography")
                return node, method
            return None, "unmatched"

        schedule_nodes = [node for node in flat_nodes if node.kind == "schedule"]
        part_nodes = [node for node in flat_nodes if node.kind == "part"]
        resolved_entries = []
        for entry in printed_toc:
            if _TOC_SCHEDULE.match(entry["heading"] or ""):
                identity = _schedule_identity(entry["heading"])
                candidates = [
                    node for node in schedule_nodes
                    if identity is not None
                    and _schedule_identity(
                        f"{node.label} {node.heading or ''}") == identity
                ]
                if len(candidates) == 1:
                    node, method = candidates[0], "schedule_identity"
                else:
                    rule_reference = _schedule_rule_reference(entry["heading"])
                    candidates = [
                        candidate for candidate in schedule_nodes
                        if rule_reference is not None
                        and _schedule_rule_reference(
                            f"{candidate.label} {candidate.heading or ''}"
                        ) == rule_reference
                    ]
                    if len(candidates) == 1:
                        node, method = candidates[0], "schedule_rule_reference"
                    else:
                        node, method = None, "unmatched"
            elif _TOC_PART.match(entry["heading"] or ""):
                identity = _part_identity(entry["heading"])
                candidates = [
                    node for node in part_nodes
                    if identity is not None
                    and _part_identity(f"PART {node.label}") == identity
                ]
                if len(candidates) == 1:
                    node, method = candidates[0], "part_identity"
                else:
                    node, method = None, "unmatched"
            else:
                node, method = toc_node(entry)
            resolved_entries.append({
                **entry,
                "kind": (
                    "schedule" if _TOC_SCHEDULE.match(entry["heading"] or "")
                    else "part" if _TOC_PART.match(entry["heading"] or "")
                    else "section"
                ),
                "node": node,
                "method": method,
            })
        # A printed heading may say only "Omitted" while the body retains its
        # historical marginal heading followed by omission marks. After the
        # strong matches above, source order can resolve such an entry only
        # when adjacent resolved entries bound exactly one same-label node.
        for index, resolved in enumerate(resolved_entries):
            if resolved["node"] is not None:
                continue
            prior = next((item["node"] for item in reversed(resolved_entries[:index])
                          if item["node"] is not None), None)
            following = next((item["node"] for item in resolved_entries[index + 1:]
                              if item["node"] is not None), None)
            lower = node_order[id(prior)] if prior is not None else -1
            upper = node_order[id(following)] if following is not None else len(flat_nodes)
            candidates = [
                node for node in nodes_by_citation_key.get(
                    _citation_label_key(resolved["label"]), [])
                if lower < node_order[id(node)] < upper
            ]
            used_node_ids = {
                id(item["node"]) for item in resolved_entries
                if item["node"] is not None
            }
            candidates = [node for node in candidates
                          if id(node) not in used_node_ids]
            # In a Roman SECTION document the TOC's global display index and
            # the body's local child label are different numbering systems.
            # Source order alone cannot bridge them: doing so linked TOC 10 to
            # an unrelated local section 10 in observation 4725.  Preserve the
            # ordinary omitted-heading recovery elsewhere, but require actual
            # heading evidence in this mixed-numbering regime.
            if roman_section_division_seen:
                candidates = [
                    node for node in candidates
                    if ((not mixed_numbering_entry(resolved)
                         and not under_roman_section_division(node))
                        or _heading_supports(
                            node.heading or node.text,
                            resolved.get("heading"),
                        ))
                ]
            # Bounded order may recover an omitted/weakly-headed rule only in
            # a clause sequence. It must not use an incidental clause nested
            # between two top-level sections to manufacture a section match.
            if candidates and all(node.kind == "clause" for node in candidates):
                clause_context = ((prior is not None and prior.kind == "clause")
                                  or (following is not None
                                      and following.kind == "clause"))
                if not clause_context:
                    candidates = []
            if len(candidates) == 1:
                resolved["node"] = candidates[0]
                resolved["method"] = "label_order"

        # A consolidated statute may preserve an omitted/repealed section only
        # in its printed contents.  That is a lifecycle fact, not missing body
        # text.  Materialise it only from a separately recorded assertion whose
        # entry identity and rendered source coordinates still match this exact
        # parser run.  The resulting citable node has an operation='omitted'
        # version and no invented operative text.
        disposition_by_key = {
            (int(item["source_block_id"]),
             _citation_label_key(item["printed_label"])): item
            for item in toc_dispositions
        }

        def disposition_word(value: str | None) -> str | None:
            match = re.match(
                r"^\s*(?:\d+\s*)?[\[(]*\s*(omitted|repealed)\b",
                value or "", re.I,
            )
            return match.group(1).casefold() if match else None

        def is_disposition_placeholder(node: Node) -> bool:
            value = _norm(" ".join((node.heading or "", node.text))).casefold()
            return (len(value) <= 500
                    and ("omitt" in value or "repeal" in value
                         or bool(re.fullmatch(r"[\s\[\]()*._-]+", value))))

        def section_neighbour(index: int, step: int):
            cursor = index + step
            while 0 <= cursor < len(resolved_entries):
                node = resolved_entries[cursor].get("node")
                if node is not None and node.kind in {"section", "article"}:
                    return cursor, node
                cursor += step
            return None, None

        def structure_between(start: int | None, stop: int | None) -> bool:
            if start is None or stop is None:
                return False
            low, high = sorted((start, stop))
            return any(
                item.get("node") is not None
                and item["node"].kind in {
                    "part", "chapter", "division", "schedule", "appendix",
                }
                for item in resolved_entries[low + 1:high]
            )

        for index, resolved in enumerate(resolved_entries):
            assertion = disposition_by_key.get((
                int(resolved.get("source_block_id") or -1),
                _citation_label_key(resolved["label"]),
            ))
            if assertion is None:
                continue
            exact_identity = (
                resolved.get("source_block_id") == assertion.get("source_block_id")
                and resolved.get("source_page") == assertion.get("source_page")
                and disposition_word(resolved.get("heading"))
                    == assertion.get("disposition")
            )
            if not exact_identity:
                raise ValueError(
                    "stale TOC disposition assertion for ordinal "
                    f"{resolved['ordinal']} label {resolved['label']}"
                )

            node = resolved.get("node")
            if (node is not None
                    and (node.kind not in {"section", "article"}
                         or not is_disposition_placeholder(node))):
                # An identically numbered schedule row or historical footnote
                # is not the current citable section. Keep that evidence where
                # it is and create the explicit omitted node below.
                node = None
                resolved["node"] = None

            if node is None:
                prior_index, prior = section_neighbour(index, -1)
                next_index, following = section_neighbour(index, 1)
                prior_parent = prior.parent if prior is not None else None
                next_parent = following.parent if following is not None else None
                if prior_parent is next_parent and prior_parent is not None:
                    parent = prior_parent
                elif structure_between(prior_index, index) and next_parent is not None:
                    parent = next_parent
                elif structure_between(index, next_index) and prior_parent is not None:
                    parent = prior_parent
                elif prior_parent is not None and next_parent is None:
                    parent = prior_parent
                elif next_parent is not None and prior_parent is None:
                    parent = next_parent
                elif prior_parent is not None and next_parent is not None:
                    before = index - int(prior_index)
                    after = int(next_index) - index
                    parent = prior_parent if before <= after else next_parent
                else:
                    parent = root

                # S6 admits no two sibling sections under one citation label,
                # and this pass runs AFTER repeated-label demotion, so it can
                # create the very collision that pass exists to prevent. It did:
                # document 4501 already holds section 34A, and materialising the
                # omitted 34A beside it made the citation ambiguous. The
                # disposition is a statement ABOUT a section, so where the
                # parent already has one under that label, record it on that
                # node rather than manufacturing a second.
                existing = next(
                    (child for child in parent.children
                     if child.kind in {"section", "article"}
                     and _citation_label_key(child.label)
                         == _citation_label_key(resolved["label"])),
                    None,
                )
                # Fall through with the existing node rather than skipping: the
                # block below is what records the lifecycle fact, and an
                # assertion left unapplied raises. The disposition is
                # source_verified -- a person read the page and reported the
                # section omitted -- so where it and the parse disagree the
                # reading wins, and the source block stays in the assignment
                # ledger either way, so C5 is unaffected.
                if existing is not None:
                    resolved["node"] = existing
                    resolved["method"] = "source_verified_disposition"
                    node = existing

            if node is None:
                node = Node(
                    kind="section", label=resolved["label"], depth=parent.depth + 1,
                    first_page=resolved.get("source_page"),
                    last_page=resolved.get("source_page"),
                    first_block=resolved.get("source_block_id"), parent=parent,
                )
                prior_sibling = next((
                    item.get("node") for item in reversed(resolved_entries[:index])
                    if item.get("node") is not None
                    and item["node"].parent is parent
                ), None)
                next_sibling = next((
                    item.get("node") for item in resolved_entries[index + 1:]
                    if item.get("node") is not None
                    and item["node"].parent is parent
                ), None)
                if next_sibling is not None and next_sibling in parent.children:
                    parent.children.insert(parent.children.index(next_sibling), node)
                elif prior_sibling is not None and prior_sibling in parent.children:
                    parent.children.insert(parent.children.index(prior_sibling) + 1, node)
                else:
                    parent.children.append(node)
                resolved["node"] = node
                resolved["method"] = "source_verified_disposition"

            # A placeholder is lifecycle metadata, not operative text. Its
            # source block remains preserved in the assignment ledger.
            node.text_parts = []
            node.heading = None
            node.operation = "omitted"
            node.amendment_note = _norm(assertion["printed_heading"])
            node.amended_by_id = assertion.get("amending_instrument_id")
            node.toc_disposition_assertion_id = int(assertion["id"])
            applied_disposition_ids.add(int(assertion["id"]))
            resolved["method"] = "source_verified_disposition"
        represented_labels = {
            entry["label"] for entry in resolved_entries
            if entry["kind"] != "schedule"
        }
        # In marginal-note layouts the body number and operative words occupy
        # one column while the official heading is a separate block.  Once the
        # entry-level linker has independently resolved that TOC row to a
        # unique primary provision, the printed contents heading is the exact
        # heading source (doc 02 §5.1). Do not copy it onto nested clauses: a
        # schedule/rule row may retain its full heading in node text.
        for entry in resolved_entries:
            node = entry["node"]
            if (node is not None
                    and (node.kind in {"section", "article"}
                         or (node.kind == "subsection"
                             and re.match(r"^\d{1,4}\(", entry["label"])))
                    and not node.heading and entry.get("heading")):
                node.heading = _norm(entry["heading"])
        unresolved_labels = {
            entry["label"] for entry in resolved_entries
            if entry["kind"] != "schedule" and entry["node"] is None
        }
        unresolved_labels.update(promised - represented_labels)
        seg.matched = len(promised - unresolved_labels)
        seg.missing = sorted(unresolved_labels)[:200]
        seg.toc_entries = [
            entry for entry in resolved_entries
        ]
        seg.toc = {k: v for k, v in toc.items() if k not in sched_entries}
    if len(applied_disposition_ids) != len(toc_dispositions):
        missing_assertions = [item for item in toc_dispositions
                              if int(item["id"]) not in applied_disposition_ids]
        available = [
            {
                "assertion": int(item["id"]),
                "expected": (item["toc_entry_ordinal"], item["printed_label"]),
                "same_label_entries": [
                    (entry["ordinal"], entry["label"],
                     entry.get("source_block_id"), entry.get("heading"))
                    for entry in seg.toc_entries
                    if _citation_label_key(entry["label"])
                       == _citation_label_key(item["printed_label"])
                ],
            }
            for item in missing_assertions
        ]
        raise ValueError(
            "stale or unmatched TOC disposition assertions were not materialised: "
            + repr(available[:20])
        )
    seg.toc_dispositions_materialised = len(applied_disposition_ids)
    return seg


def assign_paths(seg: Segmentation, prefix: str) -> list[tuple[Node, str]]:
    """Give every node its ltree path: fed.act.1860_XLV.ch_XVI.s_302.cl_c

    ltree labels accept only [A-Za-z0-9_], so labels are transliterated. The
    ordinal is appended where a label would otherwise collide -- two provisos
    under one section are both "prov", and the path must stay unique because it
    is what a citation resolves against.
    """
    abbrev = {"part": "pt", "chapter": "ch", "schedule": "sch",
              "form": "form", "appendix": "app", "annexure": "ann",
              "order": "ord", "section": "s",
              "article": "art", "subsection": "ss", "clause": "cl",
              "proviso": "prov", "explanation": "expl", "illustration": "illus",
              "preamble": "pre"}
    out: list[tuple[Node, str]] = []
    used: set[str] = set()

    def slug(text: str) -> str:
        s = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
        return (s or "x")[:40]

    def walk(node: Node, base: str):
        for i, child in enumerate(node.children):
            raw = f"{base}.{abbrev.get(child.kind, 'n')}_{slug(child.label)}"
            p = raw
            # A suffix must itself be collision checked.  ``cl_2.4`` slugs to
            # ``cl_2_4``; the old fallback for a repeated ``cl_2`` at ordinal 4
            # produced that exact path and violated the database constraint.
            # The label remains verbatim; only the internal ltree key receives
            # an explicit occurrence suffix.
            occurrence = 1
            while p in used:
                p = f"{raw}_n{i}_{occurrence}"
                occurrence += 1
            used.add(p)
            out.append((child, p))
            walk(child, p)

    walk(seg.root, prefix)
    return out
