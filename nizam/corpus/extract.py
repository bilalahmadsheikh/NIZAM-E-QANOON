"""L1 extraction — Document 02 §4, lane E2 (born-digital PDF).

Pure: bytes in, an `ExtractedDocument` out. No database, no filesystem writes,
no network. That is what makes it testable against a fixture and what keeps
`.importlinter` contract 6 (no database drivers outside storage) true.

Only lane E2 is implemented here. §4 routes five lanes and does so *per page*,
so that "one bad page does not force OCR across an entire Act" — the page-level
lane is recorded from the start even though every page currently resolves to E2.
E3/E4 (render and OCR the failed pages) attach at `_page_lane` when the ~150
document OCR fallback is built; nothing above this module changes when they do.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from statistics import median

import pymupdf

from nizam.shared.corpus_types import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionRejected,
)

# §4 acceptance for E2: ">=95% printable characters; no missing-page or
# repeated-glyph anomaly."
MIN_PRINTABLE_RATIO = 0.95

# A scan can carry a tiny, perfectly printable overlay on every page (scanner
# branding, a repeated portal stamp, or page furniture).  Treating that as the
# document's text layer silently discards the photographed law.  These bounds
# are intentionally conjunctive: sparse text alone is allowed, and repeated
# text alone is allowed; only a multipage document dominated by the same tiny
# signature is routed to full-page OCR.
SPARSE_OVERLAY_MAX_MEDIAN_CHARS = 32
SPARSE_OVERLAY_MAX_MEAN_CHARS = 40
SPARSE_OVERLAY_MIN_PAGES = 3
SPARSE_OVERLAY_DOMINANCE = 0.80

# Junk means extraction damage, not "str.isprintable() said no".
#
# Python's isprintable() is False for every whitespace character except a literal
# space, so U+00A0 NO-BREAK SPACE counts as unprintable to it. Pakistani statutes
# are typeset with non-breaking spaces everywhere -- they were 15-19% of the
# characters in several documents -- and using isprintable() rejected 31 perfectly
# good born-digital Acts, including the Companies Ordinance 1984 and a 376-page
# consolidation. Soft hyphens (U+00AD) are legitimate typography too.
#
# What §4 is actually screening for is a broken text layer: control bytes,
# unpaired surrogates, unassigned code points, private-use glyphs from a bad
# embedded font, and U+FFFD where a decode failed.
_JUNK_CATEGORIES = frozenset({"Cc", "Cs", "Co", "Cn"})
_ALLOWED_CONTROLS = frozenset("\t\n\r\f\v")
_REPLACEMENT = "�"

_ARABIC = re.compile(r'[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]')
_LATIN = re.compile(r'[A-Za-z]')


def _remove_exact_overlay_spans(page: pymupdf.Page, raw: list[tuple],
                                *, flags: int = 3) -> tuple[list[tuple], int]:
    """Canonicalise one rendered glyph stack to one semantic text occurrence.

    Code-portal PDFs sometimes paint a running update stamp twice at the same
    bbox, font, size, colour and flags. Others use sub-point offsets to simulate
    bold text.  Both render as one line while the block API emits each paint.
    The PDF and old revisions remain retained; text at distinct geometry is
    deliberately untouched. A 0.25pt bound is below a rendered pixel at 300dpi.
    """
    detail = page.get_text("dict", sort=True, flags=flags)
    painted: dict[tuple, list[tuple[float, float, float, float]]] = {}
    for block in detail.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                value = span.get("text", "")
                if not value.strip():
                    continue
                bbox = tuple(round(float(v), 3) for v in span["bbox"])
                style = (value, span.get("font"),
                         round(float(span.get("size", 0)), 3),
                         span.get("color"), span.get("flags"))
                painted.setdefault(style, []).append(bbox)

    overlays: list[tuple[str, tuple[float, float, float, float], int]] = []
    for style, boxes in painted.items():
        clusters: list[list[tuple[float, float, float, float]]] = []
        for bbox in boxes:
            cluster = next((c for c in clusters
                            if max(abs(a - b) for a, b in zip(c[0], bbox)) <= .25), None)
            (cluster if cluster is not None else clusters.append([bbox]))
            if cluster is not None:
                cluster.append(bbox)
        overlays.extend((style[0], cluster[0], len(cluster) - 1)
                        for cluster in clusters if len(cluster) > 1)
    if not overlays:
        return raw, 0

    cleaned: list[tuple] = []
    removed = 0
    rendered_stack_seen: set[int] = set()
    for item in raw:
        values = list(item)
        x0, y0, x1, y1, text = values[:5]
        drop_item = False
        for overlay_no, (duplicate, bbox, copies) in enumerate(overlays):
            sx0, sy0, sx1, sy1 = bbox
            if not (x0 - .01 <= sx0 and y0 - .01 <= sy0
                    and x1 + .01 >= sx1 and y1 + .01 >= sy1):
                continue
            for _ in range(copies):
                first = text.find(duplicate)
                second = text.find(duplicate, first + len(duplicate)) if first >= 0 else -1
                if second < 0:
                    break
                text = text[:second] + text[second + len(duplicate):]
                removed += 1
            # With sub-point faux-bold offsets PyMuPDF emits separate blocks,
            # not repeated text inside one block. Keep the first rendered stack.
            if text.strip() == duplicate.strip() and max(
                    abs(a - b) for a, b in zip((x0, y0, x1, y1), bbox)) <= .5:
                if overlay_no in rendered_stack_seen:
                    drop_item = True
                    removed += 1
                else:
                    rendered_stack_seen.add(overlay_no)
        values[4] = text
        if not drop_item:
            cleaned.append(tuple(values))
    # A faux-bold PDF may expose each paint as its own block even when span
    # metadata is fragmented differently. Exact block text at sub-point-equal
    # geometry is still one rendered glyph stack; no ordinary repeated legal
    # text can occupy the same pixels as a distinct semantic occurrence.
    deduped: list[tuple] = []
    for item in cleaned:
        bbox = tuple(float(v) for v in item[:4])
        text = str(item[4]).strip()
        duplicate = any(
            text == str(prior[4]).strip()
            and max(abs(a - b) for a, b in zip(bbox, prior[:4])) <= .25
            for prior in deduped
        )
        if duplicate:
            removed += 1
        else:
            deduped.append(item)
    return deduped, removed


def _script_of(text: str) -> str | None:
    """Label the block's script so bidi handling downstream has something to read.

    Urdu and Sindhi publications are separate official expressions (§4.1), and
    the client applies isolates per run rather than per document, so the label
    belongs on the block.
    """
    has_ar = bool(_ARABIC.search(text))
    has_la = bool(_LATIN.search(text))
    if has_ar and has_la:
        return "mixed"
    if has_ar:
        return "arabic"
    if has_la:
        return "latin"
    return None


def _is_junk(ch: str) -> bool:
    if ch in _ALLOWED_CONTROLS:
        return False
    if ch == _REPLACEMENT:
        return True
    return unicodedata.category(ch) in _JUNK_CATEGORIES


def _printable_ratio(text: str) -> float:
    if not text:
        return 1.0
    return 1.0 - (sum(1 for c in text if _is_junk(c)) / len(text))


def _page_lane(text: str) -> str:
    """Per-page routing, which is the whole point of §4 doing it per page.

    A page with a usable text layer is E2. A page with none is E4 -- it needs
    rendering and OCR -- and marking it here is what lets that pass find exactly
    which pages to redo, instead of re-rendering an entire Act.
    """
    return "E2" if text.strip() else "E4"


def _text_signature(text: str) -> str:
    """Comparable page-text signature without weakening stored evidence."""
    compact = re.sub(r"\s+", " ", text).strip().casefold()
    # Running page numbers do not make an otherwise repeated scanner overlay
    # into substantive page text.  This is used only for routing, never storage.
    return re.sub(r"\d+", "#", compact)


def _is_repeated_sparse_overlay(page_texts: list[str]) -> bool:
    """Return true when a tiny repeated overlay is masquerading as a text layer."""
    if len(page_texts) < SPARSE_OVERLAY_MIN_PAGES:
        return False
    nonempty = [text for text in page_texts if text.strip()]
    if len(nonempty) < SPARSE_OVERLAY_MIN_PAGES:
        return False
    lengths = [len(re.sub(r"\s+", "", text)) for text in nonempty]
    if (median(lengths) > SPARSE_OVERLAY_MAX_MEDIAN_CHARS
            or sum(lengths) / len(lengths) > SPARSE_OVERLAY_MAX_MEAN_CHARS):
        return False
    signatures = [_text_signature(text) for text in nonempty]
    dominant = Counter(signatures).most_common(1)[0][1]
    return dominant / len(page_texts) >= SPARSE_OVERLAY_DOMINANCE


def extract_pdf(
    data: bytes,
    sha256: str,
    *,
    language: str = "en",
    publication_role: str = "code_portal",
) -> ExtractedDocument:
    """Extract one born-digital PDF into blocks with coordinates.

    Raises ExtractionRejected when the result does not meet §4 acceptance, so a
    bad extraction never reaches the database.
    """
    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        if doc.page_count == 0:
            raise ExtractionRejected(f"{sha256[:12]}: no pages")
        if doc.is_encrypted and not doc.authenticate(""):
            raise ExtractionRejected(f"{sha256[:12]}: encrypted, cannot extract")

        pages: list[ExtractedPage] = []
        blocks: list[ExtractedBlock] = []
        reading_order = 0
        total_chars = 0
        printable_chars = 0.0
        empty_pages = 0
        exact_overlay_spans_removed = 0
        page_texts: list[str] = []

        for index in range(doc.page_count):
            page = doc[index]
            page_no = index + 1

            # Preserve every text paint operation in the PDF media box.  The
            # default TEXT_MEDIABOX_CLIP flag (64) silently drops a whole span
            # when even part of it falls outside the box; measured failures went
            # from 0.26560 to 1.00000 recall by using only the non-destructive
            # ligature/whitespace flags (1|2).  Malformed portal crop boxes also
            # cut through body pages, so extraction temporarily opens the full
            # media box and records whether each resulting block was visible in
            # the publisher-declared crop box.
            original_crop = pymupdf.Rect(page.cropbox)
            media_box = pymupdf.Rect(page.mediabox)
            if original_crop != media_box:
                page.set_cropbox(media_box)

            # sort=True asks PyMuPDF for blocks in reading order rather than in
            # the order the content stream happens to place them. Legal PDFs
            # frequently interleave headers and marginal notes.
            raw = page.get_text("blocks", sort=True, flags=3)
            raw, page_overlays = _remove_exact_overlay_spans(page, raw, flags=3)
            exact_overlay_spans_removed += page_overlays
            page_text_len = 0

            for block_no, item in enumerate(raw):
                x0, y0, x1, y1, text, _, block_type = item[:7]
                if block_type != 0:          # 1 = image block; no text to keep
                    continue
                if not text.strip():
                    continue
                # NFC only. §4.1 forbids destroying the page evidence, so this
                # is the one normalisation applied: it makes the same visible
                # character compare equal without changing what was printed.
                text = unicodedata.normalize("NFC", text)
                blocks.append(
                    ExtractedBlock(
                        page_no=page_no,
                        block_no=block_no,
                        reading_order=reading_order,
                        x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1),
                        text=text,
                        script=_script_of(text),
                        confidence=None,      # a text layer is not a guess
                        inside_cropbox=original_crop.contains(
                            pymupdf.Rect(float(x0), float(y0), float(x1), float(y1))
                        ),
                    )
                )
                reading_order += 1
                page_text_len += len(text)
                total_chars += len(text)
                printable_chars += _printable_ratio(text) * len(text)

            if page_text_len == 0:
                empty_pages += 1

            rect = page.rect
            page_text = page.get_text("text", flags=3)
            page_texts.append(page_text)
            pages.append(
                ExtractedPage(
                    page_no=page_no,
                    width=float(rect.width),
                    height=float(rect.height),
                    char_count=page_text_len,
                    lane=_page_lane(page_text),
                    crop_box=tuple(float(v) for v in original_crop),
                    media_box=tuple(float(v) for v in media_box),
                )
            )

        ratio = (printable_chars / total_chars) if total_chars else 0.0

        # A document with no text anywhere is a scan. That is lane E4's work and
        # there is nothing here to store.
        if total_chars == 0:
            raise ExtractionRejected(
                f"{sha256[:12]}: no text layer at all -- this is lane E4 (OCR), not E2"
            )
        if ratio < MIN_PRINTABLE_RATIO:
            raise ExtractionRejected(
                f"{sha256[:12]}: printable ratio {ratio:.4f} below {MIN_PRINTABLE_RATIO} "
                f"-- the text layer is damaged, not merely sparse"
            )
        if _is_repeated_sparse_overlay(page_texts):
            raise ExtractionRejected(
                f"{sha256[:12]}: repeated sparse text-layer overlay across "
                f"{doc.page_count} pages -- route the complete document to OCR"
            )

        # A document with *some* blank pages is lane E3, not a rejection. §4:
        # "E3 | Mixed PDF | E2 on good pages; render and OCR only failed pages",
        # accepted when "every page assigned a lane; page order preserved". A
        # three-page Act with one blank cover is still a statute; throwing it away
        # loses real law to keep a tidy rule.
        lane = "E3" if empty_pages else "E2"

        meta = {k: v for k, v in (doc.metadata or {}).items() if v}

        return ExtractedDocument(
            sha256=sha256,
            language=language,
            publication_role=publication_role,
            page_count=doc.page_count,
            char_count=total_chars,
            printable_ratio=round(ratio, 4),
            empty_pages=empty_pages,
            lane=lane,
            # Pinned in the row, not inferred later: doc 09a §7 wants the exact
            # producing version recorded so a re-extraction is a deliberate,
            # visible change rather than a silent one.
            extractor=f"pymupdf-{getattr(pymupdf, '__version__', 'unknown')}",
            extractor_config={"mode": "blocks", "sort": True,
                              "normalization": "NFC",
                              "text_flags": 3,
                              "clip_policy": "full-media-box",
                              "exact_overlay_policy": "same-span-geometry-style",
                              "exact_overlay_spans_removed": exact_overlay_spans_removed},
            pdf_metadata=meta,
            pages=pages,
            blocks=blocks,
        )
    finally:
        doc.close()
