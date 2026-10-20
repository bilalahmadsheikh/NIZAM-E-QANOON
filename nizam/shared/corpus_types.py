"""Data structures passed from L1 extraction to L2 storage.

They live in `shared` because it is the one package every layer may import and
which imports none of them (`.importlinter` contract 3). That keeps `corpus`
free of a database driver and `storage` free of PDF libraries, while both agree
on the shape of an extracted document.

The shape follows Document 02 §4.1: "Each block carries {page, bbox,
reading_order, script, extractor, confidence}". Nothing here is normalised or
repaired — hyphen repair, ligature expansion and whitespace normalisation
produce *derived* text later, "while the exact extracted form remains available
for audit".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Unnumbered provisions (INV-1, INV-4; docs/SCHEMA.md `provision`) ────────
# A provision the instrument prints with no number -- doc 128's Act-level
# "Repeal:" paragraph after its Schedule -- is stored as an ordinary `section`
# whose label is its printed lead word.  The absence of a numeral in a
# numbered kind's label IS the marker; no flag column carries it.  Every
# renderer asks this predicate before writing "section N": an unnumbered
# provision is cited by its printed word ('the unnumbered "Repeal" provision'),
# never as "section Repeal", and no number is ever invented for it.
NUMBERED_PROVISION_KINDS = frozenset({"section", "article", "subsection"})
_ROMAN = re.compile(r"[ivxlcdm]+", re.I)


def is_unnumbered_label(label: str | None) -> bool:
    """A printed word, not a number: no digit in any script (``\\d`` matches
    Urdu and Arabic-Indic digits too), not a roman numeral, at least two letters."""
    value = (label or "").strip()
    return (sum(ch.isalpha() for ch in value) >= 2
            and not re.search(r"\d", value)
            and not _ROMAN.fullmatch(value))


def is_unnumbered_provision(kind: str, label: str | None) -> bool:
    """Is this stored provision one the instrument prints without a number?"""
    return kind in NUMBERED_PROVISION_KINDS and is_unnumbered_label(label)


# ── Order suffix (INV-1, INV-4; docs/SCHEMA.md `provision`) ─────────────────
# Doc 999 prints two sections "2" and the owner kept both citable (decision
# 2026-10-06 q1 'keep-both', 7 Oct: an order suffix).  Both keep the printed
# label "2"; the later print's ltree key ends `__o2` (profile rule
# `order_suffix_label`, written at segmentation from print order), and the
# citation renders "s.2 (second)".  A renderer reads the occurrence from the
# stored path -- never from a model, never from a count over siblings at
# render time -- and appends the suffix whenever it writes the label.
_ORDER_SUFFIX = re.compile(r"__o([0-9]+)$")
_ORDER_WORDS = {2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth",
                7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}


def print_occurrence(path: str | None) -> int:
    """The print-order occurrence the stored path records: 1 unless its last
    ltree label ends in the `__oN` marker."""
    last = (path or "").rsplit(".", 1)[-1]
    found = _ORDER_SUFFIX.search(last)
    return int(found.group(1)) if found else 1


def order_suffix(path: str | None) -> str:
    """The citation suffix for a stored provision: '' for a first (or only)
    print, '(second)', '(third)', ... for a later print of a kept label."""
    occurrence = print_occurrence(path)
    if occurrence == 1:
        return ""
    return f"({_ORDER_WORDS.get(occurrence, f'print {occurrence}')})"


# ── Named schedule rows (INV-1, INV-4; docs/SCHEMA.md `provision`) ──────────
# Docs 1078 and 1121 print a recruitment table with no serial column: each row
# is identified only by the post it fills, 'Cane Commissioner (BS-19)'.  The
# owner ruled (2026-10-07, export -e: 1078 q1 'schedule-rows-by-post', 1121 q2
# 'rows-by-post') that each row is a citable Schedule row identified by that
# printed post name, with no number supplied.  It is stored as a `clause` under
# the schedule whose label is the post name verbatim; its ltree key ends
# `__nr` (profile rule `named_schedule_row`, written at segmentation from a
# reviewed override).  The label's shape cannot carry the marker -- a grade
# like '(BS-19)' carries digits, so is_unnumbered_label refuses it -- and a
# renderer asking only the kind would write 'clause Cane Commissioner
# (BS-19)'.  A renderer asks this predicate first and cites such a row as the
# Schedule entry for the post: 'Schedule, Cane Commissioner (BS-19)'.
_NAMED_ROW = re.compile(r"__nr$")


def is_named_schedule_row(path: str | None) -> bool:
    """Is this stored provision a Schedule row identified by its printed post
    name (no number)?  Read from the stored path's last ltree label, as
    `order_suffix` is -- never from the label's shape, never generated."""
    last = (path or "").rsplit(".", 1)[-1]
    return last.startswith("cl_") and bool(_NAMED_ROW.search(last))


