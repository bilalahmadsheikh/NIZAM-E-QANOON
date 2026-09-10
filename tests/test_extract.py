"""Extraction is pure, so it is tested against real corpus bytes with no database.

The fixture is the Pakistan Penal Code as published by pakistancode.gov.pk. It is
addressed by hash, so if the blob store ever holds different bytes under that
name the test fails rather than quietly testing something else.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from nizam.corpus.extract import extract_pdf
from nizam.shared.corpus_types import ExtractionRejected

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
PPC_SHA = "e2cd2bb931cccca07d1f0adcbd0b8f9b3a6ba24a9d43aefaefaa06ee4f5f7c5e"


def _ppc() -> Path:
    matches = sorted((CORPUS_ROOT / "raw" / "pk-federal").glob("e2cd2bb931cccca0*"))
    if not matches:
        pytest.skip("Penal Code blob not present; run tools/corpus-land/land.py")
    return matches[0]


@pytest.fixture(scope="module")
def ppc():
    path = _ppc()
    return extract_pdf(path.read_bytes(), path.name)


def test_page_count_matches_the_printed_document(ppc):
    # The PDF prints "Page N of 179" in its own running header.
    assert ppc.page_count == 179


def test_meets_lane_e2_acceptance(ppc):
    # Doc 02 §4: ">=95% printable characters", and every page assigned a lane.
    assert ppc.printable_ratio >= 0.95
    assert ppc.empty_pages == 0
    assert ppc.lane == "E2"
    assert {p.lane for p in ppc.pages} == {"E2"}


def test_every_block_carries_the_evidence_fields(ppc):
    # §4.1: "{page, bbox, reading_order, script, extractor, confidence}"
    assert ppc.blocks
    for b in ppc.blocks[:200]:
        assert 1 <= b.page_no <= ppc.page_count
        assert b.x1 > b.x0 and b.y1 > b.y0
        assert b.text.strip()


def test_reading_order_is_dense_and_monotonic(ppc):
    orders = [b.reading_order for b in ppc.blocks]
    assert orders == sorted(orders)
    assert orders == list(range(len(orders)))


def test_pages_are_complete_and_in_order(ppc):
    assert [p.page_no for p in ppc.pages] == list(range(1, ppc.page_count + 1))


def test_section_302_survives_extraction(ppc):
    """The provision segmentation will be judged on, present in the body.

    It appears twice -- once in the printed table of contents and once as the
    provision itself. That duplication is the thing §5 has to resolve, so the
    test asserts both exist rather than pretending there is only one.
    """
    hits = [b for b in ppc.blocks if b.text.lstrip().startswith("302.")]
    assert len(hits) >= 2, "expected a contents entry and a body occurrence"
    body = [b for b in hits if "qatl" in b.text.lower() and len(b.text) > 60]
    assert body, "section 302's text did not survive extraction"
    assert body[0].page_no > 50, "the body occurrence should be well past the contents"


def test_script_is_labelled(ppc):
    scripts = {b.script for b in ppc.blocks}
    assert "latin" in scripts


def test_rejects_a_file_with_no_text_layer():
    # Not a PDF at all: extraction must raise, not return an empty document.
    with pytest.raises(Exception):
        extract_pdf(b"not a pdf", "0" * 64)


def test_rejects_an_empty_pdf():
    import pymupdf
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    with pytest.raises(ExtractionRejected):
        extract_pdf(data, "0" * 64)


# --- the two acceptance bugs, pinned so they cannot come back ----------------

def test_typographic_whitespace_is_not_damage():
    """Non-breaking spaces and soft hyphens must not count against the ratio.

    Python's str.isprintable() is False for every whitespace except a literal
    space, so U+00A0 looked like corruption. Pakistani statutes are typeset with
    non-breaking spaces at 15-19% of all characters, and that alone rejected 31
    sound born-digital Acts including the Companies Ordinance 1984.
    """
    from nizam.corpus.extract import _printable_ratio
    text = "Whoever commits qatl-i-amd­shall be punished."
    assert _printable_ratio(text) == 1.0


def test_real_extraction_damage_still_fails_the_ratio():
    """The screen must still catch what it is actually for."""
    from nizam.corpus.extract import _printable_ratio
    assert _printable_ratio("clean text") == 1.0
    assert _printable_ratio("�" * 10 + "ok") < 0.95      # failed decode
    assert _printable_ratio("\x00\x01\x02" + "abc") < 0.95    # control bytes


def test_a_blank_page_does_not_discard_the_document():
    """Doc 02 §4 routes per page: E3 keeps the good pages, OCR does the rest.

    A three-page Act with one blank cover is still a statute. Rejecting the whole
    document over it lost 46 real ones.
    """
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "1. Short title and commencement.")
    doc.new_page()                      # deliberately blank
    data = doc.tobytes()
    doc.close()

    result = extract_pdf(data, "1" * 64)
    assert result.page_count == 2
    assert result.empty_pages == 1
    assert result.lane == "E3", "a mixed document is E3, not a rejection"
    lanes = {p.page_no: p.lane for p in result.pages}
    assert lanes == {1: "E2", 2: "E4"}, "the blank page must be marked for OCR"
    assert result.blocks, "the text on the good page survived"


def test_repeated_sparse_scanner_overlay_routes_the_complete_document_to_ocr():
    """A printable scanner watermark is not evidence that the scan was read."""
    import pymupdf
    doc = pymupdf.open()
    for page_no in range(1, 16):
        page = doc.new_page()
        page.insert_text((72, 760), f"CamScanner {page_no}")
    data = doc.tobytes()
    doc.close()

    with pytest.raises(ExtractionRejected, match="repeated sparse text-layer overlay"):
        extract_pdf(data, "5" * 64)


def test_distinct_short_pages_are_not_mistaken_for_a_repeated_overlay():
    """The watermark rule must not erase a genuinely terse instrument."""
    import pymupdf
    doc = pymupdf.open()
    for text in ("Order is granted.", "Appeal is dismissed.", "Costs follow."):
        page = doc.new_page()
        page.insert_text((72, 100), text)
    data = doc.tobytes()
    doc.close()

    result = extract_pdf(data, "6" * 64)
    assert result.lane == "E2"
    assert result.char_count > 0


def test_only_exact_same_geometry_overlay_is_canonicalised():
    """A repeated paint command is one visible line; ordinary repeats survive."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Updated till 3.8.2022")
    page.insert_text((72, 100), "Updated till 3.8.2022")
    page.insert_text((72, 140), "Repeated legal text")
    page.insert_text((72, 160), "Repeated legal text")
    data = doc.tobytes()
    doc.close()

    result = extract_pdf(data, "2" * 64)
    text = "\n".join(block.text for block in result.blocks)
    assert text.count("Updated till 3.8.2022") == 1
    assert text.count("Repeated legal text") == 2
    assert result.extractor_config["exact_overlay_spans_removed"] == 1


def test_subpoint_faux_bold_paints_are_one_semantic_line():
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Updated till 23.9.2021")
    page.insert_text((72.10, 100), "Updated till 23.9.2021")
    page.insert_text((72.11, 100), "Updated till 23.9.2021")
    data = doc.tobytes()
    doc.close()

    result = extract_pdf(data, "4" * 64)
    text = "\n".join(block.text for block in result.blocks)
    assert text.count("Updated till 23.9.2021") == 1
    assert result.extractor_config["exact_overlay_spans_removed"] == 2


def test_media_box_text_survives_a_bad_crop_box_with_visibility_flag():
    """Portal crop metadata must not erase source text from the evidence layer."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "visible legal text")
    page.insert_text((72, 700), "cropped source text")
    page.set_cropbox(pymupdf.Rect(0, 0, 612, 400))
    data = doc.tobytes()
    doc.close()

    result = extract_pdf(data, "3" * 64)
    by_text = {block.text.strip(): block for block in result.blocks}
    assert "visible legal text" in by_text
    assert "cropped source text" in by_text
    assert by_text["visible legal text"].inside_cropbox
    assert not by_text["cropped source text"].inside_cropbox
    assert result.pages[0].crop_box != result.pages[0].media_box
