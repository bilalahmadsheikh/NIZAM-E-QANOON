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

import functools
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
# Repeated, because a provision amended twice carries two markers. The West
# Pakistan Motor Vehicles Ordinance prints its section 67 as
#
#     1[ 2[67. Compensation for the death of, or injury to, a passenger.--(1) ...
#
# -- substituted by one Ordinance and then added to by another. A single
# optional prefix matched "2[67." and returned ('section','67'); against
# "1[ 2[67." it returned None, and the section was not in the tree at all while
# its contents row sat in the gap queue. Found by reading the rendered page of
# an instrument blocked by exactly one gap.
#
# Bounded to three so this cannot consume an arbitrary run of brackets, and the
# inner shape is unchanged, so nothing that matched before stops matching.
#
# The run of markers is named separately below, because a consolidated edition
# footnotes a provision once per amendment and prints every marker it has
# collected -- so the run is a LIST -- and because a marker may carry a letter
# suffix where the publisher inserted a note between two existing ones. It has
# a name because `_INNER` needs the same run to find these openers mid-block,
# and the rule in this file is to extend the shared fragment, not restate it.
#
# Reader-instruction pattern (t), read off the pages of the Customs Act, 1969
# (document 4451):
#
#     1a,25[3A. Directorate General of Intelligence and Risk Management, ...
#     14a,129[19C. Minimal duties not to be demanded.- Where the value ...
#     44a,94,130[25D. Review of the value determined.- Notwithstanding ...
#     7,31[82.   Procedure in case of goods not cleared or warehoused ...
#     5a[193A. Procedure in appeal.-  (1) The Collector (Appeals) shall ...
#     9,81[194A. Appeals to the Appellate Tribunal.- (1) Any person ...
#     16a[203A.    Power to authorize expenditure.- The Board may ...
#
# against the siblings on the same pages that DID resolve -- 27[185A.,
# 54[187A., 81[194B., 81[194C. -- which differ from them only in carrying a
# single plain marker. That is the discriminator. The label after the bracket
# is unchanged and still required in full, so what is admitted here is
# provenance, never a citation.
_AMEND_MARKERS = r"(?:\d{1,4}[a-z]?(?:\s*,\s*\d{1,4}[a-z]?)*\s*)?"
# An opening parenthesis is admitted after the bracket for the same reason a
# quote already is: it is punctuation the amendment carries, not part of the
# label. Document 4451 prints section 21A as ``24[(21A. Power to defer
# collection of customs-duty.-``.
_AMEND_PREFIX = (
    r"(?:" + _AMEND_MARKERS + r"\[\s*[(\"\u201c\u2018']?\s*|[*\u2020\u2021]\s*){0,3}"
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
    # Source-history pages sometimes parenthesize a display Chapter heading
    # directly after an editorial note. Its dash-form is layout evidence, not
    # a prose reference such as "(Chapter II of this Act)".
    ("chapter", "chapter", re.compile(
        r"^\s*\(\s*CHAPTER(?:\s+|\s*[-\u2013\u2014]\s*)([IVXLC\d]+[A-Z]?)"
        r"\s*(?:\.|[-\u2013\u2014]){1,3}\s*(.*?)\s*\)?\s*$", re.I | re.S)),
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
        r"^\s*" + _AMEND_PREFIX + r"((?:THE\s+)?(?:FIRST\s+|SECOND\s+|THIRD\s+|FOURTH\s+|"
        r"FIFTH\s+|SIXTH\s+|SEVENTH\s+|[IVXLC\d]+\s+)?"
        r"S\s+C\s+H\s+E\s+D\s+U\s+L\s+E)\s*[.\-:]?\s*(.*)$",
        re.I | re.S)),
    # The ordinal is more commonly printed after the word (``SCHEDULE II``).
    # Capture it in the label rather than as trailing prose; otherwise the
    # short Roman numeral looks like a run-on fragment and the second schedule
    # is silently appended to the first.
    ("schedule", "schedule", re.compile(
        r"^\s*" + _AMEND_PREFIX + r"((?:THE\s+)?SCHEDULE\s*[-–—]?\s*"
        r"(?:[IVXLC]+|\d+|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH))"
        r"\s*[.\-–—:]?\s*(.*)$", re.I | re.S)),
    ("schedule", "schedule", re.compile(
        r"^\s*" + _AMEND_PREFIX + r"(?:THE\s+)?((?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|[IVXLC\d]+)?\s*SCHEDULE)\s*[.\-–—:]?\s*(.*)$",
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
    #
    # BUT a digit set against an amendment bracket is a MARKER, not a level.
    # `\s*\.\s*` between the levels admits any whitespace, newlines included,
    # and what that actually collected in this corpus was the footnote or
    # amendment marker printed after a section's stop:
    #
    #     doc 2686 p4   "5. \n1 [Regularization of Services of PBT Employees.---"
    #     doc 2893 p2   "3. \n7 [Chief Administrator].- 8 [(1) Secretary ..."
    #     doc 4348 p16  "23. 2 [ Invalidity pension]. -(1) An insured person ..."
    #
    # Section 5 of the KP Employees of Transport Department (Regularization of
    # Services) Act 2017 -- the ONLY operative section that Act has -- sat in the
    # tree as "5. 1", reachable by no citation at all. `_AMEND_MARKERS` already
    # reads a marker glued to a bracket BEFORE a label (``54[187A.``); the same
    # apparatus after the label's stop is the same evidence, because a bracket is
    # the amendment's own delimiter.
    #
    # TWO LOOSER FORMS ARE REFUTED BY MEASUREMENT -- do not retry them:
    #   * refusing the newline outright moved 479 pieces in 90 documents and
    #     invented six sections out of the fee table on page 23 of doc 3344
    #     ("24. \n16 Rs 1,000,000");
    #   * the bracket rule WITHOUT the tight-form alternative first destroyed
    #     Punjab Excise Manual rule "5.30 [4]", a real compound label followed
    #     by a bracket.
    # Hence the tight form `\.\d{1,4}` is matched FIRST and keeps its bracket;
    # only the spaced form refuses one. Shape alone was not enough; the bracket
    # is. Measured blast radius of the rule as it stands: 21 pieces in 10
    # documents, every one from a phantom compound label to the printed section
    # number, none in the other direction.
    #
    # Deliberately NOT fixed: doc 4296 "13. 1 The 2[Chairperson]" has no bracket
    # after the marker and shape cannot tell it from a real "13.1 The ...".
    ("section",    "section",    re.compile(
        r"^\s*" + _AMEND_PREFIX
        + r"(\d{1,4}(?:\.\d{1,4}|\s*\.\s*\d{1,4}(?![ \t ]*\[)){1,4}"
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
    # An inserted section suffix can use a dot instead of a dash: the Land
    # Preservation Act prints TOC "5.A." and body "5-A.". Keep the printed
    # suffix inside its label; otherwise it becomes a second section 5 with
    # heading "A. Power ...". No newline/space after the internal dot is
    # admitted, so a section ending in "5." followed by clause "A." is not
    # joined. Numeric dotted hierarchy continues through its own rule above.
    ("section", "section", re.compile(
        r"^\s*" + _AMEND_PREFIX + r"(\d{1,4}\.[A-Z]{1,3})\s*\.\s*(.*)$", re.S)),
    # The same inserted-suffix shape printed WITHOUT the closing stop. The
    # Karachi Port Trust Act prints "59.F Establishment of sinking fund." while
    # its own contents prints "59A.", "59B.", "59C." The rule above needs the
    # trailing stop, so this fell through to the plain form below, the label
    # became "59", the F was eaten into the heading, and section 59F collided
    # with the real section 59 (bye-laws to be exhibited) and was demoted.
    #
    # Measured: 46 blocks in 26 documents open this way; 28 kept only the bare
    # number while 7 (documents 4235 and 4495) kept the compound label
    # correctly -- an inconsistency in the opener, not a missing capability.
    #
    # The guard is what keeps it to provisions, and each half was chosen
    # against a false-positive family found by reading all 46. Whitespace
    # immediately after a SINGLE letter excludes abbreviation runs read as
    # labels ("2.M.S.PESSI", "3.S.M.O.(HQ.)"); a Capitalised word next excludes
    # schedule rows ("2.A 4Computer Programmer") and scan noise
    # ("13.U V 11\\13"). The letter must sit against the dot, so a section
    # ending "5." followed by a clause "A." on the next line still does not join.
    ("section", "section", re.compile(
        r"^\s*" + _AMEND_PREFIX + r"(\d{1,4}\.[A-Z])\s+(?=[A-Z][a-z])(.*)$", re.S)),
    # "302." / "302A." / "302-A."  -- 20.5% of blocks
    ("section",    "section",    re.compile(r"^\s*" + _AMEND_PREFIX + r"(\d{1,4}\s*[-–]?\s*[A-Z]{0,3})\s*\.\s*(.*)$", re.S)),
    # A section number printed BARE, with its first subsection set in the next
    # column or on the next line -- reader-instruction pattern (c). The Punjab
    # Urban Immovable Property Tax Rules 1958 print rule 1 on page 3 as
    #
    #     1
    #     (1)
    #     these rules may be called the West Pakistan urban Immovable
    #     Property Tax Rules, 1958.
    #
    # while rules 3 to 30 on the pages after it all carry their period. No rule
    # above matches it, so the body never opens at 1; the leading integer never
    # falls below the contents list's peak of 25; `parse_contents` finds no
    # candidate boundary at all and reports that the document prints no
    # contents; and all 25 printed contents rows are then built as sections,
    # every one of which collides with the real rule carrying that number. One
    # missing character costs the document its entire contents list and leaves
    # 24 structural collisions behind.
    #
    # A section opens at its FIRST subsection, never its fourth, which is what
    # separates this from a cross-reference. `fused_sub` in `_classify_body`
    # already takes that judgement for the tight "23(1)." form.
    #
    # The separator must be a NEWLINE or two or more spaces. One space is
    # ordinary prose spacing, and it is exactly the form measured unsafe when
    # the looser rule was tried for `fused_sub`: "3 (1) There shall be a Dean
    # for each Faculty" on page 21 of document 2452 is paragraph 3(1) of an
    # appended Statute, not section 3 of the Act. 15 blocks in the corpus carry
    # that one-space shape and are still refused; 43 carry this one.
    #
    # The subsection must then be followed by a letter or an opening quote,
    # which is what keeps out the cross-reference grid in block 537239 on page
    # 14 of document 3974 -- "5 / (1) / 5 / (1) / (a) / 5 / (2) / ..." is a
    # table of provision references, not a provision.
    ("section",    "section",    re.compile(
        r"^\s*" + _AMEND_PREFIX
        + r"(\d{1,4}(?:\s*[-–]\s*[A-Z]{1,3}|[A-Z]{1,3})?)"
          r"(?:[ \t ]*\n|[ \t ]{2,})\s*"
          r"(\(\s*1\s*\)\s*[A-Za-z\"“‘].*)$", re.S)),
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


def _consecutive_roman_parts(previous: str, following: str) -> bool:
    """Validate printed Roman labels before using their sequence as scope proof."""
    def number(label: str) -> int | None:
        label = label.upper()
        if not label or not re.fullmatch(
            r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})", label
        ):
            return None
        values = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
        return sum(-values[c] if i+1<len(label) and values[c]<values[label[i+1]]
                   else values[c] for i,c in enumerate(label))
    left,right = number(previous),number(following)
    return left is not None and right is not None and right==left+1

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
    r"[.:-]?\s*S\.?\s*\d{1,4}\s*[-\u2013]?\s*[A-Z]?\s*,?\s*"
      r"(?:ins|inserted|subs|substituted|omitted|deleted)\b|"
    # Historical consolidations use terse editorial provenance, not the
    # wording of an operative amending provision: ``S. 15-D ins. by ...``,
    # ``The words ... rep. by ...`` and ``See now the Code ...``. The explicit
    # abbreviations / retrospective reference make these source apparatus;
    # do not broaden this to "are repealed by" or "In section ...", which can
    # be enacted amendment text.
    r"[.:-]?\s*See\s+now\s+(?:the\s+)?Code\s+of\s+Civil\s+Procedure\b"
      r"(?![\s\S]{0,200}\b(?:shall|must|may|will)\b)|"
    r"[.:-]?\s*The\s+(?:original\s+)?(?:words?|brackets|provisions?)\b"
      r"[\s\S]{0,1200}\brep\.?\s+by\b|"
    # The same editorial frame, written out: ``The word "Local" omitted by
    # the Punjab Act IV of 1944, s.10.`` The Land Preservation Act 1900's
    # page-14 note run is three of these, and without them the run scored
    # one provenance line of the two it needs, so its markers 1, 2 and 3
    # were handed to the grammar as section numbers and collided with the
    # Act's real sections 1 and 2. Requiring a NAMED instrument keeps this
    # to provenance: an enacted amendment says "shall be omitted", and the
    # unquoted-modality test in _split_note_is_apparatus refuses those.
    r"[.:-]?\s*The\s+(?:original\s+)?(?:words?|brackets|provisions?)\b"
      r"[\s\S]{0,200}\bomitted\s+by\b[\s\S]{0,80}"
      r"\b(?:Act|Ordinance|Order|Regulations?|Rules?|Notification)\b|"
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
    # Source-reviewed S7 decisions this parse carried out, and the ones it
    # declined to carry out with the reason. Evidence, not a counter: a
    # reviewer has to be able to see what their reading did to the tree.
    structural_reviews_enacted: list = field(default_factory=list)
    structural_reviews_refused: list = field(default_factory=list)
    schedule_sections_retyped: int = 0
    nested_list_items_reparented: int = 0
    detached_heading_bodies_merged: int = 0
    marginal_notes_split: int = 0
    toc_dispositions_materialised: int = 0
    curation_patches_applied: int = 0
    # Which structural-heading repair, if any, produced this parse.
    structural_repair: str | None = None
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

# Section 1's extent, commencement and application sub-sections. Pakistan Code
# and KP Code consolidations often print them with bare numbers --
#     1. Short title, extent and commencement.-- (1) This Act may be called...
#     2. It extends to the whole of Pakistan.
#     3. It shall come into force at once.
# -- or behind an amendment bracket, ``2[(2) It extends to...``. Read as
# sections they collide with the real sections 2 and 3, and the collision was
# repeatedly decided the wrong way round: on 17 Sep 2026, 26 released
# instruments were found answering "section 2" with the extent sentence while
# the Definitions section sat demoted beneath it (Pakistan Nuclear Regulatory
# Authority Ordinance 2001, Torture and Custodial Death Act 2022, West Pakistan
# Departmental Inquiries (Powers) Act 1958 among them). The sentence is short,
# closed and never a section of its own.
_SECTION_ONE_SUBPART = re.compile(
    r"\s*(?:It|They|The\s+same)\s+"
    r"(?:extends?|shall\s+extend|applies|shall\s+apply|"
    r"shall\s+come\s+into\s+force|comes?\s+into\s+force|"
    r"shall\s+be\s+deemed\s+to\s+have\s+come\s+into\s+force|"
    r"shall\s+have\s+come\s+into\s+force)\b[^.]{0,240}\.\s*\]?\s*", re.I | re.S)

# The sub-part speaks about the instrument itself -- its subject is "It".
# Once some other actor acquires a duty in the same sentence, the sentence
# is operative law and must not be demoted, however much it opens like an
# extent clause. This is the stub guard's rule in the parser: never demote
# a unit that carries law of its own.
_SUBPART_FOREIGN_DUTY = re.compile(
    r"\b(?:the|a|an|every|any)\s+\w+(?:\s+\w+){0,3}\s+shall\b", re.I)


# ------------------------------------------------- bare Roman display headings
#
# A document that prints ``I- General`` / ``II. Issue and Cancellation of
# Membership:`` over rules that restart at 1 in each division means a Part
# heading.  The grammar above requires the literal word PART, CHAPTER or
# SECTION, so those headings become no node at all: each lands in the TAIL of
# the preceding rule's text, and in the Quaid-e-Azam Library Membership Rules
# (document 3393) Part VII's entire operative sentence -- "A suggestion book
# shall be kept in the Library in which the members may record their
# suggestions" -- is buried inside Part VI rule 4 on page 6.
#
# A bare-Roman pattern cannot be gated on SHAPE.  I, V and X are ordinary list
# markers and "I" is a pronoun; four lines above its own Part I heading the same
# document prints "I. Ordinary" and "II. Student" as items of its rule 2.  So
# the promotion is gated on CONSEQUENCE, in three parts, all required:
#
#   (i)   the block reads as a display heading -- short, display-cased, narrow,
#         and centred in the body column.  Geometry is what separates the two
#         forms in document 3393: "I. Ordinary" is indented at x0 144.1 with its
#         centre 112.7pt to the left of the column's, while "I- General" is
#         centred on the column to within a fifth of a point;
#   (ii)  the numerals form a run starting at I.  A document with a real Part V
#         prints I to IV first, so one stray "V." cannot open a division;
#   (iii) the promotion resolves a repeated-sibling-label collision the document
#         ACTUALLY HAS.  That is read off the finished tree rather than guessed:
#         the walk runs, its collisions are collected, and the parse is repeated
#         with the promotion only where a candidate heading separates two
#         siblings that collided.
_ROMAN_DISPLAY = re.compile(
    r"^\s*([IVXLC]{1,6})\s*[.\-–—:)]\s+(\S.*)$", re.S)
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
# Words a display title may carry in lower case and still be a heading.
_TITLE_STOPWORDS = {"a", "an", "and", "as", "at", "by", "for", "from", "in",
                    "of", "on", "or", "the", "to", "with"}
# Two is too short to be a run: "I." then "II." happens inside an ordinary
# two-item list.  Three consecutive display headings is a division scheme.
_ROMAN_DISPLAY_MIN_RUN = 3
# Upper-case dominance is real evidence, but it is evidence about the RUN, not
# about every member of it.  Seven of document 3393's nine Part headings are
# capitalised; "I- General" and "II. Issue and Cancellation of Membership:" are
# title-cased.  Requiring capitals of every member would break the run at I and
# promote nothing, so each heading must be display-cased (capitals or title
# case) and the run must be predominantly capitals.
_ROMAN_DISPLAY_MIN_UPPER = 0.5
# An amending instruction is a schedule CELL: its words name the enactment being
# amended, never the row's own subject.  Used only to refuse a schedule exit,
# and only where the printed contents promised something else entirely.
_AMENDING_ITEM = re.compile(
    r"^\s*(?:In|After|Before|For|Omit|Insert|Substitute|Add)\b"
    r"[^.]{0,120}?\b(?:section|sub-section|clause|rule|schedule|paragraph)\b",
    re.I)


def _roman_number(label: str) -> int | None:
    """The value of a well-formed Roman numeral, else None."""
    label = (label or "").upper()
    if not label or not re.fullmatch(
            r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})",
            label):
        return None
    return sum(
        -_ROMAN_VALUES[c]
        if i + 1 < len(label) and _ROMAN_VALUES[c] < _ROMAN_VALUES[label[i + 1]]
        else _ROMAN_VALUES[c]
        for i, c in enumerate(label))