# ── Schedule group captions (INV-1, INV-4; docs/SCHEMA.md `provision`) ──────
# Doc 1106's 1996 Schedule prints wing titles ('GAZETTED STAFF OF FLORICULTURE
# WING') and group captions ('GREEN BELT GROUP') across the table, and the post
# serials restart under each.  The owner ruled (2026-10-07, export -e q3
# 'rows-by-group') that each row is identified by its group caption and its
# printed serial (or post name).  A caption is stored as a `part` under the
# schedule (or under its wing) -- there is no 'group' kind -- labelled with
# the caption as printed; its ltree key ends `__gc` (profile rule
# `schedule_group_caption`).  A renderer asks this predicate first and cites
# the caption exactly as printed ('GREEN BELT GROUP, 2'), never as
# 'Part GREEN BELT GROUP'.
_GROUP_CAPTION = re.compile(r"__gc$")


def is_schedule_group_caption(path: str | None) -> bool:
    """Is this stored provision a Schedule group caption (a `part` the copy
    prints as a caption, not as a numbered Part)?  Read from the stored path's
    last ltree label, never from the label or kind."""
    last = (path or "").rsplit(".", 1)[-1]
    return last.startswith("pt_") and bool(_GROUP_CAPTION.search(last))


# ── Printed number markers (INV-1, INV-4; docs/SCHEMA.md `provision`) ──────
# Doc 1225 (Sindh Finance Act, 2006) prints nine contents rows and eight body
# sections: row 3 is the margin note of the quoted Stamp Act s.29 that body
# s.2(ii) substitutes, and from body s.3 on the contents runs one ahead.  The
# owner chose the CONTENTS numbering (export -f, 2026-10-08, q1 'contents'):
# the quotation is cited s.3 and body ss.3-8 are cited 4-9.  The stored
# `label` is the cited number -- what a lawyer cites -- and the print is kept
# on the path: `s_4__p3` (printed '3.'), `s_3__pnone` (the copy prints no
# number of this instrument there).  Only a reviewed owner-cited override
# (profile rule `owner_cited_label`) writes the marker; a renderer reads it
# here and never derives it at render time.
_PRINTED_MARKER = re.compile(r"__p([A-Za-z0-9]+)$")


# Rule `owner_cited_compound_label` (agent JE; docs 4498, 4400): a compound print N-M / N.M is written
# `__pN_M`; its separator is the stored (cited) label's -- the shape rule requires the same one.
_PRINTED_COMPOUND = re.compile(r"__p([0-9]{1,4})_([0-9]{1,4})(?:(_?)([A-Z])|_([0-9]{1,3}))?$")
_LABEL_COMPOUND = re.compile(r"([0-9]{1,4})([.\-])([0-9]{1,4})(?:[.\-]?[A-Z])?")


def printed_label(path: str | None, label: str | None = None) -> str | None:
    """The label the copy PRINTS for an owner-renumbered provision, read from
    the stored path's last ltree label: None when the path carries no `__p`
    marker (the stored label is the print); '' when the copy prints no number
    of this instrument (`__pnone`); otherwise the printed label ('3' for
    `s_4__p3`; '1.32' for `s_1_132__p1_32` with stored label '1.132')."""
    last = (path or "").rsplit(".", 1)[-1]
    compound = _PRINTED_COMPOUND.search(last)
    if compound:
        lm = _LABEL_COMPOUND.fullmatch(label or "")
        # extension `owner_cited_cross_chapter_label` (agent JE, doc 4498): the print's N may differ from the stored
        # label's ('13-21' printed for rule 14-2); the separator is still the stored label's
        if lm is None:
            raise ValueError(f"compound printed marker on {last!r} needs its stored compound label, got {label!r}")
        # extension `owner_cited_lettered_compound_label` (agent JE): a printed letter, after '-' when the marker has '_'
        # extension (agent JE, doc 4498 q5): a three-part print, '23-18.1' from __p23_18_1
        if compound.group(5):
            return f"{compound.group(1)}{lm.group(2)}{compound.group(2)}.{compound.group(5)}"
        return (f"{compound.group(1)}{lm.group(2)}{compound.group(2)}"
                + (("-" if compound.group(3) else "") + compound.group(4) if compound.group(4) else ""))
    found = _PRINTED_MARKER.search(last)
    if not found:
        return None
    return "" if found.group(1) == "none" else found.group(1)


