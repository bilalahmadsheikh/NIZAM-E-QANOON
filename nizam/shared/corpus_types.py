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
    amendment history we do not have.
    """
    document_id: int
    source_observation_id: int
    sha256: str
    jurisdiction: str
    kind: str
    number: str | None
    year: int
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