def _display_cased(title: str) -> tuple[bool, bool]:
    """(reads as a display title, is upper-case dominant)."""
    letters = [ch for ch in title if ch.isalpha()]
    if len(letters) < 4:
        return False, False
    if sum(1 for ch in letters if ch.isupper()) / len(letters) >= 0.8:
        return True, True
    words = re.findall(r"[A-Za-z][A-Za-z'’]*", title)
    if not words:
        return False, False
    return all(word[0].isupper() or word.casefold() in _TITLE_STOPWORDS
               for word in words), False


def _roman_display_heading(text: str) -> tuple[str, str] | None:
    """(numeral, title) when a block reads as a bare Roman display heading."""
    flat = _norm(text)
    if not flat or len(flat) > 80:
        return None
    match = _ROMAN_DISPLAY.match(flat)
    if not match:
        return None
    value = _roman_number(match.group(1))
    if value is None or not 1 <= value <= 30:
        return None
    # ``III.  A.  MEMBERSHIP FEE`` prints a sub-letter before its words; the
    # letter belongs to the heading's own subdivision, not to the numeral.
    title = re.sub(r"^[A-Z]\s*[.\-]\s*", "", match.group(2).strip())
    title = title.strip(" .:;-–—")
    if not title or len(title.split()) > 9:
        return None
    reads, _ = _display_cased(title)
    return (match.group(1).upper(), title) if reads else None


def _centred_in_body_column(block: dict, left: float | None,
                            right: float | None) -> bool:
    """A narrow run of text centred in the body column, not at its margin."""
    if left is None or right is None or right - left < 80:
        return False
    x0, x1 = block.get("x0"), block.get("x1")
    if x0 is None or x1 is None or x1 <= x0:
        return False
    width = right - left
    return ((x1 - x0) <= width * 0.75
            and x0 >= left + width * 0.08
            and abs((x0 + x1) / 2 - (left + right) / 2) <= width * 0.05)


def _column_edge(values: list, quantile: float) -> float | None:
    """A percentile edge of the body column, not an extreme one: one wide table
    row must not widen it and one deep quotation must not narrow it."""
    if len(values) < 4:
        return None
    return values[min(len(values) - 1,
                      max(0, int(quantile * (len(values) - 1))))]


def _contradicts_promise(rest: str, context: str | None,
                         expected: str | None,
                         toc: dict | None = None,
                         key: str | None = None) -> bool:
    """Does the body unit positively name something the contents did not promise?

    Deliberately silent where the body prints no heading at all.  Absence of
    corroboration is not contradiction, and treating it as such would swallow a
    whole Act into a false schedule -- exactly the failure the contents-based
    schedule exit exists to prevent.

    Two positive contradictions, both of which take real printed words to reach:

      * the unit is an amending INSTRUCTION.  Its words name the enactment being
        amended, so they can never be the heading of the section whose number it
        shares;
      * the unit reproduces a printed contents heading filed under a DIFFERENT
        label.  Document 4089 needs this one: its contents numbers thirty
        amended Acts as entries 3 to 32 while the schedule's serial column
        restarts at 1, so serial 2 reads "The University of Karachi Act, 1972
        (Sindh Act No.XXV of 1972)" -- which the contents prints verbatim as its
        entry 4.  The list itself proves the label coincidence spurious.
    """
    candidate = _norm(rest)
    if not expected or not candidate:
        return False
    if (_heading_supports(candidate, expected)
            or _heading_tail_supports(context, expected)):
        return False
    if _AMENDING_ITEM.match(candidate):
        return True
    return bool(toc) and any(
        other != key and _heading_supports(candidate, heading)
        for other, heading in toc.items())


def _names_a_printed_entry(text: str, toc: dict | None) -> bool:
    """Does this row reproduce a heading the printed contents list promises?

    The evidence that a schedule row is the schedule's citable ENTRY rather than
    anonymous table content.  Document 4089's schedule numbers thirty amended
    Acts in its left column and lists each Act's amendments, restarting at 1, in
    its right; the left column reproduces the contents list verbatim and the
    right column never does.
    """
    return bool(toc) and any(_heading_supports(text, heading)
                             for heading in toc.values())


def _source_proved_labels(seg, blocks: list) -> set:
    """Citable labels whose OWN printed block reproduces the promised heading.

    A label is not evidence of identity by itself.  In document 4089 the parser
    hands section 1 the contents heading "Short title and Commencement" while
    its printed block reads "1. In section 2 -" -- a schedule row wearing a
    section's number.  Only labels the source itself proves are protected from
    a structural repair; a label that resolved to the wrong text is exactly what
    a repair is for.
    """
    text_by_id = {block.get("id"): block.get("text") or "" for block in blocks}
    proved = set()
    for node in seg.flatten():
        if node.kind not in ("section", "article"):
            continue
        key = node.label.replace(" ", "")
        promise = seg.toc.get(key)
        if not promise:
            continue
        own = _norm(text_by_id.get(node.first_block, ""))
        found = classify(own)
        if _heading_supports(_norm(found[2]) if found else own, promise):
            proved.add(key)
    return proved


def _roman_display_part_run(candidates: list) -> frozenset:
    """The maximal prefix of the candidates that is a run starting at I."""
    run: list = []
    expected = 1
    for block_id, (numeral, title) in candidates:
        if _roman_number(numeral) != expected:
            break
        run.append((block_id, title))
        expected += 1
    if len(run) < _ROMAN_DISPLAY_MIN_RUN:
        return frozenset()
    capitals = sum(1 for _, title in run if _display_cased(title)[1])
    if capitals / len(run) < _ROMAN_DISPLAY_MIN_UPPER:
        return frozenset()
    return frozenset(block_id for block_id, _ in run)


def _collision_separated_by(decisions: list, order: dict,
                            cuts: list) -> bool:
    """Would cutting at *cuts* put two colliding siblings under different parents?"""
    for decision in decisions:
        if decision.get("parent") is not None:
            continue
        left = order.get(decision["candidate"].first_block)
        right = order.get(decision["canonical"].first_block)
        if left is None or right is None:
            continue
        low, high = min(left, right), max(left, right)
        if any(low < cut < high for cut in cuts):
            return True
    return False


def _structural_repair_is_safe(before, after, blocks: list) -> bool:
    """A structural repair may add citable law; it may never remove any.

    Five refusals, in the order they matter.

      * a citable label whose identity the SOURCE proved and which the repair
        removes is a citation that stops resolving (INV-4).  Labels the source
        did not prove are not protected -- see `_source_proved_labels`;
      * an instrument left with no citable provision at all is not an
        improvement, whatever it tidies;
      * a found contents list that stops being found has been handed back to the
        body, and a document's own list of sections then becomes its law;
      * a repair that does not reduce the collisions it was chosen to resolve
        has not earned the re-parse;
      * a block attached to a provision before and to nothing after has had its
        printed characters stranded (CORPUS-CRITERIA C4/C5).  Moving into an
        apparatus role is allowed, because a contents list is apparatus; falling
        out of the ledger is not.
    """
    citable = ("section", "article")
    was = {node.label.replace(" ", "") for node in before.flatten()
           if node.kind in citable}
    now = {node.label.replace(" ", "") for node in after.flatten()
           if node.kind in citable}
    if (was - now) & _source_proved_labels(before, blocks):
        return False
    if was and not now:
        return False
    if before.toc_found and not after.toc_found:
        return False
    if len(after.repeated_label_decisions) >= len(
            before.repeated_label_decisions):
        return False
    stranded = ({bid for bid, (role, _) in after.block_roles.items()
                 if role == "unassigned"}
                - {bid for bid, (role, _) in before.block_roles.items()
                   if role == "unassigned"})
    return not stranded


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
            # No provision's text opens with a closing parenthesis, but a label
            # printed inside brackets is followed by one: document 4149 page 14
            # prints definition clause (23A) as `1[(23A.) \u201cService Delivery
            # Centre\u201d means ...`. The amendment prefix admits the opening
            # bracket, so the closing one is what tells the two apart.
            if kind in ("section", "article") and rest.lstrip().startswith(")"):
                return None
            return kind, label, rest
    return None


def _opens_section(text: str, key: str) -> bool:
    """True when *text* opens a section carrying exactly the label *key*."""
    found = classify(text)
    return (found is not None and found[0] == "section"
            and found[1].replace(" ", "") == key)


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
    + _AMEND_MARKERS + r"\[\s*[\"“‘'(]?\s*\d{1,4}\s*[-–]?\s*[A-Z]{0,3}\s*\.\s*(?:[A-Z(*\"“]|\d{1,4}\s*\[)" # 3[19-B. / 1[“6-A. / 1a,25[3A.
    r"|(?:\d{1,4}\s*)?\[\s*\d{1,4}\s*[-–]\s*[A-Z]{1,3}\s*\]\s*\.\s*[A-Z]" # 7[3-A]. Notices
    r"|(?:\d{1,4}\s*)?\[\s*Sections?\s+\d{1,4}[A-Z]{0,3}\s*\." # 1[Section 10.
    r"|" + _AMEND_MARKERS + r"\[\s*\d{1,4}[A-Z]{0,3}\s*\n\s*[\"“]?[A-Z]" # 697[72A newline Heading / 4[5 newline “Delegation
    r"|(?:\d{1,4}\s*)?\[\s*[lI]\d{1,3}[A-Z]{0,3}\s*\.\s*[A-Z]" # 3[l35A. OCR glyph
    r"|\d{5,8}[A-Z]{0,3}\s*\.\s+[A-Z(]"                    # 52337A. TOC-proved fused marker
    r"|\d{1,4}\s*[-–]?\s*[A-Z]{0,3}\s*\.\s+[A-Z(*]"       # 302. heading / 42. ***
    r"|\d{1,4}\.[A-Z]{1,3}\s*\.\s+[A-Z(*]"              # 5.A. inserted suffix
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

# Older Sindh consolidations print ``15B.---(1)`` and even ``15D..---(1)``.
# Fused chapter tails / preceding paragraphs hide these starts because _INNER
# requires an immediate word or subsection after the dot. Expose only a NEW
# extracted line with a complete label, one or two separator dots, a bounded
# dash run, and subsection (1) followed by an uppercase word. This does not
# interpret dotless ``22A---`` or redefine citation labels. Ordinary list /
# quotation / schedule context still passes through the body classifier.
_INNER_DASH_SECTION = re.compile(
    r"(?<=\n)[ \t\u00a0]*"
    r"(?=" + _AMEND_PREFIX
    + r"\d{1,4}\s*[-\u2013]?\s*[A-Z]{1,3}\s*\.{1,2}\s*"
      r"[-\u2013\u2014]{1,3}\s*\(\s*1\s*\)\s*[A-Z])",
)
# A few source-history notes share their block with a parenthesized printed
# Chapter heading. The note must be footnote material, but the heading remains
# a structural node; it is split before the normal classification walk.
_PARENTHESIZED_CHAPTER = re.compile(
    r"(?<=\n)[ \t\u00a0]*(?=\(\s*CHAPTER\s+[IVXLC\d]+[A-Z]?"
    r"\s*(?:\.|[-\u2013\u2014]){1,3})", re.I)

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