def printed_note(path: str | None, label: str | None = None) -> str:
    """The citation note for a renderer: '' for an ordinary provision,
    '(printed 3)' for an owner-renumbered one, '(no number printed)' for one
    the copy prints with no number of this instrument."""
    value = printed_label(path, label)
    if value is None:
        return ""
    return "(no number printed)" if value == "" else f"(printed {value})"


@dataclass(frozen=True, slots=True)
class ExtractedBlock:
    page_no: int
    block_no: int          # index within the page, as the extractor emitted it
    reading_order: int     # monotonic across the whole document
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    script: str | None = None       # 'latin' | 'arabic' | 'mixed' | None
    confidence: float | None = None  # None for a text layer; set by OCR lanes
    inside_cropbox: bool = True


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_no: int
    width: float
    height: float
    char_count: int
    lane: str              # per-page: §4 "one bad page does not force OCR across an entire Act"
    crop_box: tuple[float, float, float, float] | None = None
    media_box: tuple[float, float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    sha256: str
    language: str
    publication_role: str
    page_count: int
    char_count: int
    printable_ratio: float
    empty_pages: int
    lane: str
    extractor: str
    extractor_config: dict
    pdf_metadata: dict
    pages: list[ExtractedPage] = field(default_factory=list)
    blocks: list[ExtractedBlock] = field(default_factory=list)


class ExtractionRejected(Exception):
    """The document did not meet Document 02 §4 acceptance for its lane.

    Raised rather than returned: a document that fails acceptance must not reach
    storage at all. §8 — "Nothing reaches retrieval because a script finished."
    """


@dataclass(frozen=True, slots=True)
class SegmentedInstrument:
    """One statute, segmented: the instrument and its whole provision tree.

    Passed from L1 segmentation to L2 storage. Provisions arrive in document
    order, which is already topological -- a parent always precedes its children
    -- so the writer can resolve parent_id as it inserts, in one pass.

    `as_at` is the date the source was observed. Doc 03 §2.3's validity range
    opens there rather than at enactment, because what the code portals publish
    is the CONSOLIDATED current text: saying it applied from 1860 would assert an
    amendment history we do not have. The one exception is `version_validity`
    (below): a reviewed, owner-declared historical window.
    """
    document_id: int
    source_observation_id: int
    sha256: str
    jurisdiction: str
    kind: str
    number: str | None
    # None only for an owner-declared undated instrument (migration 0063: the
    # active expression manifest cites an answer whose choice is 'undated');
    # its path prefix reads 'yundated'. Never inferred.
    year: int | None
    short_title: str
    long_title: str | None
    preamble: str | None
    source_url: str | None
    as_at: str                       # ISO date
    confidence: float | None
    provisions: list[dict] = field(default_factory=list)
    # The statute's own printed contents list, in printed order. Each entry
    # names the provision the body walk produced for it, by row key, or None --
    # which is a gap the document itself proves exists. Migration 0011.
    toc_entries: list[dict] = field(default_factory=list)
    # (block_id, role, provision_key or None, chars) for EVERY block in the
    # document. docs/CORPUS-CRITERIA.md C4: nothing in the PDF is discarded;
    # what is not enacted text is classified, not dropped.
    block_roles: list[tuple] = field(default_factory=list)
    # Item-level evidence for any citable-label collision resolved by the
    # parser.  Storage persists these beside the exact instrument revision;
    # they are candidates until an independent adjudication event accepts,
    # restores, reparents, or splits them.
    structural_decisions: list[dict] = field(default_factory=list)
    # One official observation may be a compilation containing several legal
    # instruments.  Ordinal 0 remains the ordinary one-observation/one-
    # instrument case; positive ordinals identify source-reviewed embedded
    # expressions without copying or altering their underlying text blocks.
    expression_ordinal: int = 0
    source_start_block_id: int | None = None
    source_end_block_id: int | None = None
    expression_role: str = "primary"
    # Exact-tree overlays (for example a rendered-source omitted-section fact)
    # preserve every instrument metadata field from this immutable predecessor.
    # Ordinary parser builds leave this NULL and use their inferred metadata.
    copy_instrument_id: str | None = None
    # None: current consolidated text, whose versions open at `as_at` and stay
    # open (docs/03 §2.3). (from, to) ISO dates: an owner-declared HISTORICAL
    # expression (migration 0064; decision 'historical-expression'), whose
    # versions are written daterange(from, to, '[)') -- in force only inside
    # the reviewed window, never shown as current law (INV-5). Set only from a
    # reviewed plan or carried from the active manifest; legal_write.save()
    # refuses it and save_many() requires the manifest to carry the same window.
    version_validity: tuple[str, str] | None = None
