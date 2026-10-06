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

import contextvars
import functools
import hashlib
import re
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass, field

from nizam.shared.corpus_types import is_unnumbered_label as _is_unnumbered_label

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
    # Profile rule `quoted_form_letter` (unreleased-v2; see classify): doc 2857
    # prints its forms as "FORM ‘B’ REGISTER OF ..." and "FORM 'C' [See Rule
    # 3 (6)] ...". The quotes are the printer's; the identity is the letter.
    ("form_quoted", "form", re.compile(
        r"^\s*(?:\d{1,3}\s*\[\s*)?FORM\s+[‘’'\"“”]?([A-Z0-9]{1,3})"
        r"[‘’'\"“”]?(?=[\s.\-:\[]|$)"
        r"\s*[.\-:]?\s*(.*)$", re.S)),
    ("form", "form", re.compile(
        r"^\s*(FORM(?:\s+(?:NO\.?\s*)?[A-Z0-9IVXLC()./-]+)?)"
        r"\s*[.\-:]?\s*(.*)$", re.I | re.S)),
    # Profile rule `quoted_division_letter` (unreleased-v2; see classify): doc
    # 2019 prints "APPENDIX ―A‖" and "APPENDIX ―B‖" -- printer's quotes the
    # text layer decoded as U+2015/U+2016 -- and its s.5 cites "Appendix ‗A‘".
    # The generic rule labels both "APPENDIX"; the identity is the letter.
    ("appendix_quoted", "appendix", re.compile(
        r"^\s*(APPENDIX|ANNEXURE|ANNEX)\s+[‘’'\"“”―‖‗]\s*([A-Z0-9]{1,3})\s*"
        r"[‘’'\"“”―‖‗](?=[\s.\-:\[(]|$)\s*[.\-:]?\s*(.*)$", re.S)),
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
    # Profile rule `first_statutes_schedule` (see classify): a university
    # Act's "THE FIRST STATUTES", printed alone or with only its statutory
    # reference "(see section 34)", is the Act's schedule of statutes.
    ("first_statutes", "schedule", re.compile(
        r"^\s*((?:THE\s+)?FIRST\s+STATUTES)\s*[.:]?\s*"
        r"((?:\(\s*see\s+section\s+\d{1,3}[A-Z]?\s*\)\s*)?)$", re.I | re.S)),
    # Qualifiers, which attach to whatever they follow rather than opening a new
    # branch. Doc 03b §1.1: "never a proviso without what it qualifies".
    # An amendment's superscript marker may be fused to the opening bracket.
    # It is provenance, not the proviso's printed label.  Require the exact
    # bracket + qualifier shape; ordinary bracketed amendments are untouched.
    ("proviso",      "proviso",      re.compile(
        r"^\s*(?:\d{1,3}\s*\[\s*)?(Provided)\b\s*(.*)$", re.S)),
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
    # An inserted section can be the innermost of two amendment brackets. The
    # Sindh Service Tribunals Act prints ``3[4[5-A]. (1) The Chairman ...``:
    # the close bracket belongs to the amendment, not to the citation label.
    # Require an inserted letter suffix and at least one numbered bracket so
    # an ordinary bracketed table cell cannot become a section.
    ("section", "section", re.compile(
        r"^\s*(?:\d{1,4}[a-z]?\s*\[\s*){1,3}"
        r"(\d{1,4}\s*[-–]\s*[A-Z]{1,3})\s*\]\s*\.\s*(.*)$", re.S)),
    # A consolidation may open a quoted insertion before its footnote marker:
    # ``“2[22-A. Recovery of Authority dues.``. Keep both delimiters in the
    # original source text, while classifying the printed 22-A citation.
    ("section", "section", re.compile(
        r"^\s*[\u201c\u2018]\s*\d{1,4}[a-z]?\s*\[\s*"
        r"(\d{1,4}\s*[-–]\s*[A-Z]{1,3})\s*\.\s*([A-Z].*)$", re.S)),
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
    if not flat:
        return False
    if len(flat) <= 24 and _PAGE_FOOTER.match(flat):
        return True
    # Consolidations commonly fuse the parenthesised Act/Ordinance number and
    # ``N | P a g e`` into one top-of-page block.  The changing page number
    # prevents exact-repeat detection, but the whole block is still furniture.
    # Profile rule `page_first_running_header` (unreleased-v4): doc 4453 prints
    # the page number first, "6 | P a g e THE STAMP ACT, 1899 (ACT II OF
    # 1899)"; the order-sensitive test missed all 79 page heads.
    if (profile_rule("page_first_running_header") and len(flat) <= 140
            and re.match(r"^\d{1,4}PAGE.{0,90}\((?:[^()]*(?:ACT|ORDINANCE|RULES?|REGULATIONS?|ORDER)[^()]*)\)$",
                         flat, re.I)):
        return True
    return bool(
        len(flat) <= 140
        and re.search(
            r"\((?:[^()]*(?:ACT|ORDINANCE|RULES?|REGULATIONS?|ORDER)[^()]*)\)"
            r"\d{1,4}PAGE$",
            flat,
            re.I,
        )
    )
_FOOTNOTE = re.compile(
    r"^\s*\d{1,2}\s*(?:"
    r"[.:-]?\s*(?:Substituted|Subs|Inserted|Ins|Added|Ibid|"
    r"(?:A\s+)?New\s+(?:sub[- ]?)?section)\b|"
    r"S\.?\s*No\.?\s*.{0,40}\b(?:substituted|inserted|omitted|deleted)\b|"
    r"[.:-]?\s*(?:For\b.{0,120}\b(?:Gazette|statement|report)\b|"
      r"For\s+notification\s+see\b)|"
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
# Profile rule `new_section_paragraph_not_note` (unreleased-v4): doc 3785's
# Schedule amends another Act in numbered paragraphs, "12. New section 24-A.–
# After section 24 of the said Act the following shall be deemed to be
# inserted ...", which the "New section" footnote alternative above took for
# editorial provenance, so paragraphs 12 and 15 vanished and their quoted text
# ran into the paragraphs before them. A paragraph whose "New section X." is
# closed by a heading dash enacts; it is no note.
_NEW_SECTION_PARAGRAPH = re.compile(
    r"^\s*\d{1,2}\s*\.\s*\n?\s*New\s+section\s+[\dA-Z]+(?:-[A-Z])?\s*\.\s*[–—-]", re.I)


class _FootnotePattern:
    """`_FOOTNOTE_PATTERN`, refusing an enacting "N. New section X.–" paragraph under v4."""

    def match(self, text, *args):
        if profile_rule("new_section_paragraph_not_note") and _NEW_SECTION_PARAGRAPH.match(text or ""):
            return None
        return _FOOTNOTE_PATTERN.match(text, *args)


_FOOTNOTE_PATTERN = _FOOTNOTE
_FOOTNOTE = _FootnotePattern()
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


def _schedule_amendment_item(schedule_node, text):
    """Profile rule `schedule_amendment_item`: an enacting amendment item of an open schedule (doc 2739)."""
    m = re.match(r"^\s*(\d{1,3})\s*[.:-]", text or "")
    if not m:
        return False
    unquoted = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', "", text)
    if not re.search(r"\bshall\s+be\s+(?:substituted|inserted|omitted|deleted|added)\b", unquoted, re.I):
        return False
    items = [n for n in schedule_node.children
             if n.kind in ("clause", "section") and str(n.label).isdigit()]
    return bool(items) and int(items[-1].label) == int(m.group(1)) - 1


def _schedule_amendment_block(body, block):
    """Unit-build side of `schedule_amendment_item`: an enacting amendment block that follows a display
    SCHEDULE heading and the block opening item N-1 -- subdivided like any body block, not kept whole."""
    text = block.get("text") or ""
    m = re.match(r"^\s*(\d{1,3})\s*[.:-]", text)
    if not m or int(m.group(1)) < 2:
        return False
    unquoted = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', "", text)
    if not re.search(r"\bshall\s+be\s+(?:substituted|inserted|omitted|deleted|added)\b", unquoted, re.I):
        return False
    try:
        at = next(i for i, other in enumerate(body) if other is block)
    except StopIteration:
        return False
    previous = re.compile(r"^\s*" + str(int(m.group(1)) - 1) + r"\s*\.\s*(?:\n|$)")
    found_previous = False
    for other in reversed(body[:at]):
        other_text = other.get("text") or ""
        if not found_previous and previous.match(other_text):
            found_previous = True
        if re.match(r"^\s*(?:THE\s+)?SCHEDULE\s*\.?\s*(?:\n|$)", other_text):
            return found_previous
    return False

# Enactment-history notes can open "1This Act was passed by ..." rather than
# the amendment verbs accepted by _FOOTNOTE.  Only the source-verified 1985
# Punjab note is classified here.  A corpus trial of a broader formulation
# changed hundreds of released trees without source review, so other notes
# cannot be swept into this rule.  Document
# 118 p.2 block 3429 is below the printed footnote rule at y=682/842.
_ENACTMENT_HISTORY_NOTE = re.compile(
    r"^\s*1\s*This\s+Act\s+was\s+passed\s+by\s+the\s+Punjab\s+Assembly\s+"
    r"on\s+10th\s+November,?\s+1985\b"
    r"(?=[\s\S]{0,350}\bassented\s+to\s+by\b)"
    r"(?=[\s\S]{0,500}\bpublished\s+in\b[\s\S]{0,100}\bGazette\b)",
    re.I,
)
_SOURCE_HISTORY_BLOCKS = {
    # Document 362, official PDF page 3. PyMuPDF split this one publication
    # footnote across two blocks, so neither block satisfies the ordinary
    # whole-note recognizer. Match both immutable block IDs and exact text;
    # a changed extraction fails closed instead of hiding operative law.
    (15811, 3): ("1 This Act was passed by the Provincial Assembly of Balochistan "
            "on 1st October 2015; assented to by the Governor of Balochistan "
            "on 2nd"),
    (15812, 3): ("October, 2015, and published in the Balochistan Gazette "
            "(Extraordinary) No. 175, dated 2nd October, 2015."),
    # Document 17 p.2: the official PDF puts this note below the footnote
    # rule, not inside section 3. A generic "This Act was passed" recognizer
    # changed unrelated released trees, so this source anchor stays exact.
    (279, 2): ("1 This Act was passed by the Provincial Assembly of Balochistan "
               "on 27th June, 1989; assented to by the Governor of Balochistan; "
               "and published in the Balochistan Gazette (Extraordinary) "
               "No. 127, dated 30th July, 1989."),
}

# Document 671 p.14: the PDF's publication/amendment footnotes begin in block
# 28229 and continue in block 28230. The continuation has no opening marker,
# so a generic footnote recognizer gives it to section 10(ii). Its complete
# normalized source text is pinned here by digest; a changed extraction fails
# closed instead of silently removing possible enacted words.
_SOURCE_HISTORY_BLOCK_SHA256 = {
    # Document 671 p.9: all three printed notes below the footer rule were
    # split into two non-citable clause candidates. The whole block is notes.
    (28176, 9): "8d087a966ba3e6f89030ccbf9e4bdc106d0f8fcd553a7b17dc2044982e692e14",
    (28230, 14): "9e3842cbc40e950ca2c982e388468456226d04e1e34b5a369e7806131bea832f",
    # Document 220 p.2: the publisher's footnote under section 2 is not a
    # numbered clause. Its exact source text and lower-page position are both
    # required, so an extraction change cannot silently suppress enacted text.
    (9075, 2): "ca36fa965e4d00770091392b78d99c2565179c67eb8256b9a9975d3b2babbd39",
}

_SOURCE_EDITORIAL_SEPARATOR_BLOCKS = {
    # Visibly outside the enacted text on the official pages. The source
    # coordinates and exact block text make these local corrections inert for
    # every other instrument, including legislative underscore placeholders.
    (278, 2): "____",       # Document 17, after section 3.
    (309, 2): "______",     # Document 19, after section 2.
    (5529, 2): "____________",  # Document 157, after section 2 proviso.
    (28228, 14): "_______", # Document 671, before bottom footnotes.
}

_SOURCE_MARGINAL_HEADING_BLOCKS = {
    # Document 220 p.2: "Preamble." is a right-margin label aligned with the
    # WHEREAS opening, not part of the enacted preamble sentence.
    (9067, 2): "Preamble.",
}

# Document 3 is a one-page Sindh Act. The right-margin labels, divider and
# post-enactment Speaker/Secretary publication furniture were fused after
# section 2 by the block-order reader. Each immutable block is pinned to its
# exact normalized source text so an extractor change fails closed.
_SOURCE_NON_OPERATIVE_BLOCK_ROLES = {
    (21, 1): ("heading", "5aeed31f34f129c085e15af8c8bbe4ef16bd2056206c16e0eea47521b747a862"),
    (24, 1): ("heading", "c4a21ff5adc8a1b354f62419b7b2f598b5f9d5ed6bd6e4c81767fc754357f93a"),
    (25, 1): ("preface", "ac688b09d8d93158fc7565322d8333c9870b476cdc8c27653950933c989689c2"),
    (26, 1): ("preface", "1feceb6e2358da1a67821e410e6f804c660710ae723104fdb863eda2eb006618"),
    (27, 1): ("preface", "d49e8636d668f0a1d01cd08b387b5fa4f648241d5f21cba0a612cb428877352f"),
    # Document 3320 p.4: the blocks following rule 16's closing sentence
    # contain the signatory's office and a later download stamp, not law.
    (350849, 4): ("preface", "88321d44fb871717acd5d437becde49fb91b79c773a9e1cb99901450fcc350d5"),
    (350850, 4): ("preface", "20c224bb30e4032a97aa9bd485904ef6de2f6c6594ca97fc2bde43fa843f3309"),
}

# Document 3320's contents puts "3." on one extraction span and both named
# sub-rules on the next two spans of the SAME block. The number is visibly a
# contents row, but the generic detached-heading reader only joins separate
# blocks; without this exact-source anchor row 3 silently disappears from the
# contents ledger. The raw block and both printed sub-headings stay unchanged.
_SOURCE_COMPOUND_TOC_HEADING = {
    (350823, 1, "3"): (
        "9892047ead111eeb34e01a6a92d33fef0b92f5a8a00c7e77ebbaca267b779def",
        "(1) Custody of moneys. (2) Investment of moneys.",
    ),
}

_SOURCE_PREAMBLE_INTRO_SHA256 = {
    # Document 3 p.1 packs AN ACT, WHEREAS, the enacting formula and section 1
    # into one extracted block. The printed marginal label is separately
    # classified as heading; the source's opening prose still is a preamble.
    (22, 1): "d9237acbf8f21ddf7c311c035501062101a6068d844ea0655fae609abd5a2399",
}


def _is_source_preamble_intro_block(block: dict) -> bool:
    expected = _SOURCE_PREAMBLE_INTRO_SHA256.get(
        (block.get("id"), block.get("page_no")))
    return bool(expected and hashlib.sha256(
        " ".join((block.get("text") or "").split()).encode("utf-8")
    ).hexdigest() == expected)


def _source_nonoperative_role(block: dict) -> str | None:
    reviewed = _SOURCE_NON_OPERATIVE_BLOCK_ROLES.get(
        (block.get("id"), block.get("page_no")))
    if reviewed is None:
        return None
    role, expected = reviewed
    actual = hashlib.sha256(
        " ".join((block.get("text") or "").split()).encode("utf-8")
    ).hexdigest()
    return role if actual == expected else None


def _is_source_marginal_heading(block: dict) -> bool:
    return bool(
        (block.get("text") or "").strip() ==
        _SOURCE_MARGINAL_HEADING_BLOCKS.get((block.get("id"), block.get("page_no")))
        and block.get("x0") is not None and float(block["x0"]) >= 500
    )


def _is_source_editorial_separator(text: str, block: dict) -> bool:
    return text.strip() == _SOURCE_EDITORIAL_SEPARATOR_BLOCKS.get(
        (block.get("id"), block.get("page_no")))


def _is_source_history_digest_block(block: dict) -> bool:
    expected = _SOURCE_HISTORY_BLOCK_SHA256.get(
        (block.get("id"), block.get("page_no")))
    if expected is None:
        return False
    y0 = block.get("y0")
    height = block.get("page_height")
    return bool(
        y0 is not None and height and float(y0) >= float(height) * 0.75
        and hashlib.sha256(
            " ".join((block.get("text") or "").split()).encode("utf-8")
        ).hexdigest() == expected
    )


def _is_enactment_history_footnote(text: str, block: dict) -> bool:
    y0 = block.get("y0")
    height = block.get("page_height")
    if _is_source_history_digest_block({**block, "text": text}):
        return True
    source_text = _SOURCE_HISTORY_BLOCKS.get((block.get("id"), block.get("page_no")))
    if (source_text is not None and y0 is not None and height
            and float(y0) >= float(height) * 0.75
            and " ".join(text.split()) == source_text):
        return True
    return bool(
        y0 is not None and height and float(y0) >= float(height) * 0.75
        and _ENACTMENT_HISTORY_NOTE.match(text)
    )


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


# Profile rule `serial_column_header_owner`: an upper-case 'S.NO.' column header at a text's end.
_SERIAL_COLUMN_HEADER_END = re.compile(
    r"(?:^|[.:;\u2014-]\s+)S\.\s?NO\.?\s+(?:[A-Z][A-Z&()/,'-]*\.?\s+){2,}[A-Z][A-Z&()/,'-]*\.?\s*$")


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


# Profile rule `enacting_formula_ends` (unreleased-v2): "It is hereby enacted
# as follows :—" ends in a dash, which `_UNFINISHED` reads as a sentence still
# running -- but the formula is complete, and what follows it is the first
# division. Doc 2019 p2 read "CHAPTER – I / PRELIMNARY" into the preamble.
_ENACTING_FORMULA_TAIL = re.compile(
    r"\b(?:enacted|ordained)\s+as\s+follows\s*[:;.\-–—]*$", re.I)
# Profile rule `promulgating_formula_ends` (unreleased-v3): the Ordinance
# form, "... is pleased to make and promulgate the following Ordinance:—"
# (doc 2923 p3, before "CHAPTER I PRELIMINARY").
_PROMULGATING_FORMULA_TAIL = re.compile(
    r"\bpromulgate\s+the\s+following\s+(?:Ordinance|Regulations?|Order|Act)"
    r"\s*[:;.\-–—―]*$", re.I)


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
    # Profile rule `letter_closing_finished` (unreleased-v4): doc 1874 closes
    # Form A with "Yours faithfully" (no stop) and prints "FORM 'B'" at the
    # head of the next page; the closing line read as an unfinished sentence,
    # so Form B ran into Form A. A letter's subscription line is finished.
    if profile_rule("letter_closing_finished") and _LETTER_CLOSING.search(tail):
        return False
    return bool(tail) and bool(_UNFINISHED.search(tail))


_LETTER_CLOSING = re.compile(r"\bYours?\s+(?:faithfully|truly|sincerely|obediently)\s*,?\s*$", re.I)


# A cross-reference whose NUMBER the printer wrapped onto the next line of the
# same paragraph:
#
#     doc 2271 p4   "...powers and functions provided in section \n12. \n(2) ..."
#     doc 2489 p11  "...the field operations of the Rescue \n1122. \n \n(2) ..."
#     doc 3193 p16  "...incentives outlined in sections 20 and \n21. \n \n(2) ..."
#     doc 3862 p39  "...shall affect the provisions of section \n49. \n \n(3) ..."
#     doc 1357 p12  "...funds established under section \n20. Such rules ..."
#
# `subdivide` cuts at each of those numbers, correctly for what it can see, and
# every one became a phantom section that swallowed the host's later
# subsections and collided with the real section of that number.
#
# The preceding word is necessary and never sufficient: "...shall apply to this
# section" can lose its full stop in extraction and still be followed by a real
# "12.". So the last line must END in a reference word, a conjunction joining
# numbered references, or a capitalised name -- and `_wraps_a_cross_reference`
# then asks for independent evidence the number continues the sentence.
_WRAPPED_REFERENCE_NUMBER = re.compile(r"^\s*\d{1,4}[A-Z]?\s*\.")
_REFERENCE_LINE_END = re.compile(
    r"(?:"
    # A SINGULAR reference noun ending a line demands a number after it.
    # Plurals do not ("...made under these rules"), so they qualify only in
    # the numbered form below.
    r"(?i:\b(?:sub-?)?(?:section|clause|rule|regulation|article|paragraph"
    r"|item|entry))"
    # "sections 20 and" / "rules 1247, 1248 and" -- a conjunction joins
    # references only when a number stands immediately before it.
    r"|\d{1,4}[A-Z]?(?:\s*\([^()\n]{1,6}\))*\s*,?\s+(?i:and|or|to)"
    r")[ \t\u00a0]*$")
# A name that carries a number: "the field operations of the Rescue" / "1122."
# A capitalised word ending a line is also how a list or table row ends
# ("Match Box/Lighter" / "29. Yogurt (Dehi)" in the Prisons Rules' diet
# scale), so this class is admitted only on the strongest continuation
# evidence -- nothing after the number, then a LATER subsection of the host.
_NAME_LINE_END = re.compile(r"\b[A-Z][a-z]{2,}[ \t\u00a0]*$")
_OPENS_FIRST_SUBPART = re.compile(r"^\s*\(\s*1\s*\)")
_LATER_SUBPART = re.compile(r"^\s*\(\s*(\d{1,3})\s*\)")
# "Definitions.--", "Powers of the Board.___", "Short title." alone on its line.
# Deliberately generous: a short sentence closed by a full stop is read as a
# heading too, and a heading keeps the unit a section.
_HEADING_SHAPED = re.compile(
    r"^\s*[\"\u201c]?[A-Z][^.:\n]{0,120}[.:]"
    r"(?:\s*[-\u2013\u2014_]|[ \t\u00a0]*(?:\n|$))")


def _wraps_a_cross_reference(before: str | None, text: str, rest: str,
                             following: str | None, keys: tuple[str, ...],
                             owner_label: str | None, seen: set[str],
                             toc: dict[str, str]) -> bool:
    """Is this line-initial "N." the wrapped tail of a cross-reference?

    `before` is the preceding unit ONLY when `subdivide` carved both from the
    same source block, else None; `following` is the next unit; `keys` are the
    label as printed and as `_repair_label` reads it; `owner_label` is the
    section the walk is inside.

    Every test below is a reason to KEEP the section, and the unit is
    continuation only when none of them fires.  Where the evidence is mixed
    the section stands: a phantom costs an S7 decision, a lost section costs
    law its citation.
    """
    if before is None or not _WRAPPED_REFERENCE_NUMBER.match(text):
        return False
    lines = [line for line in before.splitlines() if line.strip()]
    if not lines:
        return False
    by_reference = bool(_REFERENCE_LINE_END.search(lines[-1].rstrip()))
    if not by_reference and not _NAME_LINE_END.search(lines[-1].rstrip()):
        return False
    owner = re.match(r"\d+", owner_label or "")
    if owner is None:
        return False
    # The body's high-water mark as well as the owner: an owner whose label
    # is itself misread (doc 4474's rule 1248 sits under an owner read as
    # "13-L") must not make the next rule look out of sequence.
    running = [int(owner.group())] + [
        int(found.group()) for found in (re.match(r"\d+", value)
                                         for value in seen) if found]
    for key in keys:
        if not key:
            continue
        # Ordered contents evidence that this is the next section wins, as
        # it does for the prefixed "Rule 21." form this extends.
        if _toc_label_is_next(key, toc, seen):
            return False
        # The body's own running sequence: the owner's number again with a
        # suffix (5 -> 5A) or the number after it -- or after the highest
        # number read so far -- is the NEXT section, even when the line
        # before it lost its full stop. A gap of two is NOT protected here
        # -- doc 3862's "section / 49." sits inside s.47 -- which is why the
        # heading and subsection tests below are also required.
        lead = re.match(r"\d+", key)
        if (lead and key not in seen
                and any(0 <= int(lead.group()) - value <= 1
                        for value in (running[0], max(running)))):
            return False
        if _heading_supports(rest, toc.get(key)):
            return False
    body = (rest or "").strip()
    if body:
        # Text after the number on its own line is how a real section opens
        # when its predecessor was never printed and its heading sits in the
        # margin: "...under this section" / "7. The Board shall meet" with no
        # s.6 in the body. So this form is a reference only when the number
        # names a section the body has ALREADY read -- a unit cannot open a
        # second time. Doc 1357 is that: s.20 is read on p11, and p12's
        # "...under section" / "20. Such rules and regulations ..." is s.21(2)
        # citing it. Forward numbers with text after them stay sections.
        #
        # And never for the name class, whose line ends are also list rows;
        # nor for a heading, an opening "(1)", or an omission placeholder
        # ("12. [Omitted]", "12. ***"), which are how a section opens.
        if (not by_reference or keys[0] not in seen
                or _OPENS_FIRST_SUBPART.match(body) or _HEADING_SHAPED.match(body)
                or body[0] in "[*"):
            return False
        return True
    # Nothing after the number on its line: only a LATER subsection of the
    # host proves the sentence carried on. "(1)" would be this section's own
    # first subsection -- the number merely stranded on its line.
    later = _LATER_SUBPART.match((following or "").strip())
    return bool(later and int(later.group(1)) >= 2)


# A four-digit YEAR at the start of a line is the same mechanism with a
# different word before it. It closes a wrapped citation in a marginal note --
#
#     "Amendment of section 17 of West Pakistan Ordinance XX of" / "1966."
#
# -- or heads a title ("1973." / "An Act to amend the Sind Service Tribunal
# Act"), or is debris ("1958. (See Section 3)"). `_YEAR_TITLE_LINE` refuses the
# title shape by whitelisting what may FOLLOW the year, and a whitelist of
# followers does not converge: "An Act to amend", "2[KHYBER PAKHTUNKHWA]
# ORDINANCE", "(W. P. ORD NO.", "CONTENTS" all escaped it.
#
# An absolute ceiling is not safe either: the Punjab Prisons Rules (doc 4474)
# number real rules 1249 and 1250. What separates a year from a provision
# number is RELATIVE -- a real rule 1850 follows rule 1849, a year follows
# section 3. So a year-shaped label stays a section only while some reading of
# it (as printed, or as `_repair_label` strips a fused marker) continues the
# body's running sequence, or the contents promises it.
# The year may also close the instrument's OWN title, wrapped so that its last
# word leads the line -- "...(Pension" / "Regulations 1997.", "...Oil Tankers)"
# / "Rules 2018." -- which `_INNER_RULE` cuts and the grammar reads as rule
# 2018. A real "Rule 1850." after rule 1849 stays in sequence below.
_YEAR_OPENER = re.compile(
    r"^\s*(?:(?i:rules?|regulations?)\s*)?(?:18|19|20)\d{2}\s*\.")
_YEAR_LABEL = re.compile(r"(?:18|19|20)\d{2}")
# How far past the body's highest number a real provision may still sit: an
# omitted rule or an OCR-missed opener leaves a small gap, never hundreds.
_SEQUENCE_REACH = 10


def _year_is_not_a_provision_number(text: str, rest: str,
                                    keys: tuple[str, ...],
                                    owner_label: str | None, seen: set[str],
                                    toc: dict[str, str]) -> bool:
    """Is this line-initial "1966." a year rather than provision 1966?"""
    if not _YEAR_OPENER.match(text) or not keys or not _YEAR_LABEL.fullmatch(keys[0]):
        return False
    leads = [int(found.group()) for found in
             (re.match(r"\d+", value) for value in [*seen, owner_label or ""])
             if found]
    running = max(leads, default=0)
    for key in keys:
        if not key:
            continue
        # The document's own contents promising the number is evidence of a
        # provision, whatever the body has reached.
        if (key in toc or _toc_label_is_next(key, toc, seen)
                or _heading_supports(rest, toc.get(key))):
            return False
        lead = re.match(r"\d+", key)
        if (lead and key not in seen
                and 0 <= int(lead.group()) - running <= _SEQUENCE_REACH):
            return False
    return True


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
    # An explicit ``CONTENTS`` banner remains strong enough when fused into a
    # title block.  The weaker bare column header (``Rules``, ``Sections``)
    # must be the WHOLE block, not merely one physical line inside it.  OCR and
    # column extraction routinely split operative prose as ``These / rules /
    # may ...``; treating that middle line as a marker made the body of docs
    # 3720 and 4465 its own contents list and a later appendix/list the body.
    if (any(_CONTENTS.match(line) for line in text.splitlines())
            or bool(_CONTENTS_COLUMN_HEADER.match(text))):
        return True
    # Profile rule `contents_banner_block` (unreleased-v4): doc 2875 heads its
    # list "CONTENT / Preamble / Sections" in one block -- the singular banner
    # (accepted above only as a whole block) with the column headers fused to
    # it -- so no marker was found and the 21 rows became sections 1-21. A block
    # of nothing but those banner lines, one of them CONTENT(S), is the marker.
    if profile_rule("contents_banner_block"):
        lines = [line for line in text.splitlines() if line.strip()]
        return bool(lines) and any(
            re.fullmatch(r"\s*c\s*o\s*n\s*t\s*e\s*n\s*t\s*s?\s*[.:]?\s*", line, re.I)
            for line in lines) and all(
            _CONTENTS_COLUMN_HEADER.match(line)
            or re.fullmatch(r"\s*preamble\s*[.:]?\s*", line, re.I) for line in lines)
    return False


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
    # The segmentation profile this parse ran under (SEGMENTATION_PROFILES).
    profile: str = "default"
    # Profile rule `contents_heading_alignment`: contents row ordinal -> the
    # body label its printed heading names (None: no body unit), when used.
    contents_alignment: dict | None = None

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
    r"(?:ACT|ORDINANCE)\s+NO\b|AN\s+ACT\s+TO\b|"
    r"NORTH[-\s]+WEST\s+FRONTIER\s+PROVINCE\s+REGULATION\s+NO\b|"
    r"\d{1,2}\s*\[\s*KHYBER\s+PAKHTUNKHWA\s*\]\s+ORDINANCE\s+NO\b|"
    r"\d{1,2}\s*\[\s*RECEIVED\s+THE\s+ASSENT\s+OF\b)",
    re.I | re.S)

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


_MARK_ONLY_ROW = re.compile(r"\[?\s*(?:[*.…]\s*){3,}\]?\s*\.?")
_BRACKETED_OMISSION_STUB = re.compile(
    r"^\s*(?:\d{1,3}\s*)?\[\s*(\d{1,4}[A-Z]{0,2})\s+((?:\*\s*){3,}\]?)\s*$")
_PAREN_OMISSION_STUB = re.compile(
    r"^\s*(?:\d{1,3}\s*)?\[?\s*\(\s*(\d{1,4})\s*\)\s*((?:\*\s*){3,}\]?)\s*$")


def classify(text: str) -> tuple[str, str, str] | None:
    """Return (rule_name, label, remainder), or None for continuation prose."""
    # Profile rule `marked_proviso_cut` (unreleased-v4): (doc 4447 p53): a note marker fused to Provided with no bracket
    if profile_rule("marked_proviso_cut") and text:
        _mp = re.match(r"^\s*\d{3}(?=Provided\b)", text)
        if _mp:
            _found = classify(text[_mp.end():])
            if _found is not None and _found[0] == "proviso":
                return _found
    # Profile rule `inserted_three_letter_clause` (unreleased-v4): (doc 4447 s.8(1) p36): "259[(caa) purchases, ..."
    if profile_rule("inserted_three_letter_clause") and text:
        _tl = re.match(r"^\s*\d{1,3}\s*\[\s*\(\s*([a-z]{2}a)\s*\)\s*(?=[a-z])", text)
        if _tl:
            return "clause", _tl.group(1), text[_tl.end():]
    # Profile rule `marked_chapter_heading` (unreleased-v4): (doc 4447 p7): a chapter heading opening an amendment bracket
    if profile_rule("marked_chapter_heading") and text:
        _mc = re.match(r"^\s*\d{1,3}\s*\[\s*(?=CHAPTER\s*[-\u2013\u2014]\s*[IVXLC]+\b)", text, re.I)
        if _mc:
            _found = classify(text[_mc.end():])
            if _found is not None and _found[0] == "chapter":
                return _found
    # Profile rule `multi_letter_subsection` (unreleased-v4): (doc 4447): a sub-section label with a two- or three-letter suffix
    if profile_rule("multi_letter_subsection") and text:
        _ms = re.match(r"^\s*(?:\d{1,3}\s*\[\s*)?\(\s*(\d{1,3}[A-Z]{2,3})\s*\)\s*\]?[ \t]*\n?[ \t]*(?=[A-Z“\"]|\*\s*\*\s*\*)", text)
        if _ms:
            return "subsection", _ms.group(1), text[_ms.end():]
    # Profile rule `bare_marker_label` (unreleased-v4): (doc 4447): a note marker fused before a label with no bracket
    if profile_rule("bare_marker_label") and text:
        _bm = re.match(r"^\s*(?:\[\s*\d{1,3}(?=\(\s*(?:\d{1,3}[A-Z]{0,2}|[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)[ \t]*\n?[ \t]*[A-Za-z])|\d{1,3}(?=\(\s*(?:\d{1,3}[A-Z]{0,2}|[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)[ \t]*\n?[ \t]*[A-Z])|\d{3}(?=\(\s*(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)[ \t]*\n?[ \t]*[a-z]))", text)
        if _bm:
            _found = classify(text[_bm.end():])
            if _found is not None and _found[0] in ("subsection", "clause", "romanette"):
                return _found
    # Profile rule `fbr_definition_label` (unreleased-v4): (doc 4447 s.2)
    if profile_rule("fbr_definition_label") and text:
        _fd = re.match(r"^\s*(?:\d{0,3}\s*\[\s*)?(?:(\d{1,3})(?=\())?[“\"]?\s*\(\s*(\d{1,3}\s*[A-Z]{0,3})\s*\)\s*\]?[ \t]*\n?[ \t]*(?=(?:[“\"][^”\"\n]{1,80}[”\"][\s\S]{0,80}?\b(?:means?|includes?|shall|in\s+relation\s+to)\b|the\s+expression\s+[“\"]))", text)
        if _fd and (len(re.sub(r"[\s\d]", "", _fd.group(2))) >= 2 or _fd.group(1)):
            return "subsection", re.sub(r"\s+", "", _fd.group(2)), text[_fd.end():]
    # Profile rule `e_prefix_section_start` (unreleased-v4): (doc 4447 s.52A p103, contents p5): "52A. e-intermediaries to be
    # appointed" -- a section name opening with the lower-case prefix "e-"
    if profile_rule("e_prefix_section_start") and text:
        _ep = re.match(r"^\s*(?:\d{1,3}\s*\[\s*)?(\d{1,3}[A-Z]{0,2})\s*\.\s+(?=e-[a-z]{3,})", text)
        if _ep:
            return "section", _ep.group(1), text[_ep.end():]
    # Profile rule `high_ordinal_schedule` (unreleased-v4): (doc 4447 pp185-207): the grammar names schedules FIRST..SEVENTH;
    # "942[The EIGHTH SCHEDULE", "NINTH" .. "THIRTEENTH SCHEDULE" open schedules too
    if profile_rule("high_ordinal_schedule") and text:
        _hs = re.match(r"^\s*(?:\d{1,4}\s*\[\s*)?(?:THE\s+)?((?:EIGHTH|EIGHT|NINTH|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH)\s+SCHEDULE)[”\"]?[ \t]*[.\-–—:]?", text, re.I)
        if _hs:
            return "schedule", _norm(_hs.group(1)).upper(), text[_hs.end():]
    # Profile rule `capital_letter_item` (unreleased-v4): (doc 4447 Sixth Schedule rows 100A and 112): "(A). Conditions and
    # procedure for imports.-" and a bold category "A. ANGIOPLASTY PRODUCTS" open lettered items
    if profile_rule("capital_letter_item") and text:
        _ci = re.match(r"^\s*(?:\(\s*([A-Z])\s*\)\s*\.[ \t]+(?=[A-Z])|([A-Z])\.[ \t]+(?=[A-Z]{3,}\b(?:[^\n:]*[^\n:.\s])?[ \t]*(?:\n|$))|([A-Z])\.[ \t]+(?=[A-Za-z][^\n]{0,60}\d%))", text)
        if _ci:
            return "clause", _ci.group(1) or _ci.group(2) or _ci.group(3), text[_ci.end():]
    # Profile rule `figure_led_item` (unreleased-v4): (doc 4447 Sixth Schedule pp146, 153): a numbered item or row whose text opens
    # with a figure ("10. 3-D Cardiac Mapping System", "143. 9937" -- a serial over only its heading number)
    if profile_rule("figure_led_item") and text:
        _fi = re.match(r"^\s*(?:\d{1,4}\s*\[\s*)?(\d{1,3}[A-Z]?)\s*\.[ \t]+(?=\d-[A-Z]|\d{4}(?:\.\d{2,4})?[ \t]*(?:\n|$))", text)
        if _fi:
            return "section", _fi.group(1), text[_fi.end():]
    # Profile rule `range_stub_row` (unreleased-v4): (doc 4447 pp173, 175, 187): a table row whose serial is a printed range,
    # over only its omission stub ("955[35 to 42]. [..........]] omitted", "960[48 & 49 [...]] omitted")
    if profile_rule("range_stub_row") and text:
        _rs = re.match(r"^\s*(?:\d{1,4}\s*\[\s*|\[\s*)?(\d{1,3}[A-Z]?[ \t]*(?:to|&)[ \t]*\d{1,3}[A-Z]?)[ \t]*\]?[ \t]*\.?[ \t]*(?=\[\s*(?:\.{3,}|\*{3,})|\*{3,})", text)
        if _rs:
            return "section", re.sub(r"\s+", " ", _rs.group(1)), text[_rs.end():]
    # Profile rule `stacked_marker_row` (unreleased-v4): (doc 4447 p168): "909[910[13. ***"
    if profile_rule("stacked_marker_row") and text:
        _sm = re.match(r"^\s*(?:\d{1,4}\s*\[\s*){2,}(\d{1,3}[A-Z]?)\s*\.[ \t]*(?=\*{3,}|\[\s*\*{3,})", text)
        if _sm:
            return "section", _sm.group(1), text[_sm.end():]
    # Profile rule `marked_quoted_label` (unreleased-v4): (doc 4447 p206): "1020[\u201c(4) The refund ..."
    if profile_rule("marked_quoted_label") and text:
        _mq = re.match(r"^\s*\d{1,4}\s*\[\s*[“\"]\(\s*(\d{1,3}[A-Z]?)\s*\)[ \t]*(?=[A-Z])", text)
        if _mq:
            return "subsection", _mq.group(1), text[_mq.end():]
    # Profile rule `bare_omission_stub` (unreleased-v4): (doc 4447 s.46 p96): an omitted sub-section printed behind two note
    # markers and a bracket, only stars after it ("600[601(2A)***]")
    if profile_rule("bare_omission_stub") and text:
        _sd = re.match(r"^\s*\d{1,3}\s*\[\s*\d{1,3}\(\s*(\d{1,3}[A-Z]{0,2})\s*\)\s*(?=(?:\*\s*){3,})", text)
        if _sd:
            return "subsection", _sd.group(1), text[_sd.end():]
    # Profile rule `four_letter_section_suffix` (unreleased-v4): (doc 4447 s.30DDDA p64; contents p3)
    if profile_rule("four_letter_section_suffix") and text:
        _fl = re.match(r"^\s*(?:\d{1,3}\s*\[\s*)?(\d{1,4}[A-Z]{4})\s*\.\s*(?=[A-Z])", text)
        if _fl:
            return "section", _fl.group(1), text[_fl.end():]
    # Profile rule `misprinted_chapter_word` (unreleased-v4): (doc 4003 p14 and its contents p2: 'CHAPER-IV / Assessment and Recovery')
    if profile_rule("misprinted_chapter_word") and text:
        _agar_cm = re.match(r"^\s*CHAPER\s*[-\u2013\u2014]?\s*([IVXLC]+)(?![A-Za-z])\s*[.\-\u2013\u2014:]?\s*(.*)$", text, re.S)
        if _agar_cm:
            return "chapter", _agar_cm.group(1), _agar_cm.group(2)
    # Profile rule `misprinted_form_word` (unreleased-v4): (doc 4003 pp25-27 and contents p3: 'FROM A', 'FROM B', 'FROM \u2018C\u2019'
    # alone on their line over '[Rule 28(2)]' ... -- the forms rules 28(2), 28(3)(a), 28(3)(b) cite as Form "A", "B", "C")
    if profile_rule("misprinted_form_word") and text:
        _agar_fm = re.match(r"^\s*FROM[ \t]+[\u2018\u2019'\"\u201c\u201d]?([A-Z])[\u2018\u2019'\"\u201c\u201d]?[ \t]*(?=\n|$)(.*)$",
                            text, re.S)
        if _agar_fm:
            return "form", "FORM " + _agar_fm.group(1), _agar_fm.group(2)
    # Profile rule `quoted_hyphen_form_label` (unreleased-v4): (doc 4003 pp30-32, 35: "FORM \u2018F-1\u2019", "FORM \u2018F-2\u2019",
    # "FORM \u2018F-3\u2019", "FORM-\u2018I\u2019"): quoted_form_letter takes 'F' and leaves '-1\u2019' as the heading
    # (three forms all 'FORM F'), and no grammar admits a dash between FORM and the quote ('FORM' headed '\u2018I\u2019').
    if profile_rule("quoted_hyphen_form_label") and text:
        _agar_qm = re.match(r"^\s*FORM\s*([-\u2013]\s*)?[\u2018\u2019'\"\u201c\u201d]\s*([A-Z](?:\s*-\s*\d{1,3})?)\s*"
                            r"[\u2018\u2019'\"\u201c\u201d](?=[\s.\-:\[]|$)(.*)$", text, re.S)
        if _agar_qm and (_agar_qm.group(1) or "-" in _agar_qm.group(2)):
            return "form", "FORM " + re.sub(r"\s+", "", _agar_qm.group(2)), _agar_qm.group(3)
    # Profile rule `quoted_item_label` (unreleased-v4): doc 1746 prints
    # inserted items as `“(v) information ...` and `“(5) Other ...` on their
    # own lines. The quote is not part of the label; keep the item citable.
    if profile_rule("quoted_item_label"):
        quoted_item = re.match(
            r'^\s*[\u201c"](?=\(\s*(?:\d{1,3}|[a-z]{1,2}|[ivxlc]{1,6})\s*\)\s*[A-Za-z])',
            text or "", re.I)
        if quoted_item:
            found = classify(text[quoted_item.end():])
            if found is not None and found[0] in ("subsection", "clause"):
                return found
    # Profile rule `suffixed_decimal_label` (unreleased-v4): doc 2418 numbers
    # the rules of an inserted chapter "11-A.2.", "11-A-9." and doc 3108 prints
    # "7.2.A", "7.2.B"; the section grammar took "11-A" / "7.2" and left the
    # rest in the text, so six rules were all labelled 11-A. The whole printed
    # number is the label (as printed: "11-A.2", "11-A-9", "7.2.A").
    if profile_rule("suffixed_decimal_label"):
        m = _SUFFIXED_DECIMAL_LABEL.match(text or "")
        if m:
            return "section", re.sub(r"\s+", "", m.group(1)), text[m.start(2):]
    # Profile rule `letter_number_form_code` (unreleased-v4): doc 3108 p13 prints
    # "FORM L-37-A" alone on its line; it was labelled "FORM L" with rest "37-A".
    if profile_rule("letter_number_form_code") and text:
        _lm = re.match(r"^\s*FORM\s+([A-Z]\s*-\s*\d{1,3}(?:\s*-\s*[A-Z])?)[ \t]*(?=\n|$)(.*)$", text, re.S)
        if _lm:
            return "form", "FORM " + re.sub(r"\s+", "", _lm.group(1)), _lm.group(2)
    # Profile rule `appendix_number_label` (unreleased-v4): (doc 3803)
    if profile_rule("appendix_number_label") and text:
        _am = re.match(r"^\s*APPENDIX\s*(?:[-\u2013\u2014.]\s*)?(?:N[Oo]\s*\.\s*)?"
                       r"((?:[IVX]{1,4}|\d{1,2})(?:\s*[.\-\u2013]\s*(?:[IVX]{1,4}|\d{1,2})){0,2})"
                       r"\s*\.?[ \t]*(?=\n|$)(.*)$", text, re.S)
        if _am:
            return "appendix", "APPENDIX " + re.sub(r"\s+", "", _am.group(1)), _am.group(2)
    # Profile rule `hyphen_letter_division_label` (unreleased-v4): doc 4330
    # prints "CHAPTER VII-A" and "FORM II-A" alone on their lines; the
    # division grammar ate the hyphen as a separator and opened a second
    # Chapter VII / Form II headed "A". The whole string is the label.
    if profile_rule("hyphen_letter_division_label") and text:
        m = _HYPHEN_LETTER_CHAPTER.match(text)
        if m:
            return "chapter", m.group(1), m.group(2)
        m = _HYPHEN_LETTER_FORM.match(text)
        if m:
            return "form", re.sub(r"\s+", " ", m.group(1)), m.group(2)
    # Profile rule `lettered_paragraph_sequence` (unreleased-v4): see
    # _lettered_paragraph_sequence -- only paragraphs of a printed A, B, C ...
    # run after "(N)-A." open, and "(2)" alone before "-A." is its sub-section.
    if profile_rule("lettered_paragraph_sequence") and text and _LETTERED_SEQUENCE.get():
        m = _LETTERED_PARAGRAPH.match(text)
        if m and (text.lstrip().startswith("-A.") or _norm(text)[:40] in _LETTERED_SEQUENCE.get()):
            return "clause", m.group(1), m.group(2)
        m = _LETTERED_SUBSECTION.match(text)
        if m:
            return "subsection", m.group(1), ""
    # Profile rule `bracketed_omission_stub` (unreleased-v3): doc 1142 p3 prints
    # an omitted section as "3[5 * * *]" -- footnote 3, "Section-5, omitted
    # vide order ibid." The default grammar takes "3[5. * * *]" as section 5
    # but not the stub without its full stop, so the contents row "5.
    # Adaptations." had no unit. The whole unit must be the bracketed number
    # and three or more asterisks.
    if profile_rule("bracketed_omission_stub"):
        stub = _BRACKETED_OMISSION_STUB.match(text)
        if stub:
            return "section", stub.group(1), stub.group(2)
    # Profile rule `form_code_number` (unreleased-v4): doc 3665 labels its forms
    # "FORM PCT-2", "FORM PCT-8", "FORM PCT—13", "FORM PCT-I". v2's
    # quoted_form_letter took "PCT" as the form's letter (its lookahead admits
    # the hyphen), so every form was "FORM PCT" and its number went into the
    # heading. A letter code joined by a dash to a number is one label.
    # Profile rule `quote_before_bracket` (unreleased-v4): doc 2299 p19 prints
    # '3"[28. The provisions of this Act shall apply ...' -- the quote between
    # the note marker and the amendment bracket, where the grammar admits it
    # only after the bracket ('3["28.'). The quote is read after the bracket.
    if profile_rule("quote_before_bracket"):
        moved = _QUOTE_BEFORE_BRACKET.match(text)
        if moved:
            text = (text[:moved.start(2)] + text[moved.end(2):moved.end(3)]
                    + moved.group(2) + text[moved.end(3):])
    # Profile rule `bracketed_section_number` (unreleased-v4): doc 3785 p11
    # prints "1[11]. Meetings of the Authority.– (a) ..." -- the renumbered
    # section's number inside the amendment bracket (footnote 1: "Renumbered
    # for '11(1)'") -- which no section opener read, so s.11 and its (a)-(e)
    # stood in Chapter III's title.
    if profile_rule("bracketed_section_number"):
        bracketed = _BRACKETED_SECTION_NUMBER.match(text)
        if bracketed:
            return "section", bracketed.group(1), text[bracketed.start(2):]
    if profile_rule("form_code_number"):
        form = _FORM_CODE_NUMBER.match(text)
        if form:
            return "form", f"FORM {form.group(1)}-{form.group(2)}", text[form.start(3):]
    # Profile rule `quoted_schedule_heading` (unreleased-v4): doc 2508's
    # annexure sets out the two schedules its s.4 substitutes, each opened by
    # a quote -- "“SCHEDULE -II / (See section 4)". The schedule grammar wants
    # the word first, so Schedule II never opened and its rows ran into
    # Schedule I's. A quote straight before SCHEDULE and its number is the
    # schedule when the unit is nothing but that heading, or states the section
    # it is made under.
    if profile_rule("quoted_schedule_heading"):
        quoted = _QUOTED_SCHEDULE_HEADING.match(text)
        if quoted and (not _norm(quoted.group(2)) or re.search(
                r"\(\s*see\s+(?:sections?|rules?|regulations?)\s*\d", text[:200], re.I)):
            return "schedule", _norm(quoted.group(1)), text[quoted.start(2):]
    # Profile rule `joint_schedule_heading` (unreleased-v4): doc 3132 (the
    # Arbitration Act, 1940) ends with the stub "THE THIRD AND FOURTH
    # SCHEDULES. [ENACTMENTS REPEALED. ENACTMENTS AMENDED.] Rep. by the
    # Repealing and Amending Act, 1945 ..." -- two schedules named in one
    # capitalised heading, which no schedule grammar reads, so the stub ran
    # into the Second Schedule's item 5.
    if profile_rule("joint_schedule_heading"):
        joint = _JOINT_SCHEDULE_HEADING.match(text)
        if joint:
            return "schedule", _norm(joint.group(1)), text[joint.start(2):]
    head = text[:200]
    for name, kind, pat in RULES:
        m = pat.match(head)
        if m:
            # Profile rule `prose_explanation_word`: "explanation shall be
            # inserted, namely:" (doc 1021 s.2(b)) is a sentence about an
            # Explanation, not one. An opener is capitalised or punctuated.
            if (kind == "explanation" and m.group(1)[:1].islower()
                    and re.match(r"\s+[a-z]", head[m.end(1):])
                    and profile_rule("prose_explanation_word")):
                continue
            if name == "first_statutes" and not profile_rule("first_statutes_schedule"):
                continue
            # Profile rule `exception_word_boundary` (unreleased-v3): doc 2818
            # s.3 prints "Exceptional cases, which are not covered by the
            # regulations ..." and the qualifier grammar read an Exception
            # labelled "Exception" with the text "al cases, ...".
            if (name == "exception" and profile_rule("exception_word_boundary")
                    and re.match(r"[A-Za-z]", head[m.end(1):m.end(1) + 1])):
                continue
            if name == "form_quoted":
                if not profile_rule("quoted_form_letter"):
                    continue
                # Profile rule `form_word_not_letter` (unreleased-v4): doc 2344
                # heads a form "FORM III / FORM OF NOTING FOR DISHONOUR." and the
                # title line opened a second form lettered "OF". A form's
                # letter is never an ordinary word; the generic rule below then
                # refuses "FORM OF" as well.
                if (profile_rule("form_word_not_letter")
                        and m.group(1).upper() in {"OF", "FOR", "TO", "THE", "AND", "IN", "NO", "ON", "BY"}):
                    continue
                return "form", f"FORM {m.group(1)}", text[m.start(2):]
            if name == "appendix_quoted":
                if not profile_rule("quoted_division_letter"):
                    continue
                word = m.group(1).upper()
                return ("appendix" if word == "APPENDIX" else "annexure",
                        f"{word} {m.group(2)}", text[m.start(3):])
            # Under the same rule a form's identity is never an ordinary word:
            # doc 2857 titles Form D "Form of Certificate", which the generic
            # rule read as a second form labelled "Form of".
            if (name == "form" and profile_rule("quoted_form_letter")
                    and re.fullmatch(r"(?i)form\s+(?:of|for|to|the|and|in|no\.?)",
                                     _norm(m.group(1)))):
                return None
            label = _norm(m.group(1))
            rest = text[m.start(2):] if m.lastindex and m.lastindex >= 2 else ""
            # Profile rule `bracket_not_division_label` (unreleased-v4): doc 3302
            # heads its annexure "ANNEXURE / (See regulation 14 )"; the grammar
            # admits a bracket in the identity, so the annexure was labelled
            # "ANNEXURE (See" and headed "regulation 14 )". A bracket after the
            # word opens the reference, not the identity.
            if name in ("annexure", "appendix") and profile_rule("bracket_not_division_label"):
                word = re.match(r"\s*(ANNEXURE|ANNEX|APPENDIX|APPENDICES)\s+(?=\(\s*see\b)", head, re.I)
                if word:
                    return kind, _norm(word.group(1)), text[word.end():]
            if kind == "section" and "." in label:
                first = re.match(r"\d+", label.replace(" ", ""))
                # Decimal rates and tariff headings are quantities, not legal
                # hierarchy.  They were the few regressions revealed by the
                # compound-label repair (e.g. ``1.5 Percent`` and
                # ``9812.7900 Others``).
                if ((first and int(first.group()) in {0}
                     or first and int(first.group()) >= 1000)
                        or (_DOTTED_VALUE_REST.match(rest.lstrip())
                            and not (profile_rule("dotted_other_heading")
                                     and re.match(r"(?:OTHER|Other)\s+[A-Z][A-Za-z]", rest.lstrip())))):
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
            # Profile rule `part_range_label` (unreleased-v4): doc 904 prints the
            # stubs of its repealed parts as "PART I AND II" and "PART IV to
            # XIV. [Criminal Jails; ...] 17 to 52. [Rep. Act IX of 1894.]". The
            # first became Part I headed "AND II"; the second's lower-case rest
            # read as a cross-reference and the stub ran into s.16A(5). The
            # range is the division's label.
            if kind == "part" and profile_rule("part_range_label"):
                rng = re.match(r"\s*(AND|TO)\s+([IVXLC]+)\b\s*\.?", rest, re.I)
                if rng:
                    label = f"{label} {rng.group(1).upper()} {rng.group(2).upper()}"
                    rest = rest[rng.end():]
            return kind, label, rest
    # Profile rule `long_romanettes` (unreleased-v4): the romanette grammar
    # ends every label in i, ii, iii, iv or ix, and a two-letter (xv), (xx) or
    # (xl) passes as a letter clause; doc 1695's regulation 8(2) runs (i) to
    # (xli), and "(xxv)", "(xxx)", "(xxxv)" and "(xli)" matched nothing, so
    # each ran into the clause before it. A label of three or more letters
    # that is a well-formed roman number below fifty is a clause.
    if profile_rule("long_romanettes"):
        m = _LONG_ROMANETTE.match(head)
        if m:
            return "clause", _norm(m.group(1)), text[m.start(2):]
    # Profile rule `lettered_part_label` (unreleased-v4): doc 1563's Schedule is
    # printed as "PART A [See section 5 (2)]", "PART B", "PART C", "PART D". The
    # part grammar wants a Roman numeral or a digit, so only "PART C" opened (C
    # reads as a hundred) and the other three ran into the part before. A part
    # label that is one capital letter, the word PART in capitals, is that part.
    if profile_rule("lettered_part_label"):
        m = _LETTERED_PART.match(head)
        # Profile rule `sequential_part_heading` (unreleased-v4): doc 4433's
        # appendices print "Part-B", "Part-D" in mixed case.
        if m is None and profile_rule("sequential_part_heading"):
            m = _MIXED_LETTERED_PART.match(head)
        if m:
            return "part", m.group(1), text[m.start(2):]
    # Profile rule `hyphen_suffix_labels` (unreleased-v4): Sindh amendments
    # insert sub-sections and clauses labelled with a hyphen -- doc 1794 s.21
    # prints '1["(1-A). On such appeal being preferred ...' and '(1-B)',
    # doc 3714 s.2 prints '2[(a-i) "adjacent province's waters" means ...' --
    # which the grammar (digits and an optional letter, or one or two letters)
    # never read, so each ran into the unit before. The label keeps its hyphen.
    if profile_rule("hyphen_suffix_labels"):
        m = _HYPHEN_SUBSECTION.match(head)
        if m:
            return "subsection", re.sub(r"\s+", "", m.group(1)), text[m.start(2):]
        m = _HYPHEN_CLAUSE.match(head)
        if m:
            return "clause", re.sub(r"\s+", "", m.group(1)), text[m.start(2):]
    # Profile rule `lowercase_suffix_subsection` (unreleased-v4): doc 2299
    # inserts definitions "(39-a)", "(50-a)", "(65-a)" and "(17a)" -- digits and
    # a lower-case letter -- which the grammar (a capital suffix only) never
    # read, so each ran into the definition before it.
    if profile_rule("lowercase_suffix_subsection"):
        m = _LOWER_SUFFIX_SUBSECTION.match(head)
        if m:
            return "subsection", re.sub(r"\s+", "", m.group(1)), text[m.start(2):]
    # Profile rule `lowercase_section_start` (unreleased-v4): doc 2299 p17
    # prints "19." alone on its line and the section's text "where, by any
    # 3[Provincial] Act ..." in lower case below it; every section opener
    # wants a capital, so s.19 ran into the cross-heading before it.
    if profile_rule("lowercase_section_start"):
        m = _LOWER_SECTION_START.match(head)
        if m:
            return "section", m.group(1), text[m.start(2):]
    # Profile rule `repeated_letter_clause` (unreleased-v4): doc 4263 s.2
    # inserts '5[(ccc) "Institution" means ...' after (cc) -- one letter
    # printed three times -- and the clause grammar reads at most two letters,
    # so (ccc) ran into (cc).
    if profile_rule("repeated_letter_clause"):
        m = _REPEATED_LETTER_CLAUSE.match(head)
        if m:
            return "clause", m.group(1), text[m.start(3):]
    # Profile rule `parenthesised_letter_label` (unreleased-v4): doc 4453's
    # Schedule I prints inserted articles as "1[6(A). Allotment order ...",
    # "6(B) Transfer of Allotment Orders", "12(A) BANK GUARANTEE"; the grammar
    # opens "6A." but never a capital letter in brackets, so each inserted
    # article ran into the one before it. The label is kept as printed.
    if profile_rule("parenthesised_letter_label"):
        m = _PAREN_LETTER_LABEL.match(text)
        if m:
            return "section", f"{m.group(1)}({m.group(2)})", text[m.start(3):]
    return None


_LONG_ROMANETTE = re.compile(
    r"^\s*" + _AMEND_PREFIX
    + r"\(\s*((?=[xlvi]{3,6}\s*\))(?:xl|x{0,3})(?:ix|iv|v?i{0,3}))\s*\)\s*(.*)$", re.S)
_FORM_CODE_NUMBER = re.compile(
    r"^\s*(?:\d{1,3}\s*\[\s*)?FORM\s+([A-Z]{2,5})\s*[-–—]+\s*(\d{1,3}|[IVX]{1,4})"
    r"(?![A-Za-z0-9])\s*[.:]?\s*(.*)$", re.S)
_QUOTED_SCHEDULE_HEADING = re.compile(
    r"^\s*[“\"]\s*(SCHEDULE\s*[-–—]?\s*(?:[IVXLC]+|\d{1,2}))(?![A-Za-z0-9])\s*[.\-–—:]?\s*(.*)$", re.S)
_HYPHEN_LETTER_CHAPTER = re.compile(r"^\s*CHAPTER\s+([IVXLC]+-[A-Z])[ \t]*(?:\n|$)(.*)$", re.S)
_HYPHEN_LETTER_FORM = re.compile(r"^\s*(FORM\s+[IVXLC]+-[A-Z])[ \t]*(?=\n|$)(.*)$", re.S)
_SUFFIXED_DECIMAL_LABEL = re.compile(
    r"^\s*(\d{1,4}\s*-\s*[A-Z]{1,2}\s*[.\-]\s*\d{1,3}|\d{1,4}(?:\.\d{1,3}){1,3}\.[A-Z])(?=[\s.])\.?\s*(.*)$", re.S)
_PAREN_LETTER_LABEL = re.compile(
    r"^\s*(?:\d{1,3}\s*\[\s*)?[\"“]?\s*(\d{1,3})\s*\(\s*([A-Z])\s*\)\s*\.?[ \t]*\n?\s*(?=[A-Z\"“])(.*)$", re.S)
_PAREN_LETTER_LABEL_CUT = re.compile(
    r"(?<=\n)[ \t]*(?=(?:\d{1,3}\s*\[\s*)?[\"“]?\s*\d{1,3}\s*\(\s*[A-Z]\s*\)\s*\.?[ \t]*\n?\s*[A-Z\"“])")
_CLAUSE_THEN_ROMANETTE_CUT = re.compile(
    r"(?<=\n)[ \t]*(?=\(\s*[a-z]{1,2}\s*\)[ \t]*\n?[ \t]*\(\s*(?:x{0,3})(?:ix|iv|v?i{1,3})\s*\)\s*[A-Za-z])")
_REPEATED_LETTER_CLAUSE = re.compile(
    r"^\s*" + _AMEND_PREFIX + r"\(\s*(([a-z])\2{2,4})\s*\)\s*(.*)$", re.S)
_BRACKETED_SECTION_NUMBER = re.compile(r"^\s*\d{1,3}\s*\[\s*(\d{1,4})\s*\]\s*\.\s*(?=[A-Z])(.*)$", re.S)
# "1[TABLE [see section 7(1)]": a TABLE heading carrying the substitution
# marker that opens it and the section reference beneath it (doc 4276).
_QUOTED_SCHEDULE_WORD_END = re.compile(
    r"\bfollowing\s+shall\s+be\s+substituted\s*[-:—–,]*\s*(?:namely\s*[:\-—–]*\s*)?"
    r"[\"“]\s*(?:THE\s+)?SCHEDULE\s*(?:[-–]?\s*(?:[IVX]{1,4}|\d{1,2}))?\s*[\"”]"
    r"\s*(?:[\[(]\s*see\s+sections?\s+\d{1,4}[A-Z]?(?:\s*\(\s*[0-9a-z]{1,4}\s*\))*\s*[\])])?\s*$", re.I)
# Profile rule `ordinal_quoted_schedule_word` (unreleased-v4): doc 255: a quoted ordinal schedule word ('"TWELFTH SCHEDULE" (See section 116-A)') owns the table rows.
_ORDINAL_QUOTED_SCHEDULE_WORD_END = re.compile(
    r"\bfollowing\s+shall\s+be\s+substituted\s*[-:—–,]*\s*(?:namely\s*[:\-—–]*\s*)?"
    r"[\"“]\s*(?:THE\s+)?(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|"
    r"TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|SIXTEENTH|SEVENTEENTH|EIGHTEENTH|NINETEENTH|TWENTIETH)\s+SCHEDULE"
    r"\s*[\"”]"
    r"\s*(?:[\[(]\s*see\s+sections?\s+\d{1,4}(?:\s*-?\s*[A-Z])?(?:\s*\(\s*[0-9a-z]{1,4}\s*\))*\s*[\])])?\s*$",
    re.I)
# "4. In the Sindh Finance Act, 1964, for the Seventh Schedule ..." -- the
# amending Act's own next instruction, which closes a substituted Schedule.
_NEXT_AMENDING_SECTION = re.compile(
    r"In\s+the\s+[^.;:]{3,90}?\b(?:Act|Ordinance|Order|Rules|Regulations)\b", re.I)
_REFERENCED_TABLE_HEADING = re.compile(
    r"(?:\d{1,3}\s*\[\s*)?(?:THE\s+)?TABLE\s*[\[(]\s*see\s+(?:sub-?\s*)?"
    r"(?:sections?|rules?|regulations?)\s+\d{1,4}[A-Z]?(?:\s*\(\s*[0-9a-z]{1,4}\s*\))*"
    r"\s*[\])]", re.I)
_QUOTE_BEFORE_BRACKET = re.compile(r"^(\s*\d{1,4}[a-z]?\s*)([\"“])(\s*\[)")
_LOWER_SUFFIX_SUBSECTION = re.compile(
    r"^\s*" + _AMEND_PREFIX + r"\(\s*(\d{1,3}\s*-?\s*[a-z])\s*\)\s*\.?\s*(.*)$", re.S)
_LOWER_SECTION_START = re.compile(r"^\s*(\d{1,4})\s*\.[ \t]*\n[ \t]*(?=[a-z])(.*)$", re.S)
_QUOTED_DEFINITION_START = re.compile(
    r"(?<=\n)[ \t ]*(?=\(\s*\d{1,3}(?:\s*-?\s*[A-Za-z])?\s*\)\s*(?:[\"“]|''))")
_MEMBER_DESIGNATION_END = re.compile(
    r"(?:Chair(?:man|person)|Vice[-\s]*Chair(?:man|person)|Members?"
    r"|Member\s*/\s*Cum[-\s]*Secretary|Secretary)\s*$", re.I)
_ORDINAL_WORD = r"(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)"
_JOINT_SCHEDULE_HEADING = re.compile(
    r"^\s*(?:THE\s+)?(" + _ORDINAL_WORD + r"\s+(?:AND|TO)\s+" + _ORDINAL_WORD + r"\s+SCHEDULES)"
    r"\s*[.\-–—:]?\s*(.*)$", re.S)
_UNBRACKETED_DIVISION_REFERENCE = re.compile(
    r"(?:^|\n)\s*see\s+(?:sub-?)?(?:rules?|sections?|regulations?)\s*\(?\s*\d", re.I)
_BRACKETED_SUB_RULE_REFERENCE = re.compile(
    r"[\[(]\s*see\s+sub-?\s*(?:rules?|sections?|regulations?)\s*\(\s*\d", re.I)
_HYPHEN_SUBSECTION = re.compile(
    r"^\s*" + _AMEND_PREFIX + r"\(\s*(\d{1,3}\s*-\s*[A-Z])\s*\)\s*\.?\s*(.*)$", re.S)
_HYPHEN_CLAUSE = re.compile(
    r"^\s*" + _AMEND_PREFIX
    + r"\(\s*((?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*-\s*"
      r"(?:(?:x{0,3})(?:ix|iv|v?i{1,3})|[A-Z]))\s*\)\s*(.*)$", re.S)
_HYPHEN_LABEL_START = re.compile(
    r"(?<=\n)[ \t ]*(?=(?:\d{1,3}\s*\[\s*[\"“‘]?\s*)?\(\s*(?:\d{1,3}\s*-\s*[A-Z]"
    r"|(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*-\s*(?:(?:x{0,3})(?:ix|iv|v?i{1,3})|[A-Z]))"
    r"\s*\)\s*\.?\s*[\"“‘A-Za-z])")
_LETTERED_PART = re.compile(
    r"^\s*PART\s*[-–—]?\s*([ABDEFGHJKMNOPQRSTUWYZ])(?![A-Za-z])\s*[.:\-–—]?\s*"
    r"(?=\[|\(|$|[A-Z“\"‘])(.*)$", re.S)
_MIXED_LETTERED_PART = re.compile(
    r"^\s*Part\s*[-–—]?\s*([ABDEFGHJKMNOPQRSTUWYZ])(?![A-Za-z])\s*[.:\-–—]?\s*"
    r"(?=\[|\(|$|[A-Z“\"‘])(.*)$", re.S)


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
    r"|(?:\d{1,4}[a-z]?\s*\[\s*){1,3}\d{1,4}\s*[-–]\s*[A-Z]{1,3}\s*\]\s*\.\s*\(" # 3[4[5-A]. (1)
    r"|[\u201c\u2018]\s*\d{1,4}[a-z]?\s*\[\s*\d{1,4}\s*[-–]\s*[A-Z]{1,3}\s*\.\s*[A-Z]" # “2[22-A. Recovery
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

# A footnote marker and amendment bracket can prefix a later subsection in
# the same extracted block (document 220: ``1[(2) It shall...``). Require an
# actual new line. The general _INNER sentence-boundary rule would also split
# ``7. 1[(1) ...`` between the section label and its first subsection.
_INNER_AMEND_SUBSECTION = re.compile(
    r"(?<=\n)[ \t\u00a0]*(?=\d{1,4}[a-z]?\s*\[\s*\(\s*\d{1,3}[A-Z]?\s*\)\s*[A-Za-z])")

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
_RULE_RANGE_REFERENCE = re.compile(
    r"(?:Rules?|Regulations?)\s*\d{1,4}(?:\.\d{1,4})*\s+(?:to|and|&)\s+\d", re.I)
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
_REFERENCE_WORD_TAIL = re.compile(
    r"\b(?:sub-?\s?)?(?:sections?|paragraphs?|clauses?|rules?|regulations?|articles?)$",
    re.I)
# Profile rule `decoded_quote_openers` (unreleased-v2): some Sindh Code text
# layers decode the printed opening quotes as U+2015 "\u2015" and U+2017 "\u2017". Doc
# 2019 s.2 prints "1957; / (b) \u2015Board\u2016 means ..." and (b) never opened: the
# rule above admits only real quotes after the letter.
_INNER_ALPHA_DECODED_QUOTE = re.compile(
    r"(?:(?<=[.;:\u2014\-])\s+|(?<=\n)[ \t\u00a0]*)"
    r"(?=\(\s*(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)\s*[\u2015\u2017])",
    re.I,
)
# Some official text layers use a straight opening apostrophe for a defined
# term. Keep the same line-boundary guard as _INNER_ALPHA so a cross-reference
# in running prose cannot become a new clause.
_INNER_ALPHA_ASCII_QUOTE = re.compile(
    r"(?:(?<=[.;:\u2014\-])\s+|(?<=\n)[ \t\u00a0]*)"
    r"(?=\(\s*(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)\s*')",
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
    # The label can own its line (doc 1847: ``... subsection 8(2)\n9\nAny
    # number of localities ...``) or share the line with a wide column gap.
    # This only exposes a candidate boundary; `_classify_body` still requires
    # ordered TOC and heading corroboration before it becomes a section.
    r"(?:[ \t\u00a0]{2,}|[ \t\u00a0]*\n[ \t\u00a0]*)[A-Z])",
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
_FUSED_PREAMBLE_SECTION = re.compile(
    r"^(Preamble\.)\s*\n\s*(1\s*\.\s*[a-z]\s*\.\s*.*)$",
    re.I | re.S,
)


# Profile rule `lowercase_heading_split` (unreleased-v2): a printed heading
# set in lower case. Doc 2622 p4 prints "... under this Ordinance. / 9.
# indemnity. No suit ..." inside one block; every `_INNER` alternative wants a
# capital after "N. ", so section 9 was never cut out. The line must follow a
# sentence end and a line break, and the lowercase words must close with a
# stop and be followed by the capitalised enacted text -- the shape of a
# heading, not of a wrapped sentence.
_INNER_LOWER_HEADING = re.compile(
    r"(?<=[.;:—\-])[ \t ]*\n\s*"
    r"(?=\d{1,4}\s*\.\s+[a-z][a-z\-]{2,}(?:\s+[a-z][a-z\-,]*){0,8}\s*\.\s*"
    # doc 3635 p8: "11. / repeal.— the efficiency and discipline rules ..."
    # -- a heading closed by a dash may be followed by either case.
    r"(?:[-–—]+\s*[A-Za-z(]|[A-Z(]))")


def _rs_line_item(text: str, cut: int) -> bool:
    """Profile rule `rs_line_item` (unreleased-v4): an item, not an amount.

    Doc 3665's Form PCT-9 prints "1. Current Tax for the year ___ Rs." and on
    the next line "2. Arrears Rs.". The tariff guard keeps a number after
    "Rs." in the cell it belongs to, so item 2 ran into item 1. A one- or
    two-digit number followed on its own line by a capitalised word is item N
    when item N-1 opens a line earlier in the same block.
    """
    if not profile_rule("rs_line_item"):
        return False
    item = re.match(r"(\d{1,2})\.[ \t]+[A-Z][a-z]", text[cut:])
    if not item or int(item.group(1)) < 2:
        return False
    return bool(re.search(r"(?:^|\n)[ \t ]*%d\.[ \t]" % (int(item.group(1)) - 1), text[:cut]))


def _numbered_line_ends_with_no(text: str, cut: int) -> bool:
    """Profile rule `number_abbreviation_line_end` (unreleased-v4): doc 3803's
    Appendix 1.2 prints "2. National Identity Card No. / 3. District." -- the
    line ending in "No." is itself item N-1, so the next line's "N." is the
    next item, not a number after the abbreviation. Doc 4453's "namely:-- No.
    / 2. Administration Bond" has no item 1 before it and keeps no cut."""
    before = re.search(r"(?:^|\n)[ \t ]*(\d{1,3})[ \t]*\.[^\n]*\bNo\.[ \t]*\n\s*$", text[:cut])
    after = re.match(r"\s*(\d{1,3})[ \t]*\.", text[cut:])
    return bool(before and after and int(before.group(1)) + 1 == int(after.group(1)))


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
    fused = (_FUSED_MARGIN_PREFIX.match(text)
             or _FUSED_PREAMBLE_SECTION.match(text))
    if fused and not _FOOTNOTE.match(text):
        # group(2) starts partway into the text; shift the recursion's offsets
        # so they stay relative to the block and not to the tail.
        shift = fused.start(2)
        return ([(fused.start(1), fused.group(1))]
                + [(shift + offset, piece)
                   for offset, piece in subdivide_spans(fused.group(2))])

    # Profile rule `bare_number_schedule_name_row` (unreleased-v4): doc 2731: a block that is only '31. / First Schedule.' is one contents row.
    if (profile_rule("bare_number_schedule_name_row")
            and re.fullmatch(r"\s*\d{1,3}\s*\.\s*\n\s*(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|"
                             r"TENTH)\s+SCHEDULE\s*\.\s*", text, re.I)):
        return [(0, text)]
    lower_heading_cuts = ({m.end() for m in _INNER_LOWER_HEADING.finditer(text)}
                          if profile_rule("lowercase_heading_split") else set())
    if profile_rule("decoded_quote_openers"):
        lower_heading_cuts |= {m.end() for m in _INNER_ALPHA_DECODED_QUOTE.finditer(text)}
    if profile_rule("ascii_quote_openers"):
        lower_heading_cuts |= {m.end() for m in _INNER_ALPHA_ASCII_QUOTE.finditer(text)}
    if profile_rule("quoted_item_label"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r'(?<=\n)[ \t\u00a0]*(?=[\u201c"]\(\s*(?:\d{1,3}|[a-z]{1,2}|[ivxlc]{1,6})'
            r'\s*\)\s*[A-Za-z])', text, re.I)}
    # Profile rule `dotted_omission_stub_cut` (unreleased-v4): doc 3805 p3 prints s.3 as
    # the stub '5[3. .........]' on the next line of s.2(d)'s block; a new line opening a
    # bracketed note number, 'N.' and only leader dots and ']' starts its own unit.
    if profile_rule("dotted_omission_stub_cut"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\d{1,3}\s*\[\s*\d{1,3}[A-Z]?\s*\.[ \t]*\n?[ \t]*"
            r"(?:\.{3,}|\u2026+)[ \t]*\])", text)}
    # Profile rule `dotted_contents_row_cut` (unreleased-v4): doc 4296's contents prints row
    # '26.' followed only by a spaced dotted line; a new line holding only a number, its
    # stop and four or more space-separated dots starts its own unit.
    if profile_rule("dotted_contents_row_cut"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\d{1,3}[A-Z]?\s*\.(?:[ \t]+\.){4,}[ \t]*(?:\n|$))", text)}
    # Profile rule `quoted_definitions_after_omission` (unreleased-v4): doc
    # 2783 s.2 prints the omitted definition (1) as stars, then (2)
    # "Collector" means ... and (3) "defaulter" means ... in one source block.
    # The normal subsection cut expects a letter straight after the label;
    # preserve each quoted term and its citable subsection, only when a
    # preceding omission stub in this block proves the definition context.
    if profile_rule("quoted_definitions_after_omission"):
        omission = re.search(r"(?:\*[ \t]*){3,}", text)
        if omission:
            lower_heading_cuts |= {m.end() for m in re.finditer(
                r'(?<=\n)[ \t\u00a0]*(?=\(\s*\d{1,3}\s*\)\s*[\u201c"]'
                r'\s*[A-Za-z][^\u201d"\n]{1,50}[\u201d"]\s+means\b)',
                text, re.I) if m.start() > omission.end()}
    # Profile rule `tight_first_subsection` (unreleased-v2): doc 1521 prints
    # "10.(1) Health workers shall ..." with no space after the section's
    # full stop, so (1) never parted from the number and s.10 opened no
    # sub-section (1) while (2)-(5) followed. Cut after the number when the
    # block opens with it and "(1) Capital" follows directly.
    if profile_rule("tight_first_subsection"):
        tight = re.match(r"\s*\d{1,4}[A-Z]{0,3}\s*\.(?=\(\s*1\s*\)\s*[A-Z])", text)
        if tight:
            lower_heading_cuts.add(tight.end())
    # Profile rule `marked_clause_opener` (unreleased-v3): doc 1142 p3 prints
    # "... extend to the added area; / 1(b) all laws in force ..." -- a note
    # marker set straight before the clause letter, no bracket. The line
    # starts its own unit; the walk decides, by the letter sequence, whether
    # it is a clause.
    if profile_rule("marked_clause_opener"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"[;:][ \t ]*\n(?:[ \t ]*\n)*[ \t ]*"
            r"(?=\d{1,2}\(\s*[a-z]\s*\)\s)", text)}
    # Profile rule `inblock_footnote_tail` (unreleased-v3): doc 4222 p16's
    # last block holds s.22-D's first line and then, after a blank line, the
    # page's footnote "60Inserted by the Punjab Wildlife ... Act 2025 ...".
    # A line that opens with a note number fused to an amendment verb, after
    # a blank line, starts its own unit, which the footnote grammar then reads
    # as apparatus.
    if profile_rule("inblock_footnote_tail"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t ]*\n[ \t ]*(?=\d{1,3}(?:Inserted|Substituted|Added|Omitted|"
            r"Numbered|Renumbered|Repealed)\s+(?:by|as|for|vide)\b)", text)}
    # Profile rule `paren_amendment_opener` (unreleased-v4): doc 1563 marks
    # amended text with a note number and a round bracket -- "4. 1(The
    # authority having power to register ...", "2(for the registration" --
    # where the openers above expect "1[". Section 4 ran into the paragraph
    # before it.
    if profile_rule("paren_amendment_opener"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?:(?<=[.;:—\-])\s+|(?<=\n)[ \t ]*)"
            r"(?=\d{1,4}\s*\.\s+\d{1,3}\s*\(\s*[A-Z])", text)}
    # Profile rule `hyphen_suffix_labels` (unreleased-v4; see classify): a
    # line opening "(1-A)" or "(a-i)" starts its own unit, unless the line
    # before ends in a reference word ("sub-section / (1-A)").
    if profile_rule("hyphen_suffix_labels"):
        lower_heading_cuts |= {
            m.end() for m in _HYPHEN_LABEL_START.finditer(text)
            if not _REFERENCE_WORD_TAIL.search(text[:m.start()].rstrip())}
    # Profile rule `quoted_definition_cut` (unreleased-v4): doc 2299 sets
    # several definitions in one block -- '(15) "Commissioner" ... / (16)
    # "commencement" used with reference to ...' -- and the sub-section cut
    # wants a letter after the label, so (16) ran into (15). A new line
    # opening "(N)" and a quote starts its own unit when definition N-1 opened
    # in an earlier block -- no "(N-1)" opens a line before it in this text --
    # and not after a reference word. A definitions list held whole in one
    # section's text (docs 3486, 3665, 3794 s.2) is left as it is.
    if profile_rule("quoted_definition_cut"):
        for m in _QUOTED_DEFINITION_START.finditer(text):
            number = int(re.match(r"\(\s*(\d{1,3})", text[m.end():]).group(1))
            if (number >= 2
                    and not re.search(r"(?:^|\n)[ \t ]*(?:\d{1,3}\s*\[\s*)?\(\s*%d\s*(?:-?\s*[A-Za-z])?\s*\)"
                                      % (number - 1), text[:m.start()])
                    and not _REFERENCE_WORD_TAIL.search(text[:m.start()].rstrip())):
                lower_heading_cuts.add(m.end())
    # Profile rule `side_noted_definition_cut` (unreleased-v4): (doc 3649 s.3)
    if profile_rule("side_noted_definition_cut"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\(\s*\d{1,3}\s*\)\s*[\u2018\u201c\"']\s*([A-Za-z][A-Za-z ,'-]{0,60}?)\s*\.?\s*"
            r"[\u2019\u201d\"']{1,2}\s*\.?\s*[\u201c\"\u2018]\s*\1\s*\.?\s*[\u2019\u201d\"']{1,2}\s*"
            r"(?:means|includes|implies)\b)", text, re.I)}
    # Profile rule `closed_marked_first_subsection` (unreleased-v4): doc 2299
    # s.7 prints "7. / 5[(1)] Where this Act ... (2) Where any Central Act"
    # -- the substituted label closed in its own bracket -- and the marked
    # sub-section cut wants a letter straight after "(1)", so (1) stayed in
    # the section's text while (2) opened. A line opening "N[(1)]" and a
    # capital starts its own unit.
    if profile_rule("closed_marked_first_subsection"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t ]*(?=\d{1,3}\s*\[\s*\(\s*1\s*\)\s*\]\s*[A-Z])", text)}
    # Profile rule `bracketed_section_number` (unreleased-v4; see classify):
    # a line opening "1[11]. Meetings ..." starts its own unit.
    if profile_rule("bracketed_section_number"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t ]*(?=\d{1,3}\s*\[\s*\d{1,4}\s*\]\s*\.\s*[A-Z])", text)}
    # Profile rule `lowercase_section_start` (unreleased-v4; see classify):
    # "19." alone on a line and then a lower-case word starts its own unit.
    if profile_rule("lowercase_section_start"):
        lower_heading_cuts |= {
            m.end() for m in re.finditer(r"(?<=\n)[ \t ]*(?=\d{1,4}\s*\.[ \t]*\n[ \t]*[a-z])", text)
            if not _REFERENCE_WORD_TAIL.search(text[:m.start()].rstrip())}
    # Profile rule `percent_led_item` (unreleased-v4): doc 3794 s.6 lists the
    # Board's members "1. Minister of Social Welfare ..." to "9. Eminent
    # scholar ..." and then "10. 50% of the members of the board shall be
    # women." Every cut wants a capital after the number, so item 10 ran into
    # item 9. A line opening "N." and a percentage followed by a lower-case
    # word is item N when item N-1 opens a line earlier in the same block.
    if profile_rule("percent_led_item"):
        for m in re.finditer(r"(?<=\n)[ \t ]*(\d{1,3})[ \t]*\.[ \t]*\n?[ \t]*"
                             r"(?=\d{1,3}[ \t]*%[ \t]+[a-z])", text):
            prior = int(m.group(1)) - 1
            if prior >= 1 and re.search(r"(?:^|\n)[ \t ]*%d[ \t]*\." % prior, text[:m.start()]):
                lower_heading_cuts.add(m.start(1))
    # Profile rule `tight_first_clause` (unreleased-v3): doc 2818 prints "25.
    # Issue of certificate and provisional order.(a) When a certificate is
    # required ..." -- (a) set against the heading's full stop, so it never
    # opened and (b) followed it as the section's first clause. Rule 14 prints
    # "Inspection at special times. .(a) No examination ...".
    if profile_rule("tight_first_clause"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\.)(?=\(\s*a\s*\)\s*[A-Z])", text)}
    # Profile rule `decoded_dash_first_subsection` (unreleased-v3): doc 2923
    # closes its headings with U+2015 -- "8. Composition of the Commission.―
    # (1) The Commission shall consist of ..." and "7. ... Commission.― 2[(1)
    # The Federal Government ..." -- where the openers above expect an em
    # dash, so sub-section (1) never parted from the heading and (1)'s items
    # hung on the section. Cut after the bar before a capitalised (1).
    if profile_rule("decoded_dash_first_subsection"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=[―—])[ \t ]*(?=(?:\d{1,3}\s*\[\s*)?\(\s*1\s*\)\s*[A-Z])", text)}
    # Profile rule `marked_first_subsection` (unreleased-v4): doc 3144 prints
    # "18. Non-disclosure of confidential requests for assistance.—(1)
    # 1[Under the said Act], a person ..." -- the note marker between (1) and
    # its capital -- so (1) stayed in the heading's text while (2) and (3)
    # opened. Cut after the dash before "(1) N[Capital". Doc 3177 closes its
    # headings with an en dash: "3. ... alienations.– (1) 2[Save as ...".
    if profile_rule("marked_first_subsection"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=[―—–])[ \t ]*(?=\(\s*1\s*\)\s*\d{1,3}\s*\[\s*[A-Z\"“])", text)}
    # Profile rule `numbered_marked_first_subsection` (unreleased-v4): doc 1295
    # prints right-margin headings and no heading dash, so where (1) opens with
    # amended text -- '4. / (1) / 6[The Provincial Government] ...' -- (1) stayed
    # in the section's text while (2) opened. Cut after the number.
    if profile_rule("numbered_marked_first_subsection"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"^\s*\d{1,4}[A-Z]{0,2}[ \t]*\.[ \t ]*\n?[ \t ]*"
            r"(?=\(\s*1\s*\)[ \t ]*\n?[ \t ]*\d{1,3}\s*\[\s*[A-Za-z])", text)}
    # Profile rule `quoted_first_definition` (unreleased-v4): doc 1295 s.3 'In
    # this Act-- / (1) / "furnace" means ...': a new line opening (1) and a quote
    # after text ending in a dash or colon starts its own unit.
    if profile_rule("quoted_first_definition"):
        for m in _QUOTED_DEFINITION_START.finditer(text):
            if (re.match(r"\(\s*1\s*\)", text[m.end():])
                    and re.search(r"(?:--|[—–:])[ \t ]*(?:\n[ \t ]*)*$", text[:m.start()])):
                lower_heading_cuts.add(m.end())
    # Profile rule `marked_suffixed_definition` (unreleased-v4): doc 1295's
    # inserted definition '2[(1A)] "Flue" ...' on a new line starts its own unit.
    if profile_rule("marked_suffixed_definition"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t ]*(?=\d{1,3}\s*\[\s*\(\s*\d{1,3}\s*-?\s*[A-Z]\s*\)\]?\s*[\"“])", text)}
    # Profile rule `bare_trailing_label_cut` (unreleased-v4): doc 2452's contents
    # prints '20. Regulations. / 21.' -- row 21 has no name; a label alone on the
    # last line, whose predecessor opens a line earlier in the block, is cut off.
    if profile_rule("bare_trailing_label_cut"):
        for m in re.finditer(r"(?<=\n)[ \t ]*(\d{1,3})[ \t]*\.[ \t ]*(?:\n[ \t ]*)*$", text):
            prior = int(m.group(1)) - 1
            if prior >= 1 and re.search(r"(?:^|\n)[ \t ]*%d[ \t]*\.[ \t]*\S" % prior, text[:m.start()]):
                lower_heading_cuts.add(m.start(1))
    # Profile rule `marked_clause_cut` (unreleased-v4): doc 3144 s.2 inserts a
    # definition inside the block of the one before it -- "(v) the freezing or
    # seizure of proceeds ...; or / 2[(l) “criminal offence” means ..." -- and
    # only sub-sections behind a note marker ("1[(2) The ...") had a cut, so
    # (l) ran into (k)(v). A new line opening "N[(letter)" or "N[(roman)"
    # followed by a word or a quote starts its own unit.
    if profile_rule("marked_clause_cut"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t ]*(?=\d{1,3}[a-z]?\s*\[\s*\(\s*(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))"
            r"\s*\)\s*[A-Za-z\"“‘])", text)}
    # Regulation 5 printed alone above sub-regulation 5.1 is two units,
    # not the compound label "5. 5.1". Cut only when the integer repeats and
    # the decimal child begins on the next printed line (document 3069 p4).
    if profile_rule("regulation_then_decimal_child"):
        lower_heading_cuts |= {m.start(2) for m in re.finditer(
            r"(?m)^[ \t]*(\d{1,4})[ \t]*\.[ \t]*\n[ \t]*"
            r"(\1\.\d{1,3}[ \t]+[A-Z])", text)}
    # Profile rule `sequence_omission_stub` (unreleased-v3): doc 2923 p4's
    # "CONSTITUTION OF SUPARCO / 1[(3)* * * * * * *]" is one block; the stub
    # line starts its own unit (the walk decides whether it is a section).
    if profile_rule("sequence_omission_stub"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t ]*(?=\d{0,3}\s*\[\s*\(\s*\d{1,4}\s*\)\s*(?:\*\s*){3,})", text)}
    # Profile rule `subsection_then_clause_cut` (unreleased-v4): doc 1515
    # prints reg 11(2) as "(2) (i) Where recruitment is to he made ..." on
    # the line after (1)'s last clause; the sub-section cut wants a letter
    # after "(2)", so (2) never opened and its (i)-(ii) joined (1)'s clauses.
    # A line opening a sub-section number followed at once by a clause label
    # and a capital starts its own unit.
    if profile_rule("subsection_then_clause_cut"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"(?<=\n)[ \t]*(?=\(\s*\d{1,3}\s*\)\s*\(\s*(?:[ivx]{1,4}|[a-z])\s*\)\s*[A-Z])", text)}
    # Profile rules `parenthesised_letter_label` and `clause_then_romanette_cut`
    # (unreleased-v4, doc 4453 Schedule I): a line opening "6(A)." starts the
    # inserted article; a line opening "(a)" followed at once by "(i) when ..."
    # (Arts. 33 and 35) starts clause (a) -- the clause cut wants a word after
    # the label, so (a) stayed in the article's own text.
    if profile_rule("parenthesised_letter_label"):
        lower_heading_cuts |= {m.end() for m in _PAREN_LETTER_LABEL_CUT.finditer(text)}
    if profile_rule("clause_then_romanette_cut"):
        lower_heading_cuts |= {m.end() for m in _CLAUSE_THEN_ROMANETTE_CUT.finditer(text)}
    if profile_rule("lettered_paragraph_sequence") and _LETTERED_SEQUENCE.get():
        lower_heading_cuts |= {m.end() for m in _LETTERED_CUT.finditer(text)}
    # Profile rule `bracketed_repeal_stub_cut` (unreleased-v4): doc 3284 prints
    # its repealed sections as stubs inside the block of the text before them:
    # "... proposing so to apply it. / 7. [Exercise by Governor General in
    # Council of powers of Local Government.] Rep. by A.O., 1937." The grammar
    # reads the stub as section 7 but no cut opened it, so it ran into s.6. A
    # line opening "N. [" whose bracket closes and is followed by "Rep" or
    # "Omitted", after a sentence end, starts its own unit.
    if profile_rule("bracketed_repeal_stub_cut"):
        lower_heading_cuts |= {m.end() for m in re.finditer(
            r"[.;:\]][ \t]*\n(?:[ \t]*\n)*[ \t]*"
            r"(?=\d{1,4}[A-Z]?[ \t]*\.[ \t]*\[[^\]\n]{3,200}\][ \t]*\.?[ \t]*"
            r"(?:Rep\b|Rep\.|Repealed\b|Omitted\b))", text)}
    # Profile rule `no_cut_after_number_abbreviation` (unreleased-v4): doc
    # 4453 s.29(a) lists Schedule I articles as "No.    2. (Administration
    # Bond), No. 6 ...": the sentence-end cut fired after the abbreviation
    # "No." and opened the article numbers as units.
    # Profile rule `contents_row_decimal_cut` (unreleased-v4): doc 3103 prints decimal
    # paragraphs '4.1 Constitution ...' mid-block; a new line opening a decimal label and
    # word that a one-line contents row of the same document prints starts its own unit.
    if profile_rule("contents_row_decimal_cut") and _CONTENTS_DECIMAL_ROWS.get():
        for _m in re.finditer(r"(?<=\n)[ \t\u00a0]*(?=(\d{1,2}\.\d{1,2})[ \t]+([A-Z][A-Za-z-]*))", text):
            if (_m.group(1), _m.group(2).casefold()) in _CONTENTS_DECIMAL_ROWS.get():
                lower_heading_cuts.add(_m.end())
    if profile_rule("repeated_decimal_label_cut") and _REPEATED_DECIMAL_LABELS.get():
        for _m in re.finditer(r"\n[ \t\u00a0]*\n(?:[ \t\u00a0]*\n)*[ \t\u00a0]*(?=(\d{1,2}(?:\.\d{1,2}){1,3})\.?"
                              r"(?:[ \t\u00a0]+|[ \t\u00a0]*\n(?:[ \t\u00a0]*\n)*[ \t\u00a0]*)[A-Z*])", text):
            if _m.group(1) in _REPEATED_DECIMAL_LABELS.get():
                lower_heading_cuts.add(_m.end())
    # Profile rule `lowercase_hyphen_label_cut` (unreleased-v4): (doc 3803)
    if profile_rule("lowercase_hyphen_label_cut"):
        lower_heading_cuts |= {
            m.end() for m in re.finditer(
                r"(?<=\n)[ \t\u00a0]*(?=\(\s*\d{1,3}\s*-\s*[a-z]\s*\)[ \t]*\n?[ \t]*[A-Z\"\u201c])", text)
            if not _REFERENCE_WORD_TAIL.search(text[:m.start()].rstrip())}
    # Profile rule `ditto_item_cut` (unreleased-v4): (doc 3803)
    if profile_rule("ditto_item_cut"):
        for m in re.finditer(r"(?<=\n)[ \t\u00a0]*\((\d{1,2})\)[ \t]*(?=-{3,}[ \t]*do\b)", text):
            prior = int(m.group(1)) - 1
            if prior >= 1 and re.search(r"(?:^|\n)[ \t]*\(%d\)" % prior, text[:m.start()]):
                lower_heading_cuts.add(m.start(1) - 1)
    # Profile rule `dotted_nameless_contents_row` (unreleased-v4): (doc 3803)
    if profile_rule("dotted_nameless_contents_row"):
        for m in re.finditer(r"(?<=\n)[ \t]*(\d{1,3})[ \t]*\.[ \t]*\n[ \t]*\.{8,}[ \t]*\n[ \t]*(\d{1,3})[ \t]*\.", text):
            if int(m.group(2)) == int(m.group(1)) + 1:
                lower_heading_cuts.add(m.start(1))
    # Profile rule `four_letter_section_suffix` (unreleased-v4): (doc 4447): the same opener on a new line
    if profile_rule("four_letter_section_suffix"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,3}\s*\[\s*)?\d{1,4}[A-Z]{4}\s*\.\s*(?=[A-Z]))", text)}
    # Profile rule `bare_omission_stub` (unreleased-v4): (doc 4447 s.46 p96): a new line opening a sub-section label, with no
    # bracket or behind two note markers, and only stars ("(4) \n***", "600[601(2A)***]")
    if profile_rule("bare_omission_stub"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,3}\s*\[\s*\d{1,3})?\(\s*\d{1,3}[A-Z]{0,2}\s*\)[ \t]*\n?[ \t]*(?:\*\s*){3,})", text)}
    # Profile rule `column_head_line_cut` (unreleased-v4): (doc 4447 pp185-207): a schedule title, its reference and a table's
    # column heads on one line ("S. No. Description ... (1) (2) (3)") in one block; the column-head line
    # starts its own unit, so the title is not read as the table's header
    if profile_rule("column_head_line_cut"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:S\.\s*No\.?|S\.No\.?|Serial\s+No\.?)\s[^\n]*\(\s*1\s*\)[^\n]*\(\s*2\s*\))", text)}
    # Profile rule `roman_stub_item_cut` (unreleased-v4): (doc 4447 Fifth Schedule p128): a new line opening a romanette whose
    # entry is omitted -- dots, stars, a bracket or nothing ("762[(x) ...", "(xvii)", "(xviii) 764[***]")
    if profile_rule("roman_stub_item_cut"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,4}\s*\[\s*)?\(\s*(?=[ivx])(?:x{0,3})(?:ix|iv|v?i{0,3})\s*\)[ \t]*(?:\.{3}|\u2026|\*{3}|\[|\d{1,4}\s*\[))", text)}
    # Profile rule `stub_row_cut` (unreleased-v4): (doc 4447 Schedules): a new line opening a row serial whose entry is a bracketed
    # omission ("744[50. [***] omitted ...", "769[17. [***] omitted")
    if profile_rule("stub_row_cut"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,4}\s*\[\s*)?\d{1,3}[A-Z]?\s*\.\s*\[\s*(?:\*{3,}|\.{3,}|omitted\b))", text)}
    # Profile rule `four_digit_marker_label_cut` (unreleased-v4): (doc 4447 pp204-206): a new line opening a FOUR-digit note marker,
    # its bracket and a clause label ("1010[(ix) \nSupply of sand ...")
    if profile_rule("four_digit_marker_label_cut"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\d{4}\s*\[\s*\(\s*(?:[a-z]{1,2}|(?=[ivx])(?:x{0,3})(?:ix|iv|v?i{0,3}))\s*\)\s*[A-Za-z\"\u201c])", text)}
    if profile_rule("range_stub_row"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,4}\s*\[\s*|\[\s*)?(?:\d{1,3}[A-Z]?[ \t]*(?:to|&)[ \t]*\d{1,3}[A-Z]?)[ \t]*\]?[ \t]*\.?[ \t]*(?=\[\s*(?:\.{3,}|\*{3,})|\*{3,}))", text)}
    if profile_rule("stacked_marker_row"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,4}\s*\[\s*){2,}\d{1,3}[A-Z]?\s*\.[ \t]*(?=\*{3,}|\[\s*\*{3,}))", text)}
    if profile_rule("marked_quoted_label"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\d{1,4}\s*\[\s*[“\"]\(\s*\d{1,3}[A-Z]?\s*\)[ \t]*(?=[A-Z]))", text)}
    # Profile rule `figure_led_item` (unreleased-v4): (doc 4447): the same opener on a new line
    if profile_rule("figure_led_item"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,4}\s*\[\s*)?\d{1,3}[A-Z]?\s*\.[ \t]+(?=\d-[A-Z]|\d{4}(?:\.\d{2,4})?[ \t]*(?:\n|$)))", text)}
    # Profile rule `capital_letter_item` (unreleased-v4): (doc 4447): the same openers on a new line
    if profile_rule("capital_letter_item"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\(\s*[A-Z]\s*\)\s*\.[ \t]+(?=[A-Z])|[A-Z]\.[ \t]+(?=[A-Z]{3,}\b(?:[^\n:]*[^\n:.\s])?[ \t]*(?:\n|$))|[A-Z]\.[ \t]+(?=[A-Za-z][^\n]{0,60}\d%)))", text)}
    # Profile rule `schedule_tables_annexes_parts` (unreleased-v4): (doc 4447): a "Table-2" title alone on its line starts a unit
    if profile_rule("schedule_tables_annexes_parts"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,4}\s*\[\s*)?(?:TABLE\s*[-–]\s*(?:\d{1,2}|[IVX]{1,4}))\b[ \t]*(?:\n|\*{3,}))", text, re.I)}
        # ... a schedule's conditions heading or "Note:" paragraph after its table (pp197-207)
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:[A-Z][A-Z,]*\s+){1,5}CONDITIONS[ \t]*\n|Procedure\s+and\s+conditions\s*:?\s*[-\u2013\u2014]*[ \t]*\n|Note\s*:\s+[A-Z]|Notes\s*:\s*[-\u2013\u2014]+[ \t]*\n)", text)}
        # ... and an Annex title behind a note marker, or lettered ("937[\u201cAnnex-A", "Annex-B")
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,4}\s*\[\s*[\"\u201c]?ANNEX(?:URE)?(?:\s*[-\u2013]\s*(?:[A-Z]|[IVX]{1,4})\b)?|[\"\u201c]?ANNEX\s*[-\u2013]\s*(?:[A-Z]|[IVX]{1,4})\b)[ \t]*\n)", text, re.I)}
    # Profile rule `high_ordinal_schedule` (unreleased-v4): (doc 4447): the same heading on a new line
    if profile_rule("high_ordinal_schedule"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,4}\s*\[\s*)?(?:THE\s+)?(?:(?:EIGHTH|EIGHT|NINTH|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH)\s+SCHEDULE)[”\"]?[ \t]*[.\-–—:]?)", text, re.I)}
        # ... and a FIRST..SEVENTH title behind a note marker and its "The" ("728[The THIRD SCHEDULE", p123)
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\d{1,4}\s*\[\s*The\s+(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH)\s+SCHEDULE\b)", text)}
    # Profile rule `e_prefix_section_start` (unreleased-v4): (doc 4447): the same opener on a new line
    if profile_rule("e_prefix_section_start"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,3}\s*\[\s*)?\d{1,3}[A-Z]{0,2}\s*\.\s+(?=e-[a-z]{3,}))", text)}
    # Profile rule `fbr_definition_label` (unreleased-v4): (doc 4447 s.2): a new line opening a definition's label
    if profile_rule("fbr_definition_label"):
        for _m in re.finditer(r"(?<=\n)[ \t\u00a0]*(?=(?:(?:\d{0,3}\s*\[\s*|\d{1,3}(?=\())[“\"]?\s*\(\s*\d{1,3}\s*[A-Z]{0,3}\s*\)\s*\]?[ \t]*\n?[ \t]*|[“\"]?\s*\(\s*\d{1,3}\s*[A-Z]{2,3}\s*\)\s*\]?[ \t]*\n?[ \t]*)(?:[“\"][^”\"\n]{1,80}[”\"][\s\S]{0,80}?\b(?:means?|includes?|shall|in\s+relation\s+to)\b|the\s+expression\s+[“\"]))", text):
            if not _REFERENCE_WORD_TAIL.search(text[:_m.start()].rstrip()):
                lower_heading_cuts.add(_m.end())
    # ... and a plain label alone on its line before the quoted term, only in a block that also prints a
    # definition label behind a note marker (the amended FBR definition lists)
    if profile_rule("fbr_definition_label") and re.search(r"(?:\d{1,3}\s*\[\s*[“\"]?\s*|\d{1,3}(?=\())\(\s*\d{1,3}\s*[A-Z]{0,3}\s*\)|\(\s*\d{1,3}[A-Z]{1,3}\s*\)", text):
        for _m in re.finditer(r"(?<=\n)[ \t\u00a0]*(?=[“\"]?\s*\(\s*\d{1,3}\s*[A-Z]?\s*\)\s*\]?[ \t]*\n[ \t]*(?:[“\"][^”\"\n]{1,80}[”\"][\s\S]{0,80}?\b(?:means?|includes?|shall|in\s+relation\s+to)\b|the\s+expression\s+[“\"]))", text):
            if not _REFERENCE_WORD_TAIL.search(text[:_m.start()].rstrip()):
                lower_heading_cuts.add(_m.end())
    # Profile rule `label_then_marked_text_cut` (unreleased-v4): (doc 4447): a new line opening a bare label whose text opens
    # with an amendment note marker and bracket; or such a label inside its own closed bracket
    # ("691[(1)] 692[The Board] may ...", s.71 p116)
    if profile_rule("label_then_marked_text_cut"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,3}\s*\[\s*\(\s*\d{1,3}\s*\)\s*\]|\(\s*(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3})|\d{1,3}[A-Z]{0,2})\s*\))"
            r"[ \t]*\n?[ \t]*\d{1,3}\s*\[\s*(?:[A-Za-z]|[.\u2026]))", text)
            if not _REFERENCE_WORD_TAIL.search(text[:_m.start()].rstrip())}
    # Profile rule `marked_proviso_cut` (unreleased-v4): (doc 4447): a new line opening a note marker, its bracket and Provided
    if profile_rule("marked_proviso_cut"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\d{3}\s*\[?\s*Provided\b)", text)}
        # a two-digit marker only after the FBR copy's substituted colon "55[:]." on the line before
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"\d{1,3}\[:\]\.[ \t]*\n(?:[ \t]*\n)*[ \t\u00a0]*(?=\d{1,2}\s*\[\s*Provided\b)", text)}
    # Profile rule `bare_marker_label` (unreleased-v4): (doc 4447): the same shape on a new line
    if profile_rule("bare_marker_label"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\[\s*\d{1,3}(?=\(\s*(?:\d{1,3}[A-Z]{0,2}|[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)[ \t]*\n?[ \t]*[A-Za-z])|\d{1,3}(?=\(\s*(?:\d{1,3}[A-Z]{0,2}|[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)[ \t]*\n?[ \t]*[A-Z])|\d{3}(?=\(\s*(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)[ \t]*\n?[ \t]*[a-z])))", text)
            if not _REFERENCE_WORD_TAIL.search(text[:_m.start()].rstrip())}
    # Profile rule `multi_letter_subsection` (unreleased-v4): (doc 4447): the same label on a new line
    if profile_rule("multi_letter_subsection"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=(?:\d{1,3}\s*\[\s*)?\(\s*\d{1,3}[A-Z]{2,3}\s*\)\s*\]?[ \t]*\n?[ \t]*(?=[A-Z“\"]|\*\s*\*\s*\*))", text)
            if not _REFERENCE_WORD_TAIL.search(text[:_m.start()].rstrip())}
    # Profile rule `marked_lettered_omission_stub` (unreleased-v4): (doc 4447 p34): a new line opening a note marker,
    # its bracket, a clause label and only stars ("237[(iv) ***]")
    if profile_rule("marked_lettered_omission_stub"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\d{1,3}\s*\[\s*\(\s*(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)\s*\*{3,})", text)}
    # Profile rule `bare_bracket_clause_cut` (unreleased-v4): (doc 4447 p31): a new line opening an amendment bracket with no
    # note marker and a clause label ("[(a) goods exported ...") or a sub-section label ("[(1B) The ...", p94)
    if profile_rule("bare_bracket_clause_cut"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\[\s*\(\s*(?:(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)\s*[A-Za-z]|\d{1,3}[A-Z]{1,2}\s*\)\s*[A-Z]))", text)}
    # Profile rule `inserted_three_letter_clause` (unreleased-v4): (doc 4447): the same label on a new line
    if profile_rule("inserted_three_letter_clause"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\d{1,3}\s*\[\s*\(\s*[a-z]{2}a\s*\)\s*(?=[a-z]))", text)}
    # Profile rule `closed_marked_clause_cut` (unreleased-v4): (doc 4447 s.22(1) p51): a new line opening "340[(d)] records ..."
    if profile_rule("closed_marked_clause_cut"):
        lower_heading_cuts |= {_m.end() for _m in re.finditer(
            r"(?<=\n)[ \t\u00a0]*(?=\d{1,3}\s*\[\s*\(\s*(?:[a-z]{1,2}|(?:x{0,3})(?:ix|iv|v?i{1,3}))\s*\)\s*\]\s*[A-Za-z])", text)}
    no_after_no = profile_rule("no_cut_after_number_abbreviation")
    raw_cuts = (lower_heading_cuts
                | {m.end() for m in _INNER.finditer(text)
                   if not (no_after_no and re.search(r"\bNo\.\s*$", text[:m.end()])
                           and not (profile_rule("number_abbreviation_line_end")
                                    and _numbered_line_ends_with_no(text, m.end())))}
                | {m.end() for m in _INNER_AMEND_SUBSECTION.finditer(text)}
                | {m.end() for m in _INNER_DASH_SECTION.finditer(text)}
                | {m.end() for m in _INNER_RULE.finditer(text)
                   # Profile rule `rule_range_not_opener` (unreleased-v4):
                   # doc 2418 rule 11-A.6 reads "Rules 9.12 to 9.27 of the
                   # Punjab Distillery Rules ... shall apply": a line opening
                   # with a range of rule numbers is a reference, not rule 9.
                   if not (profile_rule("rule_range_not_opener")
                           and _RULE_RANGE_REFERENCE.match(text, m.end()))}
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
            and re.match(r"\d{1,4}\s*\.", text[c:])
            and not _rs_line_item(text, c))
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
        or re.search(r"(?:^|\n)\s*Notes?\.\s*$", text[:c], re.I)
        # Profile rule `wrapped_bracket_reference` (unreleased-v3): a line
        # that ends in a reference word wraps its bracketed number onto the
        # next line -- doc 1521 s.17(1) "... of section 7, sub-section / (1)
        # of section 8", doc 2983 "set out in sub-paragraph / (3) shall
        # participate". A lower-case word after the bracket continues the
        # sentence; an opener starts with a capital.
        or (profile_rule("wrapped_bracket_reference")
            and _REFERENCE_WORD_TAIL.search(text[:c].rstrip())
            and re.match(r"\(\s*[0-9A-Za-z]{1,6}\s*\)\s*[a-z]", text[c:]))))
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
                or _SPLIT_NOTE_BODY.match(body)
                # `_SPLIT_NOTE_BODY` is a list of literal note openings
                # collected one document at a time, so a note the same
                # consolidation prints in a slightly different order -- an
                # extraction artefact as small as the doubled dot in doc
                # 4451's ".Substituted by the Finance Ordinance, 2000.." --
                # falls out of it and takes the whole block with it, because
                # this test must hold for EVERY item.  `_EDITORIAL_NOTE` asks
                # the general question instead: editorial verb, then `by`,
                # then the instrument that did the amending.  The run still
                # needs two items matching the narrow `_FOOTNOTE` before this
                # is consulted at all, so it widens what a proved run may
                # contain and never what proves one.
                or _EDITORIAL_NOTE.search(unquoted))


# Editorial provenance vocabulary for a note already proved to sit inside a
# footnote run.  It is deliberately broader than `_FOOTNOTE`, which must stand
# alone with no other evidence and therefore only recognises an opening verb.
# Here the run has already been proved by the neighbouring lines, so the only
# question left for this line is whether it is of the same kind -- a reference
# to a source, an amending instrument, a notification, a Code volume -- rather
# than enacted text.  Each alternative names an instrument, an editorial
# abbreviation or a citation apparatus; none of them is a form an operative
# provision takes.  `Gazette` alone is NOT admitted: statutes say "published in
# the Official Gazette" in their own operative text.
_EDITORIAL_NOTE = re.compile(
    r"(?:"
    r"\bibid\b"
    r"|\bw\.\s*e\.\s*f\.\s*\d"
    # The Adaptation Order abbreviation is printed with and without its
    # closing stop: doc 2789's "Omitted vide A.O, 1949" beside "A.O., 1937".
    r"|\bA\.\s*O\b\.?\s*,?\s*(?:of\s+)?1[89]\d\d\b"
    r"|\bPakistan\s+Code\b"
    r"|\bCentral\s+Acts?\s*,"
    # "Gazettee" is how several consolidations spell it (doc 2034 page 5).
    r"|\bGazett?e+\s+of\s+(?:India|Pakistan)\b"
    r"|\bsee\s+(?:the\s+)?Gazett?e+\b"
    # The editorial cross-reference: "For delegation of powers ... see
    # Gazettee of India, 1905", "For modifications of this provision ... see
    # s. 3".  Anchored at the start of the note and requiring `see`, which is
    # the frame; an operative provision does not open "For ... see".
    r"|^\s*For\b[^;]{0,220}?\bsee\b"
    r"|\b(?:See\s+)?[Nn]ow\s+the\b[^.]{0,90}"
      r"\b(?:Act|Code|Ordinance|Order)\b"
    r"|\bFor\s+notification\b"
    r"|\bNo\s+[Nn]otification\s+has\s+been\s+issued\b"
    # An editorial verb is not enough on its own: an amending Act's own
    # section says "is substituted" in the same words.  What an editorial
    # note always carries and an operative provision does not is the NAMED
    # instrument that did the amending -- "Subs. by the Finance Act, 2006",
    # "Ins. by Sind Ord. LXVIII of 1984".  Require the verb, then `by`/`vide`,
    # then an instrument word, all inside one clause.
    r"|\b(?:subs|ins|add|del|rep|amended|substituted|inserted|added|"
      r"deleted|omitted|repealed|re[- ]?numbered)\b[^;]{0,50}?"
      # `vide` without its trailing boundary: extraction glues it to the
      # instrument it cites ("Omitted videOrd. No. XXVII. of 1981", doc 2789).
      r"\b(?:by\b|vide|ibid\b)[^;]{0,70}?"
      r"\b(?:Acts?|Ordinances?|Ord|Orders?|Regulations?|Rules?|"
      r"Notification|Adaptation|Amendment|Sch|Code|ibid)\b"
    r")", re.I)


def _run_member_is_apparatus(text: str) -> bool:
    """Is this ONE note of a proved footnote run itself apparatus?

    Membership of a run is evidence about the PAGE, not about this block: a
    page can set an operative provision immediately above its notes and the
    run test would still pass on the notes alone.  So each block must show
    provenance of its own, and must show no unquoted operative modality at
    all, before it is demoted out of the citable slot.

    Where neither is settled the answer is False and the block stays a
    section.  That asymmetry is deliberate.  A footnote wrongly left citable
    is a visible S7 collision that a reader can adjudicate; a section wrongly
    demoted is silently uncitable law, which is INV-4 breakage and nothing
    downstream reports it.
    """
    stripped = text.strip()
    body = re.sub(r"^\s*\d{1,3}\s*[.):-]?\s*", "", stripped, count=1)
    # A note is short.  The ceiling is not the test -- it is a refusal to
    # decide about a block long enough to be a provision.
    if not body or len(body) > 1200:
        return False
    # A provision REPEALED IN SITU prints its own name in brackets and then
    # the repeal formula: doc 1927's "12. [Condition as to sale of land
    # acquired under the Act ...]---Repealed by Punjab Act VIII of 1926."  Word
    # for word that is the vocabulary of an editorial note, and it is a section
    # -- a citable, repealed one, which INV-5 needs to keep answering "as at a
    # date".  A note names no provision of its own, so the bracketed or quoted
    # opening is the discriminator.  Where it is present, abstain.
    if re.match(r'^\s*[\[\u201c\u2018"\']', body):
        return False
    # Past-tense editorial references quote the very words they replaced, and
    # those quotations routinely contain "shall".  Outside the quotation marks
    # operative modality contradicts apparatus; abstain rather than swallow an
    # amendment.  Same rule, same reason, as `_split_note_is_apparatus`.
    unquoted = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d|\u2018[^\u2019]*\u2019|\'[^\']*\'',
                      "", body)
    # "May" is the one month name that is also a modal verb, and an editorial
    # note is mostly dates: doc 3892's "The word 'Sind' omitted ibid, s. 3
    # (iii) (b) (w.e.f. 30th May, 1951)" was refused as operative text by the
    # modality test alone.  Remove May only where it is written as a date --
    # against a day or a year -- so a genuine "may" keeps its veto.
    dated = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)?\s+May\b"
                   r"|\bMay\s*,?\s*(?:\d{1,2}\s*,?\s*)?(?:1[89]|20)\d\d\b",
                   " ", unquoted, flags=re.I)
    # A note that ANNOUNCES a quotation of the text it replaced -- "Subs by
    # the W.P. Ordinance 3 of 1968 for the amended sub-section (1) which read
    # as the Commissioner shall be the court of wards ..." (doc 2034 page 5),
    # "At the time of omission this proviso was as under:-" -- often prints
    # that old text without quotation marks.  The announcing phrase is the
    # quotation mark; drop what follows it.  Only these announcing frames
    # count, and only AFTER an editorial verb and its instrument have already
    # appeared before the frame, so an operative provision that happens to
    # say "read as" keeps its modality veto.
    announced = re.search(
        r"\b(?:which|that)\s+(?:read|reads|ran|stood)\s+(?:as|thus)\b"
        r"|\b(?:was|were|stood|read)\s+as\s+(?:under|follows)\b",
        dated, re.I)
    if announced and _EDITORIAL_NOTE.search(dated[:announced.start()]):
        dated = dated[:announced.start()]
    if re.search(r"\b(?:shall|must|may|will)\b", dated, re.I):
        return False
    return bool(_FOOTNOTE.match(stripped)
                or _SPLIT_NOTE_BODY.match(body)
                or _EDITORIAL_NOTE.search(unquoted))


def _every_inline_note_is_apparatus(lines: list[str]) -> bool:
    """Every logical note in an inline run, on its own evidence.

    `_is_footnote_run` asks about the block -- enough numbered lines, ascending
    and distinct, two of them carrying provenance.  This asks about each item
    in it, which is the question that matters before the WHOLE block is given
    a non-citable role.  A block opening with unnumbered prose is refused
    outright: notes below a provision cannot vouch for the provision above
    them.  This is the guard that keeps the inline run test from swallowing an
    amending Act's own numbered sections, which read like notes and are not.
    """
    if not lines or not _NUMBERED_LINE.match(lines[0]):
        return False
    logical: list[list[str]] = []
    for line in lines:
        if _NUMBERED_LINE.match(line):
            logical.append([line])
        elif logical:
            logical[-1].append(line)
    return all(_run_member_is_apparatus(" ".join(item)) for item in logical)


def _is_footnote_run(text: str, *, split_numbers_only: bool = False,
                     require_every_item: bool = False) -> bool:
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
    # The body walk asks with `require_every_item`, because there the answer
    # decides whether a block of the document leaves the citable tree.  The
    # contents reader asks without it: there the answer only decides whether a
    # printed row is admitted to the TOC ledger, and a wrong answer costs a
    # gap, not a provision.
    if require_every_item and not _every_inline_note_is_apparatus(lines):
        return False
    return sum(1 for _, ln in numbered if _FOOTNOTE.match(ln)) >= 2


def _without_trailing_inline_footnotes(text: str) -> str:
    """Remove a proved apparatus run fused below a provision in one block.

    A source block can contain enacted/deleted provision text followed by the
    page's numbered amendment notes.  Treating the whole tail as provision
    text makes a real contents entry resolve to apparatus.  The cut is allowed
    only at a later physical line and only when *every* remaining numbered item
    independently passes the guarded apparatus test.  One operative item makes
    this a no-op.
    """
    for match in re.finditer(r"(?m)^(?=\s*\d{1,2}\s*[.:-]?\s*\S)", text):
        if match.start() == 0:
            continue
        prefix = text[:match.start()].rstrip()
        suffix = text[match.start():]
        if prefix and _is_footnote_run(suffix, require_every_item=True):
            return prefix
    return text


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
            # Profile rule `contents_bare_number_rows` (unreleased-v4): doc
            # 876's contents prints "11 Chancellor." with no full stop between
            # "10. Visitation." and "12. Rector."; the row never counted, and
            # its second contents run's "11. Functions of the Finance and
            # Planning Committee." then named the Act's s.11. A bare number
            # and a capitalised name is a row only between N-1 and N+1.
            if (not c and profile_rule("contents_bare_number_rows")
                    and out and i + 1 < len(blocks)):
                bare = re.fullmatch(r"\s*(\d{1,4})\s+([A-Z][^\n]{2,120}?)\s*", piece)
                if bare and out[-1][1] == int(bare.group(1)) - 1:
                    following = classify(blocks[i + 1].get("text") or "")
                    if (following and following[0] == "section"
                            and re.match(r"\d+$", following[1].replace(" ", ""))
                            and int(following[1].replace(" ", "")) == int(bare.group(1)) + 1):
                        c = ("section", bare.group(1), bare.group(2))
            if not c or c[0] != "section":
                continue
            label = c[1].replace(" ", "")
            heading = _norm(c[2])
            # Profile rule `contents_leader_page_strip` (unreleased-v4): (doc 4447)
            if profile_rule("contents_leader_page_strip") and heading:
                _lead = re.match(r"^(.*?[A-Za-z\])][^\n]*?)\s*(?:[.\u2026]\s*){3,}\s*\d{0,4}\s*$", heading)
                if _lead:
                    heading = re.sub(r"(?:\s*[.:]?\s*[-\u2013\u2014\u2015]+|\s*\.)\s*$", "",
                                     _lead.group(1).strip()).strip()
            if not heading:
                # The number was set alone in its own column block and its
                # heading is the next one -- reader-instruction pattern (j).
                heading = _detached_heading(blocks, i)
            if not heading:
                source = _SOURCE_COMPOUND_TOC_HEADING.get(
                    (b.get("id"), b.get("page_no"), label))
                if source:
                    digest, printed_heading = source
                    actual = hashlib.sha256(
                        " ".join((b.get("text") or "").split()).encode("utf-8")
                    ).hexdigest()
                    if (actual == digest and
                            f"{label}. {printed_heading}" in _norm(b["text"])):
                        heading = printed_heading
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
    # Profile rule `detached_heading_after_division` (unreleased-v4): doc
    # 3350's contents prints "CHAPTER IV" / "FUNCTIONS OF THE CORPORTION" /
    # "10." -- section 10 has no heading in the contents or in the text -- and
    # the block above, the chapter's own title, became section 10's heading.
    # A block set directly under a CHAPTER or PART line is that division's
    # title; the stranded number then has no printed heading, and the block
    # below (there, the page's "Page 1 of 9") is not one either.
    if (profile_rule("detached_heading_after_division") and index >= 2
            and blocks[index - 2].get("page_no") == page
            and (classify(blocks[index - 2].get("text") or "")
                 or ("",))[0] in ("chapter", "part")):
        return ""
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


# A contents entry is a short line; enacted text is long and carries operative
# verbs. `_SWALLOW_MIN_CHARS` is a chosen floor, not a fitted one: a single
# contents entry is one heading line, so apparatus longer than this is a fused
# RUN of entries (several in one layout block), which is excluded by shape
# below rather than by length. Erring long only makes the fence stand down.
_SWALLOW_MIN_CHARS = 300
_OPERATIVE_VERB = re.compile(
    r"\b(?:shall|means|is hereby|are hereby|shall be deemed|may not)\b", re.I)
# Three or more "N. Some Heading." pieces in one block is a contents page the
# extractor emitted as a single layout block, not a section of enacted text.
_FUSED_CONTENTS_RUN = re.compile(
    r"(?:(?<![0-9])[0-9]{1,3}[A-Z]?\s*\.\s+[A-Z][^.]{2,80}\.\s*){3,}")
_DOT_LEADER = re.compile(r"\.{4,}")


def _swallowed_body_frontier(blocks: list[dict], start: int) -> int:
    """First block at or after `start` that is enacted text, not apparatus.

    Used to fence the POSITIONAL tie-break in :func:`parse_contents`. Moving
    the boundary later can only be right when what it absorbs is more contents;
    the moment enacted text is absorbed the boundary is wrong, whatever the
    label-overlap score says, because those characters become citable by
    nothing (INV-4).

    Every exclusion here is front matter that legitimately sits between a
    printed contents list and the body it summarises. Without them the frontier
    lands on a preamble and the boundary is dragged too EARLY, which is the
    worse failure: contents rows then open as provisions and the document gains
    phantom sections.
    """
    for index in range(max(0, start), len(blocks)):
        text = _norm(blocks[index].get("text") or "")
        if len(text) < _SWALLOW_MIN_CHARS:
            continue
        if not _OPERATIVE_VERB.search(text):
            continue
        if _ENACTING_FORMULA.search(text):
            continue
        if _has_contents_marker(text):
            continue
        if _FUSED_CONTENTS_RUN.search(text):
            continue
        if _DOT_LEADER.search(text):
            continue
        return index
    return len(blocks)


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

    # A printed CONTENTS banner is evidence that a list exists, but it cannot
    # turn numbering printed AFTER the enacting formula into that list.  Some
    # PDFs lose the contents page's number column while retaining only its
    # headings.  In doc 1586 the first parseable number is therefore operative
    # section 1 after WHEREAS; a later First Schedule restart made sections
    # 1--19 score as the "contents" and the schedule as the "body".  With no
    # numbered row between the banner and the formula there is no label ledger
    # to reconcile, so abstain and retain every block as body evidence.
    if saw_marker:
        first_formula = next(
            (i for i, block in enumerate(blocks[contents_start:], contents_start)
             if _ENACTING_FORMULA.search(block["text"])),
            None,
        )
        numbered_before_formula = any(
            contents_start <= idx < first_formula
            for idx, _, _, _ in nums
        ) if first_formula is not None else False
        first_number = nums[0][0] if nums else None
        if (first_formula is not None and first_number is not None
                and first_number > first_formula
                and not numbered_before_formula):
            return {}, 0, False

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
    for position, (idx, n, _, _) in enumerate(nums):
        # An editorial-looking restart is inside the current numbered run only
        # when that run visibly resumes: ``... 7, [note 1], 8 ...``.  Stop at
        # another 1/2 restart so a later body that happens to reach `peak + 1`
        # cannot retroactively provide this proof.
        resumes_current_run = False
        for _, later_n, _, _ in nums[position + 1:]:
            if later_n <= 2:
                break
            if later_n == peak + 1:
                resumes_current_run = True
                break
        # Numbered editorial notes can sit *inside* a multi-page contents list.
        # Keep them in `nums` so source accounting and the printed-entry ledger
        # remain unchanged, but do not let one nominate the body boundary.
        # Document 3581 prints sections 1--7, then ``1. Repealed vide A.O
        # 1937.``, then continues with sections 8--36.  That note made the
        # seven-entry prefix score 1.000 and stranded the reviewed disposition
        # for section 16.  Bracketed in-situ provisions such as
        # ``16. [Repealed.]`` are deliberately refused by the per-item
        # apparatus proof and remain eligible legal numbering.
        embedded_editorial_note = (
            resumes_current_run
            and _run_member_is_apparatus(blocks[idx]["text"])
        )
        if (peak >= peak_needed and n <= 2 and idx > 0
                and not embedded_editorial_note):
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
            if _is_year(label) and _contents_title_year(
                    label, blocks[idx]["text"],
                    saw_marker and idx == contents_start):
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
    #
    # Position, however, is evidence of nothing. Where a document prints a
    # second numbered run that repeats the contents labels -- a Schedule of
    # standing orders, a form, an appendix table restarting at 1 -- agreement
    # and corroboration tie exactly, and position alone hands the boundary to
    # the late run, burying the whole operative body in `role='contents'`
    # attached to nothing. Doc 2846 loses its fourteen sections that way.
    #
    # So fence position, and only position: a later candidate whose contents
    # list actually predicts the headings that follow it still wins on
    # corroboration, because corroboration is source evidence. Position may
    # advance the boundary only while what it absorbs is apparatus.
    #
    # The frontier is sought from where the printed contents BEGINS, not from
    # the earliest candidate. Where enacted text precedes even the earliest
    # candidate, every candidate already buries law and the fence has nothing
    # safe to choose -- so it stands down and the vote is exactly what it was.
    # Without this the fence made things worse in the two documents where the
    # earliest candidate was itself too late: it moved the boundary into the
    # front-matter window and REVIVED a contents hypothesis that the existing
    # guards had rightly killed. Doc 4473 (Sind Standard Weights and Measures
    # Enforcement Rules 1976) filed its rules 1-26 -- 21,806 characters of
    # pages 2-9 -- as contents and re-labelled dotted-leader table rows as the
    # rules; doc 3392 filed the operative text of s.13 of the West Pakistan
    # Finance Act 1964 the same way. The fence may move the boundary of a
    # contents list; it must never be the reason one survives.
    swallow_frontier = _swallowed_body_frontier(blocks, contents_start)
    fence_position = swallow_frontier >= pick[0][0]

    def position_vote(position: int, candidate: int) -> int:
        if not fence_position:
            return position
        return position if candidate <= swallow_frontier else -1

    best_idx, best_score, best_toc = max(
        enumerate(pick),
        key=lambda item: (heading_corroboration(item[1][0], item[1][2]),
                          position_vote(item[0], item[1][0])),
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
    # An unmarked contents list summarizes provisions; it is not made from the
    # provisions' full operative sentences.  Label overlap alone cannot tell a
    # front body run from a later appendix/table restart.  Doc 3720 produced a
    # six-entry hypothesis whose headings include "shall be made", "shall not
    # be bound" and "shall continue" -- four operative sentences out of six.
    # A majority of independently operative headings refutes an unmarked list.
    operative_headings = sum(
        1 for heading in best_toc.values()
        if _OPERATIVE_VERB.search(_norm(heading))
    )
    implicit_summarises = operative_headings * 2 < len(best_toc)
    found = bool(best_toc) and (
        saw_marker or (len(best_toc) >= 5 and implicit_is_front_matter
                       and implicit_summarises))
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
    # A reading just past the body's own high-water mark continues the body's
    # sequence, and no footnote marker can produce one.  A marker m glued in
    # front of the NEXT section's number n reads as m * 10**len(n) + n, which
    # is at least ten past the highest number the body has read -- so a
    # reading one to nine past it is the next section, not a fusion.  This is
    # the sequence half of the old ``int(key) == max(seen) + 1`` test, freed
    # from its collision precondition (see the collision rule below) and
    # widened only as far as that arithmetic allows.
    #
    # Doc 3868 needs it: once rules 82 and 92 keep their numbers, rule 2 has
    # not yet been read when "102. Rental and Renewal Fee" arrives straight
    # after 101, and three digits against a contents reaching 72 is exactly
    # the overflow the magnitude test above admits as fusion.
    numeric_seen = [int(value) for value in seen or () if value.isdigit()]
    continues_sequence = bool(
        key.isdigit() and numeric_seen
        and 0 < int(key) - max(numeric_seen) < 10)
    toc_order = list(toc)
    for strip in (1, 2, 3, 4):
        # A number the document's own contents shows to be in range is a
        # provision number, not a marker glued to a shorter one; so is one
        # that continues the body's own sequence.
        if (within_printed_range or continues_sequence) and key not in toc:
            break
        if len(key) > strip and key[:strip].isdigit():
            candidate = key[strip:]
            if candidate and candidate[0].isdigit() and candidate in toc:
                # If the stripped label has already occurred in the body,
                # stripping does not RECOVER a section -- it manufactures a
                # duplicate, and one of the two loses citability.  That is the
                # harm this repair exists to prevent, so the collision is
                # itself proof that the leading digits belong to the number.
                #
                # This rule used to require the full reading to be exactly
                # ``max(seen) + 1`` as well.  That covers an official contents
                # list omitting its own omitted rows -- after section 15, body
                # ``16. 2[Omitted.]`` is section 16, not a second 6 -- but it
                # is far narrower than the harm.  Doc 4594 p27 reads "143.
                # Children born in prison" with 142, 140, 134 and 128 already
                # seen and rule 3 seen on page 2, and the exact-continuation
                # test still let a three-row contents peel it to 3.
                #
                # BREAK, not continue: a collision proves the leading digit
                # belongs to the number, and a deeper strip removes even more
                # of it.  Measured with ``continue``, the loop went on to peel
                # "2015" past a colliding "15" down to "5", and "111" past a
                # colliding "11" down to "1" -- 68 calls in two documents.
                #
                # Only for a reading inside the range the document has already
                # evidenced -- its contents or its body.  Beyond that range the
                # collision proves nothing about a provision number, because
                # the reading is not one either way: doc 1910's Fourth Schedule
                # prints "8. rule 38. Fee for duplicate certificate", the
                # parser carves "rule 38." out as a unit, and in a ten-section
                # Act keeping it citable as section 38 tipped the contents-
                # refutation count and filed the whole Act as contents.  Just
                # past the range is the sequence rule's business, above.
                numeric_seen_b = [int(value) for value in seen or ()
                                  if value.isdigit()]
                if (seen is not None and candidate in seen and key.isdigit()
                        and int(key) <= max([highest_printed, *numeric_seen_b])):
                    break
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


def _contents_title_year(label: str | None, block_text: str,
                         marker_block: bool) -> bool:
    """Is this year-shaped contents label the instrument's own title year?

    A title wrapped so that its year leads a line is read as a contents row
    that no body section can keep. Two narrow proofs, each from the block that
    carries the year; a four-digit row printed INSIDE the list stays a row
    (test_four_digit_labels_after_contents_marker_are_not_discarded), and a
    weak "SECTIONS" header still authorises nothing:

    * the year precedes the CONTENTS marker line in the marker's own block --
      the doc 1224 pre-marker rule, applied by line rather than by block
      ("2010." / "CONTENTS", docs 2856 and 3190; "1988. 2[KHYBER
      PAKHTUNKHWA] ACT NO. IV OF 1988. CONTENTS", doc 1806);
    * the block cites the instrument by that same year -- "1981. 2[KHYBER
      PAKHTUNKHWA] ORDINANCE NO. IV OF 1981." (docs 244, 1346, 1368),
      "1962. (W. P. ORD NO. VIII OF 1962)" (doc 1319).
    """
    year = (label or "").strip()
    if not re.fullmatch(r"(?:1[89]\d{2}|20\d{2})", year):
        return False
    lines = block_text.splitlines()
    if marker_block:
        year_line = next((i for i, line in enumerate(lines)
                          if re.match(rf"\s*{year}\s*\.", line)), None)
        marker_line = next((i for i, line in enumerate(lines)
                            if _CONTENTS.match(line)), None)
        if (year_line is not None and marker_line is not None
                and year_line < marker_line):
            return True
    return re.search(
        rf"\b(?:ORDINANCE|ACT|REGULATION|ORD)\.?\s*NO\.?\s*[IVXLC\d]+\s+OF\s+{year}\b",
        block_text, re.I) is not None


def _withheld_heading(expected: str | None) -> bool:
    """A contents row whose heading is printed only as asterisks.

    Punjab service rules print their contents as ``1. ****** 2. ****** 3.
    ******`` (documents 1105, 1886, 4060): the number is promised, the heading
    withheld. Such a row is evidence that a unit numbered N exists and nothing
    about what it says, so it can neither support nor contradict a body block.
    """
    return bool(expected) and re.fullmatch(r"[\s*]+", expected) is not None


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


def _owner_decision_citation(value) -> bool:
    """Is `value` a well-formed citation of one owner decision-review answer?

    The parser is pure, so it checks only the citation's shape; that the
    export file exists and holds the answer for that document and question is
    checked where the reading enters the system (`owner_decision_answer` in
    nizam/workers/segment.py, used by the recorder and the dry run)."""
    return (isinstance(value, dict)
            and set(value) == {"export", "document_id", "question_id"}
            and isinstance(value["export"], str) and value["export"].endswith(".json")
            and type(value["document_id"]) is int and value["document_id"] > 0
            and isinstance(value["question_id"], str)
            and re.fullmatch(r"q\d+", value["question_id"]) is not None)


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
        # Punjab Auqaf service rules (docs 2374, 3929) list "Schedule I" to
        # "Schedule IX" in the contents and print "SCHEDULE PART-I" to
        # "SCHEDULE PART-IX" in the body: one schedule, nine parts, which the
        # contents names by part. Read only when no plain ordinal is printed.
        match = re.search(
            r"\bschedule\s*[-–—]?\s*part\s*[-–—]?\s*([ivxlc]+|\d+)\b",
            normalized,
        )
    if not match:
        return None
    names = {
        "first": "i", "second": "ii", "third": "iii", "fourth": "iv",
        "fifth": "v", "sixth": "vi", "seventh": "vii",
    }
    return names.get(match.group(1), match.group(1))


def _standalone_listed_schedule(block_text: str, label: str | None,
                                rest: str | None,
                                toc_schedule_identities: set[str],
                                following: str | None) -> bool:
    """``Schedule II`` alone in its block, listed in the contents, and followed
    on the same page by the rule it is made under -- ``(Rule 5)``.

    The uppercase test above proves a display heading; title case is left to
    the cross-reference guards, which read an unfinished previous line as a
    sentence the heading continues. A form ends on a signature line --
    ``Attested by Oath / Commissioner`` -- that has no full stop, so doc 2042's
    Schedule II was read as a reference and its whole form was appended to
    Schedule I's last paragraph.

    A standalone block is not proof enough: doc 1337 p3 wraps "in accordance
    with / Schedule-I" so the reference is its own block at the foot of the
    page, followed by the page number. The statutory reference printed under
    the heading is what a cross-reference never carries.
    """
    if (rest or "").strip():
        return False
    if not re.match(r"^\s*(?:the\s+)?schedule\b", block_text or "", re.I):
        return False
    identity = _schedule_identity(label)
    if identity is None or identity not in toc_schedule_identities:
        return False
    return bool(re.match(
        r"^\s*[\[(]\s*(?:see\s+|under\s+)?(?:sub-?)?(?:rules?|sections?|regulations?|"
        r"paras?|paragraphs?|articles?)\s*[-–—]?\s*\d",
        following or "", re.I))


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


_DIVISION_REFERENCE = re.compile(
    r"[\[(]\s*see\s+(?:sub-?)?(?:rules?|sections?|regulations?|paras?|paragraphs?)"
    r"\s*\d", re.I)
# Profile rule `sequential_form_label` (unreleased-v4): doc 4317 prints
# "Form C1" after Form C's witness block and "Form C2 SCHEDULE OF PROPERTY"
# after C1's title -- no reference, after lines that read unfinished. A form
# label alone on its line (or with an upper-case title) that continues the
# sequence of the forms printed before it (C -> C1, C1 -> C2, C2 -> D) opens.
_SEQUENTIAL_FORMS: contextvars.ContextVar[frozenset] = contextvars.ContextVar(
    "sequential_form_labels", default=frozenset())
_FORM_LABEL_START = re.compile(
    r"\s*FORM[ \t]*-?[ \t]*([A-Z])(\d?)(?=[ \t]*(?:\n|$)|[ \t]+[A-Z][A-Z \t]+(?:\n|$))", re.I)
_FORM_LABEL_LINE = re.compile(r"(?m)^[ \t]*FORM[ \t]*-?[ \t]*([A-Z])(\d?)[ \t]*$", re.I)
# Profile rule `quoted_sequential_form_label` (unreleased-v4): doc 3108 heads
# its forms FORM 'A', FORM "B" -- the same sequence test, a printer's quote
# admitted on either side of the letter.
_FORM_LABEL_LINE_Q = re.compile(r"(?m)^[ \t]*FORM[ \t]*-?[ \t]*['\"\u2018\u2019\u201c\u201d]?([A-Z])(\d?)['\"\u2018\u2019\u201c\u201d]?[ \t]*$", re.I)
_FORM_LABEL_START_Q = re.compile(r"\s*FORM[ \t]*-?[ \t]*['\"\u2018\u2019\u201c\u201d]?([A-Z])(\d?)['\"\u2018\u2019\u201c\u201d]?(?=[ \t]*(?:\n|$)|[ \t]+[A-Z][A-Z \t]+(?:\n|$))", re.I)


def _sequential_form_labels(blocks: list[dict]) -> frozenset:
    def successor(prev, cur):
        (pl, pd), (cl, cd) = prev, cur
        if cl == pl:
            return (pd == "" and cd == "1") or (pd.isdigit() and cd.isdigit() and int(cd) == int(pd) + 1)
        return cd == "" and ord(cl) == ord(pl) + 1
    seen, allowed = [], set()
    for b in blocks:
        _agar_rx = (_FORM_LABEL_LINE_Q if profile_rule("quoted_sequential_form_label") else _FORM_LABEL_LINE)
        # Profile rule `misprinted_form_word` (unreleased-v4): a misprinted 'FROM X' form label line counts in the form sequence (doc 4003: FROM A, FROM B,
        # FROM 'C', then FORM 'D' -- D continues C)
        if profile_rule("misprinted_form_word"):
            _agar_rx = re.compile(_agar_rx.pattern.replace("FORM[ \\t]*-?", "(?:FORM[ \\t]*-?|(?-i:FROM)[ \\t]+)", 1),
                                  _agar_rx.flags)
        for m in _agar_rx.finditer(b.get("text") or ""):
            if not m.group(1).isupper():
                continue
            cur = (m.group(1), m.group(2))
            if seen and successor(seen[-1], cur):
                allowed.add(cur)
            seen.append(cur)
    return frozenset(allowed)


def _division_reference_search(text: str):
    found = _DIVISION_REFERENCE.search(text)
    if found or not profile_rule("sequential_form_label"):
        return found
    label = (_FORM_LABEL_START_Q if profile_rule("quoted_sequential_form_label")
             else _FORM_LABEL_START).match(text)
    if label and label.group(1).isupper() and (label.group(1), label.group(2)) in _SEQUENTIAL_FORMS.get():
        return label
    return None


def _division_reference_match(text: str):
    return _DIVISION_REFERENCE.match(text)


# Profile rule `left_column_margin_heading` (unreleased-v4): doc 4399 prints no contents
# list and sets each section in three columns -- margin heading on the left, number in the
# middle, text on the right. A heading-shaped left-column block level with a section opener,
# or heading lines before 'N.' inside a block, names the next section.
def _left_margin_heading_shape(text: str) -> bool:
    flat = _norm(text or "")
    lines = [ln for ln in (text or "").split("\n") if ln.strip()]
    return bool(3 <= len(flat) <= 120 and 1 <= len(lines) <= 7
                and re.match(r"[A-Z]", flat) and flat.endswith(".")
                and not re.search(r"[“”\"‘’]", flat)
                and not re.search(r"[.;:]\s+[a-z]", flat)
                and not re.search(r"\b(?:shall|may|means|is|are)\b", flat)
                and classify(text) is None)


def _left_margin_heading_tail(piece: str):
    """(head, heading) when the last 1-4 non-blank lines of `piece` are a margin heading and the line before
    them closes a sentence or a quotation; else None."""
    lines = piece.split("\n")
    nb = [i for i, ln in enumerate(lines) if ln.strip()]
    best = None
    for k in range(1, 5):
        if len(nb) <= k:
            break
        cut = nb[-k]
        before = lines[nb[-k - 1]].rstrip()
        tail = "\n".join(lines[cut:])
        if _left_margin_heading_shape(tail) and re.search(r"[”\".:;\-]$", before):
            best = ("\n".join(lines[:cut]) + "\n", tail)
    return best


def _split_heading(rest: str, toc_heading: str | None) -> tuple[str | None, str]:
    head, text = _split_heading_base(rest, toc_heading)
    if head is not None and not toc_heading:
        # Profile rules `label_only_heading_none` and `not_reproduced_text`
        # (unreleased-v4, doc 3108): a guessed heading made only of bracketed
        # labels ("7.2.D (1) (a). In this rule ...") or opening "Not
        # reproduced" (a placeholder rule's whole text) is not a heading.
        if (profile_rule("label_only_heading_none")
                and re.fullmatch(r"(?:\(\s*(?:\d{1,3}|[a-z]{1,2}|[ivxlc]{1,6})\s*\)\s*)+", _norm(head))):
            return None, _norm(rest.lstrip(" .—-\t\n"))
        if (profile_rule("not_reproduced_text")
                and re.match(r"Not\s+reproduced?\b", _norm(head), re.I)):
            return None, _norm(rest.lstrip(" .—-\t\n"))
    # Profile rule `colon_closed_heading_guess` (unreleased-v4): with no
    # contents list, doc 4317 rules 32-35 print "32. Fee for revised plan and
    # service designs: A sponsor shall deposit ..."; the guesses want a stop or
    # a dash after the name, so the names stayed in the text. Only when no other
    # guess found a name: a capitalised span of 4-110 characters with no
    # sentence end and no operative word, closed by a colon before a capital.
    if head is None and not toc_heading and profile_rule("colon_closed_heading_guess"):
        flat = _norm(rest)
        # A dash may follow the colon ("13. Maintenance of the farm: - The
        # owner shall ...", doc 3110).
        m = re.match(r"^([A-Z][^:\n]{3,109}?)\s*:\s*(?:[-–—]+\s*)?\s(?=[A-Z])", flat)
        if (m and not re.search(r"[.;]\s", m.group(1))
                and not _HEADING_OPERATIVE.search(m.group(1))):
            return _norm(m.group(1)), _norm(flat[m.end():])
    return head, text
# Profile rule `quoted_insertion_span` (unreleased-v4). An amending provision
# introduces new text ("the following sections shall be substituted:-") and
# quotes it. A decoded opening quote "―" counts only after whitespace and
# before a character: the same code point closes headings as a dash
# ("Commission.―(1)", doc 2923).
_INSERTION_INTRO = re.compile(r"\bfollowing\b[^\n]{0,200}?\b(?:substituted|inserted|added)\b", re.I)
_INSERTION_OPEN_QUOTE = re.compile(r"“|(?:(?<=\s)|^)―(?=\S|\s*$)")
_INSERTION_CLOSE_QUOTE = re.compile(r"[”‖]")
_AMENDING_OPENER = re.compile(
    r"\s*\d{1,3}[A-Z]?\s*\.\s+(?:In|For|After|Before|Throughout)\s+(?:the\s+said|section|"
    r"sections|sub-section|clause|rule|the\s+\w+\s+(?:Act|Ordinance|Order|Rules))\b"
    # ... or an amending instruction set out as a clause of one: "(ii) for
    # Article 2, ...", "(iv) after clause (36), ..." (doc 3442) -- lower case,
    # where quoted new clauses open with a quote or a capital.
    r"|\s*\(\s*(?:[ivxlc]{1,6}|[a-z]{1,2})\s*\)\s+(?:for|after|in|before|throughout|"
    r"the\s+(?:word|words|existing|figure|figures))\s")
_AMENDING_INSTRUCTION = re.compile(
    r"(?:In|Throughout|Through\s+out|For|After|Before)\s+(?:the\s+said\b|the\s+Act\b|sections?\b|"
    r"sub-?sections?\b|clauses?\b|rules?\b|the\s+words?\b|the\s+figures?\b|the\s+existing\b|"
    r"the\s+\w+\s+(?:Act|Ordinance|Order|Rules)\b)", re.I)
_AMENDING_OPENER_NOT_RESPECT = re.compile(
    _AMENDING_OPENER.pattern.replace("|in|before|", r"|in(?!\s+respect\s+of\b)|before|"))
assert _AMENDING_OPENER_NOT_RESPECT.pattern != _AMENDING_OPENER.pattern
_NUMBERED_AMENDING_OPENER = re.compile(
    r"\s*\d{1,3}[A-Z]?\s*\.\s+(?:In|For|After|Before|Throughout)\s+(?:the\s+said|section|"
    r"sections|sub-section|clause|rule|the\s+\w+\s+(?:Act|Ordinance|Order|Rules))\b")


def _quote_balance(text: str) -> int:
    return (len(_INSERTION_OPEN_QUOTE.findall(text or ""))
            - len(_INSERTION_CLOSE_QUOTE.findall(text or "")))


def _quoted_insertion_spans(texts: list[str], pages: list[int],
                            limit: int = 80, max_pages: int = 2) -> dict[int, int]:
    """Unit ranges that an amending provision quotes as new text.

    A span opens after a unit whose introduction ("the following ... shall be
    substituted") leaves a quotation open, or at the next unit when that unit
    itself opens with the quote; it ends at the unit that closes it. A span
    that does not close within `limit` units and `max_pages` pages is not a
    span: a lost closing quote must not swallow the rest of the instrument.
    """
    spans: dict[int, int] = {}
    i, n = 0, len(texts)
    while i < n:
        intro = None
        flat = _norm(texts[i] or "")
        for intro in _INSERTION_INTRO.finditer(flat):
            pass
        if intro is None and i + 1 < n and re.search(r"\bfollowing\b", flat, re.I):
            # "(v) for clauses (42) and (43), the following shall be" /
            # "substituted:--" (doc 1950): the introduction wraps into the next
            # unit, which then carries it.
            joined = f"{flat} {_norm(texts[i + 1] or '')}"
            for intro in _INSERTION_INTRO.finditer(joined):
                pass
            if intro is not None and intro.end() > len(flat):
                i += 1
                flat = joined
            else:
                intro = None
        if intro is None:
            i += 1
            continue
        tail = flat[intro.end():]
        balance = _quote_balance(tail)
        start = None
        if balance > 0:
            start = i + 1
        elif balance == 0 and not _INSERTION_CLOSE_QUOTE.search(tail):
            # The quote may open a few units on, past the new text's own
            # margin note (doc 1144: "Declaration of urban areas." then "―8.").
            # Profile rule `whole_schedule_quote`: a substituted Schedule may
            # open on the next page, past its three running-head units (doc
            # 4433 s.10(s)).
            reach = (7 if profile_rule("whole_schedule_quote")
                     and re.search(r"\bSchedule\b", flat, re.I) else 4)
            for k in range(i + 1, min(n, i + reach)):
                if re.match(r"\s*(?:\d{1,3}\s*\[\s*)?(?:“|―)", texts[k] or ""):
                    start = i + 1
                    break
                if len(_norm(texts[k] or "")) > 100 or _quote_balance(texts[k]):
                    break
        if start is None or start >= n:
            i += 1
            continue
        j = start
        closed = False
        opened = balance > 0
        # Profile rule `whole_schedule_quote` (unreleased-v4): doc 4433
        # s.10(r) and (s) substitute the whole First and Second Schedules of
        # the Sales Tax on Services Act -- "for the existing First Schedule,
        # the following shall be substituted, namely: “First Schedule [see
        # ...]" -- five and eighteen pages of quoted rows. The two-page bound
        # refused both spans and the rows became units of the Finance Act. A
        # quotation that opens with a SCHEDULE heading after words naming a
        # Schedule may run to its closing quote; the amending-opener stop
        # still applies.
        # Only the numbered opener ("7. In the said Ordinance") stops such a
        # span: the Schedule's own rows print lower-case instructions such as
        # "(i) for Umrah services; and".
        span_limit, span_pages = limit, max_pages
        # Profile rule `in_respect_of_not_opener` (unreleased-v4): doc 4276
        # s.6(d) quotes a fee entry whose rows read "(a) in respect of Motor
        # Cycles ...": the clause-form opener ("(ii) in Article 2") matched
        # the first row and refused a span whose quotes are both printed.
        opener = (_AMENDING_OPENER_NOT_RESPECT if profile_rule("in_respect_of_not_opener")
                  else _AMENDING_OPENER)
        if (profile_rule("whole_schedule_quote") and re.search(r"\bSchedule\b", flat, re.I)
                and any(re.match(r"\s*(?:\d{1,3}\s*\[\s*)?[“\"]\s*(?:THE\s+)?(?:[A-Za-z]+\s+)?SCHEDULE\b",
                                 texts[k] or "", re.I)
                        for k in range(start, min(n, start + 4)))):
            span_limit, span_pages = 4000, 60
            opener = _NUMBERED_AMENDING_OPENER
        # Profile rule `whole_section_quote` (unreleased-v4): doc 4399's 'for Section N, the following
        # shall be substituted' and 'following new sections shall be inserted' quote whole sections
        # over many pages; the span is held to its close, stopped only by a numbered amending opener.
        _whole_section_quote = bool(
            profile_rule("whole_section_quote")
            and re.search(r"\bfor\s+section\s+\d{1,3}[A-Z]?\b.{0,80}?\bfollowing\s+shall\s+be\s+substituted\b"
                          r"|\bfollowing\s+(?:\w+\s+){0,2}new\s+sections?\s+shall\s+be\s+(?:inserted|added)\b",
                          flat, re.I)
            and any(re.match(r"\s*[“\"]\s*\d{1,3}[A-Z]?\s*\.\s+[A-Z]", texts[k] or "")
                    for k in range(start, min(n, start + 4))))
        if _whole_section_quote:
            span_limit, span_pages = 4000, 60
            opener = _NUMBERED_AMENDING_OPENER
        # Profile rule `quoted_part_span` (unreleased-v4): doc 2621 substitutes a quoted Schedule Part.
        # The words naming the Schedule may close the unit before ("14. ... in Schedule V / (a) for
        # Part I, the following shall be substituted"); a numbered opener may carry its section's
        # moved margin heading ("14. Amendment of Schedule V to Sind Ordinance XII of 1979. In the said").
        _quoted_part = bool(
            profile_rule("quoted_part_span") and not _whole_section_quote
            and re.search(r"\bfor\s+Part\s*[-\u2014\u2013]?\s*(?:[IVXLC]+|\d{1,2})\b[^\n]{0,40}?"
                          r"\bfollowing\s+shall\s+be\s+substituted\b", flat, re.I)
            and (re.search(r"\bin\s+Schedule\s+[IVXLC\d]+\b", flat, re.I)
                 or (i > 0 and re.search(r"\bin\s+Schedule\s+[IVXLC\d]+\s*$", _norm(texts[i - 1] or ""), re.I)))
            and any(re.search(r"(?:^|\s)[\u201c\"]\s*PART\s*[-\u2014\u2013]+\s*[IVXLC\d]", texts[k] or "")
                    for k in range(max(i, start - 1), min(n, start + 4))))
        if _quoted_part:
            span_limit, span_pages = 4000, 60
            opener = re.compile(
                r"\s*\d{1,3}[A-Z]?\s*\.\s+(?:(?:Amendment|Insertion|Omission|Substitution|Repeal)\s+of\b"
                r"[^\n.]{0,100}?\d{4}\s*\.\s+)?(?:In|For|After|Before|Throughout)\s+(?:the\s+said|section|"
                r"sections|sub-section|clause|rule|the\s+\w+\s+(?:Act|Ordinance|Order|Rules))\b")
            _whole_section_quote = True
        while j < n and j - start < span_limit and pages[j] - pages[i] <= span_pages:
            if _whole_section_quote and opener.match(texts[j] or ""):
                # the opener of the next amending section: the quotation closed at the last unit before it that
                # ends with a closing quote (a margin heading or a page number may stand between).
                for _q in range(j - 1, max(start - 1, j - 5), -1):
                    if re.search(r"[”\"]\s*\.?\s*$", texts[_q] or ""):
                        j, closed = _q, True
                        break
                break
            # The next amending provision of the instrument itself ("7. In the
            # said Ordinance, ...") can never sit inside quoted new text; a
            # quote still open there was lost, and the span is refused.
            if opener.match(texts[j] or ""):
                break
            balance += _quote_balance(texts[j])
            opened = (opened or balance > 0
                      or bool(_INSERTION_OPEN_QUOTE.search(texts[j] or "")))
            if opened and balance <= 0:
                closed = True
                break
            j += 1
        if (closed and _whole_section_quote
                and re.search(r"\bnew\s+sections\b", flat, re.I)):
            _k = j + 1
            while _k < n and pages[_k] - pages[start] <= 60 and not opener.match(texts[_k] or ""):
                if re.search(r"[”\"]\s*\.?\s*$", texts[_k] or ""):
                    j = _k
                _k += 1
        if closed:
            # Profile rule `stray_close_extends_span` (unreleased-v4): doc 1746
            # closes the quote after inserted 20-A(i), then prints (ii),
            # (iii), and 20-B before the actual closing quote. Keep this
            # bounded insertion together; never cross the next amending
            # provision's opener.
            if (profile_rule("stray_close_extends_span")
                    and re.search(r"\bfollowing\s+new\s+sections\s+shall\s+be\s+inserted\b",
                                  flat, re.I)):
                k = j + 1
                while (k < n and k - start < limit
                       and pages[k] - pages[start] <= max_pages
                       and not _AMENDING_OPENER.match(texts[k] or "")):
                    if _quote_balance(texts[k]) < 0:
                        j = k
                    k += 1
            spans[start] = j
            i = j + 1
        else:
            i += 1
    return spans


# "FORM D [Rule 22(1)]", "Form-B [Rule 21(1)(d)]": a division label and nothing
# but a bracketed reference to the rule or section it is made under.
_BRACKETED_DIVISION_HEADING = re.compile(
    r"(?:THE\s+)?(?:FORM|SCHEDULE|APPENDIX|ANNEXURE|ANNEX)\s*[-–]?\s*[\"'‘“]?[A-Z0-9]{1,4}[\"'’”]?"
    r"\s*[\[(]\s*(?:see\s+)?(?:sub-?)?(?:rules?|sections?|regulations?|paras?|paragraphs?)"
    r"\s*\d{1,3}[A-Z]?(?:\s*\(\s*[0-9a-z]{1,4}\s*\))*\s*[\])]", re.I)
_SCHEDULE_DISPLAY = re.compile(
    r"(?:THE\s+)?SCHEDULE(?:\s+[A-Z][A-Z ,&'\-]{2,60})?")
_UPPER_TITLE_LINE = re.compile(r"[A-Z][A-Z ,&'\-]{2,60}")
_SECTION_REFERENCE_LINE = re.compile(
    r"[\[(]\s*(?:see\s+)?sections?\s+\d{1,4}[A-Z]?(?:\s*\([^()]{1,6}\))*"
    r"(?:\s*(?:,|and)\s*\d{1,4}[A-Z]?(?:\s*\([^()]{1,6}\))*)*\s*[\])]", re.I)


_AMENDMENT_NOTE_ROW = re.compile(
    r"^(?:\*\s*(?:Rep|Omitted|Subs|Sub|Ins|Added|Amended)\b"
    r"|(?:Subs|Substituted|Sub|Ins|Inserted|Added)\.?\s+(?:vide|by)\b)", re.I)
_OMISSION_NOTE_ROW = re.compile(r"^(?:Omitted|Rep\.?|Repealed|Deleted)\s*(?:vide|by)\b", re.I)
_CITATION_ROW = re.compile(
    r"^\(?\s*(?:W\.\s*P\.\s*|N\.\s*W\.\s*F\.\s*P\.\s*)?"
    r"(?:(?:Act|Ord\.?|Ordinance|Regulation)\s+)?No\.?\s*[IVXLC\d]+\s+of\s+\d{4}\s*\)?\.?$",
    re.I)


def _false_contents_row(entry: dict) -> bool:
    """Profile rule `contents_false_rows`: a parsed contents row that is not one.

    Doc 264's contents page closes with its footnote "1. Subs Vide the Khyber
    Pakhtunkhwa Act.IV of 2011." and doc 2027's with "*Rep. by the Repealing
    Act 1938 ..."; docs 2215 and 1142 read a title line -- "1ACT. No. XXIII of
    1918", "1960. (W. P. Ord. No. XXXII of 1960)" -- as a numbered row. None
    names a unit: an amendment note (starred, or "Subs./Ins./Added ... vide/
    by") or a bare instrument citation is never a contents heading. A plain
    "Rep. by ..." row is left alone -- it can be a real repealed entry.
    """
    heading = _norm(entry.get("heading") or "")
    return bool(_AMENDMENT_NOTE_ROW.match(heading) or _CITATION_ROW.match(heading))


_DESIGNATION_CELL = re.compile(
    r"(?:\.{2,}\s*)?-?\s*(?:(?:Vice|Co)[- ]?)?(?:Chair(?:man|person)|Members?|Secretary|"
    r"Convene?r|President|Director)(?:\s*/\s*(?:Secretary|Member|Convene?r))?"
    r"\s*\.?\s*\]?\s*(?:\.{2,})?|\.{2,}", re.I)
_NUMBERED_ROW = re.compile(r"^\s*\d{1,3}\s*\.?\s")
_BRACKET_ROW = re.compile(r"^\s*\(\s*(?:[ivxlc]{1,6}|[a-z]{1,2})\s*\)\s")


def _align_designation_cells(blocks: list[dict], opener_ends_row: bool = False,
                             bracket_rows: bool = False) -> list[dict]:
    """Profile rule `designation_cells` (unreleased-v2): a composition table's
    designation column, put back beside its row.

    A membership table prints each member's designation -- "Chairman",
    "Member", "Member/ Secretary", or ".." leaders -- in a right-hand column,
    and the text layer emits each cell as its own block, out of reading order:
    doc 1017 read "Chairperson, Sindh Textbook Board. Member Member" and left
    row 1 bare; doc 1934 gave the Chief Secretary "Chairman .. Member" and
    the next row none. The page settles it: a cell belongs to the numbered row
    whose vertical span holds its top edge. Only cells that are nothing but a
    designation or leader dots move, only to directly after a numbered row
    block on the same page and well to its right, and only when exactly one
    row holds them. No text changes and no block is dropped.
    """
    placed: dict[int, list[dict]] = {}
    moving: set[int] = set()

    def is_row(text: str) -> bool:
        # Profile rule `designation_bracket_rows` (unreleased-v3): doc 1934
        # numbers its Board's members "(i)" to "(x)", each with ".. Member"
        # in the right-hand column.
        return bool(_NUMBERED_ROW.match(text)
                    or (bracket_rows and _BRACKET_ROW.match(text)))

    for page in {block.get("page_no") for block in blocks}:
        page_blocks = [block for block in blocks if block.get("page_no") == page]
        # A row runs from its own top edge to the next numbered row's (blocks
        # carry no bottom edge here).
        rows = sorted((block for block in page_blocks
                       if is_row(block.get("text") or "")
                       and block.get("y0") is not None
                       and block.get("x0") is not None),
                      key=lambda block: float(block["y0"]))
        if not rows:
            continue
        spans = [(row, float(row["y0"]) - 3,
                  float(rows[index + 1]["y0"]) - 3 if index + 1 < len(rows)
                  else float(row["y0"]) + 60)
                 for index, row in enumerate(rows)]
        for cell in page_blocks:
            if (cell.get("id") is None or cell.get("y0") is None
                    or cell.get("x0") is None
                    or not _DESIGNATION_CELL.fullmatch(_norm(cell.get("text") or ""))):
                continue
            top = float(cell["y0"])
            holders = [row for row, low, high in spans
                       if low <= top < high
                       and float(cell["x0"]) >= float(row["x0"]) + 150]
            if len(holders) != 1:
                continue
            placed.setdefault(id(holders[0]), []).append((cell, holders[0]))
            moving.add(id(cell))
    if not moving:
        return blocks
    # Each row's cells go after the row's own continuation lines -- doc 258
    # row 9 wraps "One nominee of Vice / Chancellor ..." into a second block --
    # i.e. before the next numbered row, the next page, or a block below the
    # row's span.
    remaining = [block for block in blocks if id(block) not in moving]
    out: list[dict] = []
    pending: list[tuple[dict, float]] = []
    for index, block in enumerate(remaining):
        out.append(block)
        if id(block) in placed:
            high = max(float(cell["y0"]) for cell, _ in placed[id(block)]) + 60
            pending = [(cell, high) for cell, _ in sorted(
                placed[id(block)], key=lambda item: float(item[0]["x0"]))]
            owner_page = block.get("page_no")
        if pending:
            following = remaining[index + 1] if index + 1 < len(remaining) else None
            if (following is None
                    or following.get("page_no") != owner_page
                    or is_row(following.get("text") or "")
                    # Profile rule `designation_before_opener` (unreleased-v3):
                    # doc 258 p6 prints member 10 and then "(4) The functions of
                    # the Board shall be" within the cell's span; the cell
                    # belongs before the sub-section, not in it.
                    # Doc 1934 p5: the block after the tenth member holds the
                    # row's last words and then "(2) The Board shall meet".
                    or (opener_ends_row and re.search(
                        r"(?:^|\n)\s*\(\s*[0-9A-Za-z]{1,4}\s*\)\s", following.get("text") or ""))
                    or id(following) in placed
                    or (following.get("y0") is not None
                        and float(following["y0"]) >= pending[0][1])):
                out.extend(cell for cell, _ in pending)
                pending = []
    return out


def _align_row_cells(blocks: list[dict], relaxed: bool = False) -> list[dict]:
    """Profile rule `row_aligned_cells` (unreleased-v2): a table cell put back
    beside the numbered row it is printed level with.

    `relaxed` is profile rule `row_cells_within_rows` (unreleased-v3). Doc
    4222's First Schedule (game birds, bag limits, open seasons) sets most
    rows as one wide block carrying their own cells, so no row shows a
    separate cell beside it and the evidence below never held; its "Ditto",
    "Six only per day" and season cells then hung on the row above. Under
    the relaxed rule a row may be any width, the cell may run to 120
    characters, and the table shows itself by the cell lying inside another
    numbered row's horizontal span -- a margin heading never does.

    Doc 2019 p14's financial-powers tables print "Upto 5%" on the line of row
    3 ("3. Sanction of amount in excess of the sanctioned estimates."), but the
    text layer emits it before row 3, so row 2 read "... by contract. Upto Rs.
    25.0 lacs Upto 5%". The shape is a table's: the row block stops well short
    of the text column's right edge (the median right edge of the page's long
    lines) and the cell starts inside the column, right of the row's text. A
    section opener spans the column and a margin heading starts at or beyond
    its edge -- docs 2386 and 2846 set theirs level with the opener -- so
    neither is a cell. The table must also show itself apart from the cell:
    two or more such rows starting at one left edge, and another of them
    with a cell level beside it. A short cell moves only when its top edge
    is level (within 2.5 pt) with exactly one such row on its page and it
    currently comes before that row; it goes directly after the row block.
    Designation cells are the other rule's. No text changes and no block is
    dropped.
    """
    index_of = {id(block): index for index, block in enumerate(blocks)}
    moves: dict[int, list[dict]] = {}
    moving: set[int] = set()
    by_page: dict = {}
    for block in blocks:
        by_page.setdefault(block.get("page_no"), []).append(block)
    for page_blocks in by_page.values():
        placed_blocks = [block for block in page_blocks
                         if block.get("y0") is not None and block.get("x0") is not None
                         and block.get("x1") is not None]
        edges = sorted(float(block["x1"]) for block in placed_blocks
                       if len(_norm(block.get("text") or "")) >= 60)
        if len(edges) < 2 and not relaxed:
            continue
        edge = (edges[len(edges) // 2] if len(edges) >= 2
                else max((float(block["x1"]) for block in placed_blocks), default=0.0))
        all_rows = [block for block in placed_blocks
                    if _NUMBERED_ROW.match(block.get("text") or "")]
        rows = [block for block in all_rows if float(block["x1"]) < edge - 40]
        if relaxed:
            rows = all_rows
        if len(rows) < 2:
            continue

        def cells_beside(row: dict) -> list[dict]:
            return [other for other in placed_blocks
                    if other is not row
                    and not _NUMBERED_ROW.match(other.get("text") or "")
                    and abs(float(other["y0"]) - float(row["y0"])) <= 2.5
                    and float(row["x1"]) - 2 <= float(other["x0"]) < edge - 20]

        for cell in placed_blocks:
            text = _norm(cell.get("text") or "")
            if (cell.get("id") is None or not text
                    or len(text) > (120 if relaxed else 60)
                    or len(text.split()) > (20 if relaxed else 8)
                    or _NUMBERED_ROW.match(cell.get("text") or "")
                    or re.match(r"^[(\[]", text)
                    or _DESIGNATION_CELL.fullmatch(text)):
                continue
            top, left = float(cell["y0"]), float(cell["x0"])
            level = [row for row in rows if abs(float(row["y0"]) - top) <= 2.5]
            if len(level) != 1:
                continue
            row = level[0]
            if (left < float(row["x1"]) - 2
                    or (not relaxed and left >= edge - 20)
                    or index_of[id(cell)] >= index_of[id(row)]):
                continue
            table = any(abs(float(other["x0"]) - float(row["x0"])) <= 5
                        and cells_beside(other)
                        for other in rows if other is not row)
            if not table and relaxed:
                # A row carries words; a page number ("15", doc 1521 p15,
                # spanning the page) is not a row whose span proves a table.
                table = any(float(other["x0"]) < left
                            and float(other["x1"]) >= float(cell["x1"]) - 2
                            and re.search(r"[A-Za-z]{3,}", other.get("text") or "")
                            for other in all_rows if other is not row)
            if not table:
                continue
            moves.setdefault(id(row), []).append(cell)
            moving.add(id(cell))
    if not moving:
        return blocks
    out: list[dict] = []
    for block in blocks:
        if id(block) in moving:
            continue
        out.append(block)
        out.extend(sorted(moves.get(id(block), []), key=lambda cell: float(cell["x0"])))
    return out


_COLUMN_NUMBER_CELL = re.compile(r"\(\s*(\d{1,2})\s*\)")


def _column_number_cells(blocks: list[dict]) -> set[int]:
    """Profile rule `column_number_cells` (unreleased-v2): a table's column-index row.

    Tables in schedules and appendices number their columns "(1) (2) (3)"
    under the column heads, each index its own block on one line. Doc 2019
    p14 prints "S.No. / Nature of Power / Extent of Power" over "(1) (2) (3)";
    read as openers they became three empty sub-sections and the table's rows
    nested under the third. Two or more blocks on one page, each nothing but
    a bracketed number, set on one line (tops within 3 pt) and numbered 1, 2,
    3 ... from left to right, are that row: table text, never a provision.
    """
    by_page: dict = {}
    for block in blocks:
        if (block.get("id") is not None and block.get("y0") is not None
                and block.get("x0") is not None
                and _COLUMN_NUMBER_CELL.fullmatch(_norm(block.get("text") or ""))):
            by_page.setdefault(block.get("page_no"), []).append(block)
    found: set[int] = set()
    for cells in by_page.values():
        cells.sort(key=lambda cell: float(cell["y0"]))
        lines: list[list[dict]] = []
        for cell in cells:
            if lines and abs(float(cell["y0"]) - float(lines[-1][0]["y0"])) <= 3:
                lines[-1].append(cell)
            else:
                lines.append([cell])
        for line in lines:
            ordered = sorted(line, key=lambda cell: float(cell["x0"]))
            numbers = [int(_COLUMN_NUMBER_CELL.fullmatch(_norm(cell["text"])).group(1))
                       for cell in ordered]
            if len(numbers) >= 2 and numbers == list(range(1, len(numbers) + 1)):
                found.update(cell["id"] for cell in ordered)
    return found


def _promised_only_after_restart(entries: list[dict], key: str) -> bool:
    """Profile rule `schedule_contents_run`: does every printed contents entry
    for `key` sit after the contents numbering restarts at 1?"""
    labels = [_citation_label_key(str(entry.get("label") or "")) for entry in entries]
    restart = next((index for index in range(1, len(labels))
                    if labels[index] == "1" and "1" in labels[:index]), None)
    wanted = _citation_label_key(key)
    positions = [index for index, label in enumerate(labels) if label == wanted]
    return bool(restart is not None and positions
                and all(index > restart for index in positions))


_MEMBER_LIST_INTRO = re.compile(
    r"(?:\bconsist(?:s|ing)?\s+of|\bcomprising|\bcomposed\s+of|\bfollowing\s+"
    r"(?:members|persons|officers|officials)|\bnamely|\bas\s+(?:under|follows))"
    # A designation cell may follow the colon -- "- Chairperson" (doc 258),
    # "Member" (doc 1017), ".." (doc 1934).
    r"[^.;]{0,160}?[:\-–—]+\s*(?:-?\s*[A-Z][\w/ ]{0,30}|\.{2,})?\s*$", re.I)


def _introduces_member_list(node: "Node") -> bool:
    """Does this provision's own text end by introducing a numbered list?"""
    if node.kind not in ("section", "article", "subsection", "clause"):
        return False
    # The whole text's tail: doc 258 sets the first member's designation
    # ("- Chairperson") in its own block after the introduction.
    tail = _norm(" ".join(node.text_parts))[-200:]
    # Profile rule `enacting_formula_not_member_list` (unreleased-v4): doc 4296's Preamble
    # (f) ends 'It is hereby enacted as follows:-', which introduces no list.
    if profile_rule("enacting_formula_not_member_list") and _ENACTING_FORMULA_TAIL.search(tail):
        return False
    return bool(tail) and bool(_MEMBER_LIST_INTRO.search(tail))


# "Date: 05-08-2024" (Pakistan Code); "RGN- Dated. 13-08-2025" (a Sindh Code
# compiler's initials, doc 2950 p18).
_DOWNLOAD_STAMP = re.compile(
    r"(?:[A-Z]{2,5}\s*-\s*)?Dated?\s*[.:]\s*\d{1,2}-\d{1,2}-\d{4}")


def _download_stamp_blocks(body: list[dict]) -> set[int]:
    """Profile rule `download_stamp_furniture` (unreleased-v2).

    Pakistan Code PDFs print the download date -- "Date: 05-08-2024" -- at the
    foot of the last page, after a rule line; the text layer reads both into
    the last section (doc 2027 s.12 "6[Omitted] ____________ Date: 05-08-2024",
    doc 2215 s.14). A block that is only the stamp is page furniture, and so is
    a block of nothing but underscores directly above it on the same page.
    """
    found: set[int] = set()
    for index, block in enumerate(body):
        if block.get("id") is None or not _DOWNLOAD_STAMP.fullmatch(
                _norm(block.get("text") or "")):
            continue
        found.add(block["id"])
        prior = body[index - 1] if index else None
        if (prior is not None and prior.get("id") is not None
                and prior.get("page_no") == block.get("page_no")
                and re.fullmatch(r"_{5,}", _norm(prior.get("text") or ""))):
            found.add(prior["id"])
    return found


def _margin_heading_blocks(body: list[dict], headings: list[str | None],
                           tails: bool = False) -> set[int]:
    """Profile rule `margin_heading_blocks` (unreleased-v2): right-margin headings.

    A block set in the right margin -- starting at or beyond the right edge of
    the page's text column, taken as the median right edge of its long lines
    -- that is short, non-operative, and repeats one of the document's own
    contents headings exactly, is a margin heading, never text. The text layer
    otherwise reads it into whatever unit is open: doc 2386 p15 sets
    "Functions of the Board of Faculty." inside statute 2(3)'s sentence across
    the page break. The block keeps role `heading` in the ledger.

    `tails` is profile rule `margin_heading_tail` (unreleased-v3): a margin
    block that is the last two or more words of a contents heading is that
    heading's fragment. Doc 1142 sets "Application" beside s.4's first line on
    p2 (fused into the line) and "of laws." at the top of p3's margin, which
    the text layer read into s.4's sentence.
    """
    wanted = {lead for lead in (_heading_lead(value) for value in headings)
              if len(lead) >= 6}
    whole = [_heading_lead(value) for value in headings if value]
    by_page: dict = {}
    for block in body:
        by_page.setdefault(block.get("page_no"), []).append(block)
    found: set[int] = set()
    for blocks in by_page.values():
        edges = sorted(float(block["x1"]) for block in blocks
                       if block.get("x1") is not None
                       and len(_norm(block.get("text") or "")) >= 60)
        if len(edges) < 2:
            continue
        edge = edges[len(edges) // 2]
        for block in blocks:
            text = _norm(block.get("text") or "")
            if (block.get("id") is None or block.get("x0") is None
                    or float(block["x0"]) < edge - 2
                    or not text or len(text) > 110 or len(text.split()) > 14
                    or _HEADING_OPERATIVE.search(text)
                    or re.match(r"^[(\[\d]", text)):
                continue
            if _heading_lead(text) in wanted:
                found.add(block["id"])
            elif tails and len(text.split()) >= 2:
                # Only the END of a heading. Taking every piece out of the body
                # (doc 2983 splits "Tax treatment of the / income of the Fund.")
                # also took the evidence the contents linker reads beside each
                # opener, and 24 of its 28 rows fell unlinked.
                fragment = _heading_lead(text)
                if fragment and any(heading != fragment and heading.endswith(" " + fragment)
                                    for heading in whole):
                    found.add(block["id"])
    return found


def _margin_heading_pieces(body: list[dict], headings: list[str | None]) -> set[int]:
    """Profile rule `margin_heading_pieces` (unreleased-v3): a margin heading
    printed over several blocks.

    Doc 2983 sets each Scheme paragraph's margin heading over two or three
    blocks -- "Disbursement of" / "benefits.", "Tax treatment of the" /
    "income of the" / "workers." -- and where a piece fell after the opener in
    reading order its words were appended to the paragraph's text ("... shall
    be as under: Disbursement of benefits."). Right-margin blocks on a page,
    in order, are joined while the joined words stay the start of one of the
    document's contents headings; a group that completes one is that margin
    heading. The blocks stay in the walk -- the contents linker reads them
    beside each opener -- and only their text is kept out of the provision.
    """
    heads = {lead for lead in (_heading_lead(value) for value in headings) if len(lead) >= 6}
    by_page: dict = {}
    for block in body:
        by_page.setdefault(block.get("page_no"), []).append(block)
    found: set[int] = set()
    for blocks in by_page.values():
        edges = sorted(float(block["x1"]) for block in blocks
                       if block.get("x1") is not None
                       and len(_norm(block.get("text") or "")) >= 60)
        if len(edges) < 2:
            continue
        edge = edges[len(edges) // 2]
        # The left margin too: doc 258 sets "Short title, extent / and /
        # commencement." left of the text column (which starts at the median
        # left edge of the long lines), level with "1. (1) This Act ...".
        starts = sorted(float(block["x0"]) for block in blocks
                        if block.get("x0") is not None
                        and len(_norm(block.get("text") or "")) >= 60)
        left_edge = starts[len(starts) // 2] if starts else 0.0
        margin = sorted((block for block in blocks
                         if block.get("id") is not None and block.get("x0") is not None
                         and block.get("x1") is not None and block.get("y0") is not None
                         and (float(block["x0"]) >= edge - 2
                              or float(block["x1"]) <= left_edge + 2)
                         and 0 < len(_norm(block.get("text") or "")) <= 110),
                        key=lambda block: float(block["y0"]))
        group: list[dict] = []
        for block in margin:
            for attempt in (group + [block], [block]):
                joined = _heading_lead(" ".join(_norm(item["text"]) for item in attempt))
                if joined and any(head.startswith(joined) for head in heads):
                    group = attempt
                    break
            else:
                group = []
                continue
            if _heading_lead(" ".join(_norm(item["text"]) for item in group)) in heads:
                found.update(item["id"] for item in group)
                group = []
    return found


def _schedule_heading_with_reference(heading: str, following: list[str]) -> bool:
    """Profile rule `schedule_reference_lines`: an uppercase SCHEDULE display
    heading followed on the same page by the section it is made under.

    Doc 2846 prints "SCHEDULE STANDING ORDERS" then "( see section 2(1)(k))";
    doc 2950 prints "SCHEDULE", "STANDING ORDERS", "[SECTION 2(g)]" as three
    blocks. `_detached_schedule_reference` admits only a bare SCHEDULE and a
    plain section number on the very next line. At most one uppercase title
    line may stand between the heading and its reference.
    """
    if not _SCHEDULE_DISPLAY.fullmatch(_norm(heading)):
        return False
    lines = [_norm(value) for value in following[:2]]
    if lines and _SECTION_REFERENCE_LINE.fullmatch(lines[0]):
        return True
    if (len(lines) == 2 and bool(_UPPER_TITLE_LINE.fullmatch(lines[0]))
            and bool(_SECTION_REFERENCE_LINE.fullmatch(lines[1]))):
        return True
    # Profile rule `schedule_title_reference_unit` (unreleased-v4): doc 4263
    # p11 prints "THE SCHEDULE" and then, in ONE block, "SCHEME / [(See
    # section 2(e)]" -- the title and the reference together, the reference
    # opened by a doubled bracket -- so nothing proved the Schedule and the
    # Scheme's paragraphs became the Act's sections.
    if profile_rule("schedule_title_reference_unit") and following:
        parts = [re.sub(r"^\[\s*\(", "[", part.strip())
                 for part in following[0].split("\n") if part.strip()]
        return (len(parts) == 2 and bool(_UPPER_TITLE_LINE.fullmatch(_norm(parts[0])))
                and bool(_SECTION_REFERENCE_LINE.fullmatch(_norm(parts[1]))))
    return False


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
        remainder = starred_undotted.group(2).strip()
        # A raised amendment marker with omission stars can start an extracted
        # block in the MIDDLE of a sentence. Doc 527 prints "4*****] of the
        # Central Government..." inside section 3(1), while its contents
        # separately promise a real section 4 on the next page. Only the bare
        # starred omission is a provision opener; words after the closing
        # bracket need independent heading evidence, not the label alone.
        if label in toc and not remainder:
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


# A printed name closes where the SOURCE closes it: at a full stop, at a stop
# followed by a dash, or at a bare em/en dash. Pakistani drafting sets a
# section as "37. Penalty for obstructing inspector.-- Whoever ..." and a
# schedule row as "15. Office Assistant - cum- Storekeeper".
_NAME_CLOSE = re.compile(r"\.\s*[\u2013\u2014-]|[\u2013\u2014]|\.\s+(?=[A-Z(])")

# `_HEADING_OPERATIVE` above is narrower than the list
# `tools/census_heading_mislabel.py` arrived at over four rounds of review, and
# a longer name span is exactly what exposes the difference: doc 893 prints
# "Any owner of a boiler who refuses or without reasonable excuse neglects -",
# which is a penalty's opening words and not a name, and carries no word on the
# shorter list. Use the census's list here so the parser and the audit agree on
# what "a name is not operative text" means.
_NAME_ENACTS = re.compile(
    r"\b(?:shall|may|must|means?|includes?|is|are|was|were|has|have|had|be|"
    r"been|appl(?:y|ies|ied)|extends?|comes?|said|this|these|whoever|nothing|"
    r"no|any|every|where|when|unless|if|subject|notwithstanding|provided|"
    r"following|hereby|such|there)\b", re.I)

# A name never opens with a preposition. Every Sindh and Punjab Finance Act
# prints its amending sections as "2. In the Stamp Act, 1899, in its
# application to Sindh, ..." with the real heading in the margin.
_NAME_PREPOSITION = re.compile(
    r"^(?:in|of|for|to|on|at|by|from|under|upon|after|before|throughout|"
    r"where|when|while|if|save|except|with|without|during|against|"
    r"notwithstanding|subject|provided|according|pursuant|whenever|whereas)\b",
    re.I)

# Editorial apparatus is not a name. Doc 1382's section 2 prints "Clause (d)
# omitted by Khyber Pakhtunkhwa Ordinance ..." where the real marginal note is
# "Definitions." -- a footnote standing at the head of a provision, which is
# A10's defect and counted there.
_NAME_APPARATUS = re.compile(
    r"^\s*(?:clause|sub-?section|sub-?rule|proviso|words?|figures?|letters?|"
    r"brackets?|commas?|entry|entries|schedule)\b[^\n]{0,80}?"
    r"\b(?:omitted|substituted|subs\.|ins\.|inserted|added|deleted|rep\.)\b"
    r"|^\s*(?:subs\.|ins\.|added|omitted|substituted|inserted)\b", re.I)


def _one_printed_name(first: str, second: str) -> bool:
    """One name written two ways, by any of the three measured equivalences."""
    a = re.sub(r"[^a-z0-9]", "", (first or "").lower())
    b = re.sub(r"[^a-z0-9]", "", (second or "").lower())
    if not a or not b:
        return False
    if a.startswith(b) or b.startswith(a):
        return True
    if _same_printed_name(first, second):
        return True
    # Whole-name similarity, for a single lost or swapped glyph in a word too
    # short for `_same_printed_name`'s four-character fuzzy floor: doc 3548
    # prints "Law Average Yields ..." against a contents "Low Average Yields
    # ...", and doc 4458 "contrary to law" against "contrary to taw".
    return SequenceMatcher(None, a, b).ratio() >= 0.9


def _prints_the_name_itself(flat: str, promised: str) -> bool:
    """Does this unit's own text PRINT the promised name rather than contradict it?

    A marginal note is not always emitted as its own block. Doc 2384 sets its
    section as "Any person who - Punishment for attempt to cause explosion, or
    for making or keeping explosive with intent to endanger life or property."
    -- note fused after the operative opener -- and doc 3708 wedges "variations
    of entries in records." into the MIDDLE of section 45's sentence. In both
    the contents list is agreeing with the page, and the heading must stand.

    Two tests, because the note arrives both ways. A span between two printed
    name-closes may BE the name; a span that enacts is not a name, which is
    what keeps a coincidence out. Inside running prose the floor is three
    consecutive words: doc 4043's contents runs one row ahead of the body and
    promises "Following procedure" for a rule actually named "Procedure for the
    selection of apprentices", and that two-word phrase does occur in its body.
    Two words of overlap is not evidence; a three-word run of a name is.
    """
    for span in _NAME_CLOSE.split(flat):
        candidate = span.strip(" \u2014\u2013-:;,")
        if candidate and not _NAME_ENACTS.search(candidate) \
                and _one_printed_name(candidate, promised):
            return True
    want, have = _name_tokens(promised), _name_tokens(flat)
    if len(want) < 3:
        return False
    best = 0
    for i in range(len(want)):
        for j in range(len(have)):
            n = 0
            while (i + n < len(want) and j + n < len(have)
                   and want[i + n] == have[j + n]):
                n += 1
            best = max(best, n)
    return best >= 3 and best / len(want) >= 0.6


def _source_closed_name_disagrees(own_text: str, promised: str) -> bool:
    """The schedule-row branch: read the name the way the source closes it.

    Runs only where `_names_another_section`'s twelve-word span to the first
    full stop declines to judge, and can only ADD a refusal. It never reads a
    LONGER span than that rule would: doc 2366's "Add. by Punjab Act IV of
    1944, s. 4." closes at its first stop and must keep closing there, or
    editorial apparatus starts reading as a name.
    """
    flat = _norm(own_text or "")
    head = min(_NAME_CLOSE.split(flat)[0], flat.split(".")[0],
               key=len).strip(" \u2014\u2013-")
    if not (2 <= len(head.split()) <= 14) or len(head) > 90:
        return False
    if _NAME_ENACTS.search(head):
        return False
    if _NAME_PREPOSITION.match(head) or _NAME_APPARATUS.match(head):
        return False
    if len(re.sub(r"[^a-z0-9]", "", head.lower())) < 10:
        return False
    if len(re.sub(r"[^a-z0-9]", "", promised.lower())) < 10:
        return False
    if _prints_the_name_itself(flat, promised):
        return False
    return not _one_printed_name(head, promised)


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
    # Profile rule `definition_lead_not_name` (unreleased-v4): (doc 3803)
    if (profile_rule("definition_lead_not_name")
            and re.match(r"\s*In\s+(?:this|these)\s+(?:Act|Ordinance|Order|Rules?|Regulations?|Bye-?laws?|Statutes?)\b",
                         own_text or "", re.I)):
        return False
    # A schedule row's own name is closed by a dash and may run past twelve
    # words; the span below cannot see it. Strictly additive -- see
    # `_source_closed_name_disagrees`. Measured over a 13,159-call corpus
    # trace: 14 headings newly refused in 9 documents, 0 newly accepted.
    if _source_closed_name_disagrees(own_text, promised):
        return True
    flat = _norm(own_text or "")
    head = flat.split(".")[0].strip(" \u2014-")
    # Profile rule `abbreviated_name_guard` (unreleased-v2): a stop after an
    # abbreviation ends no name. Doc 264 s.2 opens "The 10[..] Property
    # Acquisition Ordinance, 1972 (11[..]Ord. No. XXII of 1972), is hereby
    # repealed." -- cut at "Ord.", the fragment read as the unit's own name
    # and withheld the contents heading.
    if profile_rule("abbreviated_name_guard") and _ABBREVIATION_END.search(head):
        return False
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


_ENACTING_WORDS = re.compile(
    r"\b(?:shall|may|must|means?|includes?|is|are|was|were|has|have|had|"
    r"appl(?:y|ies|ied)|extends?|comes?|whoever|nothing|provided|"
    r"notwithstanding|hereby|subject)\b", re.I)


_ABBREVIATION_END = re.compile(
    r"\b(?:No|Nos|Ord|Art|Arts|Sec|Secs|S|Ss|Cl|Rs|Govt|Deptt|Notf|Noti|Vol|"
    r"viz|vide|Mr|Dr|St|Co|Ltd|Pvt|W\.P|N\.W\.F\.P|P\.O)\s*$", re.I)


_PRINTED_HEADING_END = re.compile(
    r"^(.{0,150}?)(?:\.\s*[-–—]+\s*|:\s*[-–—]+\s*"
    r"|\.\s+(?=[A-Z(\d])|[.:]\s*$)")


def _printed_heading_extent(flat: str, cut: int) -> tuple[str, str] | None:
    """Profile rule `printed_heading_extent`: the body's own, longer heading.

    A contents list may shorten a heading the body prints in full: doc 2803's
    contents reads "Amendment of correct valuation" where rule 9 prints
    "Amendment of correct valuation list and the filling of objections
    thereto.- The notice ...". Cutting at the contents' length left "list and
    the filling of objections thereto.-" at the head of the rule's text. Where
    the printed words run on past the contents' name to the body's own heading
    terminator, the heading is the body's, in its own words. Operative words
    stop it: a heading does not "shall".
    """
    rest = flat[cut:]
    lead = rest.lstrip()[:1]
    if not rest or rest[0] in ".:;-–—(" or lead == "(" or lead.isdigit():
        return None
    # Profile rule `colon_closed_contents_heading` (unreleased-v4): doc 3142 closes the
    # contents name with a colon ('Ground for penalty:'); the printed heading ends there.
    if (profile_rule("colon_closed_contents_heading") and cut >= 2
            and flat[cut - 1] == ":" and not flat[:cut - 1].endswith(":")):
        return None
    match = _PRINTED_HEADING_END.match(rest)
    if match is None:
        return None
    tail = match.group(1)
    if ". " in tail or _HEADING_OPERATIVE.search(tail) or len(flat[:cut] + tail) > 200:
        return None
    return _norm(flat[:cut] + tail).rstrip(" .:"), _norm(rest[match.end():])


def _merged_margin_heading(flat: str, toc_heading: str
                           ) -> tuple[str, str] | None:
    """Profile rule `printed_heading_extent`: a margin heading the text layer
    merged into the unit's own block after its first sentence -- doc 1065's
    "2. The Gift Tax Act, 1963 (XIV of 1963), is hereby repealed. Repeal of
    Act XIV of 1963." -- is the heading, when it is a whole sentence that
    exactly repeats the contents' heading for this unit."""
    want = _heading_lead(toc_heading)
    if len(want) < 8:
        return None
    sentences = re.split(r"(?<=\.)\s+", flat)
    for index, sentence in enumerate(sentences[1:], start=1):
        if _heading_lead(sentence) == want and len(sentence) <= 110:
            rest = sentences[:index] + sentences[index + 1:]
            return _norm(sentence).rstrip(" ."), _norm(" ".join(rest))
    return None


def _printed_heading_line(flat: str, toc_heading: str) -> str | None:
    """Profile rule `printed_heading_extent`: a unit's line that is only its
    heading, in words the contents corroborates ("Collection of tax through
    tax-collecting staff." against the contents' "Collection of Tax through
    Tax Collection Staff"). The default path keeps such a line as text and
    then copies the contents' wording on as the heading."""
    line = flat.rstrip(" .:-–—")
    if (not line or len(line) > 110 or len(line.split()) > 14
            or _HEADING_OPERATIVE.search(line)
            or not re.fullmatch(r".*[.:\-–—]\s*", flat)
            or not _heading_supports(line, toc_heading)):
        return None
    return _norm(line)


def _split_heading_base(rest: str, toc_heading: str | None) -> tuple[str | None, str]:
    """Separate a section's heading from its text.

    With a contents entry this is known, not guessed: the entry IS the heading,
    so it is stripped from the front of the block and what remains is the text.
    Without one, fall back to the first sentence-like span, capped so a long
    opening sentence is never mistaken for a heading.
    """
    body = rest.lstrip(" .—-\t\n")
    # Profile rule `heading_only_rest` (unreleased-v3): doc 4222 inserts ss.22-B
    # to 22-D ("22-B. Reward and punishment.- (1) If any violation ...") after
    # its contents was printed, so no contents heading exists; once (1) has
    # parted, the rest is the name alone and the guess below refused it, so
    # the section's text became "Reward and punishment.-". A short capitalised
    # name closed by a full stop and a dash, with nothing after it, is the
    # heading.
    if not toc_heading and profile_rule("heading_only_rest"):
        alone = re.fullmatch(
            r"\s*([A-Z][^.;:]{2,80}?)\s*[.:]\s*[-–—―]+\s*", rest)
        if (alone and len(alone.group(1).split()) <= 12
                and not _HEADING_OPERATIVE.search(alone.group(1))
                # Profile rule `definition_lead_not_heading` (unreleased-v4): doc 3064
                # "2. In this Order:-" -- an interpretation lead-in is never a heading.
                and not (profile_rule("definition_lead_not_heading")
                         and re.match(r"In\s+(?:this|these)\s+(?:Act|Ordinance|Order|Rules?|Regulations?|"
                                      r"Bye-?laws?|Statutes?)\b", alone.group(1).strip(), re.I))):
            return alone.group(1).strip(), ""
    if toc_heading:
        flat = _norm(body)
        if flat.lower().startswith(toc_heading.lower()[: max(len(toc_heading) - 2, 8)]):
            # Profile rule `heading_prefix_of_sentence` (unreleased-v4): doc
            # 1534's contents names s.6 "Exemption." and the body prints "6.
            # Exemption from patrol duty may be granted.-"; stripping the name
            # took the sentence's first word, leaving "from patrol duty ...".
            # A name the printed text runs straight on from, into a lower-case
            # word, is the start of the sentence, not a heading printed apart.
            if profile_rule("heading_prefix_of_sentence"):
                core = toc_heading.rstrip(" .:-—–―")
                # ("Exemptions from ..." against the contents' "Exemption.")
                if (flat.lower().startswith(core.lower())
                        and re.match(r"[a-z]{0,3}\s+[a-z]", flat[len(core):len(core) + 6])):
                    return toc_heading, flat
            if profile_rule("printed_heading_extent"):
                extended = _printed_heading_extent(flat, len(toc_heading))
                if extended is not None:
                    return extended
                # Doc 2954 prints its dash as underscores: "Local extent.___(1)".
                return toc_heading, _norm(flat[len(toc_heading):]).lstrip(" .—-_")
            return toc_heading, _norm(flat[len(toc_heading):]).lstrip(" .—-")
        if profile_rule("printed_heading_extent"):
            own = _printed_heading_line(flat, toc_heading)
            if own is not None:
                return own, ""
            merged = _merged_margin_heading(flat, toc_heading)
            if merged is not None:
                return merged
            # The body prints a SHORTER name than the contents, closed by a
            # dash: doc 2954 "1. Short title.___(1) This Act ..." against the
            # contents' "Short title, commencement".
            short = re.match(r"^(.{4,110}?)[.:]?\s*[-–—_]{2,}\s*", flat)
            if (short and toc_heading.casefold().startswith(
                    short.group(1).casefold().rstrip(" ."))
                    and not _HEADING_OPERATIVE.search(short.group(1))):
                return _norm(short.group(1)).rstrip(" ."), _norm(flat[short.end():])
            # Profile rule `fuzzy_printed_heading` (unreleased-v2): the body's
            # own wording of the contents heading, closed by a stop and a dash
            # -- doc 3635 prints "3. Ground of penalty.-- Any one ..." against
            # the contents' "Grounds of penalty.".
            closed = re.match(r"^(.{4,110}?)\s*[.:]\s*[-–—_]+\s*", flat)
            if (closed and profile_rule("fuzzy_printed_heading")
                    and not _HEADING_OPERATIVE.search(closed.group(1))
                    and _heading_supports(closed.group(1), toc_heading)):
                return _norm(closed.group(1)).rstrip(" ."), _norm(flat[closed.end():])
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
        # Profile rule `printed_heading_extent`: a full stop after an
        # abbreviation ends no heading. Doc 1021's section 2 opens "In the
        # 8[..] Ordinance No. V of 1982, ..."; the guess named it "In the
        # 8[..] Ordinance No" and began its text at "V of 1982".
        # Nor is an enacting sentence a heading: doc 1065's section 2 opens
        # "The Gift Tax Act, 1963 (XIV of 1963), is hereby repealed."
        # (unreleased-v2 lets "to be" stand in a heading: doc 2215 prints
        # "14. Power of Act to be cumulative. All powers ...".)
        enacting = (_ENACTING_WORDS if profile_rule("heading_guess_to_be")
                    else _HEADING_OPERATIVE)
        if (m and profile_rule("printed_heading_extent")
                and (_ABBREVIATION_END.search(m.group(1))
                     or enacting.search(m.group(1)))):
            m = None
        # Profile rule `serial_abbreviation` (unreleased-v4): doc 3442 s.4
        # opens "In the Sindh Finance Act, 1964, in the Seventh Schedule, for
        # entries at Sr. No.1, 4 and 5, ..." -- "Sr." abbreviates "serial" --
        # and the guess named the section "In the ... for entries at Sr".
        if (m and profile_rule("serial_abbreviation")
                and re.search(r"\bSr\s*$", m.group(1))):
            m = None
        # Profile rule `presidency_act_abbreviation` (unreleased-v4): doc 1918
        # prints its repealed s.3 as "[Repeal of Bom. Act III of 1879.] rep.
        # by ..." -- "Bom." abbreviates Bombay, as "Ben."/"Beng." and "Mad."
        # abbreviate the other presidencies in old Acts -- and the guess named
        # the section "[Repeal of Bom". The name then comes from the contents.
        if (m and profile_rule("presidency_act_abbreviation")
                and re.search(r"\b(?:Bom|Ben|Beng|Mad)\s*$", m.group(1))):
            m = None
        if m:
            return _norm(m.group(1)), _norm(body[m.end():])
        return None, _norm(body)
    # Profile rule `dash_closed_heading_guess` (unreleased-v4): with no
    # contents list, doc 1695 prints "6. Recruitment, tenure of office and
    # terms and conditions of service.- Subject to ..."; the guess below wants
    # a stop and a space, never saw the stop and the dash, and ss.2, 5 and 6
    # carried their names as text. The name is one clause-free span: no
    # sentence ends inside it and it enacts nothing.
    if not toc_heading and profile_rule("dash_closed_heading_guess"):
        m = re.match(r"^(.{4,110}?)\.\s*[-–—―]+\s*(?=[A-Z(“\"‘])", _norm(body))
        if (m and not re.search(r"\.\s+[A-Z]", m.group(1))
                and not _HEADING_OPERATIVE.search(m.group(1))):
            return _norm(m.group(1)), _norm(_norm(body)[m.end():])
    m = re.match(r"^(.{4,110}?)\.\s+(?=[A-Z(])", _norm(body))
    # Profile rule `guessed_heading_guard` (unreleased-v4): without a contents
    # list, a sentence ending in "Act No." or enacting an inserted section is
    # still operative text, not a heading. Doc 1746 ss.2, 5, 8 and 9.
    if (m and profile_rule("guessed_heading_guard")
            and (_ABBREVIATION_END.search(m.group(1))
                 or _HEADING_OPERATIVE.search(m.group(1)))):
        m = None
    if m:
        flat = _norm(body)
        return _norm(m.group(1)), _norm(flat[m.end():])
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


def _subtree_chars(node) -> int:
    """Characters this unit carries, its descendants included.

    The measure the stub guard is written in: what a citation to this label
    would actually resolve to.
    """
    total = len(node.text or "")
    for child in node.children:
        total += _subtree_chars(child)
    return total


def _apply_source_reparents(root: Node, specifications: list[dict],
                            decisions: list[dict],
                            block_roles: dict) -> list[dict]:
    """Apply exact, source-reviewed parent changes after collision handling.

    The source and parent are addressed by immutable text-block ids.  Every
    address must resolve to exactly one node and cycles are refused.  This is
    deliberately not an inference rule: without reviewed specifications it is
    inert for the rest of the corpus.
    """
    enacted: list[dict] = []

    def descendants(node: Node):
        yield node
        for child in node.children:
            yield from descendants(child)

    def reset_depth(node: Node, depth: int) -> None:
        node.depth = depth
        for child in node.children:
            reset_depth(child, depth + 1)

    def section_label(node: Node) -> str | None:
        while node is not None and node is not root:
            if node.kind in ("section", "article"):
                return node.label
            node = node.parent
        return None

    for specification in specifications:
        source_block = int(specification["source_block_id"])
        parent_block = int(specification["parent_block_id"])
        kind = specification["kind"]
        source_label = specification.get("source_label")
        source_kind = specification.get("source_kind")
        # A section's first block usually also opens its sub-section (1) or
        # clause (a): "4. (1) The Board shall ..." is one block holding two
        # nodes. Without a qualifier such a parent can never be addressed, so
        # a reviewed spec may name the parent's label and/or kind exactly as it
        # may name the source's (docs 1572, 2745, 3172, 1834).
        parent_label = specification.get("parent_label")
        parent_kind = specification.get("parent_kind")
        # One block can open several sections' sub-sections (doc 4296 block
        # 666480 opens 17(1), 18(1) and 19(1)); a reviewed spec may then also
        # name the section the parent belongs to.
        parent_section = specification.get("parent_section_label")
        nodes = list(descendants(root))
        sources = [node for node in nodes if node is not root
                   and node.first_block == source_block
                   and (source_label is None or node.label == source_label)
                   and (source_kind is None or node.kind == source_kind)]
        parents = [node for node in nodes if node is not root
                   and node.first_block == parent_block
                   and (parent_label is None or node.label == parent_label)
                   and (parent_kind is None or node.kind == parent_kind)
                   and (parent_section is None
                        or section_label(node) == parent_section)]
        # Two nodes can share block, kind and label (doc 4447 block 810168
        # holds s.73(1)'s two provisos); a reviewed spec may then pick the
        # n-th match in tree order (1-based) for the source and/or parent.
        for key, matches in (("source_ordinal", sources), ("parent_ordinal", parents)):
            ordinal = specification.get(key)
            if ordinal is not None:
                if not 1 <= int(ordinal) <= len(matches):
                    raise ValueError(f"source reparent {key} {ordinal} of {len(matches)} matches")
                matches[:] = [matches[int(ordinal) - 1]]
        if len(sources) != 1 or len(parents) != 1:
            raise ValueError(
                "source reparent must resolve one node at each block: "
                f"source {source_block} matched {len(sources)}, "
                f"parent {parent_block} matched {len(parents)}")
        source, parent = sources[0], parents[0]
        if any(parent is node for node in descendants(source)):
            raise ValueError(
                f"source reparent {source_block}->{parent_block} creates a cycle")
        if source.parent is None or source not in source.parent.children:
            raise ValueError(
                f"source reparent block {source_block} has no stable old parent")
        source.parent.children.remove(source)
        source.parent = parent
        source.kind = kind
        parent.children.append(source)
        parent.children.sort(key=lambda child: (
            child.first_block is None,
            child.first_block if child.first_block is not None else 0,
        ))
        reset_depth(source, parent.depth + 1)
        for block_id in source.blocks:
            role, owner = block_roles.get(block_id, (None, None))
            if owner is source and role == "schedule_row":
                block_roles[block_id] = ("body", source)
        # The old S7 proposal described the now-repaired sibling collision.
        # Suppress its replacement candidate only when this exact moved node
        # participated in it; the immutable old candidate remains queryable.
        for decision in decisions:
            if source in (decision.get("candidate"), decision.get("canonical")):
                decision["settled_by_review"] = "reparent"
        enacted.append({
            "resolution": "reparent",
            "source_block_id": source_block,
            "parent_block_id": parent_block,
            "kind": kind,
            **({"source_label": source_label} if source_label is not None else {}),
            **({"source_kind": source_kind} if source_kind is not None else {}),
            **({"parent_label": parent_label} if parent_label is not None else {}),
            **({"parent_kind": parent_kind} if parent_kind is not None else {}),
        })
    return enacted


def _apply_source_schedule_form_group(root: Node, spec: dict,
                                      block_roles: dict) -> dict:
    """Group two source-reviewed forms under their shared printed schedule.

    A form label may be printed above the schedule heading it qualifies. The
    ordinary walk then opens an empty form followed by a schedule holding that
    form's body. This exact-block correction is inert without an accepted
    curation reading and refuses any tree shape other than the reviewed one.
    """
    def only(block_id: int, kind: str, label: str) -> Node:
        matches = [node for node in root.children
                   if node.first_block == block_id and node.kind == kind
                   and node.label == label]
        if len(matches) != 1:
            raise ValueError(f"schedule/form group expected one {kind} {label} "
                             f"at block {block_id}; found {len(matches)}")
        return matches[0]

    schedule_id = spec["schedule_block_id"]
    first_id = spec["first_form_block_id"]
    second_id = spec["second_form_block_id"]
    schedule = only(schedule_id, "schedule", spec["schedule_label"])
    first = only(first_id, "form", spec["first_form_label"])
    second = only(second_id, "form", spec["second_form_label"])
    siblings = root.children
    at = siblings.index(first)
    if siblings[at:at + 3] != [first, schedule, second]:
        raise ValueError("source schedule/form group nodes are not adjacent")
    if (first.text_parts or first.children or first.blocks != [first_id]
            or not schedule.text_parts or not second.text_parts
            or not schedule.blocks or schedule.blocks[0] != schedule_id
            or schedule.first_page != first.first_page
            or second.first_page != schedule.last_page):
        raise ValueError("source schedule/form group no longer matches reviewed tree")

    # Keep the schedule's own heading block with it. The subsequent blocks
    # and its child rows are the first nomination form's operative content.
    first.text_parts = schedule.text_parts
    schedule.text_parts = []
    body_blocks = [bid for bid in schedule.blocks if bid != schedule_id]
    first.blocks.extend(body_blocks)
    schedule.blocks = [schedule_id]
    first.children = schedule.children
    schedule.children = [first, second]
    for child in first.children:
        child.parent = first
    def reset_depth(node: Node, depth: int) -> None:
        node.depth = depth
        for child in node.children:
            reset_depth(child, depth + 1)
    for form in (first, second):
        form.parent = schedule
        reset_depth(form, schedule.depth + 1)
    first.last_page = schedule.last_page
    schedule.last_page = second.last_page
    siblings.remove(first)
    siblings.remove(second)
    for bid in body_blocks:
        role, owner = block_roles.get(bid, (None, None))
        if owner is schedule:
            block_roles[bid] = (role, first)
    return {"resolution": "source_schedule_form_group", **spec}


# ----------------------------------------- profile rule: contents alignment
#
# A printed contents list numbered at an offset from the body it lists. Doc
# 1014 (Sind Teaching, Promotion and Use of Sindhi Language Act 1972) lists
# "3. Constitution of Governing Body", which the Act does not have, and every
# later row runs one ahead: the body's section 3 is "Provincial Language",
# the contents' row 4. Docs 3078 and 244 count "Preamble" as row 1; 1486
# skips 4. The default parser links rows to units by number, so each unit in
# the offset run is named by the NEXT row's heading, the body's own printed
# heading lines are read as the previous unit's text, and the last row is
# left unlinked.
#
# The source itself says which unit a row names: the unit's own printed
# heading -- in its opening block, on the short lines just above it, or in a
# margin note just after it. This aligns rows to units on that evidence and
# nothing else, and fires only when the page refutes the number: some row's
# heading is printed at a unit with a DIFFERENT number, and not at the unit
# with its own. The re-parse is kept only if the citable units come out
# identical (`_contents_alignment_is_safe`). A row whose heading names no unit
# is left unlinked, for a page-read adjudication.
_ALIGN_HEADING_MAX = 110
_ALIGN_MAX_ROWS = 600


def _printed_heading_matches(evidence: str, heading: str | None) -> bool:
    """Does a line printed at a unit carry this contents heading?"""
    got = _heading_lead(evidence)
    want = _heading_lead(heading)
    if len(got) < 4 or len(want) < 4:
        return False
    if got == want:
        return True
    got_words = re.findall(r"[a-z0-9]+", got)
    want_words = re.findall(r"[a-z0-9]+", want)
    # Cheap and conservative: the first printed word must agree before the
    # segmenter's own corroboration test is consulted at all.
    if not got_words or not want_words or got_words[0] != want_words[0]:
        return False
    return min(len(got), len(want)) >= 8 and _heading_supports(evidence, heading)


def _units_heading_evidence(units: list["Node"], blocks: list[dict]
                            ) -> list[tuple[list[str], list[str], list[str]]]:
    """For each unit, in order: (lines printed at or above it, weaker lines,
    sentences of its own span that count only as an exact heading).

    Several units can open in one block (doc 1065 prints "2. The Gift Tax Act
    ... is hereby repealed. Repeal of Act XIV of 1963. 3. In the West ..."),
    so each unit's own span runs from its number to the next unit's number in
    that block, and only the last unit in a block owns the line after it.
    """
    index = {block.get("id"): i for i, block in enumerate(blocks)}
    out: list[tuple[list[str], list[str], list[str]]] = []
    cursor: dict[int, int] = {}
    for position, node in enumerate(units):
        following = units[position + 1] if position + 1 < len(units) else None
        shares_block = (following is not None
                        and following.first_block == node.first_block)
        out.append(_unit_heading_evidence(
            node, blocks, index, cursor,
            next_label=following.label if shares_block else None))
    return out


def _unit_heading_evidence(node: "Node", blocks: list[dict], index: dict,
                           cursor: dict | None = None,
                           next_label: str | None = None
                           ) -> tuple[list[str], list[str], list[str]]:
    """The lines the page prints at a unit: (own or above it, weaker, exact).

    `cursor` carries, per block, where the previous unit's number was found;
    `next_label` names the unit that opens later in the same block, if any.
    """
    at = index.get(node.first_block)
    if at is None:
        return [], [], []
    block = blocks[at]
    page = block.get("page_no")
    opener = _norm(block.get("text") or "")
    start = (cursor or {}).get(at, 0)
    number = re.compile(
        rf"(?<![\w(]){re.escape(node.label)}\s*[.)]\s*").search(opener, start)
    if number is not None and cursor is not None:
        cursor[at] = number.end()
    own = opener[number.end():] if number else opener
    if next_label is not None:
        stop = re.search(rf"(?<![\w(]){re.escape(next_label)}\s*[.)]\s", own)
        if stop is not None:
            own = own[:stop.start()]
    strong = [own[:160]]
    # The lines above a block are this unit's only when the unit opens the
    # block. Doc 3078 prints "Short title, extent and commencement." above a
    # block that begins with section 1's "(2) It shall extend ..." and only
    # later opens section 2.
    above_owned = number is not None and number.start() <= 2

    def heading_line(position: int) -> str | None:
        if position < 0 or blocks[position].get("page_no") != page:
            return None
        value = _norm(blocks[position].get("text") or "")
        if not value or len(value) > _ALIGN_HEADING_MAX or classify(value):
            return None
        return value

    above = heading_line(at - 1) if above_owned else None
    if above is not None:
        strong.append(above)
        # The line before that belongs to this unit only as the first half of
        # a heading wrapped over two lines ("Short title, commencement" /
        # "and extent."); a finished line there is the previous unit's.
        wrapped = heading_line(at - 2)
        if wrapped is not None and not re.search(r"[.:—–-]\s*$", wrapped):
            strong.append(f"{wrapped} {above}")
    weak = []
    # A margin note the text layer merged into the unit's own span, after its
    # first sentence ("... is hereby repealed. Repeal of Act XIV of 1963.").
    # Only a whole sentence of the span can be one; it is inside the text,
    # not set apart from it, so it counts only as an EXACT printed heading.
    exact = [sentence for sentence in re.split(r"(?<=[.:;])\s+", own)[1:]
             if 8 <= len(sentence) <= _ALIGN_HEADING_MAX]
    # The line after the block is this unit's only if no later unit opens in
    # the same block.
    after = at + 1
    if (next_label is None and after < len(blocks)
            and blocks[after].get("page_no") == page):
        value = _norm(blocks[after].get("text") or "")
        if value and len(value) <= _ALIGN_HEADING_MAX and not classify(value):
            weak.append(value)
    return strong, weak, exact


def _contents_heading_alignment(seg: "Segmentation", blocks: list[dict],
                                explain: list | None = None
                                ) -> dict[str, str | None] | None:
    """Contents row ordinal -> body label its heading names, or None.

    None as the whole result: no alignment the source supports differs from
    the numbers. None as a value: the row's heading names no body unit.
    `explain`, when given, receives the anchors and the reason for a refusal.
    """
    def refuse(reason: str) -> None:
        if explain is not None:
            explain.append(reason)
        return None

    # Not only where a row is left unlinked: doc 2803 prints one more body
    # rule than its contents lists, so every row links -- each to the wrong
    # rule. The page's headings are the test, not the gap count.
    def under_division(node: Node) -> bool:
        parent = node.parent
        while parent is not None:
            if parent.kind in _AUXILIARY_KINDS:
                return True
            parent = parent.parent
        return False

    # A row the parse already joined to something inside a schedule, or to a
    # division itself, names no top-level unit: doc 2862's rows 49-59 are its
    # statutes. Left out of the alignment, such a row keeps its link.
    rows = [entry for entry in seg.toc_entries if entry["kind"] == "section"
            and (entry["node"] is None
                 or (entry["node"].kind in ("section", "article")
                     and not under_division(entry["node"])))]
    if not rows:
        return refuse("no contents rows")

    units = [node for node in seg.flatten()
             if node.kind in ("section", "article") and not under_division(node)]
    # The preamble shape is exact enough to hold for a two-section Act (doc
    # 306); the general alignment needs at least three units to anchor on.
    preamble_shape = bool(re.fullmatch(
        r"preamble\.?", _norm(rows[0].get("heading") or "").casefold()))
    if (len(units) < (1 if preamble_shape else 3)
            or len(rows) > _ALIGN_MAX_ROWS or len(units) > _ALIGN_MAX_ROWS):
        return refuse(f"size: {len(rows)} rows, {len(units)} units")
    evidence = _units_heading_evidence(units, blocks)
    unit_weights: dict[int, dict[int, int]] = {}

    def line_names(value: str, exact_only: bool) -> set[int]:
        """The rows one printed line names: only its best match. Doc 244
        lists "Amendment of 3[..] Act XII of 1973" and "Amendment of 4[..]
        Act X of 1977"; the looser test lets one printed line name both."""
        lead = _heading_lead(value)
        scored = []
        for index, row in enumerate(rows):
            heading = row.get("heading")
            if exact_only:
                want = _heading_lead(heading)
                matched = len(want) >= 8 and lead == want
            else:
                matched = _printed_heading_matches(value, heading)
            if matched:
                scored.append((SequenceMatcher(
                    None, lead, _heading_lead(heading)).ratio(), index))
        if not scored:
            return set()
        best = max(score for score, _ in scored)
        return {index for score, index in scored if score == best}

    def weight(row: dict, unit: int) -> int:
        if unit not in unit_weights:
            strong, weak, exact = evidence[unit]
            found: dict[int, int] = {}
            for tier, values, exact_only in ((2, strong, False), (1, weak, False),
                                             (1, exact, True)):
                for value in values:
                    for index in line_names(value, exact_only):
                        found[index] = max(found.get(index, 0), tier)
            unit_weights[unit] = found
        return unit_weights[unit].get(row["_row_index"], 0)

    rows = [dict(row, _row_index=index) for index, row in enumerate(rows)]

    if preamble_shape:
        return _preamble_row_alignment(rows, units, weight, refuse)

    n, m = len(rows), len(units)
    score = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            best = max(score[i + 1][j], score[i][j + 1])
            w = weight(rows[i], j)
            if w:
                # Ties go to the printed number, so the alignment departs from
                # it only where the headings outweigh it.
                same = (_citation_label_key(rows[i]["label"])
                        == _citation_label_key(units[j].label))
                best = max(best, score[i + 1][j + 1] + 4 * w + (1 if same else 0))
            score[i][j] = best
    anchors: list[tuple[int, int]] = []
    i = j = 0
    while i < n and j < m:
        w = weight(rows[i], j)
        same = (_citation_label_key(rows[i]["label"])
                == _citation_label_key(units[j].label))
        if w and score[i][j] == score[i + 1][j + 1] + 4 * w + (1 if same else 0):
            anchors.append((i, j))
            i, j = i + 1, j + 1
        elif score[i][j] == score[i + 1][j]:
            i += 1
        else:
            j += 1
    if explain is not None:
        explain.append("anchors: " + ", ".join(
            f"{rows[i]['label']}->{units[j].label}" for i, j in anchors))
    if len(anchors) < 3 or len(anchors) < 0.6 * n:
        return refuse(f"too few anchors: {len(anchors)} of {n} rows")

    # A shift must be corroborated. Doc 3880 prints its headings in a side
    # column and the text layer sets section 37's heading ("Departments to
    # render assistance ...") straight after section 36's block: one weak
    # anchor 37->36 between unshifted neighbours, which the gap fill then
    # turned into 36->35. Each run of consecutive shifted anchors needs two
    # anchors, or its one anchor printed on the unit's own line or above it.
    run: list[tuple[int, int]] = []
    for position, (i, j) in enumerate(anchors + [(-1, -1)]):
        shifted_here = (i >= 0 and _citation_label_key(rows[i]["label"])
                        != _citation_label_key(units[j].label))
        if shifted_here:
            run.append((i, j))
            continue
        if len(run) == 1 and weight(rows[run[0][0]], run[0][1]) < 2:
            i0, j0 = run[0]
            return refuse(f"uncorroborated shift: row {rows[i0]['label']} -> "
                          f"unit {units[j0].label} on a line after the unit only")
        run = []

    # The refutation: a row whose heading the page prints at a unit with a
    # different number, and NOT at the unit carrying its own number.
    by_label: dict[str, list[int]] = {}
    for j, node in enumerate(units):
        by_label.setdefault(_citation_label_key(node.label), []).append(j)
    shifted = 0
    for i, j in anchors:
        key = _citation_label_key(rows[i]["label"])
        if key == _citation_label_key(units[j].label):
            continue
        if any(weight(rows[i], own) for own in by_label.get(key, [])):
            return refuse(f"row {rows[i]['label']} is also printed at its own number")
        shifted += 1
    if not shifted:
        return refuse("every anchor agrees with the printed numbers")

    # Rows between two anchors pair one-to-one with the units between them,
    # in order, only when the counts agree; rows with no unit between their
    # anchors name nothing the body prints. Anything else is ambiguous, and an
    # ambiguous alignment is not used at all.
    mapping: dict[str, str | None] = {}
    bounds = [(-1, -1)] + anchors + [(n, m)]
    for (i0, j0), (i1, j1) in zip(bounds, bounds[1:]):
        gap_rows = list(range(i0 + 1, i1))
        gap_units = list(range(j0 + 1, j1))
        if gap_rows and gap_units and len(gap_rows) != len(gap_units):
            # No heading evidence inside the gap, so the printed number is
            # the only reading left -- usable when every row in the gap has
            # exactly one unit of its own number there, in order (doc 2803:
            # row 1 "Notification" against body rules 1 and 2).
            by_number = [[u for u in gap_units
                          if _citation_label_key(units[u].label)
                          == _citation_label_key(rows[r]["label"])]
                         for r in gap_rows]
            chosen = [found[0] for found in by_number if len(found) == 1]
            if len(chosen) != len(gap_rows) or chosen != sorted(set(chosen)):
                return refuse(f"ambiguous gap: rows "
                              f"{[rows[r]['label'] for r in gap_rows]} against units "
                              f"{[units[u].label for u in gap_units]}")
            gap_units = chosen
        for offset, row in enumerate(gap_rows):
            mapping[str(rows[row]["ordinal"])] = (
                units[gap_units[offset]].label if gap_units else None)
        if i1 < n:
            mapping[str(rows[i1]["ordinal"])] = units[j1].label
    return mapping


def _preamble_row_alignment(rows: list[dict], units: list["Node"], weight,
                            refuse) -> dict[str, str | None] | None:
    """A contents list that numbers the preamble as its first row.

    Docs 244, 306, 1021, 1065, 2954 and 3078 print "1. Preamble." at the head
    of the contents; the body prints the preamble unnumbered and numbers its
    sections from 1, so every later row names the section one below its own
    number. The shape is exact enough to take whole: the rows after the
    preamble must be numbered consecutively, each must have exactly one body
    unit one below it, no row's heading may be printed at the unit carrying
    its own number, and at least one row's heading must be printed at the
    unit one below. The preamble row names no unit.
    """
    first = rows[0]["label"]
    if not first.isdigit():
        return refuse("preamble row is not numbered")
    by_label: dict[str, list[int]] = {}
    for j, node in enumerate(units):
        by_label.setdefault(_citation_label_key(node.label), []).append(j)
    mapping: dict[str, str | None] = {str(rows[0]["ordinal"]): None}
    corroborated = False
    previous = -1
    for offset, row in enumerate(rows[1:], start=1):
        label = row["label"]
        if not label.isdigit() or int(label) != int(first) + offset:
            return refuse(f"preamble shape: row {label} out of sequence")
        below = by_label.get(str(int(label) - 1), [])
        if len(below) != 1 or below[0] <= previous:
            return refuse(f"preamble shape: no single unit {int(label) - 1}")
        if any(weight(row, own) for own in by_label.get(label, [])):
            return refuse(f"row {label} is also printed at its own number")
        corroborated = corroborated or bool(weight(row, below[0]))
        previous = below[0]
        mapping[str(row["ordinal"])] = units[below[0]].label
    if not corroborated:
        return refuse("preamble shape: no heading printed one below its number")
    return mapping


_STATUTES_ROW = re.compile(r"^(?:the\s+)?(?:first\s+)?statutes?\.?$", re.I)


def _link_statute_rows(resolved_entries: list[dict], flat_nodes: list["Node"],
                       blocks: list[dict]) -> None:
    """Profile rule `first_statutes_schedule`: contents rows for the statutes.

    A university Act's contents names its schedule of First Statutes either
    by one row ("39. Statutes.", doc 2922) or by listing the statutes
    themselves, numbered on from the Act's own sections (doc 2872 rows 28-38
    are statutes 1-11). Neither number is the statute's own. A row naming the
    schedule links to it; a trailing run of unlinked rows after the Act's last
    linked section pairs with the statutes in order, only when the counts are
    equal, the statutes are numbered 1..n, and at least half of the pairs
    carry the row's heading on the page at that statute.
    """
    schedules = [node for node in flat_nodes if node.kind == "schedule"
                 and re.search(r"statutes", node.label, re.I)]
    if len(schedules) != 1:
        return
    schedule = schedules[0]
    for entry in resolved_entries:
        if (entry["node"] is None and entry["kind"] == "section"
                and _STATUTES_ROW.match(_norm(entry.get("heading") or ""))):
            entry["node"], entry["method"] = schedule, "statutes_schedule"
    items = [child for child in schedule.children if child.kind == "clause"]
    if not items or [item.label for item in items] != [
            str(number) for number in range(1, len(items) + 1)]:
        return
    last_linked = max((index for index, entry in enumerate(resolved_entries)
                       if entry["node"] is not None and entry["kind"] == "section"
                       and entry["node"].kind in ("section", "article")),
                      default=-1)
    tail = resolved_entries[last_linked + 1:]
    if (len(tail) != len(items)
            or any(entry["node"] is not None or entry["kind"] != "section"
                   for entry in tail)):
        return
    index = {block.get("id"): i for i, block in enumerate(blocks)}

    def printed_here(entry: dict, item: "Node") -> bool:
        at = index.get(item.first_block)
        if at is None:
            return False
        lines = [_norm(blocks[at].get("text") or "")]
        if at > 0:
            before = _norm(blocks[at - 1].get("text") or "")
            lines.append(re.split(r"(?<=[.:;])\s+", before)[-1])
        lines.append(item.heading or "")
        if profile_rule("statute_rows_margin_evidence"):
            own = blocks[at]
            for other in blocks:
                if (other is not own and other.get("page_no") == own.get("page_no")
                        and other.get("x0") is not None and own.get("x1") is not None
                        and float(other["x0"]) >= float(own["x1"]) - 2):
                    lines.extend(_norm(piece) for piece in re.split(r"\n[ \t]*\n", other.get("text") or "")
                                 if _norm(piece))
        return any(_printed_heading_matches(line, entry.get("heading"))
                   or _heading_lead(line) == _heading_lead(entry.get("heading"))
                   for line in lines if line)

    corroborated = sum(1 for entry, item in zip(tail, items)
                       if printed_here(entry, item))
    if corroborated * 2 < len(items):
        return
    for entry, item in zip(tail, items):
        entry["node"], entry["method"] = item, "statutes_order"


def _contents_alignment_is_safe(before: "Segmentation",
                                after: "Segmentation") -> bool:
    """The alignment may rename and relink; it may not restructure."""
    def citable(seg: Segmentation) -> list[tuple[str, str]]:
        return [(node.kind, node.label) for node in seg.flatten()
                if node.kind in ("section", "article")]

    def open_collisions(seg: Segmentation) -> int:
        return sum(1 for decision in seg.repeated_label_decisions
                   if not decision.get("settled_by_review"))

    def linked(seg: Segmentation) -> int:
        return sum(1 for entry in seg.toc_entries if entry["node"] is not None)

    return (citable(before) == citable(after)
            and open_collisions(after) <= open_collisions(before)
            and linked(after) >= linked(before))


# Segmentation profiles (docs/SEGMENTATION-PROFILES.md, migration 0056).
#
# One parser, several rule sets. "default" is the parser every released tree
# was built with and must stay byte-identical; a named profile switches on
# additional rules. A document is parsed under a profile only when its source
# observation is pinned to it (segmentation_profile_pin), and the pin is only
# accepted while nothing built from that observation is released -- so a
# profile rule can repair blocked documents without re-parsing a released one.
#
# A rule helper asks `profile_rule("name")`; the active rule set lives in a
# context variable for the duration of one `segment()` call, so the parser's
# internal re-parses (`_segment`) inherit it.
SEGMENTATION_PROFILES: dict[str, frozenset[str]] = {
    "default": frozenset(),
    "unreleased-v1": frozenset({
        "contents_heading_alignment",
        "printed_heading_extent",
        "prose_explanation_word",
        "first_statutes_schedule",
        "schedule_reference_lines",
    }),
}
# A profile is frozen once something is released under it (migration 0057):
# a rule that would change a tree already released under `unreleased-v1`
# opens the next profile instead.
SEGMENTATION_PROFILES["unreleased-v2"] = SEGMENTATION_PROFILES["unreleased-v1"] | {
    "margin_heading_blocks",
    "contents_false_rows",
    "download_stamp_furniture",
    "heading_guess_to_be",
    "abbreviated_name_guard",
    "lowercase_heading_split",
    "page_number_furniture",
    "fuzzy_printed_heading",
    "introduced_member_list",
    "designation_cells",
    "quoted_form_letter",
    "divisions_end_body",
    "quoted_division_letter",
    "row_aligned_cells",
    "column_number_cells",
    "decoded_quote_openers",
    "enacting_formula_ends",
    "sequential_chapter_heading",
    "member_list_closing_words",
    "tight_first_subsection",
}
# Migration 0058: `wrapped_bracket_reference` would also mend doc 2846 standing
# order 13(3), a tree released under `unreleased-v2`. v3 froze in turn; see
# `unreleased-v4` below.
SEGMENTATION_PROFILES["unreleased-v3"] = SEGMENTATION_PROFILES["unreleased-v2"] | {
    "wrapped_bracket_reference",
    "level_margin_heading_owner",
    "schedule_contents_run",
    "bracketed_omission_stub",
    "printed_disposition_rows",
    "sequence_omission_stub",
    "decoded_dash_first_subsection",
    "promulgating_formula_ends",
    "sequence_bare_number",
    "mark_only_heading_none",
    "exception_word_boundary",
    "tight_first_clause",
    "inblock_footnote_tail",
    "heading_only_rest",
    "row_cells_within_rows",
    "marked_clause_opener",
    "margin_heading_tail",
    "schedule_item_list",
    "body_start_keeps_contents",
    "margin_heading_pieces",
    "leading_margin_heading_unit",
    "designation_before_opener",
    "designation_bracket_rows",
}
# Migration 0059: `level_margin_heading_text` would also name doc 2983's Scheme
# paragraphs 4 and 6, a tree released under `unreleased-v3`.
SEGMENTATION_PROFILES["unreleased-v4"] = SEGMENTATION_PROFILES["unreleased-v3"] | {
    "source_body_start_contetns_typo",
    "bounded_subpart_duplicate_scan",
    "ascii_quote_openers",
    "level_margin_heading_text",
    "contents_bare_number_rows",
    "paren_amendment_opener",
    "detached_heading_after_division",
    "long_romanettes",
    "dash_closed_heading_guess",
    "bracketed_rule_reference_division",
    "preamble_not_in_auxiliary",
    "bracketed_repeal_stub_cut",
    "presidency_act_abbreviation",
    "quoted_insertion_span",
    "repeated_label_note_rows",
    "heading_prefix_of_sentence",
    "subsection_then_clause_cut",
    "part_range_label",
    "sequential_chapter_title",
    "lettered_part_label",
    "hyphen_suffix_labels",
    "percent_led_item",
    "contents_banner_block",
    "form_code_number",
    "unbracketed_division_reference",
    "rs_line_item",
    "form_word_not_letter",
    "bracketed_sub_rule_reference",
    "marked_first_subsection",
    "marked_clause_cut",
    "quoted_schedule_heading",
    "serial_abbreviation",
    "joint_schedule_heading",
    "bracket_not_division_label",
    "member_designation_row",
    "quoted_definition_cut",
    "lowercase_suffix_subsection",
    "lowercase_section_start",
    "quote_before_bracket",
    "closed_marked_first_subsection",
    "letter_closing_finished",
    "new_section_paragraph_not_note",
    "bracketed_section_number",
    "schedule_title_reference_unit",
    "repeated_letter_clause",
    "regulation_then_decimal_child",
    "kept_contents_stop_at_body_start",
    "standalone_form_before_schedule",
    "duplicate_witness_fields_as_form_text",
    "guessed_heading_guard",
    "quoted_item_label",
    "stray_close_extends_span",
    "quoted_definitions_after_omission",
    "referenced_table_heading",
    "no_cut_after_number_abbreviation",
    "page_first_running_header",
    "whole_schedule_quote",
    "amendment_items_owner",
    "in_respect_of_not_opener",
    "parenthesised_letter_label",
    "clause_then_romanette_cut",
    "suffixed_decimal_label",
    "rule_range_not_opener",
    "sequential_part_heading",
    "hyphen_letter_division_label",
    "lettered_paragraph_sequence",
    "quoted_schedule_word_owner",
    "sequential_form_label",
    "colon_closed_heading_guess",
    "schedule_word_rows_own_items",
    "first_lettered_part_in_schedule",
    "sequential_schedule_heading",
    "quoted_sequential_form_label",
    "decimal_rule_resumes",
    "appended_form_at_page_top",
    "letter_number_form_code",
    "label_only_heading_none",
    "not_reproduced_text",
    "enactment_chapter_reference",
    "repeated_label_section_note_rows",
    "left_column_margin_heading",
    "whole_section_quote",
    "numbered_marked_first_subsection",
    "quoted_first_definition",
    "marked_suffixed_definition",
    "bare_trailing_label_cut",
    "apparatus_over_margin_heading",
    "dotted_omission_stub_cut",
    "ordinal_schedule_reference",
    "enacting_formula_not_member_list",
    "dotted_contents_row_cut",
    "last_promised_section_after_schedule",
    "serial_column_header_owner",
    "colon_closed_contents_heading",
    "contents_row_decimal_cut",
    "titled_appended_form",
    "definition_lead_not_heading",
    "schedule_amendment_item",
    "schedule_item_rows_in_order",
    "quoted_part_span",
    "body_start_without_contents",
    "ordinal_quoted_schedule_word",
    "repeated_decimal_label_cut",
    "dotted_other_heading",
    "indented_list_item_continues",
    "schedule_title_first_statutes",
    "statute_rows_margin_evidence",
    "bare_number_schedule_name_row",
    "side_noted_definition_cut",
    "numbered_schedule_form",
    "misprinted_chapter_word",
    "misprinted_form_word",
    "quoted_hyphen_form_label",
    "appendix_number_label",
    "lowercase_hyphen_label_cut",
    "ditto_item_cut",
    "dotted_nameless_contents_row",
    "number_abbreviation_line_end",
    "definition_lead_not_name",
    "contents_leader_page_strip",
    "omission_stub_closes_table",
    "fbr_definition_label",
    "label_then_marked_text_cut",
    "marked_proviso_cut",
    "bare_marker_label",
    "multi_letter_subsection",
    "marked_chapter_heading",
    "marked_lettered_omission_stub",
    "bare_bracket_clause_cut",
    "inserted_three_letter_clause",
    "closed_marked_clause_cut",
    "four_letter_section_suffix",
    "bare_omission_stub",
    "e_prefix_section_start",
    "high_ordinal_schedule",
    "column_head_line_cut",
    "schedule_tables_annexes_parts",
    "roman_stub_item_cut",
    "stub_row_cut",
    "schedule_table_rows_own_items",
    "capital_letter_item",
    "figure_led_item",
    "four_digit_marker_label_cut",
    "range_stub_row",
    "marked_quoted_label",
    "stacked_marker_row",
    "schedule_division_heading_lines",
    "unnumbered_tail_provision",
    "unnumbered_root_provision",
}
_ACTIVE_PROFILE_RULES: contextvars.ContextVar[frozenset[str]] = (
    contextvars.ContextVar("segmentation_profile_rules", default=frozenset()))


def profile_rule(name: str) -> bool:
    """Is profile rule `name` switched on for the parse in progress?"""
    return name in _ACTIVE_PROFILE_RULES.get()


def segment(blocks: list[dict], curation_patches: list[dict] | None = None,
            toc_dispositions: list[dict] | None = None,
            split_fused_margins: bool = False,
            detect_contents: bool = True,
            force_opening_contents: bool = False,
            structural_resolutions: list[dict] | None = None,
            structural_overrides: dict | None = None,
            profile: str = "default") -> Segmentation:
    """Build the provision tree.

    `blocks` are dicts with text, page_no, y0, page_height and id, in reading
    order -- exactly what text_block stores. `profile` names the rule set
    (SEGMENTATION_PROFILES); callers normally leave it to
    nizam.workers.segment.build(), which reads the observation's pin.
    """
    if profile not in SEGMENTATION_PROFILES:
        raise ValueError(f"unknown segmentation profile {profile!r}")
    token = _ACTIVE_PROFILE_RULES.set(SEGMENTATION_PROFILES[profile])
    sequence_token = _LETTERED_SEQUENCE.set(
        _lettered_paragraph_sequence(blocks) if profile_rule("lettered_paragraph_sequence")
        else frozenset())
    decimal_rows_token = _CONTENTS_DECIMAL_ROWS.set(
        _contents_decimal_rows(blocks) if profile_rule("contents_row_decimal_cut") else frozenset())
    repeated_decimal_token = _REPEATED_DECIMAL_LABELS.set(
        _repeated_decimal_labels(blocks) if profile_rule("repeated_decimal_label_cut") else frozenset())
    forms_token = _SEQUENTIAL_FORMS.set(
        _sequential_form_labels(blocks) if profile_rule("sequential_form_label") else frozenset())
    try:
        seg = _segment(blocks, curation_patches=curation_patches,
                       toc_dispositions=toc_dispositions,
                       split_fused_margins=split_fused_margins,
                       detect_contents=detect_contents,
                       force_opening_contents=force_opening_contents,
                       structural_resolutions=structural_resolutions,
                       structural_overrides=structural_overrides)
        # Profile rule `mark_only_heading_none` (unreleased-v3): doc 2818's
        # contents prints "*****" for every rule it gives no name -- rules 9,
        # 12 and 22 among them, printed in full in the body without a heading
        # -- and the late heading copy put the marks on those rules. A heading
        # of nothing but asterisks or leader dots names nothing. Run on the
        # finished parse, after every heading copy.
        if profile_rule("mark_only_heading_none"):
            for node in seg.flatten():
                if (node.kind in ("section", "article") and node.heading
                        and node.operation != "omitted"
                        and _MARK_ONLY_ROW.fullmatch(_norm(node.heading))):
                    node.heading = None
    finally:
        _LETTERED_SEQUENCE.reset(sequence_token)
        _SEQUENTIAL_FORMS.reset(forms_token)
        _CONTENTS_DECIMAL_ROWS.reset(decimal_rows_token)
        _REPEATED_DECIMAL_LABELS.reset(repeated_decimal_token)
        _ACTIVE_PROFILE_RULES.reset(token)
    seg.profile = profile
    return seg


# Profile rule `lettered_paragraph_sequence` (unreleased-v4): doc 4330 reg 53
# prints "21[(2)-A. Proper arrangements ..." and then, each opening its own
# block, "B. Where the slope ...", "C. All platforms ..." ... "K. whenever ...";
# its footnote calls them "Sub-regulation 2-A to K". No grammar reads a single
# capital with a stop, so A stayed as "-A. Proper ..." in (2) and B-K ran into
# clause (d) and a proviso. The paragraphs are recognised only as a sequence:
# after a block printing "(N)-A. Capital", blocks opening "B.", "C.", ... in
# order, until a block opens a sub-section "(n)" or a numbered provision.
_LETTERED_SEQUENCE: contextvars.ContextVar[frozenset[str]] = contextvars.ContextVar(
    "lettered_paragraph_sequence", default=frozenset())
# Profile rule `repeated_decimal_label_cut` (unreleased-v4): doc 2324: a decimal label after a blank line mid-block that opens a line elsewhere starts a unit.
_REPEATED_DECIMAL_LABELS: contextvars.ContextVar[frozenset] = contextvars.ContextVar(
    "repeated_decimal_labels", default=frozenset())


def _repeated_decimal_labels(blocks):
    """Profile rule `repeated_decimal_label_cut`: decimal labels (2-4 levels) that open a line in two blocks."""
    seen = {}
    for b in blocks:
        for m in re.finditer(r"(?:^|\n)[ \t\u00a0]*(\d{1,2}(?:\.\d{1,2}){1,3})\.?(?=[ \t\u00a0]*\n|[ \t\u00a0]+[A-Z*])",
                             b.get("text") or ""):
            seen.setdefault(m.group(1), set()).add(b.get("id"))
    return frozenset(k for k, v in seen.items() if len(v) >= 2)


# Profile rule `contents_row_decimal_cut`: the document's one-line decimal contents rows.
_CONTENTS_DECIMAL_ROWS: contextvars.ContextVar[frozenset] = contextvars.ContextVar(
    "contents_decimal_rows", default=frozenset())


def _contents_decimal_rows(blocks: list[dict]) -> frozenset:
    """(label, first word) of every one-line block 'N.M Name' -- a decimal contents row printed alone."""
    rows = set()
    for b in blocks:
        m = re.fullmatch(r"\s*(\d{1,2}\.\d{1,2})(?:[ \t]+|[ \t]*\n[ \t]*)([A-Z][A-Za-z-]*)[^\n]{0,100}?\s*",
                         b.get("text") or "")
        if m:
            rows.add((m.group(1), m.group(2).casefold()))
    return frozenset(rows)
_LETTERED_SHAPE = re.compile(r"\(\s*\d{1,3}\s*\)-A\.\s+[A-Z]")
_LETTERED_SUBSECTION = re.compile(r"^\s*(?:\d{1,3}\s*)?\[?\s*\(\s*(\d{1,3})\s*\)\s*$")
_LETTERED_PARAGRAPH = re.compile(r"^\s*-?([A-K])\.\s+(?=[A-Za-z])(.*)$", re.S)
_LETTERED_CUT = re.compile(
    r"(?:(?<=\(\d\))|(?<=\(\d\d\)))(?=-A\.\s+[A-Z])|(?<=\n)[ \t]*(?=[B-K]\.\s+[A-Za-z])")


def _lettered_paragraph_sequence(blocks: list[dict]) -> frozenset[str]:
    allowed, expected = [], None
    for b in blocks:
        t = b.get("text") or ""
        if _LETTERED_SHAPE.search(t):
            expected = "B"
            continue
        if expected:
            if re.match(r"\s*" + expected + r"\.\s+[A-Za-z]", t):
                allowed.append(_norm(t)[:40])
                expected = chr(ord(expected) + 1)
            elif re.match(r"\s*(?:\d{1,3}\s*\[)?\s*(?:\(\s*\d{1,3}\s*\)|\d{1,4}[A-Z-]*\.)", t):
                expected = None
    return frozenset(allowed)


def _segment(blocks: list[dict], curation_patches: list[dict] | None = None,
             toc_dispositions: list[dict] | None = None,
             split_fused_margins: bool = False,
             detect_contents: bool = True,
             force_opening_contents: bool = False,
             structural_resolutions: list[dict] | None = None,
             structural_overrides: dict | None = None) -> Segmentation:
    """`segment()` under the profile already active in this context."""
    original_blocks = blocks
    overrides = structural_overrides or {}
    reviewed_structure = _reviewed_structure_index(structural_resolutions)
    blocks, patches_applied = _apply_curation_patches(
        blocks, curation_patches or [])
    if profile_rule("designation_cells"):
        blocks = _align_designation_cells(
            blocks, opener_ends_row=profile_rule("designation_before_opener"),
            bracket_rows=profile_rule("designation_bracket_rows"))
    if profile_rule("row_aligned_cells"):
        blocks = _align_row_cells(blocks, relaxed=profile_rule("row_cells_within_rows"))
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
    # A source-reviewed second layout reading may prove a small opening
    # contents list that the corpus-wide detector deliberately refuses.  Doc
    # 1000 prints exactly one linked row (12.1) below an explicit CONTENTS
    # banner, then starts the operative TEXT on page 2.  The ordinary minimum
    # of three rows is right for inference but wrong once the rendered page has
    # been read.  This override is therefore inert unless a caller supplies an
    # exact, existing first-body block; it still requires an explicit contents
    # marker and at least one numbered row before that block.
    preface_before_body = False
    source_body_start = overrides.get("source_body_start_block")
    if source_body_start is not None:
        source_boundary = next((
            i for i, block in enumerate(blocks)
            if block.get("id") == source_body_start
        ), None)
        if source_boundary is not None and source_boundary > 0:
            source_region = blocks[:source_boundary]
            source_rows = []
            for source_block in source_region:
                # A contents hyperlink can be only ``12.1``. The ordinary
                # body grammar reads that as section 12 followed by text
                # ``.1``; under reviewed contents evidence the dotted number
                # is the label itself.
                dotted = re.match(
                    r"^\s*(\d+(?:\.\d+)+)\.?\s*(.*?)\s*$",
                    source_block["text"] or "")
                if dotted:
                    source_rows.append((dotted.group(1), dotted.group(2)))
                    continue
                source_rows.extend(
                    (label, heading)
                    for _block, _offset, label, heading
                    in _section_numbers([source_block])
                    if label)
            printed_contents = any(_has_contents_marker(block["text"])
                                   for block in source_region)
            # Doc 2674 prints CONTENTS on its first page, but extraction
            # transposes two letters to CONTETNS. Accept that exact typo only
            # with a reviewed body-start block and several numbered contents
            # rows before it; do not infer a boundary from the typo alone.
            reviewed_ocr_typo = (
                profile_rule("source_body_start_contetns_typo")
                and len(source_rows) >= 3
                and any(re.fullmatch(r"CONTETNS", _norm(block["text"]), re.I)
                        for block in source_region))
            if (printed_contents or reviewed_ocr_typo) and source_rows:
                source_toc: dict[str, str] = {}
                for label, heading in source_rows:
                    # A lone hyperlink such as ``12.1`` proves the region is
                    # contents and therefore not body, but it supplies no
                    # printed heading to link or audit as a promised named
                    # provision. Keep it as boundary evidence only.
                    if heading:
                        source_toc.setdefault(label, heading)
                # Profile rule `body_start_keeps_contents` (unreleased-v3): doc
                # 2983's contents lists sections 1-12 and then the Scheme's
                # paragraphs 1-16; a label->heading map of the region keeps
                # one heading per label and every row fell unlinked. Where the
                # ordinary parse already found the contents and merely ran on
                # past the reviewed first body block, keep its parse and move
                # only the boundary back.
                if (profile_rule("body_start_keeps_contents") and toc_found and toc
                        and boundary > source_boundary):
                    # The ordinary detector may have treated the first body
                    # rows as further contents entries. Keep its useful
                    # duplicate-label mapping, but not a heading that comes
                    # only from the reviewed body region (doc 3069, 1.1).
                    if profile_rule("kept_contents_stop_at_body_start"):
                        late_rows = {
                            (label, heading) for _, _, label, heading
                            in _section_numbers(blocks[source_boundary:boundary + 1])
                        }
                        early_rows = set(source_rows)
                        toc = {
                            label: heading for label, heading in toc.items()
                            if (label, heading) not in late_rows
                            or (label, heading) in early_rows
                        }
                    boundary = source_boundary
                else:
                    toc, toc_found, boundary = source_toc, True, source_boundary
            # Profile rule `body_start_without_contents` (unreleased-v4): doc 4639 (a Gazette
            # copy printing Act XL before Act XLI, no contents list) -- a reviewed body start
            # with no contents marker before it makes the earlier blocks preface.
            elif (profile_rule("body_start_without_contents")
                    and not printed_contents and not reviewed_ocr_typo
                    and not toc_found and not boundary):
                boundary = source_boundary
                preface_before_body = True
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
    # Profile rule `contents_false_rows`: a contents page's own footnote or a
    # title line read as a row names no unit -- see `_false_contents_row`.
    if profile_rule("contents_false_rows") and printed_toc:
        false_rows = [entry for entry in printed_toc if _false_contents_row(entry)]
        if false_rows and len(false_rows) < len(printed_toc):
            printed_toc = [entry for entry in printed_toc
                           if not _false_contents_row(entry)]
            kept_labels = {entry["label"] for entry in printed_toc}
            toc = {label: heading for label, heading in toc.items()
                   if label in kept_labels
                   or label not in {entry["label"] for entry in false_rows}}
    # Profile rule `repeated_label_note_rows` (unreleased-v4): doc 1534's
    # contents page ends with its footnotes "2. Omitted vide Khyber Pakhtunkhwa
    # Ordinance No.I of 1975." and "3. ...", doc 1413's with "1. Omitted vide.
    # Khyber Pakhtunkhwa Adapt .of Laws Order, 1975."; each was read as a row
    # repeating the number of a real row ("2. Definitions."). An "Omitted/Rep.
    # vide|by ..." row is a note only when its number is already a row's.
    if profile_rule("repeated_label_note_rows") and printed_toc:
        labels = [entry["label"] for entry in printed_toc]
        notes = [entry for entry in printed_toc
                 if labels.count(entry["label"]) > 1
                 and _OMISSION_NOTE_ROW.match(_norm(entry.get("heading") or ""))]
        if notes and len(notes) < len(printed_toc):
            printed_toc = [entry for entry in printed_toc
                           if not any(entry is note for note in notes)]
            for label in {note["label"] for note in notes}:
                real = next((entry for entry in printed_toc if entry["label"] == label), None)
                if real is not None and _norm(real.get("heading") or ""):
                    toc[label] = real["heading"]
    # Profile rule `repeated_label_section_note_rows` (unreleased-v4): doc 2221's
    # contents page prints its amendment notes ('Section 21-A, added vide ...',
    # 'Section 25 Omitted vide ...') as numbered lines that repeat real rows' numbers;
    # those rows are the page's footnote, not contents entries.
    if profile_rule("repeated_label_section_note_rows") and printed_toc:
        _agae_labels = [entry["label"] for entry in printed_toc]
        _agae_notes = [entry for entry in printed_toc
                       if _agae_labels.count(entry["label"]) > 1
                       and re.match(
                           r"^(?:(?:(?:First|Second|Third|Fourth|Fifth)\s+)?(?:Sections?|Schedule)"
                           r"(?:\s+No\.?)?\s*[\dIVXLC]*(?:\s*-?\s*[A-Z])?(?:\s*(?:,|and)\s*[\dIVXLC]+(?:\s*-?\s*[A-Z])?)*"
                           r"\s*,?\s+)?(?:Omitted|Rep\.?|Repealed|Deleted|Added|Inserted|Ins\.?|Subs\.?|Substituted)"
                           r"\s*,?\s*(?:vide|vid|by|ibid)\b",
                           _norm(entry.get("heading") or ""), re.I)]
        if _agae_notes and len(_agae_notes) < len(printed_toc):
            printed_toc = [entry for entry in printed_toc
                           if not any(entry is note for note in _agae_notes)]
            for _agae_label in {note["label"] for note in _agae_notes}:
                _agae_real = next((entry for entry in printed_toc if entry["label"] == _agae_label), None)
                if _agae_real is not None and _norm(_agae_real.get("heading") or ""):
                    toc[_agae_label] = _agae_real["heading"]
    # Profile rule `contents_heading_alignment` (docs/SEGMENTATION-PROFILES.md):
    # a printed contents numbered at an offset from the body. The mapping, from
    # contents row ordinal to the body label whose own printed heading it
    # names (None: the body prints no such unit), is built by
    # `_contents_heading_alignment` from a first parse and handed back here.
    # The body walk then reads each body label's own heading, and the linker
    # joins each row to the unit the heading names. `printed_toc` itself keeps
    # the printed labels: it is the stored source evidence.
    aligned_labels: dict[int, str | None] = {
        int(ordinal): label for ordinal, label in
        (overrides.get("contents_heading_alignment") or {}).items()}
    walk_toc = printed_toc
    if aligned_labels and printed_toc:
        walk_toc = [dict(entry, label=aligned_labels.get(entry["ordinal"],
                                                         entry["label"]))
                    for entry in printed_toc
                    if aligned_labels.get(entry["ordinal"], entry["label"])
                    is not None]
        moved = [entry for entry in printed_toc
                 if entry["ordinal"] in aligned_labels]
        toc = dict(toc)
        for entry in moved:
            toc.pop(entry["label"], None)
        for entry in moved:
            target = aligned_labels[entry["ordinal"]]
            if target is not None and entry.get("heading"):
                toc[target] = entry["heading"]
        for entry in printed_toc:
            if entry["ordinal"] not in aligned_labels and entry.get("heading"):
                toc.setdefault(entry["label"], entry["heading"])
    body = (blocks[boundary:trailing_cut]
            if (boundary or trailing_cut is not None) else blocks)
    # A source-reviewed layout reading can identify a whole extracted block as
    # editorial apparatus even when the primary text parser cannot.  This is
    # deliberately block-exact: no model label or geometric threshold is
    # consulted here, and unknown ids have no effect.  The immutable source
    # block stays in the ledger as a footnote; it simply cannot open or absorb
    # a legal provision.
    source_apparatus_blocks = {
        int(value) for value in (overrides.get("source_apparatus_blocks") or [])
    }
    # Exact, source-reviewed ownership for an unnumbered continuation.  This
    # does not infer a parent from typography and is inert without an override.
    continuation_parents = {
        item["source_block_id"]: item["parent_block_id"]
        for item in (overrides.get("source_continuation_parent_blocks") or [])
    }
    if len(continuation_parents) != len(
            overrides.get("source_continuation_parent_blocks") or []):
        raise ValueError("duplicate source continuation ownership override")
    unnumbered_openers = {
        item["source_block_id"]: item
        for item in (overrides.get("source_unnumbered_section_openers") or [])
    }
    if len(unnumbered_openers) != len(
            overrides.get("source_unnumbered_section_openers") or []):
        raise ValueError("duplicate source unnumbered section opener")
    unnumbered_parts = {
        item["source_block_id"]: item["heading"]
        for item in (overrides.get("source_unnumbered_part_headings") or [])
    }
    if len(unnumbered_parts) != len(
            overrides.get("source_unnumbered_part_headings") or []):
        raise ValueError("duplicate source unnumbered part heading")
    schedule_row_openers = {
        item["source_block_id"]: item
        for item in (overrides.get("source_schedule_row_openers") or [])
    }
    if len(schedule_row_openers) != len(
            overrides.get("source_schedule_row_openers") or []):
        raise ValueError("duplicate source schedule row opener")
    source_apparatus_blocks.update(
        block["id"] for block in body
        if block.get("id") is not None and _is_source_history_digest_block(block)
    )
    source_marginal_blocks = {
        block["id"] for block in body
        if block.get("id") is not None and _is_source_marginal_heading(block)
    }
    if profile_rule("margin_heading_blocks") and printed_toc:
        source_marginal_blocks |= _margin_heading_blocks(
            body, [entry.get("heading") for entry in printed_toc],
            tails=profile_rule("margin_heading_tail"))
    # Profile rule `apparatus_over_margin_heading` (unreleased-v4): doc 2452 -- a block a
    # page reading sets aside as apparatus is not also a margin-heading block (its
    # margin-note column had become the heading of the page's first unit).
    if profile_rule("apparatus_over_margin_heading"):
        source_marginal_blocks -= source_apparatus_blocks
    margin_piece_ids = (
        _margin_heading_pieces(body, [entry.get("heading") for entry in printed_toc])
        if profile_rule("margin_heading_pieces") and printed_toc else set())
    # Profile rule `left_column_margin_heading` shape (A): left-column heading blocks level with a section opener.
    # Shapes (B)/(B') below apply only where (A) shows the three-column layout (doc 1144 does not).
    _left_margin_level_pairs: list = []
    if profile_rule("left_column_margin_heading") and not printed_toc:
        _left_margin_by_page: dict = {}
        for _blk in body:
            _left_margin_by_page.setdefault(_blk.get("page_no"), []).append(_blk)
        for _blk in body:
            if (_blk.get("id") is None or _blk.get("x1") is None or _blk.get("x0") is None
                    or float(_blk["x1"]) >= 320 or not _left_margin_heading_shape(_blk.get("text") or "")):
                continue
            for _o in _left_margin_by_page.get(_blk.get("page_no"), []):
                if (_o is _blk or _o.get("x0") is None or _o.get("y0") is None
                        or abs(float(_o["y0"]) - float(_blk["y0"])) > 3
                        or float(_blk["x1"]) > float(_o["x0"]) + 2
                        or float(_o["x0"]) - float(_blk["x0"]) < 60):
                    continue
                _pcs = subdivide(_o.get("text") or "")
                _c = classify(_pcs[0]) if _pcs else None
                if ((_c and _c[0] == "section")
                        or (_pcs and re.fullmatch(r"\s*\d{1,3}[A-Z]?\s*\.\s*", _pcs[0]))):
                    source_marginal_blocks.add(_blk["id"])
                    _left_margin_level_pairs.append((_blk, _o["id"]))
                    break
    source_nonoperative_roles = {
        block["id"]: role for block in body
        if block.get("id") is not None
        if (role := _source_nonoperative_role(block)) is not None
    }
    if profile_rule("download_stamp_furniture"):
        source_nonoperative_roles.update(
            (block_id, "running_header") for block_id in _download_stamp_blocks(body))
    # Profile rule `page_number_furniture` (unreleased-v2): a block that is only
    # its own page number. Doc 3635's blank pages 9-11 carry just "9", "10",
    # "11", which the last rule's text absorbed.
    if profile_rule("page_number_furniture"):
        source_nonoperative_roles.update(
            (block["id"], "running_header") for block in body
            if block.get("id") is not None
            and re.fullmatch(r"\d{1,4}", _norm(block.get("text") or ""))
            and int(_norm(block["text"])) == block.get("page_no"))
    source_preamble_intro_blocks = {
        block["id"] for block in body
        if block.get("id") is not None
        and _is_source_preamble_intro_block(block)
    }
    column_number_cell_ids = (_column_number_cells(body)
                              if profile_rule("column_number_cells") else set())
    body = [block for block in body
            if block.get("id") not in source_apparatus_blocks
            and block.get("id") not in source_marginal_blocks
            and block.get("id") not in source_nonoperative_roles]
    body_page = body[0]["page_no"] if body else 1
    # The page-level footnote run, by block id so the body slice can ask about
    # it.  `_toc_source_entries` has trusted this proof since document 1918 --
    # three or more consecutive ascending numbered blocks on one page, at least
    # half of them opening with `_FOOTNOTE` provenance -- but only the contents
    # reader was ever told the answer.  The body walk needs it for exactly the
    # same reason: a Pakistan Code page sets its notes one per block, so no
    # block-level test can see the run, and each note becomes a section.
    apparatus_run_block_ids = {
        blocks[i].get("id") for i in _footnote_run_blocks(blocks)
    } - {None}

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
    seg_roles: dict = {
        block_id: ("footnote", None)
        for block_id in source_apparatus_blocks
    }
    seg_roles.update({block_id: ("heading", None)
                      for block_id in source_marginal_blocks})
    seg_roles.update({block_id: (role, None)
                      for block_id,role in source_nonoperative_roles.items()})
    in_schedule = False
    contents_proved_rows: set = set()
    schedule_node: Node | None = None
    explicit_table_owner: Node | None = None
    serial_header_table = False
    amendment_items_list = False
    schedule_word_list = False
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
    _left_margin_split_units: set = set()
    dotted_commencement_operative_units: set[int] = set()
    for b in body:
        # Keep an amendment-footnote block whole.  Subdividing first can see
        # the citation fragment ``s. 2. It was provided ...`` as a new section
        # even though the block's fused superscript and amendment verb prove
        # the whole block is apparatus (CPC pages 65, 66 and 85).
        pieces = ([b["text"]] if (
            (_FOOTNOTE.match(b["text"])
             and not _PARENTHESIZED_CHAPTER.search(b["text"]))
            or _is_footnote_run(b["text"], require_every_item=True)
            or (_PUNCTUATED_AMENDMENT_FOOTNOTE.match(b["text"])
                and not (profile_rule("schedule_amendment_item")
                         and _schedule_amendment_block(body, b)))
            or _footnote_markers_only(b["text"])
            or (b.get("id") in apparatus_run_block_ids
                and _run_member_is_apparatus(b["text"]))
        ) else subdivide(b["text"]))
        # Profile rule `left_column_margin_heading` shapes (B)/(B'): heading lines before 'N.' in one block.
        if (profile_rule("left_column_margin_heading") and not toc and len(pieces) > 1
                and _left_margin_level_pairs):
            _left_margin_pieces = []
            for _k, _piece in enumerate(pieces):
                _split = None
                _whole = False
                if _k + 1 < len(pieces):
                    _nc = classify(pieces[_k + 1])
                    if _nc and _nc[0] == "section":
                        if _left_margin_heading_shape(_piece):
                            _whole = True
                        else:
                            _split = _left_margin_heading_tail(_piece)
                if _whole:
                    _left_margin_pieces.append((_piece, True))
                elif _split:
                    _left_margin_pieces.append((_split[0], False))
                    _left_margin_pieces.append((_split[1], True))
                else:
                    _left_margin_pieces.append((_piece, False))
            for _piece, _is_head in _left_margin_pieces:
                if _is_head:
                    _left_margin_split_units.add(len(units))
                units.append((b, _without_trailing_inline_footnotes(_piece)))
            continue
        for piece in pieces:
            units.append((b, _without_trailing_inline_footnotes(piece)))

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
        for entry in walk_toc:
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
            # Profile rule `divisions_end_body` (unreleased-v2): the same stop
            # for a form or schedule heading that names the rule or section it
            # is made under -- doc 2857 "FORM 'C' [See Rule 3 (6)]", doc 2846
            # "SCHEDULE STANDING ORDERS" / "( see section 2(1)(k))". Their own
            # numbered items (Form C's "7. Time when he will be off duty")
            # otherwise carry the marker past every form before them.
            if (c and c[0] in ("schedule", "form") and boundary_seen
                    and profile_rule("divisions_end_body")
                    and (_division_reference_search(t[:200])
                         or _schedule_heading_with_reference(
                             t, [units[j][1] for j in range(i + 1, min(i + 3, len(units)))]))):
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
        block_id = units[idx][0].get("id")
        for j in range(idx - 1, max(-1, idx - 4), -1):
            block, raw = units[j]
            if block.get("page_no") != page:
                break
            # ``subdivide`` can expose a continuation subsection and the next
            # bare section from one source block.  For the latter, the former
            # is not a preceding layout block and must not prevent the scan
            # reaching the adjacent marginal heading.  Doc 1847 prints
            # subsection 8(2) and bare section 9 together, immediately after
            # the separate heading "Inclusion of different localities...".
            if block_id is not None and block.get("id") == block_id:
                continue
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
    quote_owner: Node | None = None
    quote_end = -1
    insertion_spans = (_quoted_insertion_spans([t for _b, t in units],
                                               [_b.get("page_no") or 0 for _b, _t in units])
                       if profile_rule("quoted_insertion_span") else {})
    insertion_span_end = {k: end for start, end in insertion_spans.items()
                          for k in range(start, end + 1)}
    continuation_applied: set[int] = set()
    _left_margin_heading_at: dict = {}
    unnumbered_applied: set[int] = set()
    root_provision_nodes: list[Node] = []   # opened by `unnumbered_root_provision`
    unnumbered_parts_applied: set[int] = set()
    schedule_row_openers_applied: set[int] = set()
    for idx, (b, text) in enumerate(units):
        # Once a canonical source-history footnote starts, its wrapped
        # continuation may occupy several blocks and lose the superscript
        # marker. It remains apparatus through the end of that physical page.
        if source_history_page == b["page_no"]:
            mark(b, "footnote")
            continue
        if _is_running_header(text) or _norm(text) in running_headings:
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
        # A note run that arrives one note per block is invisible to every
        # test above -- each block holds a single line, so there is no run
        # inside it to find.  The page has already proved the run; the block
        # must still prove itself (`_run_member_is_apparatus`), and a block
        # the walk reached as the body of a detached marginal heading keeps
        # the geometric evidence it was admitted on.
        if ((_is_source_editorial_separator(text, b)
                or _FOOTNOTE.match(text)
                or _is_footnote_run(text, require_every_item=True)
                # Profile rule `schedule_amendment_item` (unreleased-v4): doc 2739's amending
                # Schedule items 'N. / In section X, ... shall be substituted.' are law, not notes.
                or (_PUNCTUATED_AMENDMENT_FOOTNOTE.match(text)
                    and not (profile_rule("schedule_amendment_item") and in_schedule
                             and schedule_node is not None
                             and _schedule_amendment_item(schedule_node, text)))
                or _is_enactment_history_footnote(text, b)
                or (b.get("id") in apparatus_run_block_ids
                    and _run_member_is_apparatus(text)))
                and b.get("id") not in detached_heading_for_body):
            mark(b, "footnote")
            if _SOURCE_HISTORY_START.match(text):
                source_history_page = b["page_no"]
            continue
        if _footnote_markers_only(text):
            mark(b, "footnote")
            continue

        # Profile rule `quoted_insertion_span` (unreleased-v4): doc 1144's s.6
        # reads "... for sections 8 to 11, the following sections shall be
        # substituted ...:- ―8. ..." and prints the new sections 9, 10 and 11
        # on their own lines before the closing quote; each opened as a unit
        # of the amending Ordinance and 11 collided with its own s.11. Text an
        # amending provision introduces and opens a quotation for is that
        # provision's text until the quotation closes.
        if insertion_spans:
            # A span can begin on a running header or a footnote the checks
            # above already set aside; it opens at its first unit of text.
            if (quote_owner is None and idx in insertion_span_end and current is not root
                    and current.kind in ("section", "article", "subsection", "clause")):
                quote_owner, quote_end = current, insertion_span_end[idx]
            if quote_owner is not None and idx <= quote_end:
                quote_owner.text_parts.append(text)
                quote_owner.last_page = b["page_no"]
                quote_owner.blocks.append(b.get("id"))
                mark(b, "body", quote_owner)
                current = quote_owner
                if idx == quote_end:
                    quote_owner = None
                continue

        # A source-labelled TABLE belongs to the provision immediately before
        # it.  Its numbered rows are data, not competing sections of the Act.
        # Keep the heading itself reachable as body text and remember the
        # owning provision until a TOC-proved next section closes the table.
        # Profile rule `amendment_items_owner` (unreleased-v4): doc 715 s.2
        # revives an Act "and on such revival shall stand amended as
        # under:-", then numbers its amendments 1 to 6. The items are the
        # section's own rows, like a TABLE's: item 3 "In section 3, ..." had
        # become section 3 under the contents heading "Saving." of the real
        # s.3, which then became a clause of item 6. The next contents-
        # promised section whose heading the text supports closes the list.
        if (profile_rule("amendment_items_owner") and explicit_table_owner is None
                and current is not root
                and re.search(r"\bamended\s+as\s+(?:under|follows)\s*[:.]?\s*[-—–]*\s*$",
                              _norm(" ".join(current.text_parts)), re.I)):
            owner = current
            while owner is not root and owner.kind not in ("section", "article"):
                owner = owner.parent or root
            if owner is not root:
                explicit_table_owner = owner
                amendment_items_list = True
        # Profile rule `quoted_schedule_word_owner` (unreleased-v4): doc 3056
        # s.2(viii) reads "for the existing Schedule 1, the following shall be
        # substituted- "SCHEDULE"" -- only the heading word is quoted -- and the
        # new Schedule's articles 1-31 follow unquoted to the end of the copy.
        # With no contents list article 3 read as section 3 of the Ordinance and
        # every later article followed. The clause that substitutes the
        # Schedule owns its numbered rows, as a TABLE's owner does.
        if (profile_rule("quoted_schedule_word_owner") and explicit_table_owner is None
                and current is not root and current.kind in ("section", "subsection", "clause")
                and (_QUOTED_SCHEDULE_WORD_END.search(_norm(" ".join(current.text_parts)))
                     or (profile_rule("ordinal_quoted_schedule_word")
                         and _ORDINAL_QUOTED_SCHEDULE_WORD_END.search(_norm(" ".join(current.text_parts)))))):
            explicit_table_owner = current
            amendment_items_list = False
            schedule_word_list = True
        # Profile rule `referenced_table_heading` (unreleased-v4): doc 4276
        # prints "1[TABLE [see section 7(1)]" over s.7's thirty-seven rate
        # rows; the bare-word test refused it and the rows became sections
        # 8 to 37 under the contents headings of the real ss.8-10.
        if (re.fullmatch(r"(?:THE\s+)?TABLE\s*[.:-]?", _norm(text), re.I)
                or _is_numbered_table_header(text)
                or (profile_rule("referenced_table_heading")
                    and _REFERENCED_TABLE_HEADING.fullmatch(_norm(text)))):
            if current is not root:
                owner = current
                while owner is not root and owner.kind in (
                        {"clause"} | QUALIFIERS):
                    owner = owner.parent or root
                if owner is not root:
                    explicit_table_owner = owner
                    amendment_items_list = False
                # Under `referenced_table_heading` the heading (and the column
                # heads after it) belong to the owning unit, not to the
                # proviso that happened to be open (doc 4276 s.7(1)).
                if (owner is not root and profile_rule("referenced_table_heading")
                        and _REFERENCED_TABLE_HEADING.fullmatch(_norm(text))):
                    current = owner
                current.text_parts.append(text)
                current.last_page = b["page_no"]
                current.blocks.append(b.get("id"))
                mark(b, "body", current)
            else:
                mark(b, "preface")
            continue
        # Profile rule `column_number_cells` (unreleased-v2): "(1) (2) (3)"
        # under a table's column heads is table text of the open unit.
        if b.get("id") in column_number_cell_ids:
            if current is not root:
                current.text_parts.append(text)
                current.last_page = b["page_no"]
                current.blocks.append(b.get("id"))
                mark(b, "body" if current.kind not in _HEADING_KINDS else "heading", current)
            else:
                mark(b, "preface")
            continue

        if (_PREAMBLE.match(text)
                or (b.get("id") in source_preamble_intro_blocks
                    and re.match(r"\s*AN\s+ACT\b", text, re.I)
                    and re.search(r"\bWHEREAS\b", text, re.I))) and not any(
                    c.kind == "preamble" for c in root.children) and not (
                # Profile rule `preamble_not_in_auxiliary` (unreleased-v4): doc
                # 4318's rules have no preamble, and the recital of Form B's
                # transfer deed ("WHEREAS the Transferor is absolute owner ...",
                # p29) became the instrument's Preamble. A recital inside an
                # open form or schedule is that division's text.
                in_schedule and profile_rule("preamble_not_in_auxiliary")):
            node = Node(kind="preamble", label="Preamble", depth=1,
                        text_parts=[text], first_page=b["page_no"],
                        last_page=b["page_no"], first_block=b.get("id"), parent=root)
            root.children.append(node)
            node.blocks.append(b.get("id"))
            mark(b, "preamble", node)
            current = node
            continue

        heading_context = previous_heading_context(idx)
        # Document 3069's nomination forms print two side-by-side witness
        # fields both headed "1. Signature:" in one source block. These are
        # form cells, not two operative clauses with the same citation. Keep
        # both exact printed strings in the enclosing form/schedule's text.
        if (profile_rule("duplicate_witness_fields_as_form_text")
                and len(re.findall(r"(?m)^\s*1\.\s*Signature:", b["text"])) == 2
                and re.fullmatch(r"\s*1\.\s*Signature:\s*_+\s*", text, re.I)):
            owner = current
            while owner is not root and owner.kind not in ("form", "schedule"):
                owner = owner.parent or root
            if owner is not root:
                owner.text_parts.append(text)
                owner.last_page = b["page_no"]
                if b.get("id") not in owner.blocks:
                    owner.blocks.append(b.get("id"))
                mark(b, "body", owner)
                current = owner
                continue
        forced_part = roman_display_parts.get(b.get("id"))
        c = (("part",) + forced_part if forced_part is not None
             else _classify_body(text, toc, seen, heading_context))
        # Profile rule `schedule_tables_annexes_parts` (unreleased-v4): (doc 4447 Sixth, Eighth and Ninth Schedules): inside an open
        # schedule, a "Table-2" / "Table-I" title and an "Annex-A" / "Annexure" heading are Parts of that schedule,
        # not new top-level divisions (the Sixth Schedule prints Table-1, Annex-I, Annex-A..D, Table-2,
        # Annexure, Table-3, Annex-A, Annex-B, Annexure, Table-4 in turn)
        if (profile_rule("schedule_tables_annexes_parts") and in_schedule and schedule_node is not None
                and schedule_node.kind == "schedule"):
            _tw = re.match(r"^\s*(?:\d{1,4}\s*\[\s*)?(TABLE\s*[-–]\s*(?:\d{1,2}|[IVX]{1,4}))\b[ \t]*(?:\n|$|(?=\*{3,}))", text, re.I)
            if _tw:
                c = ("part", re.sub(r"\s+", "", _tw.group(1)), text[_tw.end():])
            elif c is None or c[0] == "annexure":
                _aw = re.match(r"^\s*(?:\d{1,4}\s*\[\s*)?[\"\u201c]?(ANNEX(?:URE)?)(?:\s*[-\u2013]\s*([A-Z]|[IVX]{1,4})\b)?(?=[ \t]*(?:\n|$|\[))", text, re.I)
                if _aw:
                    c = ("part", _aw.group(1).title() + ("-" + _aw.group(2) if _aw.group(2) else ""),
                         text[_aw.end():])
            # ... the schedule's conditions heading after its table ("LIABILITY, PROCEDURE AND CONDITIONS",
            # "Procedure and conditions:-", pp197, 205, 207) is a Part; a "Note:" paragraph after the table is
            # a note on the schedule (p199)
            if c is None:
                _ch = re.match(r"^\s*((?:[A-Z][A-Z,]*\s+){1,5}CONDITIONS|Procedure\s+and\s+conditions)\s*:?\s*[-\u2013\u2014]*[ \t]*(?:\n|$)", text)
                _nt = re.match(r"^\s*(Note)\s*:\s*(?=[A-Z])", text)
                # ... and a "Notes:--" caption over numbered notes after a table (p172: the Sixth Schedule's
                # Notes 1-3 after Table-2, "For the purpose of this Schedule ...") is a Part of the schedule
                _ns = re.match(r"^\s*(Notes)\s*:\s*[-\u2013\u2014]+[ \t]*(?=\n|$)", text)
                if _ch:
                    c = ("part", _norm(_ch.group(1)), text[_ch.end():])
                elif _ns:
                    c = ("part", "Notes", text[_ns.end():])
                elif _nt:
                    c = ("explanation", "Note", text[_nt.end():])
        # Profile rule `titled_appended_form` (unreleased-v4): docs 1385 / 3064 head the form an
        # earlier rule cites ('in the form attached to these rules', 'in the form appended to this
        # Order') with an upper-case title and no FORM label.
        if (c is None and profile_rule("titled_appended_form") and not toc and not in_schedule
                and current is not root and len(seen) >= 2
                and idx > 0 and units[idx - 1][0].get("page_no") != b.get("page_no")
                and idx + 1 < len(units) and units[idx + 1][0].get("page_no") == b.get("page_no")
                and (b.get("text") or "").lstrip().startswith(text.lstrip()[:24])):
            _tf = re.match(r"^[ \t]*([A-Z][A-Z0-9 ,.'\u2019()&\-]{8,118}[A-Z0-9).])[ \t]*(?:\n|$)", text)
            if (_tf and len(_tf.group(1).split()) >= 2 and not re.search(r"[a-z]", _tf.group(1))
                    and not re.match(r"\s*(?:\d|\(|PART\b|CHAPTER\b|SCHEDULE\b|FORM\b|APPENDIX\b|ANNEX)",
                                     _tf.group(1))
                    and any(re.search(r"\bform\s+(?:attached|appended|annexed)\s+(?:to|with)\s+"
                                      r"(?:these\s+(?:rules|regulations)|this\s+(?:Order|Ordinance|Act|"
                                      r"Notification|Regulations?))\b", _norm(prior_text), re.I)
                            for _, prior_text in units[:idx])):
                c = ("form", _norm(_tf.group(1)), text[_tf.end():])
        # Profile rule `numbered_schedule_form` (unreleased-v4): (doc 3649's SCHEDULE OF FORMS: 'No. 1.--TITLE')
        _agar_nf = None
        if c is None and profile_rule("numbered_schedule_form") and in_schedule:
            _agar_sched = next((n for n in reversed(stack) if n.kind == "schedule"), None)
            _agar_m = re.match(r"^\s*No\.[ \t]*(?:[\u2014\u2013-][ \t]*)?(\d{1,2})[ \t]*\.[ \t]*"
                               r"(?:[\u2014\u2013-]+[ \t]*)?(?=[A-Z])", text)
            if (_agar_sched is not None and _agar_m
                    and re.search(r"\bFORMS\b", " ".join([_agar_sched.label or "", _agar_sched.heading or ""]
                                                         + _agar_sched.text_parts[:1]), re.I)):
                _agar_rest = text[_agar_m.end():]
                _agar_parts = re.split(r"\n[ \t\u00a0]*\n", _agar_rest.strip(), maxsplit=1)
                _agar_title = _norm(_agar_parts[0])
                if (_agar_title and len(_agar_title.split()) >= 2
                        and not re.search(r"[a-z]{2,}", re.sub(r"\bNo\.", "", _agar_title))):
                    _agar_nf = (_agar_title, _norm(_agar_parts[1]) if len(_agar_parts) > 1 else "", _agar_sched)
                    c = ("form", "No. " + _agar_m.group(1), _agar_rest)
        # Profile rule `sequence_omission_stub` (unreleased-v3): doc 2923 p4
        # prints omitted sections 3-6 as "1[(3)* * * * * * *]" (footnote:
        # "Omitted by Ord. (CXXVII of 02), ss. 3 to 6") and p7 does the same
        # for 21 and 22; each became a sub-section of whatever was open. An
        # omitted SUB-section is printed the same way, so the stub is a
        # section only when the contents lists its number and it is the next
        # section after the highest one the walk has met.
        if (c and c[0] == "subsection" and toc
                and profile_rule("sequence_omission_stub")):
            stub = _PAREN_OMISSION_STUB.match(text)
            numbers = [int(key) for key in seen if str(key).isdigit()]
            if (stub and stub.group(1) in toc and stub.group(1) not in seen
                    and int(stub.group(1)) == (max(numbers) if numbers else 0) + 1):
                c = ("section", stub.group(1), stub.group(2))
        # Profile rule `marked_clause_opener` (unreleased-v3): "1(b) all laws
        # ..." -- a note marker before the letter -- is clause (b) when the
        # clause open is (a); the letter sequence is the evidence, since the
        # same shape could otherwise be a wrapped reference ("section / 1(b)").
        if not c and profile_rule("marked_clause_opener") and current is not root:
            marked = re.match(r"^\s*\d{1,2}\(\s*([a-z])\s*\)\s*(\S.*)$", text, re.S)
            if (marked and current.kind == "clause" and len(current.label or "") == 1
                    and current.label.isalpha()
                    and ord(marked.group(1)) == ord(current.label.lower()) + 1):
                c = ("clause", marked.group(1), marked.group(2))
        # Profile rule `sequence_bare_number` (unreleased-v3): doc 2818 prints
        # rules 26, 27, 35, 40 and 50 as "26 Certificates and provisional
        # orders ...", "50 whenever charge of a boiler passes ..." -- the
        # number without its full stop -- and each ran into the rule before.
        # A block that opens with a bare number is that section only when the
        # contents lists the number and it is the next after the highest
        # section the walk has met; a wrapped reference or a list item is not.
        if (toc and not in_schedule and profile_rule("sequence_bare_number")
                and (not c or c[0] not in ("section", "article"))
                and (b.get("text") or "").lstrip().startswith(text.lstrip()[:24])):
            bare = re.match(r"^\s*(\d{1,4})\s+(?=[A-Za-z(])", text)
            numbers = [int(key) for key in seen if str(key).isdigit()]
            if (bare and bare.group(1) in toc and bare.group(1) not in seen
                    and numbers and int(bare.group(1)) == max(numbers) + 1):
                c = ("section", bare.group(1), text[bare.end():])
        source_id = b.get("id")
        if source_id in schedule_row_openers:
            spec = schedule_row_openers[source_id]
            label = spec["label"]
            source_text = _norm(spec["source_text"])
            source_value = _norm(text)
            marker = re.search(r"(?<!\w)" + re.escape(label) + r"\.\s+", source_value)
            if (c is not None or source_id in schedule_row_openers_applied
                    or not in_schedule or schedule_node is None
                    or schedule_node.parent is not root
                    or schedule_node.first_block != spec["schedule_block_id"]
                    or source_value != source_text or marker is None
                    or any(child.kind == "clause" and child.label == label
                           for child in schedule_node.children)):
                raise ValueError(f"source schedule row {source_id} lacks exact grid evidence")
            # A cell extractor fused the functional-unit cell with the first
            # numbered post in the next column. Keep all printed words and the
            # original block ID; the separate label supplies the citation.
            body_text = (source_value[:marker.start()]
                         + source_value[marker.end():]).strip()
            node = Node(kind="clause", label=label,
                        depth=schedule_node.depth + 1,
                        text_parts=[body_text], first_page=b["page_no"],
                        last_page=b["page_no"], first_block=source_id,
                        parent=schedule_node)
            node.blocks.append(source_id)
            schedule_node.children.append(node)
            stack = [root, schedule_node, node]
            current = node
            mark(b, "schedule_row", node)
            schedule_row_openers_applied.add(source_id)
            continue
        if source_id in unnumbered_parts:
            heading = unnumbered_parts[source_id]
            if (c is not None or source_id in unnumbered_parts_applied
                    or _norm(text) != _norm(heading)):
                raise ValueError(f"source unnumbered part {source_id} lacks exact heading evidence")
            node = Node(kind="part", label=heading, heading=heading,
                        depth=DEPTH["part"], first_page=b["page_no"],
                        last_page=b["page_no"], first_block=source_id,
                        parent=root)
            node.blocks.append(source_id)
            root.children.append(node)
            stack = [root, node]
            current = node
            mark(b, "heading", node)
            unnumbered_parts_applied.add(source_id)
            continue
        # Profile rule `unnumbered_tail_provision` (unreleased-v4): doc 128 p5
        # prints, after its amending Schedule, at full width, with no number
        # and no contents row, "Repeal: The Balochistan Land Laws (Amendment)
        # Ordinance 2001 ... are hereby repealed." -- an Act-level operative
        # provision (owner decision 2026-10-06), not the Schedule's last item.
        # A reviewed opener whose after_section_label is "__AFTER_SCHEDULE__"
        # closes the open top-level schedule and opens it at the root.  Its
        # label is the printed lead word and carries no numeral: a `section`
        # label with no numeral is how an unnumbered provision is stored
        # (docs/SCHEMA.md, `provision`), so nothing here may invent a number.
        if (source_id in unnumbered_openers
                and unnumbered_openers[source_id]["after_section_label"] == "__AFTER_SCHEDULE__"
                and profile_rule("unnumbered_tail_provision")):
            specification = unnumbered_openers[source_id]
            label = specification["label"]
            heading = specification["heading"]
            prefix = specification["source_prefix"]
            division = current
            while division is not root and division.parent is not root:
                division = division.parent
            if (c is not None or source_id in unnumbered_applied
                    or division is root or division.kind != "schedule"
                    or label in seen or label in toc
                    or not _is_unnumbered_label(label)
                    or not _norm(text).startswith(prefix)
                    or not (_heading_lead(label) == _heading_lead(prefix)
                            == _heading_lead(heading))):
                raise ValueError(f"source unnumbered tail provision {source_id} lacks matching source evidence")
            node = Node(kind="section", label=label, heading=heading,
                        depth=DEPTH["section"],
                        text_parts=[_norm(text)[len(prefix):].strip()],
                        first_page=b["page_no"], last_page=b["page_no"],
                        first_block=source_id, parent=root)
            node.blocks.append(source_id)
            root.children.append(node)
            stack = [root, node]
            current = node
            seen.add(label)
            label_nodes[label] = node
            mark(b, "body", node)
            unnumbered_applied.add(source_id)
            continue
        # Profile rule `unnumbered_root_provision` (unreleased-v4): the same
        # reviewed opener with after_section_label "__ROOT__", where no unit is
        # open yet and no contents row exists.  Doc 268 (owner decision
        # 2026-10-06, q1): the 2003 notification's only operative text is the
        # clause under its caption "AMENDMENTS" (p1), and the 1998 Order prints
        # para 1 with no number before a printed "2." (p3).  A word label is the
        # printed caption or lead word, as for `unnumbered_tail_provision`.  A
        # numeric label is allowed only as "1", with no printed heading, and
        # only when the opener cites the owner decision that numbers it
        # (`owner_decision`: export, document_id, question_id); the recorder
        # and the dry run check that citation against the export.  A later
        # unit of the opener's block ("2. He is further pleased ...") is read
        # by the grammar as usual.
        root_opener = (source_id in unnumbered_openers
                       and unnumbered_openers[source_id]["after_section_label"] == "__ROOT__"
                       and profile_rule("unnumbered_root_provision")
                       and ("owner_decision" in unnumbered_openers[source_id]
                            or _is_unnumbered_label(unnumbered_openers[source_id]["label"])))
        if root_opener and source_id not in unnumbered_applied:
            specification = unnumbered_openers[source_id]
            label = specification["label"]
            heading = specification["heading"]
            prefix = specification["source_prefix"]
            decision = specification.get("owner_decision")
            if decision is None:
                evidenced = (_is_unnumbered_label(label)
                             and _heading_lead(label) == _heading_lead(prefix)
                             == _heading_lead(heading))
            else:
                evidenced = (label == "1" and heading == ""
                             and _owner_decision_citation(decision))
            if (c is not None or current is not root or not evidenced
                    or label in seen or label in toc
                    or any(child.kind in ("section", "article") for child in root.children)
                    or not _norm(text).startswith(prefix)):
                raise ValueError(f"source unnumbered root provision {source_id} lacks matching source evidence")
            node = Node(kind="section", label=label, heading=heading or None,
                        depth=DEPTH["section"],
                        text_parts=[_norm(text)[len(prefix):].strip()],
                        first_page=b["page_no"], last_page=b["page_no"],
                        first_block=source_id, parent=root)
            node.blocks.append(source_id)
            root.children.append(node)
            stack = [root, node]
            current = node
            seen.add(label)
            label_nodes[label] = node
            mark(b, "body", node)
            unnumbered_applied.add(source_id)
            root_provision_nodes.append(node)
            continue
        if source_id in unnumbered_openers and not root_opener:
            specification = unnumbered_openers[source_id]
            label = specification["label"]
            heading = specification["heading"]
            prefix = specification["source_prefix"]
            preceding = specification["after_section_label"]
            owner = current
            while owner is not root and owner.kind != "section":
                owner = owner.parent
            opening = preceding == "__ROOT__" and label == "1"
            toc_heading = _heading_lead(toc.get(label))
            source_heading = _heading_lead(heading)
            prefix_heading = _heading_lead(prefix)
            if (c is not None or source_id in unnumbered_applied
                    or (owner is root if not opening else owner is not root)
                    or (not opening and owner.label != preceding)
                    or label in seen or label not in toc
                    or toc_heading != source_heading
                    or not _norm(text).startswith(prefix)
                    or not (prefix_heading == source_heading
                            or (opening and source_heading.startswith(
                                prefix_heading + " ")))):
                raise ValueError(f"source unnumbered section {source_id} lacks matching source and contents evidence")
            container = root
            if opening:
                container = current
                while container is not root and container.kind not in ("part", "chapter"):
                    container = container.parent
            node = Node(kind="section", label=label, heading=heading,
                        depth=DEPTH["section"],
                        text_parts=[_norm(text)[len(prefix):].strip()],
                        first_page=b["page_no"], last_page=b["page_no"],
                        first_block=source_id, parent=container)
            node.blocks.append(source_id)
            container.children.append(node)
            stack = [root, node] if container is root else [root, container, node]
            current = node
            seen.add(label)
            label_nodes[label] = node
            mark(b, "body", node)
            unnumbered_applied.add(source_id)
            continue
        if source_id in continuation_parents:
            parent_block = continuation_parents[source_id]
            if c or source_id in continuation_applied:
                raise ValueError(f"source continuation {source_id} is not one unnumbered unit")
            owner = current
            while owner is not root and owner.first_block != parent_block:
                owner = owner.parent
            if owner is root:
                raise ValueError(f"source continuation {source_id} has no open parent block {parent_block}")
            current = owner
            continuation_applied.add(source_id)
        if not c:
            if b.get("id") in detached_heading_ids:
                mark(b, "heading")
                continue
            # Profile rule `margin_heading_pieces` (unreleased-v3): see
            # `_margin_heading_pieces`.
            if b.get("id") in margin_piece_ids:
                mark(b, "heading")
                continue
            # Profile rule `left_column_margin_heading`: a heading unit names the next section opened in its block.
            if (profile_rule("left_column_margin_heading") and not toc and _left_margin_level_pairs
                    and idx + 1 < len(units) and units[idx + 1][0] is b
                    and (idx == 0 or units[idx - 1][0] is not b or idx in _left_margin_split_units)
                    and _left_margin_heading_shape(text)):
                _following = classify(units[idx + 1][1])
                _nums = [int(_k) for _k in label_nodes if str(_k).isdigit()]
                _next = str(max(_nums) + 1) if _nums else "1"
                if _following and _following[0] == "section" and str(_following[1]) == _next:
                    _left_margin_heading_at[idx + 1] = _norm(text)
                    continue
            # Profile rule `leading_margin_heading_unit` (unreleased-v3): doc
            # 258's text layer prints the left-margin heading at the head of
            # the section's own block -- "Definitions. / 2. In this Act ...",
            # "Rules. / 16. The Provincial Government ..." -- and the cut before
            # "2." left "Definitions." as the tail of s.1(3). A unit that is the
            # contents heading of the section opening in the very next unit of
            # the same block is that section's heading, not text.
            if (profile_rule("leading_margin_heading_unit") and toc
                    and idx + 1 < len(units) and units[idx + 1][0] is b):
                following = classify(units[idx + 1][1])
                if (following and following[0] == "section"
                        and _heading_lead(text)
                        and _heading_lead(text) == _heading_lead(toc.get(str(following[1])))):
                    # The block is marked by the section's own unit next; the
                    # heading comes from the contents.
                    continue
            # A bracketed amendment proviso can end before the next ordinary
            # paragraph of its section.  Doc 956 p.3 closes `10[Provided ...]`
            # in one block and then prints a separate "The provisions of
            # sections ..." paragraph.  The bracket and source block boundary
            # prove the qualifier has closed; that paragraph is section 3's
            # text, not an extension of the proviso.  Keep this narrow rather
            # than treating every unnumbered block after a proviso as a new
            # section paragraph.
            opener = (source_block_by_id.get(current.first_block)
                      if current.kind == "proviso" else None)
            if (current.kind == "proviso" and current.parent is not None
                    and current.parent.kind in {"section", "article"}
                    and opener is not None
                    and opener.get("page_no") == b.get("page_no")
                    and re.match(r"^\s*\d{1,3}\s*\[\s*Provided\b",
                                 opener.get("text") or "")
                    and current.text_parts
                    and re.search(r"\]\s*[.!?]?\s*$", current.text_parts[-1])
                    and re.match(r"^The\s+provisions\s+of\s+sections?\b",
                                 _norm(text), re.I)):
                current = current.parent
            # Profile rule `member_list_closing_words` (unreleased-v2): doc 1521
            # s.3(2) lists members 1-8 with their designations, then prints
            # "In the absence of Chairman, ... shall act as the Chairperson of
            # the Board." and a proviso flush with the sub-section, outdented
            # from the list. They are s.3(2)'s words, not member 8's. A
            # capitalised block set at least 8 pt left of the open member's
            # own opener on its page, after that member's text has finished
            # (a full stop or its designation cell), returns to the list's
            # parent. A wrapped member line has not finished -- doc 2019 s.2(b)
            # "... the Karachi Water and Sewerage / Board established" -- and
            # an item without a list introduction is not a member.
            if (profile_rule("member_list_closing_words")
                    and current.kind == "clause" and current.label.isdigit()
                    and current.parent is not None
                    and _introduces_member_list(current.parent)
                    and current.text_parts
                    and (re.search(r"[.;:]\s*$", current.text_parts[-1])
                         or _DESIGNATION_CELL.fullmatch(_norm(current.text_parts[-1])))
                    and re.match(r"^\s*[A-Z]", text)):
                opener = source_block_by_id.get(current.first_block)
                if (opener is not None and opener.get("x0") is not None
                        and b.get("x0") is not None
                        and opener.get("page_no") == b.get("page_no")
                        and float(opener["x0"]) - float(b["x0"]) >= 8):
                    current = current.parent
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
                entry["heading"] for entry in walk_toc
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

        # Profile rule `serial_column_header_owner` (unreleased-v4): doc 3142 rule 11 ends
        # with the header 'S.NO. POWER IN RESPECT OF AUTHORISED OFFICER AUTHORITY.' and
        # its rows '01'-'07' are the rule's table rows, not sections.
        if (kind in ("section", "article") and explicit_table_owner is None
                and profile_rule("serial_column_header_owner") and not in_schedule
                and current is not root and current.kind in ("section", "article")
                and re.fullmatch(r"0?1", str(label))
                and _SERIAL_COLUMN_HEADER_END.search(_norm(" ".join(current.text_parts)))):
            explicit_table_owner = current
            amendment_items_list = False
            serial_header_table = True
        if serial_header_table and in_schedule:
            explicit_table_owner = None
            serial_header_table = False
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
            # An amendment list's own items are instructions ("3. In section
            # 3, ..."); the Act's next promised section is not, even where its
            # margin heading is emitted after it (doc 715's "Saving.").
            if (not next_promised_section and amendment_items_list
                    and _toc_label_is_next(table_key, toc, seen)
                    and not _AMENDING_INSTRUCTION.match(_norm(rest))):
                next_promised_section = True
            # A substituted Schedule ends at the amending Act's own next
            # section: the number after the owning section's, opening an
            # instruction "In the <...> Act, ..." (doc 1087's "4. In the Sindh
            # Finance Act, 1964, for the Seventh Schedule ..."). Needed where no
            # contents list can close it.
            if not next_promised_section and schedule_word_list:
                section = explicit_table_owner
                while section is not None and section.kind not in ("section", "article"):
                    section = section.parent
                if (section is not None and section.label.isdigit()
                        and table_key == str(int(section.label) + 1)
                        and _NEXT_AMENDING_SECTION.match(_norm(rest))):
                    next_promised_section = True
            # Profile rule `omission_stub_closes_table` (unreleased-v4): (doc 4447)
            if (not next_promised_section and profile_rule("omission_stub_closes_table")
                    and _toc_label_is_next(table_key, toc, seen)
                    and _DISPOSITION_ROW.match(expected_heading or "")
                    and re.fullmatch(r"[\s*.\[\]\u2026]*", rest or "")):
                next_promised_section = True
            if next_promised_section:
                explicit_table_owner = None
                amendment_items_list = False
                schedule_word_list = False
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
                # Profile rule `schedule_word_rows_own_items` (unreleased-v4):
                # a substituted Schedule's article owns its own "(a)", "(1)",
                # "(i)" items (doc 3056 s.2(viii), doc 1087 s.3(ii)). The row
                # was never on the stack, so ~170 items unwound past the owner
                # and became clauses and sub-sections of the amending section.
                # Profile rule `schedule_table_rows_own_items` (unreleased-v4): (doc 4447 Eighth, Ninth, Eleventh Schedules): a
                # table row inside a schedule owns its "(a)" / "(i)" items as a substituted Schedule's article does
                if ((schedule_word_list and profile_rule("schedule_word_rows_own_items"))
                        or (profile_rule("schedule_table_rows_own_items") and in_schedule)):
                    if explicit_table_owner in stack:
                        while stack and stack[-1] is not explicit_table_owner:
                            stack.pop()
                    stack.append(node)
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
        #
        # The same wrap happens to a BARE number, and there it is worse: no
        # "Rule" prefix marks it, `subdivide` cuts at it mid-paragraph, and the
        # phantom takes the host's later subsections with it (doc 2271's "in
        # section / 12. / (2) The general direction ..." made s.5(2)-(3) into
        # "section 12"). A four-digit YEAR at a line start is the same
        # mechanism -- "...Ordinance XX of / 1966." -- and is decided here too,
        # by its distance from the running sequence rather than by the word
        # before it. The evidence rules are `_wraps_a_cross_reference` and
        # `_year_is_not_a_provision_number`; the action is this guard's own.
        wrapped_reference = False
        if (kind == "section" and not in_schedule
                and (_WRAPPED_REFERENCE_NUMBER.match(text)
                     or _YEAR_OPENER.match(text))):
            reference_owner = current
            while (reference_owner is not root
                   and reference_owner.kind not in {"section", "article"}):
                reference_owner = reference_owner.parent or root
            reference_label = (reference_owner.label
                               if reference_owner is not root else None)
            reference_keys = (
                _norm(label).replace(" ", ""),
                _repair_label(label, toc, seen, rest).replace(" ", ""))
            wrapped_reference = (
                _wraps_a_cross_reference(
                    units[idx - 1][1]
                    if idx and units[idx - 1][0] is b else None,
                    text, rest,
                    units[idx + 1][1] if idx + 1 < len(units) else None,
                    reference_keys, reference_label, seen, toc)
                or _year_is_not_a_provision_number(
                    text, rest, reference_keys, reference_label, seen, toc))
        if ((kind == "section"
                and re.match(r"^\s*(?:Rules?|Regulations?)\s*\d", text, re.I)
                and _continues_previous(prior_content)
                and not displayed_rule_heading
                and not sequential_prefixed_rule
                and not _toc_label_is_next(
                    _norm(label).replace(" ", ""), toc, seen
                )) or wrapped_reference):
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
        # Profile rule `unnumbered_root_provision`: doc 268's 2003
        # notification has one reviewed, unnumbered clause, "For the existing
        # Schedule the Schedules appended here to shall be substituted", and
        # then the appended SCHEDULE (p6).  The clause is the evidence: an
        # uppercase display SCHEDULE directly after a reviewed root provision
        # whose text names the Schedules appended or annexed opens that
        # Schedule, though fewer than two units have opened.
        if (not unlisted_display_schedule and not toc
                and profile_rule("unnumbered_root_provision")
                and root_provision_nodes and current is root_provision_nodes[-1]
                and re.search(r"\bschedules?\b[^.]{0,40}?\b(?:appended|annexed)\b",
                              current.text, re.I)
                and re.match(r"^\s*(?:THE\s+)?SCHEDULE[ \t]*(?:\r?\n|$)", b["text"])):
            unlisted_display_schedule = True
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
        ) or (kind == "schedule"
              and idx + 1 < len(units)
              and units[idx + 1][0].get("page_no") == b.get("page_no")
              and _standalone_listed_schedule(b["text"], label, rest,
                                              toc_schedule_identities,
                                              units[idx + 1][1])
        ) or (kind == "schedule"
              and profile_rule("schedule_reference_lines")
              and _schedule_heading_with_reference(b["text"], [
                  unit_text for unit_block, unit_text in units[idx + 1:idx + 3]
                  if unit_block.get("page_no") == b.get("page_no")]))
        # Profile rule `divisions_end_body` (unreleased-v2): a form or schedule
        # heading that states the rule or section it is made under is a
        # division, even after a table whose last cell ends in lower case --
        # doc 2857's "FORM 'C' [See Rule 3 (6)]" follows Form B's "... by the
        # employer" column cell. The word must stand as a heading: doc 589's
        # "for the Fifth / Schedule, the following shall be substituted:-
        # FIFTH SCHEDULE (See Section 13)" is the sentence, not the division.
        # Appendices too: doc 2019's "APPENDIX ―A‖ / (See section 5)" follows
        # s.20(2)(vi)'s "... by or against the new Board;".
        referenced_division = bool(
            kind in ("form", "schedule", "appendix", "annexure")
            and profile_rule("divisions_end_body")
            and re.match(r"^\s*(?:THE\s+)?(?:FORM|SCHEDULE|APPENDIX|ANNEXURE|ANNEX)\b",
                         text, re.I)
            and not re.match(r"^\s*(?:(?i:the)\s+)?(?i:form|schedule|appendix|annexure|annex)"
                             r"\b\s*(?:[,;]|[a-z])", text)
            and (_division_reference_search(text[:200])
                 or any(_division_reference_match(_norm(unit_text))
                        for unit_block, unit_text in units[idx + 1:idx + 3]
                        if unit_block.get("page_no") == b.get("page_no"))))
        # Profile rule `ordinal_schedule_reference` (unreleased-v4): doc 3805's 'SECOND
        # SCHEDULE' / 'THIRD SCHEDULE (See Section 7 and 8)' follow a table cell with no
        # stop; an ordinal SCHEDULE heading with a division reference is the division.
        if (not referenced_division and kind == "schedule"
                and profile_rule("ordinal_schedule_reference")
                and re.match(r"^\s*(?:\d{1,3}\s*\[\s*[\"\u201c]?\s*)?(?:THE\s+)?(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|"
                             r"SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)\s+SCHEDULE\b", text)
                and (_division_reference_search(text[:200])
                     or any(_division_reference_match(_norm(unit_text))
                            for unit_block, unit_text in units[idx + 1:idx + 3]
                            if unit_block.get("page_no") == b.get("page_no")))):
            referenced_division = True
        # Profile rule `schedule_tables_annexes_parts` (unreleased-v4):: such a Table or Annex title is the division even after a
        # note or row that ends without a stop
        if (not referenced_division and kind == "part" and profile_rule("schedule_tables_annexes_parts")
                and in_schedule
                and (re.match(r"^\s*(?:\d{1,4}\s*\[\s*)?[\"\u201c]?(?:TABLE|ANNEX)", text, re.I)
                     or re.match(r"^\s*(?:(?:[A-Z][A-Z,]*\s+){1,5}CONDITIONS|Procedure\s+and\s+conditions|Notes\s*:\s*[-\u2013\u2014])", text))):
            referenced_division = True
        # Profile rule `high_ordinal_schedule` (unreleased-v4): (doc 4447 pp131-207): "772[The SIXTH SCHEDULE / [See section
        # 13(1)]" after a table row with no stop; the ordinal_schedule_reference test wants upper-case THE and no
        # note marker. An ordinal schedule title (any case, behind a note marker) with a division reference is
        # the division.
        if (not referenced_division and kind == "schedule" and profile_rule("high_ordinal_schedule")
                and re.match(r"^\s*(?:\d{1,4}\s*\[\s*)?(?:THE\s+)?(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|"
                             r"SEVENTH|EIGHTH|EIGHT|NINTH|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH)\s+SCHEDULE\b", text, re.I)
                and (re.search(r"[\[(]\s*see\s+[^\]\n]{0,80}?\b(?:sections?|rules?)\s*\d", text[:300], re.I)
                     # or an omitted schedule: the title over only its omission stub ("747[***]")
                     or re.fullmatch(r"\s*\S+(?:\s+\S+){1,2}\s+SCHEDULE\s*\d{1,4}\s*\[\s*\*{3,}\s*\]\s*",
                                     text, re.I))):
            referenced_division = True
        # Document 3069 p14 prints a bare FORM "A" above SECOND SCHEDULE,
        # after the First Schedule's signature line on p13. The preceding
        # signature has no full stop; the page-top form label is still a new
        # division, not the last words of that signature.
        if (not referenced_division and profile_rule("standalone_form_before_schedule")
                and kind == "form"
                and re.fullmatch(r"FORM\s*[\"'“”]?\s*[A-Z]\s*[\"'“”]?", _norm(text), re.I)
                and idx > 0 and units[idx - 1][0].get("page_no") != b.get("page_no")
                and idx + 1 < len(units)
                and units[idx + 1][0].get("page_no") == b.get("page_no")
                and re.match(r"^\s*(?:THE\s+)?(?:FIRST|SECOND|THIRD|FOURTH|FIFTH)\s+SCHEDULE\b",
                             units[idx + 1][1], re.I)
                and re.search(r"\b(?:Secretary|Signature|Signed)\b",
                              previous_content(idx) or "", re.I)):
            referenced_division = True
        # Profile rule `bracketed_rule_reference_division` (unreleased-v4):
        # doc 4318 heads its forms "FORM D [Rule 22(1)]" -- the reference
        # without "see" -- and Form D, after Form C1's table cell "Total Area",
        # ran into Form C1 with its twenty conditions. A unit that is nothing
        # but the division's label and a bracketed rule or section reference
        # is the division.
        if (not referenced_division and profile_rule("bracketed_rule_reference_division")
                and kind in ("form", "schedule", "appendix", "annexure")
                and _BRACKETED_DIVISION_HEADING.fullmatch(_norm(text))):
            referenced_division = True
        # Profile rule `unbracketed_division_reference` (unreleased-v4): doc
        # 3665 heads its forms "FORM PCT-8 / See rule 12 and 17." and "FORM
        # PCT-I / Survey Register. / See Rule 3(1)" -- the reference without
        # brackets -- after a form ending on a blank "Date:" line and after the
        # signature, so each ran into the unit before. A division heading in
        # capitals whose own unit, or the next unit on its page, opens with
        # "See rule/section N" is the division.
        if (not referenced_division and profile_rule("unbracketed_division_reference")
                and kind in ("form", "schedule", "appendix", "annexure")
                and re.match(r"^\s*(?:\d{1,3}\s*\[\s*)?(?:THE\s+)?(?:FORM|SCHEDULE|APPENDIX|ANNEXURE|ANNEX)\b",
                             text)
                and (_UNBRACKETED_DIVISION_REFERENCE.search(text[:200])
                     or any(_UNBRACKETED_DIVISION_REFERENCE.match(unit_text)
                            for unit_block, unit_text in units[idx + 1:idx + 3]
                            if unit_block.get("page_no") == b.get("page_no")))):
            referenced_division = True
        # Profile rule `appendix_number_label` (unreleased-v4): (doc 3803): a unit whose first line is only
        # 'APPENDIX <number>' is the division even after a form's unpunctuated last line.
        if (not referenced_division and profile_rule("appendix_number_label") and kind == "appendix"
                and re.match(r"^\s*APPENDIX\s*(?:[-\u2013\u2014.]\s*)?(?:N[Oo]\s*\.\s*)?"
                             r"(?:[IVX]{1,4}|\d{1,2})(?:\s*[.\-\u2013]\s*(?:[IVX]{1,4}|\d{1,2})){0,2}"
                             r"\s*\.?[ \t]*(?:\n|$)", text)):
            referenced_division = True
        # Profile rule `bracketed_sub_rule_reference` (unreleased-v4): doc 2344
        # heads its forms "FORM IV / FORM OF NOTING FOR DISHONOUR. / (See
        # Sub-Rule (1) of RULE 12)" -- the sub-rule's number in brackets of its
        # own, where `divisions_end_body` wants a digit -- and Form IV, after
        # Form III's closing "Signature of Notary", ran into Form III.
        if (not referenced_division and profile_rule("bracketed_sub_rule_reference")
                and kind in ("form", "schedule", "appendix", "annexure")
                and re.match(r"^\s*(?:THE\s+)?(?:FORM|SCHEDULE|APPENDIX|ANNEXURE|ANNEX)\b", text)
                and (_BRACKETED_SUB_RULE_REFERENCE.search(text[:200])
                     or any(_BRACKETED_SUB_RULE_REFERENCE.match(_norm(unit_text))
                            for unit_block, unit_text in units[idx + 1:idx + 3]
                            if unit_block.get("page_no") == b.get("page_no")))):
            referenced_division = True
        # Profile rule `sequential_schedule_heading` (unreleased-v4): doc 4353
        # p78 opens with "Schedule-III" alone, after Part-E's last table cell
        # ("... research awards", lower case) and before its title-case title,
        # so it read as a cross-reference and Schedule-III's item 1 became a row
        # of Part E. A schedule label alone on its unit, first on its page, one
        # after the last schedule opened, followed on its page by a capitalised
        # unit, is that schedule.
        if (not referenced_division and kind == "schedule"
                and profile_rule("sequential_schedule_heading")
                and not _norm(rest)
                and idx > 0 and units[idx - 1][0].get("page_no") != b.get("page_no")
                and idx + 1 < len(units)
                and units[idx + 1][0].get("page_no") == b.get("page_no")
                and re.match(r"^\s*[A-Z][A-Za-z]", _norm(units[idx + 1][1]))):
            def _schedule_value(value):
                m = re.search(r"([IVXLC]+|\d{1,2})\s*$", _norm(value or ""))
                if not m:
                    return None
                return int(m.group(1)) if m.group(1).isdigit() else _roman_number(m.group(1))
            opened_schedules = [n for n in root.children if n.kind == "schedule"]
            schedule_value = _schedule_value(label)
            if (opened_schedules and schedule_value is not None
                    and _schedule_value(opened_schedules[-1].label) == schedule_value - 1):
                referenced_division = True
        # Profile rule `appended_form_at_page_top` (unreleased-v4): doc 3108 p13
        # opens with "FORM L-37-A" after rule 7.14's "... given below:-"; rule
        # 7.12 cites it as "Form L-37-A appended hereto". A form label alone,
        # first on its page, before a capitalised unit, whose code the earlier
        # text cites as "Form <code> appended", is that form.
        if (not referenced_division and kind == "form"
                and profile_rule("appended_form_at_page_top")
                and not _norm(rest)
                and idx > 0 and units[idx - 1][0].get("page_no") != b.get("page_no")
                and idx + 1 < len(units)
                and units[idx + 1][0].get("page_no") == b.get("page_no")
                and re.match(r"^\s*[A-Z][A-Za-z]", _norm(units[idx + 1][1]))):
            _code = re.sub(r"^\s*FORM\s*", "", _norm(label), flags=re.I)
            if _code and any(re.search(r"\bForm\s+" + re.escape(_code) + r"\s+appended\b",
                                       _norm(prior_text), re.I)
                             for _, prior_text in units[:idx]):
                referenced_division = True
        finished_before_division = bool(
            kind in ("part", "chapter") and profile_rule("enacting_formula_ends")
            and _ENACTING_FORMULA_TAIL.search((previous_content(idx) or "").rstrip()))
        if (not finished_before_division and kind in ("part", "chapter")
                and profile_rule("promulgating_formula_ends")):
            finished_before_division = bool(_PROMULGATING_FORMULA_TAIL.search(
                (previous_content(idx) or "").rstrip()))
        # Profile rule `sequential_chapter_heading` (unreleased-v2): doc 2019 p4
        # prints s.4(5) without its full stop ("... or assigned by the Board")
        # and then the display heading "CHAPTER—III / APPOINTMENT POWERS AND
        # FUNCTIONS OF THE MANAGING DIRECTOR", which the unfinished sentence
        # swallowed. A bare chapter label set as its own unit, followed on its
        # page by an upper-case title, and numbered one after the last chapter
        # the walk opened, is the next chapter -- a cross-reference is neither
        # alone on its line nor next in the sequence.
        if (kind == "chapter" and profile_rule("sequential_chapter_heading")
                and not _norm(rest) and not finished_before_division):
            def chapter_value(value: str) -> int | None:
                value = _norm(value)
                return int(value) if value.isdigit() else _roman_number(value)
            opened, pending = [], list(root.children)
            while pending:
                node = pending.pop(0)
                if node.kind == "chapter":
                    opened.append(node)
                pending[:0] = [child for child in node.children
                               if child.kind in ("part", "chapter")]
            following = next((unit_text for unit_block, unit_text in units[idx + 1:idx + 3]
                              if unit_block.get("page_no") == b.get("page_no")), None)
            finished_before_division = bool(
                opened and chapter_value(label) is not None
                and chapter_value(label) == (chapter_value(opened[-1].label) or -1) + 1
                and following and not re.match(r"^\s*[\d(]", following)
                and _display_cased(_norm(following))[1])
        # Profile rule `sequential_chapter_title` (unreleased-v4): doc 3672 p5
        # prints "CHAPTER II / THE INSTITUTE" in one unit after s.2(y), whose
        # definition ends in a comma ("... declared to be teachers by
        # regulations,"), and the chapter ran into clause (y). The rule above
        # wants the label alone on its unit. A chapter numbered one after the
        # last chapter opened, whose rest is an upper-case title and nothing
        # else, is that chapter.
        if (kind == "chapter" and profile_rule("sequential_chapter_title")
                and not finished_before_division and _norm(rest)
                and len(_norm(rest)) <= 80 and _display_cased(_norm(rest))[1]
                and not re.search(r"[.;,:]\s*\S", _norm(rest))):
            opened, pending = [], list(root.children)
            while pending:
                node = pending.pop(0)
                if node.kind == "chapter":
                    opened.append(node)
                pending[:0] = [child for child in node.children
                               if child.kind in ("part", "chapter")]
            # With no chapter opened yet the first printed chapter may be I or
            # II: doc 3002 prints no Chapter I and opens "CHAPTER II / THE
            # UNIVERSITY" after the definitions' last clause ("... of the
            # University;").
            last = _roman_number(opened[-1].label) if opened else None
            value = _roman_number(label)
            finished_before_division = bool(
                (last is not None and value == last + 1)
                or (not opened and value in (1, 2)))
        # Profile rule `sequential_part_heading` (unreleased-v4): doc 4433's
        # appendices print "Part-B", "Part-D" and "PART-II PARKING VIOLATIONS"
        # straight after a table row whose last cell is an amount ("10000/-",
        # "120000/-"), which reads as an unfinished line, so each part ran
        # into the row before it. A part whose label is the next in sequence
        # after the last part opened in the same division (B after A, D after
        # C, II after I) is that part.
        if (kind == "part" and not finished_before_division
                and profile_rule("sequential_part_heading")):
            scope = current
            while scope is not root and scope.kind not in ("appendix", "schedule", "annexure", "form"):
                scope = scope.parent or root
            prior = [n for n in scope.children if n.kind == "part"] if scope is not root else []

            def _part_values(value):
                value = _norm(value)
                found = set()
                if value.isdigit():
                    found.add(int(value))
                if re.fullmatch(r"[A-Z]", value):
                    found.add(ord(value) - 64)
                if _roman_number(value) is not None:
                    found.add(_roman_number(value))
                return found
            if prior and any(x == y + 1 for x in _part_values(label)
                             for y in _part_values(prior[-1].label)):
                finished_before_division = True
            # Profile rule `first_lettered_part_in_schedule` (unreleased-v4):
            # doc 4353's Schedule-II prints "PART-A" alone on its line after an
            # item ending ";" and before "1. Essential Qualification ...". The
            # ";" read as unfinished; the sequence test above needs an earlier
            # part. The first part (A, I or 1) of a schedule with none yet,
            # followed on its page by a numbered item, is that part.
            elif (profile_rule("first_lettered_part_in_schedule") and not prior
                  and scope is not root and not _norm(rest)
                  and 1 in _part_values(label)):
                following = next((unit_text for unit_block, unit_text in units[idx + 1:idx + 2]
                                  if unit_block.get("page_no") == b.get("page_no")), None)
                if following and re.match(r"^\s*\d{1,3}\.\s", following):
                    finished_before_division = True
        # Profile rule `enactment_chapter_reference` (unreleased-v4): doc 2221's First
        # Schedule names chapters of other enactments at the head of its row groups
        # ('Chapter VIII, Pakistan Penal Code.'); inside a schedule such a chapter label
        # is row text, not a division of the Ordinance.
        _agae_enactment_chapter = False
        if (kind == "chapter" and profile_rule("enactment_chapter_reference")
                and not referenced_division):
            _agae_scope = current
            while _agae_scope is not root and _agae_scope.kind not in (
                    "appendix", "schedule", "annexure", "form"):
                _agae_scope = _agae_scope.parent or root
            if _agae_scope is not root and re.match(
                    r"^,?\s*(?:the\s+)?[A-Z][A-Za-z'\u2019.\- ]{0,80}?\b(?:Code|Act|Ordinance|Regulations?)"
                    r"(?:,?\s*\d{4})?\s*\.?\s*$", _norm(rest)):
                _agae_enactment_chapter = True
        if kind in _HEADING_KINDS and not source_proves_schedule and not referenced_division and (
                _agae_enactment_chapter or
                _runs_on(rest)
                or (kind == "schedule" and idx < last_body_section)
                or (_continues_previous(previous_content(idx))
                    and not finished_before_division)):
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

        # A proviso can introduce its own dotted list of instructions for
        # reading an earlier Act.  Document 118 p.3 prints "the following
        # provisions ... shall be read as mentioned hereunder", then 1/2/3
        # indented beneath that proviso.  "In section 2" there names the
        # earlier Act; it is not section 2 of this instrument.  All four
        # independent signals are required: an open proviso with that explicit
        # introduction, deeper source indentation, a consecutive local number,
        # and the item's own amendment-reference wording.  An ordinary
        # top-level amending section beginning "In section" stays untouched.
        if (kind == "section" and not in_schedule and str(label).isdigit()):
            list_owner = current
            while (list_owner is not root and
                   not (list_owner.kind == "proviso" and re.search(
                       r"\bfollowing\s+provisions\b.{0,200}"
                       r"\bshall\s+be\s+read\s+as\b",
                       list_owner.text, re.I))):
                list_owner = list_owner.parent or root
            if list_owner is root:
                list_owner = None
            owner_block = (source_block_by_id.get(list_owner.first_block)
                           if list_owner is not None else None)
            prior_items = ([int(child.label) for child in list_owner.children
                            if child.kind == "clause" and child.label.isdigit()]
                           if list_owner is not None else [])
            expected_item = max(prior_items) + 1 if prior_items else 1
            if (list_owner is not None and owner_block is not None
                    and b.get("x0") is not None
                    and owner_block.get("x0") is not None
                    and float(b["x0"]) >= float(owner_block["x0"]) + 18
                    and int(label) == expected_item
                    and re.match(r"^In\s+(?:the\s+Preamble\b|sections?\s+\d+\b)",
                                 _norm(rest), re.I)
                    and not _heading_supports(rest, toc.get(str(label)))):
                depth = list_owner.depth + 1
                # Qualifiers normally live in `current`, not in `stack`.
                # Install this proven list owner in the stack so its nested
                # romanettes and the next numbered sibling retain context.
                while stack and stack[-1].depth >= list_owner.depth:
                    stack.pop()
                stack.append(list_owner)
                node = Node(kind="clause", label=str(label), depth=depth,
                            text_parts=[_norm(rest)] if rest else [],
                            first_page=b["page_no"], last_page=b["page_no"],
                            first_block=b.get("id"), parent=list_owner)
                list_owner.children.append(node)
                node.blocks.append(b.get("id"))
                mark(b, "body", node)
                stack.append(node)
                current = node
                continue

        # Profile rule `introduced_member_list` (unreleased-v2): a numbered list
        # that the open provision itself introduces. Doc 258 s.4(3) reads
        # "Advisory Board shall consist of the following members:-" and prints
        # members 1-10 as "1. The Minister ... - Member"; each number satisfies
        # the section grammar, so the members became top-level units, member 7
        # pushed the real s.7 aside, and s.4's later text hung under member 10.
        # Required together: the owner's own text ends with the introduction,
        # the number continues the owner's list (one fused number may be
        # skipped), the document has a contents list, and the item's words do
        # not support the contents heading printed for that number -- which is
        # what ends the list at the next real section.
        if (profile_rule("introduced_member_list") and kind == "section"
                and not in_schedule and toc and str(label).isdigit()
                and current is not root):
            list_owner = current
            while (list_owner is not root
                   and not _introduces_member_list(list_owner)):
                list_owner = list_owner.parent or root
            if list_owner is not root:
                prior_items = [int(child.label) for child in list_owner.children
                               if child.kind == "clause" and child.label.isdigit()]
                expected_item = max(prior_items) + 1 if prior_items else 1
                allowed = ({expected_item} if not prior_items
                           else {expected_item, expected_item + 1})
                # Profile rule `member_designation_row` (unreleased-v4): doc 3836
                # s.6(1) lists the Authority's members as a table, and row 7
                # "Chief Executive Officer of the Authority | Member/Cum-
                # Secretary" shares its words with the contents heading of s.7,
                # so the list stopped there and the row opened a fake s.7. A row
                # that continues the list, ends in a membership designation and
                # carries no heading dash is the list's item.
                designation_row = bool(
                    profile_rule("member_designation_row") and prior_items
                    and _MEMBER_DESIGNATION_END.search(_norm(rest))
                    and not re.search(r"[.:]\s*[-–—―]", _norm(rest)))
                if (int(label) in allowed
                        and (designation_row
                             or not _heading_supports(rest, toc.get(str(label))))
                        and len(_norm(rest)) <= 400):
                    while stack and stack[-1].depth >= list_owner.depth:
                        stack.pop()
                    stack.append(list_owner)
                    node = Node(kind="clause", label=str(label),
                                depth=list_owner.depth + 1,
                                text_parts=[_norm(rest)] if rest else [],
                                first_page=b["page_no"], last_page=b["page_no"],
                                first_block=b.get("id"), parent=list_owner)
                    list_owner.children.append(node)
                    node.blocks.append(b.get("id"))
                    mark(b, "body", node)
                    stack.append(node)
                    current = node
                    continue

        # Profile rule `schedule_item_list` (unreleased-v3): doc 2983's Scheme
        # para 4(a) ends "... in the last of those categories gets: - /
        # Categories" and prints categories 1-3 before (b). Inside a schedule
        # the rows 1-3 became siblings of paragraphs 1-3 (two rows each
        # labelled 1, 2, 3) and (b)-(d) hung under category 3. A row numbered
        # 1 opens a list inside the open lettered item when that item's text
        # ends introducing one; the next numbers continue it, and the next
        # lettered item unwinds past it as usual.
        if (profile_rule("schedule_item_list") and kind == "section" and in_schedule
                and str(label).isdigit() and current is not root):
            item_owner = current
            if (item_owner.kind == "clause" and str(item_owner.label).isdigit()
                    and item_owner.parent is not None
                    and item_owner.parent.kind == "clause"
                    and str(item_owner.parent.label).isalpha()):
                item_owner = item_owner.parent
            if item_owner.kind == "clause" and str(item_owner.label).isalpha():
                prior_items = [int(child.label) for child in item_owner.children
                               if child.kind == "clause" and str(child.label).isdigit()]
                introduces = bool(re.search(
                    r"[:\-–—]\s*-?\s*(?:[A-Z][A-Za-z]+\s*)?$",
                    _norm(" ".join(item_owner.text_parts))))
                if ((prior_items and int(label) == max(prior_items) + 1)
                        or (not prior_items and int(label) == 1 and introduces)):
                    while stack and stack[-1].depth > item_owner.depth:
                        stack.pop()
                    node = Node(kind="clause", label=str(label),
                                depth=item_owner.depth + 1,
                                text_parts=[_norm(rest)] if rest else [],
                                first_page=b["page_no"], last_page=b["page_no"],
                                first_block=b.get("id"), parent=item_owner)
                    item_owner.children.append(node)
                    node.blocks.append(b.get("id"))
                    mark(b, "schedule_row", node)
                    stack.append(node)
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
            _prev_item_block = (source_block_by_id.get(current.first_block)
                                if current is not root and current.kind == "clause" else None)
            if (owner is not root and candidate_key in toc and heading_disagrees
                    and ((candidate_key in seen and has_next_item)
                         or (indented
                             and _continues_previous(previous_content(idx))))):
                kind = "clause"
            elif (profile_rule("indented_list_item_continues") and owner is not root and toc
                    and heading_disagrees and indented
                    and candidate_number is not None and _prev_item_block is not None
                    and str(current.label) == str(candidate_number - 1)
                    and _prev_item_block.get("x0") is not None and b.get("x0") is not None
                    and abs(float(_prev_item_block["x0"]) - float(b["x0"])) <= 3):
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
                # second printing of this label worth its cost. A withheld
                # (asterisk-only) contents heading is no evidence of a
                # different unit under this number; only the forward scan can
                # then prove one (documents 1105, 1886, 4060 print rule 2 as
                # "2. They shall come into force at once." with contents
                # "2. ******" and no other rule 2).
                # The later same-numbered opener must be in the principal
                # body. Doc 1886 prints rule 2 once, followed by a Schedule
                # whose numbered job rows include row 2. Counting that row as
                # a second rule 2 buried the real commencement rule in 1(2).
                # Profile this change so already released default-profile
                # trees remain outside its replay scope.
                extent_or_commencement = bool(
                    (candidate_key in toc
                     and not _withheld_heading(toc.get(candidate_key))
                     and not _heading_supports(rest, toc.get(candidate_key)))
                    or any(_opens_section(later, candidate_key)
                           for _, later in units[
                               idx + 1:(last_body_section + 1
                                        if profile_rule("bounded_subpart_duplicate_scan")
                                        and last_body_section >= 0 else None)
                           ])
                )
            if owner is not root and (
                    ((re.match(r"^\s*\(\s*1\s*\)", owner.text)
                      or (unlisted_commencement and first_subpart is not None))
                     and owner.first_page == b["page_no"]
                     and indented
                     and candidate_number == expected_number
                     and ((candidate_key in toc
                           and not _withheld_heading(toc.get(candidate_key))
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
                # Profile rule `schedule_contents_run` (unreleased-v3): doc
                # 2983's contents lists sections 1-12 and then, restarting at
                # 1, the Scheme's paragraphs 1-16. Paragraphs 13-16 carry
                # labels the Act never uses, so the promise test above read
                # them as the Act resuming and made them sections 13-16 of a
                # twelve-section Act. A label the contents prints only after
                # its numbering restarts belongs to what restarted it.
                if (resumes and profile_rule("schedule_contents_run")
                        and _promised_only_after_restart(walk_toc, key)):
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
            # Profile rule `decimal_rule_resumes` (unreleased-v4): doc 3108 has
            # no contents list and prints rules 7.3 ... 7.23 after Forms A-D and
            # after Form L-37-A. A decimal number of the chapter of rules opened
            # before, one to three above the highest opened, resumes the body.
            if (not resumes and not toc and schedule_node is not None
                    and profile_rule("decimal_rule_resumes")
                    and schedule_node.kind in ("form", "schedule", "appendix", "annexure")):
                _dm = re.match(r"^(\d{1,3})\.(\d{1,3})(?:\.?[A-Z])?$", key)
                if _dm:
                    _minors = [int(_m.group(2)) for _lbl in label_nodes
                               for _m in [re.match(r"^(\d{1,3})\.(\d{1,3})(?:\.?[A-Z])?$", _lbl)]
                               if _m and _m.group(1) == _dm.group(1)]
                    if _minors and max(_minors) < int(_dm.group(2)) <= max(_minors) + 3:
                        resumes = True
            # Profile rule `last_promised_section_after_schedule` (unreleased-v4): doc 3142
            # prints rule 12 'REPEAL' after its Schedule; the contents' last and highest row,
            # not yet produced and opening with its contents heading, resumes the body.
            if (not resumes and toc and key in toc and key not in seen
                    and schedule_node is not None
                    and profile_rule("last_promised_section_after_schedule")
                    and re.fullmatch(r"\d{1,3}", key)):
                _others = [k for k in toc if k != key]
                if (_others
                        and all(re.fullmatch(r"\d{1,3}", k) and int(k) < int(key) and k in seen
                                for k in _others)
                        and _heading_supports(_norm(rest), toc.get(key))):
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
        if (schedule_word_list and explicit_table_owner is not None
                and profile_rule("schedule_word_rows_own_items")
                and kind in ("subsection", "clause")):
            open_row = next((n for n in reversed(stack) if n.parent is explicit_table_owner), None)
            if open_row is not None:
                depth += open_row.depth - DEPTH["section"]
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
        # Parenthesized romanettes beneath a source-proved proviso list item
        # are children of that item, not peers of the enclosing section.
        if (kind == "clause" and not in_schedule
                and re.fullmatch(r"(?:x{0,3})(?:ix|iv|v|v?i{1,3})", str(label), re.I)):
            item_owner = current
            while (item_owner is not root
                   and not (item_owner.kind == "clause"
                            and item_owner.label.isdigit()
                            and item_owner.parent is not None
                            and item_owner.parent.kind == "proviso"
                            and re.search(r"\bfollowing\s+provisions\b.{0,200}"
                                          r"\bshall\s+be\s+read\s+as\b",
                                          item_owner.parent.text, re.I))):
                item_owner = item_owner.parent or root
            item_block = (source_block_by_id.get(item_owner.first_block)
                          if item_owner is not root else None)
            if (item_block is not None and b.get("x0") is not None
                    and item_block.get("x0") is not None
                    and float(b["x0"]) >= float(item_block["x0"]) + 18):
                depth = item_owner.depth + 1
        if _agar_nf is not None and kind == "form":
            depth = _agar_nf[2].depth + 1
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
            if idx in _left_margin_heading_at and not toc and profile_rule("left_column_margin_heading"):
                heading, body_text = _left_margin_heading_at[idx], _norm(rest)
            # Same rule: once (1) has parted from "Heading.―", the bar left
            # behind is the heading's punctuation, not the section's text.
            if (profile_rule("decoded_dash_first_subsection") and heading
                    and re.fullmatch(r"[\s―—–.:-]+", body_text or "")):
                body_text = ""
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
            # Under `sequential_part_heading` (unreleased-v4): doc 4433 p38
            # prints "Part-B / Other Commercial Properties", a blank line, then
            # the part's operative sentence "Tax for properties, used as shops
            # ... with the following formula:". The title ends at the blank line;
            # a sentence after it is the part's text, not its heading.
            if kind == "part" and profile_rule("sequential_part_heading"):
                pieces = re.split(r"\n[ \t ]*\n", rest.strip(), maxsplit=1)
                if (len(pieces) == 2 and _norm(pieces[0])
                        and re.search(r"\b[a-z]{3,}\b.*[:.]\s*$", _norm(pieces[1]))):
                    heading, body_text = _norm(pieces[0]), _norm(pieces[1])

        # Profile rule `schedule_division_heading_lines` (unreleased-v4): (doc 4447 pp194, 200, 205, 207): a high-ordinal schedule
        # or a Table / Annex / Notes / conditions Part of an open schedule takes as its heading only its
        # parenthesised subtitle and "[See ...]" reference lines (and, for a Part, a short caption ending in a
        # colon); the TABLE caption, an introductory sentence or a form grid after them is its text
        if (profile_rule("schedule_division_heading_lines") and kind in _HEADING_KINDS and rest
                and ((kind == "schedule" and re.fullmatch(r"(?:EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|"
                                                          r"FOURTEENTH|FIFTEENTH)\s+SCHEDULE", str(label)))
                     or (kind == "part" and in_schedule and re.match(
                         r"(?:TABLE|Annex|Notes$|.*CONDITIONS$|Procedure and conditions$)", str(label), re.I)))):
            _hl = [_l.strip() for _l in rest.strip().split("\n") if _l.strip()]
            _k = 0
            while _k < len(_hl) and re.fullmatch(r"\(.*\)|\[\s*See\b.*\]", _hl[_k], re.I):
                _k += 1
            if (_k == 0 and kind == "part" and _hl and len(_hl[0]) <= 80 and _hl[0].endswith(":")
                    and not re.search(r"\(\s*\d+\s*\)", _hl[0])):
                _k = 1
            if _k < len(_hl):
                heading = _norm(" ".join(_hl[:_k])) or None
                body_text = _norm(" ".join(_hl[_k:]))
        if _agar_nf is not None and kind == "form":
            heading, body_text = _agar_nf[0], _agar_nf[1]
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
        # Profile rule `schedule_title_first_statutes` (unreleased-v4): doc 2731: 'THE SCHEDULE' then 'THE FIRST STATUTES' name one schedule.
        if (profile_rule("schedule_title_first_statutes") and kind == "schedule"
                and re.search(r"FIRST\s+STATUTES", str(label), re.I)
                and current is not root and current.kind == "schedule"
                and re.fullmatch(r"(?:THE\s+)?SCHEDULE", _norm(str(current.label)), re.I)
                and not current.children and not _norm(" ".join(current.text_parts))
                and current.first_page == b["page_no"]):
            current.label = label
            if heading and not current.heading:
                current.heading = heading
            current.blocks.append(b.get("id"))
            current.last_page = b["page_no"]
            mark(b, "heading", current)
            # the unwind above popped the open schedule (same depth); it stays the open container
            if not stack or stack[-1] is not current:
                stack.append(current)
            continue
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
            seg_roles[bid] = ("preface" if preface_before_body else "contents", None)
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
    # Profile rule `level_margin_heading_owner` (unreleased-v3): the page says
    # which provision a margin heading sits beside -- the one whose opening
    # line is level with it. Doc 1521 p3's text layer emits "Definitions."
    # (level with "2. In this Act, ...") after s.2(d), so the next-block
    # fallback gave it to s.2(e). Only a single level opener to its left, on
    # its page, within 3 pt, is taken; otherwise the fallback stands.
    level_owner: dict = {}
    if profile_rule("level_margin_heading_owner"):
        by_id = {b.get("id"): b for b in blocks if b.get("id") is not None}
        openers = [(by_id[bid], node) for bid, (_role, node) in seg_roles.items()
                   if node is not None and node.first_block == bid and bid in by_id
                   and by_id[bid].get("y0") is not None
                   and by_id[bid].get("x0") is not None]
        for bid, (role, node) in seg_roles.items():
            block = by_id.get(bid)
            if (role != "heading" or node is not None or block is None
                    or block.get("y0") is None or block.get("x0") is None):
                continue
            # Either side: doc 258 sets its margin headings LEFT of the text
            # ("Short title, extent and commencement." beside "1. (1) ...").
            level = [owner for opener, owner in openers
                     if opener.get("page_no") == block.get("page_no")
                     and abs(float(opener["y0"]) - float(block["y0"])) <= 3
                     and (float(opener["x0"]) < float(block["x0"])
                          or float(opener["x0"]) >= float(block["x1"]))]
            if len(level) == 1:
                level_owner[bid] = level[0]
    for position, bid in enumerate(ordered):
        entry = seg_roles.get(bid)
        if entry is None or entry[0] != "heading" or entry[1] is not None:
            continue
        if bid in level_owner:
            seg_roles[bid] = ("heading", level_owner[bid])
            # A provision with no heading takes the margin heading printed
            # level with it: doc 876's statute 10 prints "Finance and Planning
            # Committee." beside "10. (1) The Finance and Planning Committee
            # shall consist of--", emitted after the opener, and its contents
            # row (label 10 twice in the contents) found nothing to link by.
            owner = level_owner[bid]
            # Profile rule `level_margin_heading_text` (unreleased-v4): it
            # also names doc 2983's Scheme paragraphs 4 and 6, a tree
            # released under v3, so it opened v4 (migration 0059).
            if not owner.heading and profile_rule("level_margin_heading_text"):
                heading_block = next((b for b in blocks if b.get("id") == bid), None)
                if heading_block is not None and _norm(heading_block.get("text") or ""):
                    owner.heading = _norm(heading_block["text"])
            continue
        successor = next((seg_roles[nxt][1] for nxt in ordered[position + 1:]
                          if seg_roles.get(nxt) and seg_roles[nxt][1] is not None),
                         None)
        if successor is not None:
            seg_roles[bid] = ("heading", successor)

    # Profile rule `left_column_margin_heading` shape (A): a left-column heading level with a section opener (a bare number block such as '1.'
    # may share its line with the first sub-section's block, so level_margin_heading_owner finds two openers).
    for _hb, _oid in _left_margin_level_pairs:
        _owner = next((_nd for _bid, (_r, _nd) in seg_roles.items()
                       if _nd is not None and _nd.first_block == _oid and _nd.kind == "section"), None)
        if _owner is not None:
            seg_roles[_hb["id"]] = ("heading", _owner)
            if not _owner.heading:
                _owner.heading = _norm(_hb.get("text") or "")
    # Document 3's section-2 marginal heading is extracted *after* the sole
    # operative section block, so the next-block fallback cannot attach it.
    # The exact source-block digest above and the printed page establish its
    # owner. Preserve the heading and its provenance instead of leaving an
    # unassigned ledger block or appending it to enacted section text.
    if source_nonoperative_roles.get(24) == "heading":
        section_two = next((node for node in root.children
                            if node.kind == "section" and node.label == "2"
                            and node.first_block == 23), None)
        heading_block = next((block for block in blocks
                              if block.get("id") == 24), None)
        if section_two is not None and heading_block is not None:
            section_two.marginal_note = _norm(
                re.sub(r"_+", "", heading_block["text"]))
            seg_roles[24] = ("heading", section_two)

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
            # Only where the reading is unambiguous.  TWO READINGS restoring
            # two prints of one label are two claims to be the same section,
            # and the parser is not the one to choose between them.
            #
            # ONE reading matching two prints is a different thing entirely.
            # A text block subdivides, so one block can open two units that
            # print the same label: block 56861 of document 1154 holds section
            # 1's extent subsection carrying the label 2 and, 75 characters
            # later, the real section 2.  Both answer to (56861, "2").  The
            # decision is recorded against `candidate_provision_id` -- the
            # print the parser DEMOTED -- so the print it kept is not the one
            # the reviewer described, and dropping it leaves exactly the unit
            # that was read.  Counting nodes instead of readings refused 36
            # units on documents where nobody had disagreed about anything.
            restored_keys = {
                (item.first_block, _reviewed_label_key(item.label))
                for item in nodes
                if reviewed_structure.get(
                    (item.first_block, _reviewed_label_key(item.label)))
                == "restore_citable"}
            restored: list = []
            if len(restored_keys) > 1:
                reviews_refused.append({
                    "resolution": "restore_citable",
                    "reason": "two prints of one label are both restored",
                    "printed_label": key,
                    "source_block_ids": sorted(
                        block for block, _label in restored_keys
                        if block is not None),
                })
            elif restored_keys:
                anchor = next(iter(restored_keys))
                named = [
                    item for item in nodes
                    if (item.first_block, _reviewed_label_key(item.label))
                    == anchor and item is not canonical]
                if len(named) == 1:
                    restored = named
                elif len(named) > 1:
                    # Three prints of one label opening on one block. Nothing
                    # durable separates them, so the reading cannot be placed.
                    reviews_refused.append({
                        "resolution": "restore_citable",
                        "reason": "one reading matches several prints on that "
                                  "block and label",
                        "printed_label": key,
                        "source_block_ids": [anchor[0]],
                    })
            inverted_from = None
            if restored:
                # THE STUB GUARD, in the direction a swap can break it.
                #
                # `restore_citable` is recorded for two different findings and
                # the resolution alone cannot tell them apart.  Document 2629
                # is the first: the parser kept a footnote on page 11 that had
                # swallowed 5,249 characters and demoted the real rule 14, 659
                # characters on page 17.  Swapping there REPAIRS a citation
                # that resolved to apparatus.  Document 3216 is the second:
                # page 23 of the Punjab Excise rules prints two rules both
                # numbered 9.115 and the reviewer's own words are "Both are
                # operative".  Swapping there repairs nothing -- it moves the
                # citation off 2,373 characters of operative rule onto 316 and
                # demotes the rest.  Document 2288 prints two section 5s the
                # same way.  Neither reviewer asked for a demotion; the source
                # numbers two units alike and no parser can invent the
                # distinction.
                #
                # So refuse the swap on exactly the shape
                # `tools/adjudicate_s7_from_source.py` refuses an
                # `accept_non_citable` on: the print losing the citation
                # carries 500+ characters and the print gaining it carries
                # less than half.  That is the shape that produced 359
                # citations resolving to less than half their provision.  It
                # refuses some correct repairs too, document 2629 among them.
                # Fail-closed is the right direction when one reviewer's words
                # fit two findings: a refused unit stays in the queue for a
                # second reading, an enacted one silently buries a rule.
                losing = _subtree_chars(canonical)
                gaining = _subtree_chars(restored[0])
                if losing >= 500 and gaining * 2 < losing:
                    reviews_refused.append({
                        "resolution": "restore_citable",
                        "reason": "the swap would move the citation "
                                  "onto a stub",
                        "printed_label": canonical.label,
                        "source_block_ids": [canonical.first_block,
                                             restored[0].first_block],
                        "chars_losing": losing,
                        "chars_gaining": gaining,
                    })
                    restored = []
            if restored:
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

    if set(continuation_parents) != continuation_applied:
        raise ValueError("source continuation override not reached: "
                         f"{sorted(set(continuation_parents) - continuation_applied)}")
    if set(unnumbered_openers) != unnumbered_applied:
        raise ValueError("source unnumbered section override not reached: "
                         f"{sorted(set(unnumbered_openers) - unnumbered_applied)}")
    if set(unnumbered_parts) != unnumbered_parts_applied:
        raise ValueError("source unnumbered part override not reached: "
                         f"{sorted(set(unnumbered_parts) - unnumbered_parts_applied)}")
    if set(schedule_row_openers) != schedule_row_openers_applied:
        raise ValueError("source schedule row override not reached: "
                         f"{sorted(set(schedule_row_openers) - schedule_row_openers_applied)}")
    source_reparents = overrides.get("source_reparent_blocks") or []
    if source_reparents:
        reviews_enacted.extend(_apply_source_reparents(
            root, source_reparents, repeated_label_decisions, seg_roles))
    schedule_form_group = overrides.get("source_schedule_form_group")
    if schedule_form_group:
        reviews_enacted.append(_apply_source_schedule_form_group(
            root, schedule_form_group, seg_roles))

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
        sched_entries = {e["label"] for e in walk_toc
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
        for entry in walk_toc:
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
        for entry in walk_toc:
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
            elif entry["ordinal"] in aligned_labels:
                # Profile rule `contents_heading_alignment`: the row is looked
                # up under the body label its heading names; a row naming no
                # body unit stays unmatched for a page-read adjudication.
                target = aligned_labels[entry["ordinal"]]
                if target is None:
                    # Stored as every unlinked row is; the alignment itself
                    # (run detail `contents_alignment`) records the None.
                    node, method = None, "unmatched"
                else:
                    node, method = toc_node(dict(entry, label=target))
                    method = f"heading_alignment:{method}"
            else:
                node, method = toc_node(entry)
            resolved = {
                **entry,
                "kind": (
                    "schedule" if _TOC_SCHEDULE.match(entry["heading"] or "")
                    else "part" if _TOC_PART.match(entry["heading"] or "")
                    else "section"
                ),
                "node": node,
                "method": method,
            }
            if entry["ordinal"] in aligned_labels:
                resolved["walk_label"] = aligned_labels[entry["ordinal"]]
            resolved_entries.append(resolved)
        # A printed heading may say only "Omitted" while the body retains its
        # historical marginal heading followed by omission marks. After the
        # strong matches above, source order can resolve such an entry only
        # when adjacent resolved entries bound exactly one same-label node.
        for index, resolved in enumerate(resolved_entries):
            if resolved["node"] is not None:
                continue
            # An aligned row was already looked up under the label its heading
            # names; its printed label would recover the wrong unit here.
            if "walk_label" in resolved:
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
                # Profile rule `schedule_item_rows_in_order` (unreleased-v4): doc 2739's contents lists
                # the Schedule's amendments as a second run '1. Amendment in section 3.' ... '13.' after
                # row 30; its first row is the schedule's first numbered item when the last linked row
                # precedes that schedule (the rows after it then follow in clause context).
                if (not clause_context and profile_rule("schedule_item_rows_in_order")
                        and len(candidates) == 1 and _citation_label_key(resolved["label"]) == "1"
                        and candidates[0].parent is not None
                        and candidates[0].parent.kind == "schedule"
                        and next((child for child in candidates[0].parent.children
                                  if child.kind == "clause"), None) is candidates[0]
                        and (prior is None
                             or node_order[id(prior)] < node_order[id(candidates[0].parent)])):
                    clause_context = True
                if not clause_context:
                    candidates = []
            if len(candidates) == 1:
                resolved["node"] = candidates[0]
                resolved["method"] = "label_order"

        if profile_rule("first_statutes_schedule"):
            _link_statute_rows(resolved_entries, flat_nodes, blocks)

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
            if match:
                return match.group(1).casefold()
            # Profile rule `printed_disposition_rows` (unreleased-v3): the
            # contents row is itself the printer's disposition mark -- doc
            # 2923 prints "3. [Repeal.]" for four sections it no longer
            # carries, doc 4222 "16. * * * *." -- and no lifecycle word
            # matched. A bracketed "Repeal" is "repealed"; a row of nothing
            # but asterisks or leader dots is "omitted". A bare "Repeal." is
            # a section TITLED Repeal and stays a heading.
            if profile_rule("printed_disposition_rows"):
                flat = _norm(value or "")
                if re.fullmatch(r"\[\s*Repeal(?:ed)?\s*\.?\s*\]\s*\.?", flat, re.I):
                    return "repealed"
                if _MARK_ONLY_ROW.fullmatch(flat):
                    return "omitted"
            return None

        def disposition_matches(heading: str | None, recorded: str | None) -> bool:
            # A row of marks does not say WHICH lifecycle event it records;
            # the page's footnote does (doc 4222 ss.16-19: "* * * *." in the
            # contents, "Repealed by the Punjab Protected Areas Act 2020" in
            # the body's notes), so the reviewed record may carry either.
            if (profile_rule("printed_disposition_rows")
                    and _MARK_ONLY_ROW.fullmatch(_norm(heading or ""))):
                return recorded in ("omitted", "repealed")
            return disposition_word(heading) == recorded

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
                and disposition_matches(resolved.get("heading"),
                                        assertion.get("disposition"))
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
        # An aligned row counts under the body label its heading names; a row
        # naming no body unit counts nowhere in the label arithmetic and is
        # reported as missing by its printed label below.
        def counted_label(entry: dict) -> str | None:
            return entry.get("walk_label", entry["label"])

        def absent_row(entry: dict) -> bool:
            return "walk_label" in entry and entry["walk_label"] is None

        absent_rows = {entry["label"] for entry in resolved_entries
                       if absent_row(entry)}
        represented_labels = {
            counted_label(entry) for entry in resolved_entries
            if entry["kind"] != "schedule" and not absent_row(entry)
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
                    # with it.  See _names_another_section. A row joined by
                    # the profile's heading alignment was paired with this
                    # unit on the page's own headings, so an operative opening
                    # ("In the ... Finance Act, 1973 ...", doc 244) is not
                    # another name for it.
                    and ("walk_label" in entry
                         or not _names_another_section(
                             " ".join(node.text_parts) if node.text_parts else "",
                             entry.get("heading")))):
                node.heading = _norm(entry["heading"])
        unresolved_labels = {
            counted_label(entry) for entry in resolved_entries
            if entry["kind"] != "schedule" and entry["node"] is None
            and not absent_row(entry)
        }
        unresolved_labels.update(promised - represented_labels)
        seg.matched = len(promised - unresolved_labels)
        seg.missing = sorted(unresolved_labels | absent_rows)[:200]
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
            repaired = _segment(
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

    # Profile rule `contents_heading_alignment` -- see
    # `_contents_heading_alignment`. Re-entered with the alignment named, like
    # the structural repair above; kept only if nothing citable changes.
    if (profile_rule("contents_heading_alignment")
            and seg.toc_found and seg.toc_entries
            and "contents_heading_alignment" not in overrides):
        alignment = _contents_heading_alignment(seg, blocks)
        if alignment is not None:
            aligned = _segment(
                original_blocks,
                curation_patches=curation_patches,
                toc_dispositions=toc_dispositions,
                split_fused_margins=split_fused_margins,
                detect_contents=detect_contents,
                force_opening_contents=force_opening_contents,
                structural_resolutions=structural_resolutions,
                structural_overrides={**overrides,
                                      "contents_heading_alignment": alignment},
            )
            if _contents_alignment_is_safe(seg, aligned):
                aligned.contents_alignment = alignment
                return aligned

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
        refuted = _segment(
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