def subdivide_spans(text: str) -> list[tuple[int, str]]:
    """``subdivide``, with each piece's character offset inside ``text``.

    The offset exists because a block id is not an anchor when PyMuPDF merges
    several printed lines into one block. The Sind Landing and Wharfage Fees
    Act, 1882 (document 1918) prints its twelve contents rows on page 1, and
    block 134870 arrives holding eight of them at once:

        5.  \nGovernment to fix limits of bandars, etc., ... \n \n6. \nPowers
        and duties under this Act by whom to be exercised ... \n \n7. ...

    Every entry cut out of that block recorded ``source_block_id = 134870`` and
    nothing else, so eight rows of ``instrument_toc_entry`` claimed the same
    evidence and none could name the printed line it came from. The offset makes
    the anchor per-entry: the row for label 7 is at character 178 of block
    134870 and the row for label 6 at character 108.

    ``subdivide`` is defined in terms of this, so there is one cut rule, not two.
    """
    fused = _FUSED_MARGIN_PREFIX.match(text)
    if fused and not _FOOTNOTE.match(text):
        # group(2) starts partway into the text; shift the recursion's offsets
        # so they stay relative to the block and not to the tail.
        shift = fused.start(2)
        return ([(fused.start(1), fused.group(1))]
                + [(shift + offset, piece)
                   for offset, piece in subdivide_spans(fused.group(2))])

    raw_cuts = ({m.end() for m in _INNER.finditer(text)}
                | {m.end() for m in _INNER_DASH_SECTION.finditer(text)}
                | {m.end() for m in _INNER_RULE.finditer(text)}
                | {m.end() for m in _INNER_ALPHA.finditer(text)}
                | {m.end() for m in _INNER_SOURCE_NOTE.finditer(text)}
                | {m.end() for m in _INNER_BARE.finditer(text)}
                | {m.end() for m in _INNER_DIV.finditer(text)}
                | {m.end() for m in _PARENTHESIZED_CHAPTER.finditer(text)})
    # Do not cut a whitespace-padded dotted citation label (``6 . 2 .``) at
    # its internal dot.  A genuine new section may follow a sentence-ending
    # dot, but that sentence does not itself end in a bare number.
    cuts = sorted(c for c in raw_cuts if not (
        # ``$`` also matches immediately BEFORE a final newline. That made
        # ``... section 58.\n65. Actual provision`` look like an inline
        # dotted citation (``6 . 2 .``) and hid 65. Only a same-line
        # whitespace-padded citation is suppressed; a printed new line opens
        # the independently numbered provision.
        (re.search(r"\d[ \t]*\.[ \t]*\Z", text[:c])
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
        # A section's own number, alone before its FIRST subsection, is not an
        # internal boundary -- the two are one opener (pattern (c)). The Punjab
        # Urban Immovable Property Tax Rules print rule 1 as
        #
        #     1
        #     (1)
        #     these rules may be called the West Pakistan urban Immovable ...
        #
        # and cutting at "(1)" leaves "1" alone, which no rule classifies, so
        # the rule is lost and with it the document's whole contents boundary:
        # the numbering never falls back to 1 and `parse_contents` reports that
        # the document prints no contents at all.
        #
        # Only subsection (1), and only when EVERYTHING before the cut is the
        # bare label: a cut before (2) or after any text of the provision's own
        # still stands, so no block that held two provisions is merged.
        or (re.fullmatch(r"\s*\d{1,4}(?:[-–][A-Z]{1,3}|[A-Z]{1,3})?\s*",
                         text[:c])
            and re.match(r"\(\s*1\s*\)", text[c:]))
        # ``Note. 1. ...`` numbers an explanatory note; it does not open a
        # new section. Keep the printed note attached to its governing rule.
        # "Note." must stand at the head of its own line: the unanchored
        # form matched any sentence merely ENDING in the word "note", and
        # the Contract Act 1872 prints an illustration to section 132 that
        # ends "...is no answer to a suit by C against A upon the note."
        # Section 133 follows it and was being swallowed whole.
        or re.search(r"(?:^|\n)\s*Notes?\.\s*$", text[:c], re.I)))
    if not cuts:
        return [(0, text)]
    pieces, prev = [], 0
    for c in cuts:
        piece = text[prev:c]
        if piece.strip():
            pieces.append((prev, piece))
        prev = c
    tail = text[prev:]
    if tail.strip():
        pieces.append((prev, tail))
    return pieces or [(0, text)]


def subdivide(text: str) -> list[str]:
    """Cut one block at internal provision starts. Returns >= 1 piece.

    There is no minimum length. A 60-character floor used to stand here on the
    theory that a short block cannot hold two provisions; measured against the
    corpus it silently merged 1,754 blocks, among them
    "1. Short title and commencement. \n2. Repeal." -- two sections read as one.
    _INNER is the guard, and it is a strict one: a cut needs a sentence ending or
    a line break *and* a form that opens a provision.
    """
    return [piece for _, piece in subdivide_spans(text)]


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


# A numbered line whose number is not the head of a longer number: "1960)."
# must not read as footnote 19, which is what `\d{1,2}` alone does to it.
_NUMBERED_LINE = re.compile(r"^\s*(\d{1,2})(?!\d)\s*[.:-]?\s*(\S.*)$")
_SPLIT_NOTE_NUMBER = re.compile(r"^\s*(\d{1,2})\s*[.:-]\s*$")
_SPLIT_NOTE_BODY = re.compile(
    r'^\s*(?:'
    r'(?:Cl\.?\s*\d+(?:st|nd|rd|th)?|Sub[- ]section)\s+'
      r'(?:ins\.?|inserted|repealed|omitted)\s+(?:by|ibid)\b'
    r'|See\s+now\s+(?:the\s+)?Code\s+of\s+Civil\s+Procedure\b'
    r'|For\s+notification\s+see\s+Punjab\s+Local\s+Rules\s+and\s+Orders\b'
    r'|Central\s+Acts\s*,\s*V(?:o|c)l\.?\s+[IVXLC]+\b'
    r'|Paragraph\b.{0,180}\bibid\b'
    r'|The\s+Preamble\s+omitted\s*[.,]?\s*ibid\b'
    r'|The\s+original\s+sub[- ]section\b.{0,180}'
      r'\bre[- ]numbered\b.{0,100}\bby\s+(?:Punjab|Sindh?|W\.?P\.?)\b'
    r'|Clauses?\s+[\[(].{0,80}\badded\s+by\s+'
      r'(?:Punjab|Sindh?|W\.?P\.?)\b'
    r'|The\s+(?:original\s+)?(?:words?|brackets|provisions?)\b'
      r'[\s\S]{0,1200}\b(?:omitted|rep\.?|repealed|subs\.?|amended|added)\s+'
      r'(?:by|ibid)\b'
    r')', re.I,
)


def _split_note_is_apparatus(number: int, parts: list[str]) -> bool:
    """Require provenance for this item, not just its neighbouring notes.

    Past-tense editorial references can quote words containing ``shall``.
    Outside those quotations, operative modality contradicts whole-item
    apparatus classification; abstain rather than swallow an amendment.
    """
    body = " ".join(parts)
    unquoted = re.sub(r'"[^"]*"|“[^”]*”|‘[^’]*’|\'[^\']*\'', '', body)
    if re.search(r'\b(?:shall|must|may|will)\b', unquoted, re.I):
        return False
    return bool(_FOOTNOTE.match(f"{number}. {body}")
                or _SPLIT_NOTE_BODY.match(body))


def _is_footnote_run(text: str, *, split_numbers_only: bool = False) -> bool:
    """Several numbered lines of amendment provenance, wherever they sit.

    `_is_furniture` asks two questions a long footnote run answers no to: is the
    block in the bottom margin -- a run starts high BECAUSE it is long, the
    Prevention of Corruption Act's page-2 run opening at y0 575 of 792 -- and
    does the block START with amendment vocabulary, when its first line is
    usually the one line carrying no amendment verb:

        1The Act has been applied to Baluchistan, see Gazette of India, 1947
        2Subs.by the Central Laws (Statute Reform) Ordinance, 1960
        3The original sub-section (3) omitted by the Prevention of Corruption
        4Added by the Anti-Corruption Laws (Amendment) Act, 1965
        5Subs. by the Prevention of Corruption Laws (Amendment) Act, 1977

    So `_FOOTNOTE.match` sees line 1, fails, and `subdivide` hands markers 1
    through 5 to the grammar as section numbers. That is where the corpus's
    phantom sections come from, and with them the stub citations.

    Ask about the RUN instead: numbered lines, strictly ascending and distinct
    the way a footnote list numbers, at least two carrying the amendment
    vocabulary `_FOOTNOTE` already knows. A contents list is numbered and
    ascending too, which is why the vocabulary test is required and not
    optional -- "1. Short title." and "2. Definitions." match none of it.
    """
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if len(lines) < 3:
        return False
    # Sindh's re-typeset consolidations can place a footnote's number alone
    # on one extracted line and its words on the next. The inline-only test
    # below sees none of those note starts, so their numbers vote on the TOC
    # boundary and later become phantom sections (3353, rendered pp6 and 8).
    # Reconstruct logical notes ONLY for dotted, isolated numbers, with at
    # least three ordered starts and two explicit provenance openings. Wrapped
    # legal prose and numeric tables do not satisfy that vocabulary evidence.
    if any(_SPLIT_NOTE_NUMBER.fullmatch(line) for line in lines):
        logical: list[tuple[int, list[str]]] = []
        for line in lines:
            if match := _SPLIT_NOTE_NUMBER.fullmatch(line):
                logical.append((int(match.group(1)), []))
            elif match := _NUMBERED_LINE.match(line):
                logical.append((int(match.group(1)), [match.group(2)]))
            elif logical:
                logical[-1][1].append(line)
            else:
                # A leading operative sentence means this is not a whole
                # apparatus block. Do not let its trailing notes swallow law.
                break
        else:
            sequence = [number for number, _ in logical]
            notes = [f"{number}. " + " ".join(parts)
                     for number, parts in logical]
            if (len(sequence) >= 3
                    and sequence == sorted(set(sequence))
                    # TWO good notes cannot vouch for a third item's law.
                    # Every logical item must itself be recognisable apparatus
                    # before the entire source block is assigned that role.
                    and all(_split_note_is_apparatus(number, parts)
                            for number, parts in logical)
                    and sum(bool(_FOOTNOTE.match(note) or re.match(
                        r'^\d{1,2}\.\s*Sub[- ]section\s+(?:repealed|omitted)\s+by\b',
                        note, re.I)) for note in notes) >= 2):
                return True
    if split_numbers_only:
        return False
    numbered = [(int(m.group(1)), ln) for ln in lines
                if (m := _NUMBERED_LINE.match(ln))]
    if len(numbered) < 3:
        return False
    seq = [n for n, _ in numbered]
    if seq != sorted(seq) or len(set(seq)) != len(seq):
        return False
    return sum(1 for _, ln in numbered if _FOOTNOTE.match(ln)) >= 2


def _section_number_spans(blocks: list[dict], *,
                          drop_footnote_runs: bool = True
                          ) -> list[tuple[int, int, str, str, int]]:
    """(index, number, label, heading, char offset) per section-shaped piece.

    ``drop_footnote_runs`` exists because this feeds the contents BOUNDARY, and
    a boundary can depend on the very apparatus the filter removes -- see
    `_opening_toc_hints`, which falls back to the unfiltered set rather than
    give up on a document.
    """
    out = []
    for i, b in enumerate(blocks):
        if drop_footnote_runs and _is_footnote_run((b.get("text") or "").strip()):
            continue
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
        for offset, piece in subdivide_spans(b["text"]):
            c = classify(piece)
            if not c or c[0] != "section":
                continue
            label = c[1].replace(" ", "")
            heading = _norm(c[2])
            if not heading:
                # The number was set alone in its own column block and its
                # heading is the next one -- reader-instruction pattern (j).
                heading = _detached_heading(blocks, i)
            m = re.match(r"^(\d+)", label)
            if m:
                # Anchor the printed LABEL, not the cut. A cut boundary falls
                # after the previous sentence, so the piece opens with the
                # newline and spaces that separate the two printed rows; those
                # belong to neither. Skipping them makes the offset the exact
                # character index of the label a reviewer sees on the page.
                out.append((i, int(m.group(1)), label, heading,
                            offset + len(piece) - len(piece.lstrip())))
    return out


def _detached_heading(blocks: list[dict], index: int) -> str:
    """The heading of a number that was set alone in its own column block.

    Reader-instruction pattern (j), "the section number set in its own column":
    the number is one extracted block and its heading is the next, so the two
    are never seen together. A contents row read this way keeps its label and
    loses its heading, and BOTH `parse_contents.score` and
    `_toc_source_entries` require a non-empty heading -- so the row is dropped
    from the promises AND from the stored evidence ledger. The printed row
    leaves the database entirely, and no gap is recorded either, because
    nothing remembers that the document promised anything.

    The Sindh Mental Health Act, 2013 (document 2800) prints its contents in
    two columns and strands rows this way. Page 1:

        block 251349   11.
        block 251350   Admission for treatment.

    Page 2 does the same to `23.` / "Discharge of a detained person found to be
    mentally disordered after assessment." and page 3 to `51.` / "Informed
    consent for research." Sections 11, 23 and 51 exist in the body of that Act
    and carry no heading, because no contents row survived to give them one.

    The guards are what keep this to a stranded column cell. The block must
    print NOTHING but the label and its period; the next block must be on the
    same page, must not itself open a provision, must not be a footnote run,
    must begin like a heading and must be short enough to be one. A block that
    holds a label plus any text of its own is not this defect and is untouched.
    """
    text = blocks[index].get("text") or ""
    if not re.fullmatch(r"\s*\d{1,4}\s*[-–]?\s*[A-Z]{0,3}\s*\.\s*", text):
        return ""
    page = blocks[index].get("page_no")

    def printed_heading(neighbour: int, *, capitalised: bool) -> str:
        if not 0 <= neighbour < len(blocks):
            return ""
        block = blocks[neighbour]
        if block.get("page_no") != page:
            return ""
        candidate = block.get("text") or ""
        if classify(candidate) is not None or _is_footnote_run(candidate.strip()):
            return ""
        heading = _norm(candidate)
        if not heading or len(heading) > 160:
            return ""
        opens = r"[A-Z\"“‘]" if capitalised else r"[A-Za-z\"“‘(]"
        return heading if re.match(opens, heading) else ""

    def label_only(neighbour: int) -> bool:
        if not 0 <= neighbour < len(blocks):
            return False
        return bool(re.fullmatch(r"\s*\d{1,4}\s*[-–]?\s*[A-Z]{0,3}\s*\.\s*",
                                 blocks[neighbour].get("text") or ""))

    # On some pages the extractor emits the heading BEFORE the number it
    # belongs to -- reader-instruction pattern (x), "check the reading order:
    # the item is often extracted before the heading it belongs to". The Sindh
    # Local Government Act (document 4369) prints page 7 as
    #
    #     block 705072   110.   Approval of Budgets.
    #     block 705073   Accounts.
    #     block 705074   111.
    #     block 705075   Composition of Provincial Finance Commission.
    #
    # where "Accounts." is section 111's heading and "Composition of Provincial
    # Finance Commission." is section 112's. Taking the block AFTER the number
    # gives 111 the name of 112, and a citation then renders a live provision
    # under the wrong heading -- which is worse than the gap it replaced.
    #
    # Two things separate that page from the ordinary one. The block above is
    # a heading set CAPITALISED with no number of its own -- an ordinary page
    # has the previous numbered row there, or a lowercase continuation
    # fragment, and both are refused. And the block above must not itself be
    # the heading of a stranded number two blocks up, or a run of stranded
    # rows would shift every heading onto its predecessor; `label_only` two
    # back is what rules that out.
    above = "" if label_only(index - 2) else printed_heading(index - 1,
                                                             capitalised=True)
    return above or printed_heading(index + 1, capitalised=False)


def _section_numbers(blocks: list[dict], *,
                     drop_footnote_runs: bool = True
                     ) -> list[tuple[int, int, str, str]]:
    """(index, number, label, heading) for every block that opens like a section.

    The boundary vote and the hint derivations want one row per section-shaped
    piece and no offset; `_section_number_spans` carries the offset for the
    contents ledger, which has to anchor each printed row separately.
    """
    return [(i, n, label, heading) for i, n, label, heading, _
            in _section_number_spans(blocks,
                                     drop_footnote_runs=drop_footnote_runs)]


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


# --------------------------------------------- provincial amendment precedence
#
# A provincial code reprints a rule TWICE under one number: the text as first
# made, then a preamble naming the amendment, then the text that replaced it.
# Punjab Prisons Rules (document 4474) page 44 prints, verbatim:
#
#     Fixing of date of execution.
#     Rule105. In the event of the final orders of Government to carry out
#     executions, the Superintendent shall appoint a day for execution not more
#     than a week later than the date on which such orders actually reach him
#     ...
#     Punjab Amendment:  For rule   105, the following shall be
#     substituted:-
#     Execution of Condemned Prisoners.
#     Rule 105. (i) On receipt of the final orders of the Government to carry
#     out the execution, the Superintendent Jail, shall request the Trial Court
#     concerned to fix a date for the execution of the sentence of death ...
#
# Both prints are siblings labelled 105, so the repeated-label rule below has to
# choose one, and every signal it had was blind to the line between them: both
# prints carry law, both open with an explicit "Rule 105.", the document prints
# no contents list, and source order then handed the citation to the FIRST --
# the text the page itself says was substituted.
#
# Rule 144 is the same device with a sharper edge. Page 60 prints the rule, then
# "Punjab Amendment:", then "Rule144. Omitted by Punjab Notification No. SO
# (Prs.j 18-1/2002, dated 12.1.2002." The omitted text is what stayed citable,
# so the corpus rendered as current law a rule repealed in 2002. Page review
# confirmed the same inversion on rules 105, 144, 255, 260 and 382, and all five
# were adjudicated `restore_citable` against the rendered page. This is INV-5
# failing inside the parser: no `as_of` and no `operative_provision` can be
# right about a date when the tree kept the superseded print.
#
# The printed preamble is the evidence, so the rule is the one the page states:
# where such a preamble separates two prints of one label, the LATER print is
# the law in force.
#
# Vocabulary measured over the corpus, not assumed. Anchored to a line start,
# `<Qualifier> Amendment(s):` occurs 46 times in six documents, and the
# qualifier is one of exactly four words:
#
#     Punjab        37 lines   documents 2844, 3267, 3397, 4397, 4474
#     Sindh          4 lines   document 4498
#     Sind           3 lines   document 3267
#     Baluchistan    2 lines   document 3267
#
# so the device is not Punjab's: document 3267 prints Punjab, Sind and
# Baluchistan amendments to one Act side by side. "N.-W.F.P. Amendment" and any
# Khyber Pakhtunkhwa wording do not occur in this corpus at all -- which is why
# the qualifier is left open rather than enumerated, and why a fifth province
# would cost no edit here. A flattened footnote marker may precede it ("56Punjab
# Amendment:") and the typesetting stretches the words ("Punjab    Amendment:").
# One qualifier word is required: a bare "Amendment:" heads footnote blocks in
# far too many documents to read as this device.
_AMENDMENT_PREAMBLE = re.compile(
    r"^[ \t]*\d{0,3}[ \t]*"
    r"(?:[A-Z][A-Za-z.'-]*[ \t]+){1,3}"
    r"Amendments?[ \t]*:")

# The preamble usually names the unit it replaces -- "For rule   105, the
# following shall be substituted:-", "The    existing   rule    255,    shall
# be) substituted as under:-". When it names one it must be the label in hand.
# Page 187 of the same document prints "Punjab  Amendment:   108In rule  518(i)
# the  scale  of ..." beside sibling labels 2 and 8, and that preamble is
# evidence about rule 518, not about them.
_AMENDMENT_UNIT = re.compile(
    r"\b(?:sub-?)?(?:rules?|sections?|regulations?|articles?|clauses?|"
    r"paragraphs?)\s*(\d+[A-Za-z]?(?:-[A-Za-z0-9]+)?)", re.I)

# An insertion adds a NEW unit. It is not evidence that an earlier print of the
# same number was replaced, so "After rule 545-A, the following rule 545-B shall
# be inserted:-" must not move anything.
_AMENDMENT_INSERTS = re.compile(r"\b(?:insert|add)(?:ed|ition|s)?\b", re.I)
_AMENDMENT_REPLACES = re.compile(r"\b(?:substitut|omit|delet|repeal)", re.I)

# The later print must be IDENTIFIED as that unit by the source, either because
# the preamble names the number or because the print reproduces the unit word
# with it. Without this the rule inverts a document it has no business in: the
# West Pakistan Opium Rules (document 3267) print rule 2 on page 2, then on page
# 3 "PROVINCIAL AMENDMENTS:", "Sind Amendment:1. In rule 2-Cls. (f) and (g) have
# been subs. ...", "Punjab Amendment: Cl. (f) has been subs. By Notification No.
# 64/75/43/Ex-II-(P) ... as under :", the replacement clause (f), and then
#
#     2.  Throughout the rule for the words "Boards of Revenue" wherever
#     occurring, the word "Commissioner" shall be substituted". ]
#
# That "2." is item 2 of the amending notification's own instructions, not a
# reprint of rule 2 -- the preamble names a clause, not a rule -- and moving the
# citation of rule 2 onto it would replace a definitions rule with a drafting
# instruction. Every one of the five confirmed Punjab Prisons cases clears this:
# each reprint opens "Rule105." / "Rule 105." / "Rule144." / "Rule255." /
# "Rule260." / "Rule382.", and rules 105 and 255 are named by the preamble too.
#
# Line-anchored rather than block-anchored, and bounded to the block's opening,
# because a fused marginal heading can precede the number in the same block:
# page 145 prints rule 382's replacement as "Report of previous convictions.\n
# \nRule382. (i) The Superintendent of Police shall invariably inform ...". A
# block-anchored test dropped exactly that rule, whose replacement carries a
# sub-rule (ii) the pre-amendment text does not have.
_AMENDMENT_REPRINT = (r"(?:^|\n)[ \t]*"
                      r"(?:Sections?|Rules?|Regulations?|Articles?)[ \t]*{}\b")

# How many blocks before a print may hold its preamble. The device sets the
# replacement directly beneath the preamble; the widest confirmed case is rule
# 255, where one marginal heading ("More Furniture") sits between them. Three is
# that plus one. A wider window lets a preamble belonging to another rule reach
# across a page break and decide a collision it has nothing to do with.
_AMENDMENT_WINDOW = 3


def _twocol_run_spans(
        blocks: list[dict],
        dotted: set[str] | None = None) -> list[tuple[int, int, str, str, int]]:
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
    hits: list[tuple[int, int, str, str, int]] = []
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
                # The NUMBER's start, not the match's: `_TWOCOL` opens on a line
                # break, so `m.start()` points at the newline that ends the
                # previous printed row and two adjacent rows could tie.
                hits.append((i, int(n.group(1)), label, _norm(head),
                             m.start(1)))

    def order_key(value: str) -> tuple[int, str]:
        match = re.match(
            r"^(\d{1,4})(?:\s*[-\u2013]?\s*([A-Z]{1,3}))?$",
            value.replace(" ", ""),
            re.I,
        )
        return ((int(match.group(1)), (match.group(2) or "").casefold())
                if match else (-1, ""))

    best: list[tuple[int, int, str, str, int]] = []
    run: list[tuple[int, int, str, str, int]] = []
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
    placeholders = {lbl for _, _, lbl, head, _ in best
                    if _DISPOSITION_ROW.match(head)}
    labels = {lbl for _, _, lbl, _, _ in best} - placeholders
    if not labels or len(labels & dotted) / len(labels) < _TWOCOL_MIN_CORROBORATION:
        return []
    return best


def _twocol_run(blocks: list[dict],
                dotted: set[str] | None = None) -> list[tuple[int, int, str, str]]:
    """`_twocol_run_spans` without the offsets, for the boundary vote."""
    return [(i, n, label, heading) for i, n, label, heading, _
            in _twocol_run_spans(blocks, dotted)]


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
    #
    # Bounding that prefix at the FIRST opener is too tight, because a spurious
    # opener before the marker hides it. The Khyber Pakhtunkhwa Bus Stand and
    # Traffic Control (Peshawar) Ordinance 1975 prints
    #
    #     block 2   1975. 2[KHYBER PAKHTUNKHWA]
    #     block 4   [24th January, 1975] CONTENTS.
    #
    # so the YEAR is read as section 1975, `marker_end` becomes 3, and the
    # marker at block 4 is never seen. Its contents list of 13 entries is then
    # parsed as body, its rows are built as sections, and every real section
    # collides with one -- the document holds 13 sections and 0 contents
    # entries, and one of its S7 collisions was read on the page and found
    # inverted.
    #
    # Widening the bound to the whole first PAGE was tried and measured over
    # all 4,596 documents: 9 moved, and it destroyed real law in three of them
    # -- document 3087 lost "14. Action by the Government", "15. Traveling
    # allowance", "16. Seniority" and "17. Repeal"; document 4472 lost five
    # sections including "3. Establishment of Board of Trustees". A whole page
    # of licence is enough for a numbered front table to be read as contents.
    #
    # So bound it past the spurious opener only, and only when that opener is a
    # YEAR. A four-digit year in a masthead is never a section number, and it
    # is what actually hides the marker here. Sections 3087, 3532 and 4472 open
    # on ordinary labels, so their bound does not move at all.
    def _is_year(label: str | None) -> bool:
        return bool(re.fullmatch(r"(?:1[89]\d{2}|20\d{2})", (label or "").strip()))

    first_real = next((i for i, (_, _, lbl, _) in enumerate(nums)
                       if not _is_year(lbl)), 0)
    marker_end = min(len(blocks), nums[first_real][0] + 1)
    saw_marker = any(_has_contents_marker(b["text"])
                     for b in blocks[:marker_end])
    # A title year printed BEFORE an explicit opening CONTENTS marker is
    # masthead evidence, not a listed section (doc 02 §5.1–5.2). Keep the block
    # and the numbering candidates, but do not import that year into the TOC
    # promises. Do not use the weaker "SECTIONS" column header here, or discard
    # four-digit labels inside the actual list/body. Document 1224's title
    # "1975. 2[KHYBER PAKHTUNKHWA]" used to create a fictitious section 1975.
    contents_start = max(
        (i for i, block in enumerate(blocks[:marker_end])
         if any(_CONTENTS.match(line) for line in block["text"].splitlines())),
        default=0,
    )

    # An explicit printed CONTENTS marker is direct evidence that a list exists;
    # the peak gate above exists only to stop one being INVENTED where there is
    # none. It also measures the LEADING INTEGER (`_section_numbers` takes
    # `^(\d+)`), which never rises for a dotted-decimal contents -- 1., 1.1.,
    # 1.2.1., 2.10.2.2. -- so a document that prints its marker in capitals can
    # be refused for want of a peak it cannot reach.
    #
    # Document 2324 prints CONTENTS on page 1 and lists 45 entries, but probes
    # as peak=4 against peak_needed=8, so no contents list is found at all and
    # its own contents rows become the citable sections: label 1 is kept as
    # `1 APPOINTMENT AND PROMOTION 1.1 .1. GENERAL INTRODUCTION` while the real
    # `1 APPOINTMENTS AND PROMOTIONS:- The University's policy on appointments`
    # is demoted beneath it. Measured: documents 2324, 2508 and 2603, 43 pending
    # S7 rows. Nothing else moves, because the gate only binds where
    # peak < peak_needed.
    #
    # Only the gate is relaxed. The agreement floor (_TOC_MIN_AGREEMENT), the
    # upside-down guard, opens_at_first_section and heading corroboration all
    # still run, so a contents list still has to prove itself.
    if saw_marker:
        peak_needed = 2

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
            if idx < contents_start and _is_year(label):
                continue
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
        # Use the SAME label reconciliation as score(). Comparing an exact
        # intersection here with score's repaired-label overlap can reject an
        # earlier boundary even when it retains every later body label.
        matched, _ = _reconcile_label_sets(set(best_toc), body_labels)
        return len(matched) / max(len(best_toc), 1)

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
        # A closed disposition placeholder promises no operative opening
        # section. Retain it in the TOC ledger, but do not wait for it to
        # corroborate a body boundary (3353 prints 2A [Repealed.]). Longer
        # headings about repealing another Act are NOT placeholders.
        operative = [key for key, heading in best_toc.items()
                     if not re.fullmatch(
                         r'\s*\[\s*(?:Repealed|Omitted|Deleted)\s*\.?\s*\]\s*\.?\s*',
                         heading, re.I)]
        if len(operative) != len(best_toc) and len(operative) < 3:
            return False
        needed = min(5, len(operative))
        promised = operative[:needed]
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
            if not is_match and key == promised[0]:
                # Some opening sections have a compound administrative TOC
                # heading, while the margin prints only two components:
                # "Short title. Commencement. Local extent." versus
                # "Short title Commencement." on 3353 page 6. This concession
                # applies only to that opening-heading vocabulary; two other
                # ordered source headings must still corroborate the boundary.
                components = [part.strip() for part in wanted.split('.')
                              if part.strip()]
                allowed = {'short title', 'commencement', 'extent', 'local extent'}
                if (len(operative) >= 3
                        and len(components) >= 2 and components[0] == 'short title'
                        and len(set(components)) == len(components)
                        and set(components) <= allowed):
                    is_match = any(
                        all(re.search(r'(?<!\w)' + re.escape(part) + r'(?!\w)', candidate)
                            for part in components[:2])
                        for candidate in actuals)
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
    # Enactment/title evidence above can replace the numeric candidate. Rebuild
    # BOTH the promises and their score from that final split: retaining the
    # old candidate's map imports later schedule items into the Act's contents
    # even though their blocks are beyond the boundary (docs 1438 and 2581).
    # The source-entry ledger already uses best_idx, so an unrecomputed map
    # creates run-only gaps with no printed contents entry behind them.
    best_score, best_toc = score(best_idx)
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


@functools.lru_cache(maxsize=8)
def _footnote_run_block_ids(page_key: tuple) -> frozenset:
    """Indices belonging to a page-level numbered footnote run.

    `page_key` is a tuple of (index, page_no, first_line) triples, so the result
    can be memoised per block list without hashing the blocks themselves.
    """
    by_page: dict = {}
    for idx, page_no, text in page_key:
        by_page.setdefault(page_no, []).append((idx, text))
    out: set = set()
    for rows in by_page.values():
        run: list = []

        def flush(run):
            if len(run) < 3:
                return
            provenance = sum(1 for _, t in run if _FOOTNOTE.match(t))
            if provenance * 2 >= len(run):
                out.update(i for i, _ in run)

        last = None
        for idx, text in rows:
            m = re.match(r"^\s*(\d{1,3})\s*[.)]", text)
            if m and (last is None or int(m.group(1)) > last):
                run.append((idx, text))
                last = int(m.group(1))
            else:
                flush(run)
                run, last = [], None
        flush(run)
    return frozenset(out)


def _footnote_run_blocks(blocks: list[dict]) -> frozenset:
    key = tuple((i, b.get("page_no"), (b.get("text") or "")[:120])
                for i, b in enumerate(blocks))
    return _footnote_run_block_ids(key)


def _toc_source_entries(blocks: list[dict], boundary: int,
                        toc: dict[str, str]) -> list[dict]:
    """Return every parsed printed entry with its page/block evidence.

    ``toc`` remains a label map because it is useful for heading repair during
    the body walk. It cannot, however, be the stored ground-truth object: a dict
    silently overwrites repeated printed labels. This ordered ledger preserves
    each occurrence and points back to the immutable extracted block, whose
    text and bounding box remain the exact evidence.
    """
    dotted = _section_number_spans(blocks)
    twocol = _twocol_run_spans(blocks, {label for _, _, label, _, _ in dotted})
    # A contents list may cite subprovisions directly (``4(1). Heading``).
    # Keep that printed citation intact in the evidence ledger; the body
    # grammar still parses section 4 and subsection (1) separately.
    compound: list[tuple[int, int, str, str, int]] = []
    for idx, block in enumerate(blocks[:boundary]):
        for offset, piece in subdivide_spans(block["text"]):
            match = re.match(
                r"^\s*(\d{1,4})\s*\(\s*(\d{1,3}[A-Z]?)\s*\)"
                r"\s*\.\s*(.+)$", piece, re.S,
            )
            if match:
                compound.append((
                    idx, int(match.group(1)),
                    f"{match.group(1)}({match.group(2)})",
                    _norm(match.group(3)),
                    offset + match.start(1),
                ))
    # Sorting on the block index ALONE was a silent mis-ordering wherever a
    # block held more than one printed row. `sorted` is stable, so every dotted
    # hit in a block came before every two-column hit in that same block, and
    # both came before every compound hit -- printed order only by luck. That
    # order is not cosmetic: `ordinal` is the printed position stored in
    # `instrument_toc_entry`, and the order-bounded recovery below
    # ("label_order", and the disposition neighbour search) reads adjacency out
    # of this list to decide which body node an unresolved row can be. The
    # character offset is what makes the order the page's own.
    candidates = sorted(dotted + twocol + compound,
                        key=lambda h: (h[0], h[4]))
    out: list[dict] = []
    # Deliberately the same key as before the offset existed -- block, label and
    # heading, WITHOUT the offset. Adding the offset here would admit a row that
    # the dotted and two-column readers both found at slightly different
    # character positions, and this change is an anchoring change: the set of
    # entries it produces is unchanged and only their evidence and order move.
    seen: set[tuple[int, str, str]] = set()
    for idx, _, label, heading, char_offset in candidates:
        if idx >= boundary:
            break
        block = blocks[idx]
        if _is_furniture(
                block["text"], block.get("y0", 0),
                block.get("page_height", 792) or 792,
        ):
            continue
        # A numbered footnote run is not a contents list, and nothing here stops
        # one. `_is_furniture` is given `block.get("page_height", 792)`, but
        # stored blocks often carry no page height, so every page is assumed to
        # be 792pt and the bottom-margin test misses the real page bottom --
        # measured on documents 1918, 2846, 3788 and 3970 it rejected NONE of
        # their phantom entries. `_is_footnote_run` does not fire either,
        # because it needs three numbered lines in ONE block and these arrive
        # one line per block.
        #
        # Document 1918's printed contents is page 1 alone, twelve entries, and
        # the extractor manufactured sixteen more -- eleven of them the numbered
        # footnote lines at the foot of page 2: "9. Ins. ibid.",
        # '6. Subs. by the A.O., 1937, for "the G. in C.".',
        # "7. No Notification has been issued so far." One of those phantoms is
        # LINKED to a provision while the genuine printed row "Local extent." is
        # left as a gap, so this both inflates the queue and mis-serves a
        # citation.
        #
        # The run shape alone cannot be the test: a genuine contents list is
        # also consecutive ascending numbered blocks. What separates them is the
        # vocabulary -- a footnote run carries amendment provenance and a
        # contents list carries headings. So the test is a run of three or more
        # consecutive numbered blocks on one page, ascending, of which at least
        # half open with `_FOOTNOTE` provenance. On 1918's page 2 that is eleven
        # blocks numbered 1 to 11 with eight matching; on a contents page it is
        # zero matching and the run is not claimed.
        if idx in _footnote_run_blocks(blocks):
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
            "source_char_offset": char_offset,
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
    # A dot before an alphabetic insertion suffix is typography (TOC5.A/body
    #5-A in1927), unlike numeric hierarchy 5.1. Preserve source labels and
    # accept equivalence only through the callers' ambiguity-safe buckets.
    key = re.sub(r"^(\d{1,4})\.([a-z]{1,3})$", r"\1\2", key)
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
    def derive(numbers: list[tuple[int, int, str, str]]
               ) -> tuple[dict[str, str], int]:
        if not numbers:
            return {}, 0
        first_number = numbers[0][0]
        markers = [index for index, block in enumerate(blocks[:first_number + 1])
                   if _has_contents_marker(block["text"])]
        if not markers:
            return {}, 0
        marker = markers[-1]
        formula = next((index for index, block
                        in enumerate(blocks[marker + 1:], marker + 1)
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

    # The boundary here is a REPEAT in the numbering -- the body restating a
    # label the contents already listed -- so dropping footnote runs can remove
    # the very repeat it rests on, and this would then return nothing at all,
    # taking the marginal-note splitting `parse_contents` depends on with it.
    #
    # Derive both ways and keep the earlier floor: excluding apparatus must
    # never make the body region smaller. A floor that is too early only
    # narrows the contents hints; a floor that is too late buries law.
    #
    # This is a guard, not a demonstrated repair. Bisecting the call sites
    # showed every measured difference between the two parsers flows through
    # `parse_contents`, not through here, so on the documents checked this
    # branch changes nothing. It is kept because the failure it prevents --
    # returning no boundary where one is available -- is silent and costs
    # sections, and the cost of the guard is one extra pass over the blocks.
    strict_hints, strict_floor = derive(_section_numbers(blocks))
    loose_hints, loose_floor = derive(
        _section_numbers(blocks, drop_footnote_runs=False))
    if strict_floor and (not loose_floor or strict_floor <= loose_floor):
        return strict_hints, strict_floor
    return loose_hints, loose_floor


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
    #
    # This set is a GUARD against splitting, not evidence of law, so it takes
    # the unfiltered numbering. Dropping footnote runs here shrinks it, more
    # labels read as unresolved, and the geometry splitter fires more often --
    # the exact direction the paragraph above warns about. A guard should be
    # maximally willing to say "already reconciled": being wrong there costs a
    # missed split, being wrong the other way costs sections.
    body_labels = {
        _repair_label(label, toc, actual_heading=heading).replace(" ", "")
        for _index, _number, label, heading
        in _section_numbers(blocks[body_floor:], drop_footnote_runs=False)
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


def _detached_schedule_reference(heading: str, following: str) -> bool:
    """A standalone display heading followed by its exact statutory reference.

    Commercial Documents Evidence Act, doc 1438 p3: THE SCHEDULE and
    (See sections 2 and 3) are separate PDF blocks. Neither line is a prose
    reference carried over from the preceding page's amendment apparatus.
    Callers also require same-page adjacency (doc 02 §5.1).
    """
    return bool(
        re.fullmatch(r"(?:THE\s+)?SCHEDULE", heading.strip())
        and re.fullmatch(
            r"[\[(]\s*(?:See\s+)?sections?\s+\d{1,4}[A-Z]?"
            r"(?:\s*(?:,|and)\s*\d{1,4}[A-Z]?)*\s*[\])]",
            following.strip(), re.I,
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
    # The amendment prefix belongs on this rule too -- reader-instruction
    # pattern (u), "a label inside the bracket with no period". Document 4451
    # prints three of its thirteen lost sections that way:
    #
    #     10[83C  Cargo Tracking System and e-Bilty mechanism.- (1) Any person
    #     2[193 Appeals to Collector (Appeals).-  60[ (1) Any person including
    #     4[5
    #     “Delegation of powers.- 5,24(1) The Board may, by notification
    #
    # The prefix can match empty, so no block that matched before stops
    # matching, and the contents corroboration below is unchanged: this widens
    # what the rule can SEE, not what it will accept on its own authority.
    periodless = re.match(r"^\s*" + _AMEND_PREFIX
                          + r"(\d{1,4}(?:\s*-\s*[A-Za-z0-9]{1,3}|[A-Z]{1,3})?)"
                          r"\s+(\S.*)$", text, re.S)
    if periodless:
        label = _norm(periodless.group(1)).replace(" ", "")
        rest = periodless.group(2)
        # The heading is the first corroboration, and it is not always in the
        # block. The Karachi Metropolitan Transport Authority Ordinance prints
        #
        #     26        The Chairman, Managing Director, Members, Secretary ...
        #
        # with no period, while 23., 24., 25. and 27. all have one, and its
        # heading sits in the RIGHT margin sharing a block with section 25's.
        # Nothing in the block can match "Public Servant.".
        #
        # The contents' own ORDER can vouch for it instead: this label is
        # promised, has not been seen, and the label before it in the printed
        # contents HAS been seen -- the body has just delivered 25 and this
        # block opens with 26. That is the same ordered evidence
        # `_toc_label_is_next` already licenses elsewhere.
        #
        # The length floor is what keeps a page footer out: "26 | P a g e" is
        # equally "next" and carries no provision.
        # Accepting this on the contents' ORDER instead of its heading -- label
        # promised, unseen, predecessor seen, with a length floor to exclude
        # page footers -- was tried and measured out. Together with the inline
        # note loosening below it moved 192 documents and cost 226 new
        # demotions against 23 recovered contents rows: a periodless number that
        # merely comes next matches far too much, and every false section it
        # creates collides with a real label. The heading has to be the test.
        # The heading may be printed inside a quotation, because a substituted
        # section is quoted whole in the amending instrument: document 4451
        # page 35 prints `4[5 “Delegation of powers.-`. The quote is
        # typography of the amendment, so it must not defeat the corroboration.
        # `rest` is returned untouched, so nothing printed is dropped.
        if label in toc and _heading_supports(
                rest.lstrip(" \t\n“”‘’\"'"), toc[label]):
            return "section", label, rest

    # The number fused straight onto its FIRST subsection, with the period
    # after the bracket instead of after the number:
    #
    #     23(1). Unless a work is of urgent nature is to be executed through
    #     23 (1) Unless a work is of urgent nature ...
    #
    # against the ordinary "24.(1) Every work executed whether departmentally"
    # on the same page, which classify() reads correctly. The Coastal
    # Development Authority Rules print both, three lines apart.
    #
    # This was found by reading, not by aggregate. Rule 23 was one of only
    # seven gaps in the whole queue that `review_absent_sections` proposed as
    # absent from the source -- both of its machine checks passed, because the
    # heading is not in the body and "23" never opens a block in the form the
    # grammar recognises. The page shows the rule printed in full. Recording
    # that gap as `absent_in_source` would have been a lie, and the check that
    # would have licensed it is exactly this blind spot.
    #
    # The guard is narrow because "23(1)" is also how a cross-reference is
    # written. Require the subsection to be (1) -- a section opens at its
    # first, never its fourth -- the match at the very start of the block, and
    # the label one the contents promises.
    #
    # It is narrower still: NO space before the bracket and a period after it,
    # which is the form read off the page. The looser "3 (1) There shall be"
    # was measured over 4,596 documents and moved 18, gaining 5 real sections
    # and losing none -- but one of the five was document 2452 page 21, "3 (1)
    # There shall be a Dean for each Faculty", which is paragraph 3(1) of an
    # appended Statute, not section 3 of the Act. It collided with the real
    # section 3 and cost that released expression its contents link.
    #
    # Spacing is not what separates those: "8 (1) Government may appoint any
    # Prosecutor" is a real section too. What separates them is that 2452's
    # match sits deep in a document whose numbering has restarted, and this
    # rule cannot see that -- `_classify_body` judges one block at a time. The
    # spaced form is left for whatever fixes the restart problem generally;
    # taking only the unambiguous form costs three recoveries and no
    # regressions, and that is the trade this file has taken all along.
    fused_sub = re.match(r"^\s*(\d{1,4}(?:-[A-Za-z0-9]{1,3}|[A-Z]{1,3})?)"
                         r"\(\s*1\s*\)\s*\.\s*(\S.*)$", text, re.S)
    if fused_sub:
        label = _norm(fused_sub.group(1)).replace(" ", "")
        if label in toc:
            return "section", label, "(1) " + fused_sub.group(2)

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
    # The period after the number is OPTIONAL here, and the prefix is matched
    # suffix-tolerantly, because those two defects co-occur. The Karachi
    # Metropolitan Transport Authority Ordinance, 1999 prints
    #
    #     Liabilities of Member Public servants. 26  The Chairman, Managing
    #     Director, Members, Secretary, Officers and Members of Staff ...
    #
    # -- a right-margin note fused ahead of a periodless number, where 23., 24.,
    # 25. and 27. on the same page all carry periods. The contents promises
    # "Public Servant." while the printed note reads "Liabilities of Member
    # Public servants.", sharing its tail and not its head, because that one
    # note covers sections 25 and 26 together.
    #
    # The contents still decides it, and both halves must agree: the label is
    # promised, and some TRAILING part of the printed note supports the heading
    # promised for that label. Suffix tolerance is safe here and was measured
    # unsafe in the two promotion guards -- this rule reads a block the grammar
    # already refused, while those invent a section from a printed subsection.
    # Newlines are allowed INSIDE the note. A marginal column is set narrow, so
    # the extractor wraps it: this one arrives as "Liabilities\nof\nMember\n
    # Public\nservants." and a pattern that forbade newlines could not see it at
    # all. The 60-character bound is what keeps the prefix from swallowing prose.
    inline_note = re.match(
        r"^([^\d][\s\S]{2,60}?)\s+(\d{1,4}[A-Za-z-]{0,3})\s*\.?\s+(\S.*)$",
        text, re.S)
    if inline_note:
        label = _norm(inline_note.group(2)).replace(" ", "")
        if label in toc and _heading_tail_supports(inline_note.group(1),
                                                   toc[label]):
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


_HEADING_OPERATIVE = re.compile(
    r"\b(?:shall|may|must|means?|includes?|is|are|was|were|has|have|had|be|"
    r"been|appl(?:y|ies|ied)|extends?|comes?|whoever|nothing|provided|"
    r"notwithstanding|hereby|subject)\b", re.I)


_NAME_STOP = {
    "the", "of", "a", "an", "and", "or", "to", "for", "in", "on", "by",
    "at", "its", "his", "her", "their", "etc", "not",
}


def _name_tokens(name: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-z0-9]+", (name or "").lower())
        if token not in _NAME_STOP and len(token) > 1
    ]


def _name_initialism_of(short: list[str], long: list[str]) -> bool:
    """Does a short-side token abbreviate consecutive words on the long side?"""
    initials = "".join(word[0] for word in long)
    return any(
        len(token) >= 3 and token not in long and token in initials
        for token in short
    )


def _same_printed_name(first: str, second: str) -> bool:
    """One name printed with truncation, abbreviation, or extraction damage.

    This mirrors the comparison measured by
    ``tools/census_heading_mislabel.py``. Token equality handles names
    truncated at either end; the ratio floor handles common lost-glyph OCR and
    extraction variants without treating unrelated statutory names as equal.
    """
    first_tokens = _name_tokens(first)
    second_tokens = _name_tokens(second)
    if not first_tokens or not second_tokens:
        return False
    short, long = (
        (first_tokens, second_tokens)
        if len(first_tokens) <= len(second_tokens)
        else (second_tokens, first_tokens)
    )
    matched = sum(
        any(
            token == other
            or (
                min(len(token), len(other)) >= 3
                and (
                    token in other
                    or other in token
                )
            )
            or (
                len(token) >= 4
                and len(other) >= 4
                and SequenceMatcher(None, token, other).ratio() >= 0.8
            )
            for other in long
        )
        for token in short
    )
    # Every substantive token on the shorter side must be accounted for. An
    # 80% aggregate admitted real one-word changes such as ``Application`` /
    # ``Appointment`` merely because four surrounding words agreed.
    if matched == len(short):
        return True
    return _name_initialism_of(short, long) and matched / len(short) >= 0.5


def _names_another_section(own_text: str, promised: str | None) -> bool:
    """Does this unit's OWN text already name something other than `promised`?

    A marginal-note layout prints the number and the enacted words in one
    column and the heading in another, so the unit's own text is operative and
    names nothing -- the contents entry is then the only heading source there
    is, and copying it is right.  A unit whose own text opens with a short
    nominal phrase has already been named by the source, and that name wins.
    Doc 4139's Third Schedule row prints "Administrative Officer" while the
    First Schedule -- which the parser read as the contents list -- calls row 3
    "Research Officer"; the schedules number their rows differently and the
    copy renamed thirty-four rows.
    """
    if not promised:
        return False
    flat = _norm(own_text or "")
    head = flat.split(".")[0].strip(" \u2014-")
    if not (2 <= len(head.split()) <= 12) or len(head) > 90:
        return False
    if _HEADING_OPERATIVE.search(head):
        return False
    key = re.sub(r"[^a-z0-9]", "", head.lower())
    want = re.sub(r"[^a-z0-9]", "", promised.lower())
    if len(key) < 10 or len(want) < 10:
        return False
    # Keep the compact-prefix equivalence: it correctly joins extraction-split
    # words (``Commis sioner``), hyphen variants and collapsed spacing. Add the
    # corpus-measured token comparison for lost glyphs such as ``In trument`` /
    # ``Instruments``. Replacing the prefix rule outright regressed 16 real
    # headings in a 13,159-call corpus trace.
    prefix_same = key.startswith(want) or want.startswith(key)
    return not (prefix_same or _same_printed_name(head, promised))


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
        #
        # It does not authorize discarding the name the body prints either.
        # Where the printed contents runs at an offset to the body -- doc 4499
        # lists "Penalty for obstructing inspector" at 36 while p.30 prints it
        # at 37 -- returning nothing here left the section headingless, and the
        # entry linker then pasted the contents name for THIS number onto it.
        # Fall through to the rule that applies when there is no contents list
        # at all, whose first branch requires enacted text after the name, so a
        # bare schedule row is still not named from its own words.
        m = re.match(r"^(.{4,110}?)\.\s+(?=[A-Z(])", _norm(body))
        if m:
            return _norm(m.group(1)), _norm(body[m.end():])
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


def _reviewed_label_key(label: str) -> str:
    """The typography-free form of a printed label, for decision lookup.

    Whitespace and case are typography in this position; nothing else is
    stripped, dots included, because ``12.1`` and ``121`` are different units.
    This is the Python half of the durable key -- the SQL half lives in
    `legal_write.structural_resolutions_for` and must agree with it.
    """
    return re.sub(r"\s+", "", label or "").casefold()


def _reviewed_structure_index(resolutions: list[dict] | None) -> dict:
    """(source block, printed label) -> a source-reviewed S7 resolution.

    A candidate id is regenerated by every replay and cannot anchor a reading
    across one; the source block survives re-segmentation.  The caller has
    already restricted the rows to one document, so block plus printed label is
    what identifies the unit here.  Rows carrying no block cannot be anchored
    and are dropped rather than guessed at.
    """
    index: dict[tuple, str] = {}
    for row in resolutions or []:
        block = row.get("source_block_id")
        if block is None:
            continue
        index[(block, _reviewed_label_key(row.get("printed_label")))] = (
            row.get("resolution"))
    return index


def segment(blocks: list[dict], curation_patches: list[dict] | None = None,
            toc_dispositions: list[dict] | None = None,
            split_fused_margins: bool = False,
            detect_contents: bool = True,
            force_opening_contents: bool = False,
            structural_resolutions: list[dict] | None = None,
            structural_overrides: dict | None = None) -> Segmentation:
    """Build the provision tree.

    `blocks` are dicts with text, page_no, y0, page_height and id, in reading
    order -- exactly what text_block stores.
    """
    original_blocks = blocks
    overrides = structural_overrides or {}
    reviewed_structure = _reviewed_structure_index(structural_resolutions)
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
    # A printed auxiliary division heading the contents region swallowed.
    # `parse_contents` can only cut at a numbered unit, so where a document
    # prints its preamble, its enacting formula and THE SCHEDULE between the
    # last contents entry and the first fall back to 1, all of that is filed as
    # contents.  Document 4089 is the case: pages 3 to 5 of the Sindh
    # Universities and Institutes Laws (Amendment) Act 2025 -- its preamble,
    # both of its own sections and its schedule heading -- carry role='contents'
    # and are attached to no provision, and because the SCHEDULE never opens the
    # schedule's rows become top-level sections that collide.  Restoring the
    # heading is what makes them rows again.
    moved_boundary = overrides.get("contents_boundary_block")
    if moved_boundary is not None:
        moved = next((i for i, block in enumerate(blocks)
                      if block.get("id") == moved_boundary), None)
        if moved is not None and 0 <= moved < boundary:
            boundary = moved
    # A contents list printed AFTER the body.  Document 3079's last page is
    # headed C O N T E N T and prints rules 1 to 20; the walk read it as a
    # second body and produced twenty collisions with the rules it summarises.
    # The region is cut off the END of the body and then used the way any
    # contents list is used -- boundary, heading source, acceptance test (doc
    # 02 §5).
    trailing_contents = overrides.get("trailing_contents_block")
    trailing_cut = None
    if trailing_contents is not None:
        trailing_cut = next((i for i, block in enumerate(blocks)
                             if block.get("id") == trailing_contents), None)
    if trailing_cut is not None and trailing_cut > boundary:
        region = blocks[trailing_cut:]
        trailing_toc: dict[str, str] = {}
        for _, _, label, heading in _section_numbers(region):
            if heading and label not in trailing_toc:
                trailing_toc[label] = heading
        if trailing_toc:
            toc, toc_found, boundary = trailing_toc, True, 0
            printed_toc = _toc_source_entries(region, len(region), toc)
        else:
            trailing_cut = None
    else:
        trailing_cut = None
    if trailing_cut is None:
        printed_toc = _toc_source_entries(
            blocks, boundary, toc) if toc_found else []
    body = (blocks[boundary:trailing_cut]
            if (boundary or trailing_cut is not None) else blocks)
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
    contents_proved_rows: set = set()
    schedule_node: Node | None = None
    explicit_table_owner: Node | None = None
    roman_section_division_seen = False
    roman_section_division_nodes: list[Node] = []
    max_before_schedule = 0     # highest section number seen when a schedule opened
    max_prefixed_rule_before_schedule = 0
    detached_heading_bodies_merged = 0
    nested_list_items_reparented = 0
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
    _x1s = sorted(float(block["x1"]) for block in body
                  if block.get("x1") is not None)
    body_column_left = _column_edge(_x0s, 0.10)
    body_column_right = _column_edge(_x1s, 0.90)
    roman_display_candidates: list = []
    for block in body:
        block_id = block.get("id")
        if block_id is None:
            continue
        found = _roman_display_heading(block["text"])
        if found is None or len(subdivide(block["text"])) != 1:
            continue
        if _centred_in_body_column(block, body_column_left, body_column_right):
            roman_display_candidates.append((block_id, found))
    promoted_roman_parts = overrides.get("roman_display_parts") or frozenset()
    roman_display_parts = {
        block_id: found for block_id, found in roman_display_candidates
        if block_id in promoted_roman_parts}

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
    dotted_commencement_operative_units: set[int] = set()
    for b in body:
        # Keep an amendment-footnote block whole.  Subdividing first can see
        # the citation fragment ``s. 2. It was provided ...`` as a new section
        # even though the block's fused superscript and amendment verb prove
        # the whole block is apparatus (CPC pages 65, 66 and 85).
        pieces = ([b["text"]] if (
            (_FOOTNOTE.match(b["text"])
             and not _PARENTHESIZED_CHAPTER.search(b["text"]))
            or _is_footnote_run(b["text"], split_numbers_only=True)
            or _PUNCTUATED_AMENDMENT_FOOTNOTE.match(b["text"])
            or _footnote_markers_only(b["text"])
        ) else subdivide(b["text"]))
        for piece in pieces:
            units.append((b, piece))

    # Does this document number its provisions with compound labels? Counted
    # over the grammar's own decisions rather than guessed, and needing a real
    # run of them: eight compound labels outnumbering the bare ones is a
    # numbering regime, two is a pair of decimal quantities in a rate table.
    # DISTINCT labels on both sides, which is the whole point: a numbering
    # regime keeps producing labels it has not used, while a restarting list
    # reuses one small set. Document 4405 prints 98 distinct compound labels
    # (1.1 ... 9.7) against 14 distinct bare ones ({1..13, 62}) even though the
    # bare openers outnumber the compound ones 107 to 98 -- counting openers
    # would have called it a bare-integer document and demoted nothing. An Act
    # with 50 real sections and an annexure numbered 1.1 to 1.8 goes the other
    # way and is left alone, which is the case this test exists to protect.
    _regime = [found[1].replace(" ", "")
               for _, piece in units
               for found in [classify(piece)]
               if found is not None and found[0] == "section"]
    _compound = {lbl for lbl in _regime if "." in lbl}
    _bare = {lbl for lbl in _regime if lbl.isdigit()}
    compound_section_regime = len(_compound) >= 8 and len(_compound) > len(_bare)

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
                or _is_footnote_run(text, split_numbers_only=True)
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
        forced_part = roman_display_parts.get(b.get("id"))
        c = (("part",) + forced_part if forced_part is not None
             else _classify_body(text, toc, seen, heading_context))
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
                # the schedule-rule promotion above. The heading may sit in the
                # preceding marginal block OR inside this block's own text: the
                # Federal Urdu University Ordinance, 2002 prints
                #
                #     (1) Short title, application and commencement:-- (1) This
                #     Ordinance may be called the Federal Urdu University ...
                #
                # -- section number parenthesised, heading inline, subsection
                # after it. Only `heading_context` was consulted, so a heading
                # printed in the same block could not license the promotion and
                # the Act's section 1 stayed a subsection.
                and (_heading_supports(heading_context,
                                       toc.get(subsection_key))
                     or _heading_supports(rest, toc.get(subsection_key)))):
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
                or (idx + 1 < len(units)
                    and units[idx + 1][0].get("page_no") == b.get("page_no")
                    and _detached_schedule_reference(b["text"], units[idx + 1][1]))
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
            # A short amendment may print no contents at all. Document 16
            # prints section 1(1), an indented "2. It shall come into force at
            # once.", then an aligned section 2 containing the actual amendment.
            # Do not choose between the two 2s by length. The exact commencement
            # sentence, naming subpart, local indentation and immediately next
            # aligned operative opener jointly prove the former's parentage.
            following = units[idx + 1] if idx + 1 < len(units) else None
            following_class = classify(following[1]) if following else None
            first_subpart = next((
                child for child in owner.children
                if child.kind == "subsection" and child.label == "1"
                and child.first_block == owner.first_block
            ), None) if owner is not root else None
            naming_text = owner.text + " " + (first_subpart.text if first_subpart else "")
            unlisted_commencement = bool(
                not toc and owner is not root and owner.label == "1"
                and candidate_key == "2"
                and re.fullmatch(r"\s*It\s+shall\s+come\s+into\s+force\s+at\s+once\s*\.\s*", rest, re.I)
                and re.search(r"\b(?:Act|Ordinance|Rules?|Regulations?)\s+may\s+be\s+called\b", naming_text, re.I)
                and following_class and following_class[0:2] == ("section", "2")
                and re.match(r"\s*In\b.*\b(?:Act|Ordinance|Rules?|Regulations?|Code)\b", following_class[2], re.I | re.S)
                and following[0].get("page_no") == b["page_no"]
                and owner_block is not None
                and following[0].get("x0") is not None
                and owner_block.get("x0") is not None
                and abs(following[0]["x0"] - owner_block["x0"]) <= 6
            )
            # Section 1's own extent and commencement sub-parts, printed with
            # bare numbers. Read as sections they collide with the real sections
            # 2 and 3, and on 17 Sep 2026 that collision was found decided the
            # wrong way round in 26 released instruments: "section 2" answered
            # with the extent sentence while the Definitions section sat demoted
            # beneath it. Unlike the branch above, this one cannot require
            # indentation -- the Pakistan Code sets these sub-parts flush with
            # the body. It requires instead that the sentence be the whole of
            # the block, that the owner be the section naming the instrument,
            # that the number continue section 1's own sub-part sequence, and
            # that the instrument independently show a different section under
            # that number: promised by the contents, or printed again below.
            extent_or_commencement = bool(
                owner is not root and owner.label == "1"
                and candidate_number is not None
                and candidate_number == expected_number
                and _SECTION_ONE_SUBPART.fullmatch(rest)
                and not _SUBPART_FOREIGN_DUTY.search(rest)
                and re.search(
                    r"\b(?:Act|Ordinance|Rules?|Regulations?|Order|Code)\b"
                    r"[^.]{0,80}?\bmay\s+be\s+(?:called|cited)\b",
                    naming_text, re.I)
            )
            if extent_or_commencement:
                # Only once the cheap signals agree is the forward scan for a
                # second printing of this label worth its cost.
                extent_or_commencement = bool(
                    (candidate_key in toc
                     and not _heading_supports(rest, toc.get(candidate_key)))
                    or any(_opens_section(later, candidate_key)
                           for _, later in units[idx + 1:])
                )
            if owner is not root and (
                    ((re.match(r"^\s*\(\s*1\s*\)", owner.text)
                      or (unlisted_commencement and first_subpart is not None))
                     and owner.first_page == b["page_no"]
                     and indented
                     and candidate_number == expected_number
                     and ((candidate_key in toc
                           and not _heading_supports(rest, toc.get(candidate_key)))
                          or unlisted_commencement))
                    or extent_or_commencement):
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
                if unlisted_commencement:
                    dotted_commencement_operative_units.add(idx + 1)
                    # The same physical opening block may contain a wrapped
                    # enacting reference "clause / (1) of Article 128 ...".
                    # Reunite that source text only AFTER this amendment's
                    # opening structure is independently proved; no global
                    # preamble heuristic or source content deletion is needed.
                    preamble = next((
                        n for n in root.children if n.kind == "preamble"
                        and owner.first_block in n.blocks
                        and re.search(r"\bclause\s*$", n.text, re.I)
                    ), None)
                    references = [
                        n for n in root.children if n.kind == "subsection"
                        and n.first_block == owner.first_block
                        and n.blocks == [owner.first_block] and not n.children
                        and re.match(r"^of\s+Article\s+\d+\b", n.text, re.I)
                    ]
                    if preamble is not None and len(references) == 1:
                        reference = references[0]
                        preamble.text_parts.append(f"({reference.label}) {reference.text}")
                        preamble.last_page = reference.last_page
                        root.children.remove(reference)  # derived tree only; its text/blocks survive
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
                # "A schedule cannot contain a section the Act's own contents
                # promises" is sound only where this unit IS that section. In
                # document 4089 the contents numbers thirty amended Acts as its
                # entries 3 to 32 while the schedule's own serial column
                # restarts at 1, so every row's label is a promised label it has
                # nothing to do with: row "1. In section 2 -" is matched against
                # the promise "Short title and Commencement", the schedule
                # closes on its first row, and all thirty entries plus their
                # restarting items become top-level sections.
                if (resumes and overrides.get("corroborate_schedule_exit")
                        and _contradicts_promise(
                            rest, heading_context, toc.get(key), toc, key)):
                    resumes = False
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
            if (not resumes and not toc and schedule_node is not None
                    and key == "1"
                    and re.search(
                        r"\b(?:rules?|regulations?|orders?|scheme|bye[-\s]?laws?)"
                        r"\s+may\s+be\s+(?:called|cited)\b",
                        text + " " + (units[idx + 1][1]
                                      if idx + 1 < len(units) else ""),
                        re.I)):
                # A Gazette notification often promulgates its rules as an
                # ANNEXURE to itself: "...ANNEXURE A PART-I / PRELIMINARY /
                # 1. (1) These rules may be called the Provincial Ombudsman
                # (Employees) Service Rules, 1997." The annexure heading opens
                # auxiliary mode, and with no contents list neither exit above
                # can fire -- the first requires a contents entry, the second a
                # `schedule` node carrying a printed "Rule N" prefix. So every
                # rule of the instrument became a schedule-row clause: document
                # 2754 kept 329 blocks and 0 citable sections, including "No
                # person shall be appointed by initial appointment...".
                #
                # A schedule row never names the instrument. The naming formula
                # at label 1 is therefore proof that the auxiliary was the
                # instrument's own body, and the body resumes here.
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
                # The innermost open container, not merely the top of the
                # stack. Only the FIRST row of a Part ever saw the Part here:
                # once that row is pushed, `stack[-1]` is the row itself, which
                # is not a container kind, so every later row fell back to the
                # schedule, unwound past the Part and became its sibling.
                #
                # The Commercial Documents Evidence Act shows it plainly. Its
                # Schedule prints PART I over twenty-four numbered documents --
                # "1. Lloyd's Register of Shipping.", "2. Lloyd's Daily
                # Shipping Index." and so on -- and the tree held item 1 under
                # Part I with items 2 to 24 beside it, so PART II inherited
                # nothing of its own either.
                row_container = next(
                    (node for node in reversed(stack)
                     if node.kind in (_AUXILIARY_KINDS | {"part", "chapter"})),
                    schedule_node)
                depth = row_container.depth + 1 if row_container else 3
                while stack and stack[-1].depth >= depth:
                    stack.pop()
                parent = stack[-1] if stack else (row_container or root)
                # A numbered row in a schedule table is not a section of the Act.
                # Recording it as one inflates the section count and produces
                # many provisions labelled "1" under one schedule. It is content
                # of the schedule, so it is stored as a clause of it.
                detached_heading = detached_heading_for_body.get(b.get("id"))
                row_kind = "clause"
                if (overrides.get("corroborate_schedule_exit")
                        and _names_a_printed_entry(_norm(rest), toc)):
                    row_kind = "section"
                node = Node(kind=row_kind, label=label,
                            heading=(detached_heading[1]
                                     if detached_heading else None), depth=depth,
                            text_parts=[_norm(rest)] if rest else [],
                            first_page=b["page_no"], last_page=b["page_no"],
                            first_block=b.get("id"), parent=parent)
                if row_kind == "section":
                    contents_proved_rows.add(id(node))
                    # The label coincidence is what proved this row an entry, so
                    # a heading taken from the contents AT THIS LABEL would name
                    # a different enactment than the row's own words: document
                    # 4089's serial 2 would be headed "Amendment of certain
                    # laws." over the text "The University of Karachi Act, 1972".
                    # The printed text is the entry's title; nothing is invented
                    # to sit above it.
                    node.heading = None
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
        # A bare-integer opener that the source shows is not a provision label
        # at this level is an item of a nested list (see the note in the patch
        # that added this). Attach it to the provision currently open, one level
        # down, instead of unwinding to the fixed section depth and colliding
        # with another list's item of the same number.
        #
        # It becomes a clause, which is what it is on the page: a sub-item of
        # the provision that introduces it. Nothing printed leaves the tree --
        # the text, its blocks and its role-ledger entries all move with it --
        # and the citable unit stays the provision the source numbers (9.2,
        # Chapter 3's item 5), so no stored citation can point at it.
        if (kind == "section" and compound_section_regime and not in_schedule
                and not toc and str(label).isdigit()):
            host = next((n for n in reversed(stack)
                         if n.kind in {"section", "article", "subsection"}), None)
            # ...and the provision it would nest under must be one this
            # document numbers compound. Without this the rule reaches into
            # compilations -- the Esta-Code, the PESSI rules -- where a
            # constituent instrument's own sections 1, 2, 3 are bare integers
            # and entirely real, and demotes them. See the patch that added
            # this line for the six printed provisions it was costing.
            # ...and it must actually be NESTED on the page. A compound-labelled
            # host is not enough on its own: document 3509, the University of
            # Sargodha financial rules, prints
            #
            #     3. DEFINITIONS In these rules unless the context otherwise...
            #     4. ACCOUNTS OF THE UNIVERSITY        (4.1, 4.2 indented under it)
            #     6. BUDGET The following procedures will be followed for...
            #
            # at x0 72.0 -- the left margin, the same column as the compound
            # sections around them -- and they are real top-level sections. The
            # rule demoted all eleven. Document 3216 lost seven rubber-test
            # specifications and 3108 six form names the same way; those two were
            # correct outcomes, but a rule that cannot tell them from 3509's
            # definitions section is not deciding anything.
            #
            # Indentation is the evidence the page itself supplies: a nested list
            # item is set in from its host, a peer section is not. Where the
            # geometry is missing the rule stands down, because keeping a
            # section citable is the safe failure and demoting one is not.
            host_block = source_block_by_id.get(host.first_block) if host else None
            host_x0 = (host_block or {}).get("x0")
            this_x0 = b.get("x0")
            indented_under_host = (
                host_x0 is not None and this_x0 is not None
                and float(this_x0) > float(host_x0) + 4)
            if (host is not None and "." in str(host.label)
                    and indented_under_host):
                kind, depth = "clause", host.depth + 1
                nested_list_items_reparented += 1
        # A descriptive statement form printed inside a Schedule's Part is
        # nested there, not a new peer of the Schedule. Companies Ordinance
        # Second Schedule Parts II/III each print "FORM OF STATEMENT ...".
        # Resetting the auxiliary scope to that form makes Part III a child
        # of Part II's form and disconnects it from the Second Schedule.
        # Keep named stand-alone forms (FORM A / FORM II) and forms outside
        # an actual open Schedule on their existing independent scope path.
        actual_schedule = next((n for n in reversed(stack)
                                if n.kind == "schedule"), None)
        host_part = next((n for n in reversed(stack) if n.kind == "part"), None)
        nested_descriptive_form = bool(
            kind == "form" and label == "FORM OF"
            and re.match(r"^\s*STATEMENT\b", rest, re.I)
            and actual_schedule is not None
            and host_part is not None and host_part.parent is actual_schedule
            and re.search(r"FORM\s+OF\s+STATEMENT\b", host_part.heading or "", re.I)
        )
        if nested_descriptive_form:
            depth = host_part.depth + 1
        # A Schedule can itself be divided into Parts. Globally a Part is a
        # top-level instrument division, but within an open schedule the
        # printed Part I/II headings are children of that schedule, not peers
        # that terminate it.
        if kind == "part" and in_schedule and schedule_node is not None:
            # A genuine form may have internal Parts restarting at I. Return
            # to an outer Schedule only when a source-corroborated statement
            # template sits inside its Part and this Part CONTINUES that
            # parent's printed Roman sequence (e.g. II -> III).
            form_parent = schedule_node.parent
            if (schedule_node.kind == "form" and schedule_node.label == "FORM OF"
                    and re.match(r"^\s*STATEMENT\b", schedule_node.heading or "", re.I)
                    and form_parent is not None and form_parent.kind == "part"
                    and form_parent.parent is not None
                    and form_parent.parent.kind == "schedule"
                    and re.search(r"FORM\s+OF\s+STATEMENT\b", form_parent.heading or "", re.I)
                    and _consecutive_roman_parts(form_parent.label, label)):
                schedule_node = form_parent.parent
            depth = schedule_node.depth + 1
        # unwind to this level's parent
        while stack and stack[-1].depth >= depth:
            stack.pop()
        parent = stack[-1] if stack else root

        heading, body_text = (None, _norm(rest))
        source_proven_marginal_note = None
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
            if idx in dotted_commencement_operative_units:
                # This next opener was independently proved to be operative
                # amendment text above. The first-sentence heading heuristic
                # must not turn "In ... Act ... shall be omitted." into a
                # heading and leave only the fused right marginal note as law.
                inferred_heading, inferred_tail = heading, body_text
                heading, body_text = None, _norm(rest)
                if (inferred_heading and inferred_tail
                        and re.search(r"\b(?:shall|may|must)\b", inferred_heading, re.I)
                        and re.match(r"^(?:Amendment|Omission|Insertion|Substitution|Addition|Repeal)\s+of\b", inferred_tail, re.I)
                        and len(inferred_tail.split()) <= 20
                        and not re.search(r"\b(?:shall|may|must|means)\b", inferred_tail, re.I)):
                    # Both source spans remain anchored to the unchanged block;
                    # the marginal note has its own existing schema field.
                    heading = inferred_tail.rstrip(".")
                    source_proven_marginal_note = inferred_tail
                    body_text = inferred_heading + "."
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
        marginal_note = source_proven_marginal_note
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
    # A contents list printed after the body is still apparatus, and its blocks
    # are still characters the PDF prints. Give them the role the front-matter
    # list gets rather than letting them fall to 'unassigned'.
    for b in (blocks[trailing_cut:] if trailing_cut is not None else []):
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
        if (node.kind in {"section", "article"} and beneath_schedule(node)
                and id(node) not in contents_proved_rows):
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
    # Which print an amendment preamble introduces (see the note above
    # _AMENDMENT_PREAMBLE). `body` is the ordered body block list, so "between
    # the two prints" is a window over block positions and not a page guess.
    body_position = {block.get("id"): i for i, block in enumerate(body)}

    def amendment_preamble_before(node: Node) -> tuple[int, str] | None:
        """Block position and text of the preamble that introduces `node`.

        Reads only the blocks immediately before the node's own first block --
        including, as rules 105, 144 and 260 need, the tail of the block the
        earlier print starts in, because this device prints the preamble as the
        last lines of the very rule it replaces.
        """
        end = body_position.get(node.first_block)
        if end is None:
            return None
        for pos in range(end - 1, max(-1, end - 1 - _AMENDMENT_WINDOW), -1):
            text = body[pos].get("text") or ""
            offset, hit = 0, None
            for line in text.split("\n"):
                if _AMENDMENT_PREAMBLE.match(line):
                    hit = offset
                offset += len(line) + 1
            if hit is None:
                continue
            tail = text[hit:hit + 240]
            if (_AMENDMENT_INSERTS.search(tail)
                    and not _AMENDMENT_REPLACES.search(tail)):
                return None
            label = str(node.label).replace(" ", "")
            named = _AMENDMENT_UNIT.search(tail)
            if named and named.group(1).casefold() != label.casefold():
                return None
            own = source_block_by_id.get(node.first_block) or {}
            reprint = re.search(_AMENDMENT_REPRINT.format(re.escape(label)),
                                (own.get("text") or "")[:300], re.I)
            if not named and not reprint:
                return None
            return pos, " ".join(tail.split())[:200]
        return None

    repeated_labels_demoted = 0
    repeated_label_decisions: list[dict] = []
    reviews_enacted: list[dict] = []
    reviews_refused: list[dict] = []
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

            # Amendment precedence, ranked above every heading and order
            # signal below and below carries_law alone: a print with nothing
            # under it is not the substituted rule however the page reads, and
            # the substituted text must then have landed somewhere else.
            #
            # The value is the print's own ordinal in the group, so max() takes
            # the LAST amended print -- a rule amended twice is current at its
            # last substitution -- while an unamended group scores -1 throughout
            # and falls through to the existing signals unchanged.
            amendment_rank: dict[int, int] = {}
            amendment_evidence: dict[int, str] = {}
            for index, node in enumerate(nodes):
                found = amendment_preamble_before(node)
                if found is None:
                    continue
                pos, line = found
                # The preamble must SEPARATE the two prints: an earlier print of
                # the same label must start at or before it, on the same page or
                # the one before. Both conditions are what the device looks like
                # on paper, and together they stop a preamble from reordering
                # two prints that merely share a number pages apart.
                separates = any(
                    body_position.get(other.first_block) is not None
                    and body_position[other.first_block] <= pos
                    and other.first_page is not None
                    and node.first_page is not None
                    and 0 <= node.first_page - other.first_page <= 1
                    for other in nodes[:index])
                if not separates:
                    continue
                amendment_rank[index] = index
                amendment_evidence[index] = line

            def amendment_precedence(pair, _rank=amendment_rank) -> int:
                return _rank.get(pair[0], -1)

            expected = _norm(toc.get(key, "")).casefold()
            if expected:
                def heading_score(candidate: Node) -> float:
                    actual = _norm(candidate.heading or "").casefold()
                    return (SequenceMatcher(None, expected, actual).ratio()
                            if actual else 0.0)

                canonical_index, canonical = max(
                    enumerate(nodes),
                    key=lambda pair: (carries_law(pair[1]),
                                      amendment_precedence(pair),
                                      heading_score(pair[1]), -pair[0]))
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
                canonical_index, canonical = max(
                    enumerate(nodes),
                    key=lambda pair: (carries_law(pair[1]),
                                      amendment_precedence(pair),
                                      explicit_unit_score(pair[1]), -pair[0]),
                )
            # ------------------------------ a reading of the rendered page
            #
            # Every signal above is read off the text.  A reviewer who opened
            # the page and named which print is the section outranks all of
            # them, and `restore_citable` is exactly that finding: the parser
            # kept the contents line, the footnote or the tariff row and
            # demoted the law.  Five of the first ten S7 readings ever taken
            # were inverted this way.
            #
            # Honour it by MOVING the canonical.  Simply not demoting the
            # named print would leave two citable siblings on one label, which
            # is the collision this loop exists to prevent and would put two
            # provisions behind one citation (INV-4).
            #
            # Only where the reading is unambiguous.  Two restored prints in
            # one group are two claims to be the same section; the parser is
            # not the one to choose between them.
            restored = [
                item for item in nodes
                if reviewed_structure.get(
                    (item.first_block, _reviewed_label_key(item.label)))
                == "restore_citable"]
            inverted_from = None
            if len(restored) == 1 and restored[0] is not canonical:
                inverted_from = canonical
                canonical_index = nodes.index(restored[0])
                canonical = restored[0]
                reviews_enacted.append({
                    "resolution": "restore_citable",
                    "source_block_id": canonical.first_block,
                    "printed_label": canonical.label,
                    "now_canonical": True,
                    "demoted_instead_block_id": inverted_from.first_block,
                })
            elif len(restored) > 1:
                reviews_refused.append({
                    "resolution": "restore_citable",
                    "reason": "two prints of one label are both restored",
                    "printed_label": key,
                    "source_block_ids": [item.first_block
                                         for item in restored],
                })
            # A reviewer called this print apparatus and the parser made it the
            # section.  Nothing is done about it here -- forcing a demotion
            # would remove a citable unit on an inference the reading does not
            # carry -- but it must not be silent.
            if reviewed_structure.get(
                    (canonical.first_block,
                     _reviewed_label_key(canonical.label))) == "reject_candidate":
                reviews_refused.append({
                    "resolution": "reject_candidate",
                    "reason": "the rejected print is the canonical unit",
                    "printed_label": canonical.label,
                    "source_block_ids": [canonical.first_block],
                })
            if key in label_nodes:
                label_nodes[key] = canonical
            for node in nodes:
                if node is canonical:
                    continue
                # A candidate row asks a reviewer a question that has already
                # been answered from the page.  `reject_candidate` says this
                # unit is apparatus and the collision is not genuine; the
                # inverted print is named not-the-section by the same reading
                # that named its sibling the section.  Both stay demoted
                # exactly as they are now -- the tree does not change -- and
                # the collision stays in this ledger, so every repair and
                # safety check above still sees it.  What is withheld is only
                # the fresh candidate row, which would otherwise come back
                # pending forever.
                reviewed = reviewed_structure.get(
                    (node.first_block, _reviewed_label_key(node.label)))
                settled = ("restore_citable" if node is inverted_from
                           else reviewed if reviewed == "reject_candidate"
                           else None)
                if settled:
                    reviews_enacted.append({
                        "resolution": settled,
                        "source_block_id": node.first_block,
                        "printed_label": node.label,
                        "candidate_suppressed": True,
                    })
                repeated_label_decisions.append({
                    "settled_by_review": settled,
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
                    # The printed line that made the later print canonical, so
                    # an S7 reviewer sees the parser's reason and not only its
                    # result. None for every group this device does not touch.
                    "amendment_preamble": amendment_evidence.get(
                        canonical_index),
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
                       structural_reviews_enacted=reviews_enacted,
                       structural_reviews_refused=reviews_refused,
                       schedule_sections_retyped=schedule_sections_retyped,
                       nested_list_items_reparented=nested_list_items_reparented,
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
            # Consolidations print the lifecycle word both as the whole entry
            # (``1[Repealed].``) and after a retained descriptive name
            # (PPC 376B: ``Exceptional first offenders ... [omitted]``). The
            # assertion is already keyed to the exact source block, page and
            # label, so requiring the word at character zero rejects valid,
            # source-reviewed evidence without adding identity protection.
            match = re.search(r"\b(omitted|repealed)\b", value or "", re.I)
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
                    # A schedule row is citable BECAUSE its own words reproduce
                    # a printed contents heading -- one filed under a different
                    # label.  Copying this label's heading onto it would name a
                    # different enactment than the row's own text says.
                    and id(node) not in contents_proved_rows
                    and not node.heading and entry.get("heading")
                    # The source's own word outranks a list that disagrees
                    # with it.  See _names_another_section.
                    and not _names_another_section(
                        " ".join(node.text_parts) if node.text_parts else "",
                        entry.get("heading"))):
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

    # ------------------------------------------------- structural repair, once
    #
    # Three unrecognised structural headings, one mechanism.  Each is detected
    # from the FINISHED tree, because each is gated on a collision the document
    # actually has rather than on the shape of a block, and the collisions are
    # not known until the walk has run.  The repair is applied by re-entering
    # this same function with the evidence named -- one code path, not a second
    # one -- and the re-parse is kept only if `_structural_repair_is_safe`.
    if structural_overrides is None and seg.repeated_label_decisions:
        order = {block.get("id"): i for i, block in enumerate(body)}
        repair: dict = {}

        # (1) Bare Roman display headings.  Condition (iii): promote only where
        # a candidate heading separates two siblings that collided.
        promote = _roman_display_part_run(roman_display_candidates)
        if promote and _collision_separated_by(
                seg.repeated_label_decisions, order,
                sorted(order[bid] for bid in promote if bid in order)):
            repair["roman_display_parts"] = promote

        # (2) The auxiliary heading the contents region swallowed.  Only where
        # the heading sits after the last printed contents entry, the body is
        # full of amending instructions, and the collisions are between them.
        if toc_found and boundary and trailing_cut is None:
            # Where the printed list ENDS: the block carrying its
            # highest-numbered entry.  Not simply the last entry found in the
            # swallowed region -- the schedule rows there are themselves parsed
            # as entries, which would put the end of the list past the heading
            # this is looking for.
            numbered = [
                (int(match.group(1)), entry.get("source_block_id"))
                for entry in printed_toc
                for match in [re.match(r"^(\d+)", entry.get("label") or "")]
                if match]
            highest = dict(numbered).get(max(numbered)[0]) if numbered else None
            list_end = next((i for i, block in enumerate(blocks[:boundary])
                             if block.get("id") == highest), -1)
            # The LAST standalone auxiliary heading between there and the
            # boundary: the division opens at the heading, so cutting later than
            # it would leave rows outside their own schedule again.  Standalone
            # because a contents ENTRY reading "25. Schedule I" is a promise
            # about a division, not the division itself, and it parses as a
            # section here rather than as a schedule.
            auxiliary = next(
                (blocks[i].get("id")
                 for i in range(boundary - 1, list_end, -1)
                 for found in [classify(blocks[i]["text"])]
                 if len(_norm(blocks[i]["text"])) <= 40
                 and found and found[0] in _AUXILIARY_KINDS),
                None)
            amending_rows = sum(
                1 for block in body
                for found in [classify(block["text"])]
                if found and found[0] == "section"
                and _AMENDING_ITEM.match(_norm(found[2])))
            colliding_rows = sum(
                1 for decision in seg.repeated_label_decisions
                if _AMENDING_ITEM.match(_norm(decision["candidate"].text)))
            if auxiliary is not None and amending_rows >= 5 and colliding_rows:
                repair["contents_boundary_block"] = auxiliary
                repair["corroborate_schedule_exit"] = True

        # (3) A contents list printed after the body.  The marker must sit in
        # the document's last pages, every label it prints must already be a
        # citable label above it, and every collision must be inside it.
        if not toc_found and trailing_cut is None and len(blocks) > 4:
            last_page = max((block.get("page_no") or 0) for block in blocks)
            marker = next(
                (i for i in range(len(blocks) - 1, len(blocks) // 2 - 1, -1)
                 if len(_norm(blocks[i]["text"])) <= 40
                 and _has_contents_marker(blocks[i]["text"])
                 and (blocks[i].get("page_no") or 0) >= last_page - 1),
                None)
            if marker is not None:
                region = blocks[marker:]
                region_ids = {block.get("id") for block in region}
                listed = {_citation_label_key(label)
                          for _, _, label, heading
                          in _section_numbers(region) if heading}
                # From the BODY, not from the whole tree: the region's own rows
                # parse as sections too, so counting them would let the list
                # vouch for itself.
                above = {_citation_label_key(node.label)
                         for node in seg.flatten()
                         if node.kind in ("section", "article")
                         and node.first_block not in region_ids}
                inside = [decision for decision in seg.repeated_label_decisions
                          if decision["candidate"].first_block in region_ids]
                if (len(listed) >= 4 and listed <= above
                        and len(inside) == len(seg.repeated_label_decisions)):
                    repair["trailing_contents_block"] = blocks[marker].get("id")

        if repair:
            repaired = segment(
                original_blocks,
                curation_patches=curation_patches,
                toc_dispositions=toc_dispositions,
                split_fused_margins=split_fused_margins,
                detect_contents=detect_contents,
                force_opening_contents=force_opening_contents,
                structural_resolutions=structural_resolutions,
                structural_overrides=repair,
            )
            if _structural_repair_is_safe(seg, repaired, blocks):
                repaired.structural_repair = ",".join(sorted(repair))
                return repaired

    # The contents hypothesis is scored BEFORE the body walk and never re-checked
    # after it. `parse_contents` picks a boundary on a pre-walk label-overlap
    # score that must clear _TOC_MIN_AGREEMENT; the agreement the walk actually
    # achieves is recorded and then ignored. So a boundary can be accepted on a
    # promise the body never keeps.
    #
    # Measured over the corpus on 19 Sep 2026: 21 active instruments carried
    # `toc_found = true` with post-walk agreement below the floor -- seven of
    # them at exactly 0.0000, meaning not one promised label was found in the
    # body after the split -- and those 21 held 245 of 1,547 pending contents
    # gaps, 16% of the queue from 0.67% of instruments.
    #
    # What it costs is not a bad score but a wrongly cut document. The K.D.A.
    # Disposal of Land Rules print rule 1 on page 2; the parser set
    # body_starts_page = 15, so thirteen pages of rules were filed
    # `role='contents'` owned by nothing and the only "sections" left were
    # appendix rows. The Charas Permit and Pass Rules kept a 21-entry "contents
    # list" whose entries are the full operative text of rules 1 to 21, and the
    # only citable sections the document has are the eighteen field labels of a
    # form.
    #
    # The rule is the one the comment above the pre-walk floor already argues:
    # if the evidence is too thin to claim a contents list, it is too thin to
    # cut the body on. Re-segment with the hypothesis withdrawn and every block
    # in the body. `detect_contents=False` is an existing parameter, so this is
    # a re-entry and not a second code path; it cannot recurse further because
    # the re-entry has no contents to refute.
    # The withdrawal must DO NO HARM. Refuting a false contents hypothesis
    # should hand the body back to the tree, so the refuted parse must carry at
    # least as many citable units as the one it replaces. Document 4253, the
    # Sindh sales-tax-on-services tariff, is the case that proves the guard is
    # needed: both parses of it are wrong -- with the contents hypothesis its 51
    # "sections" are tariff rows ("Advertisement on television and radio,
    # 9802.1000"), without it the only three are contents rows carrying dotted
    # leaders -- and the withdrawal would trade 51 wrong units for 3 without
    # making anything citable that was not. No text moves either way; all 591
    # blocks keep a role in both. So the refutation stands down and the document
    # stays in the review queue where a reader can see it, rather than being
    # quietly made smaller.
    if (detect_contents and seg.toc_found and seg.toc
            and not overrides.get("contents_boundary_block")
            and seg.agreement < _TOC_MIN_AGREEMENT):
        refuted = segment(
            original_blocks,
            curation_patches=curation_patches,
            toc_dispositions=toc_dispositions,
            split_fused_margins=split_fused_margins,
            detect_contents=False,
            force_opening_contents=force_opening_contents,
            structural_resolutions=structural_resolutions,
            structural_overrides=structural_overrides,
        )
        citable = ("section", "article")
        if (sum(1 for n in refuted.flatten() if n.kind in citable)
                >= sum(1 for n in seg.flatten() if n.kind in citable)):
            return refuted
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
