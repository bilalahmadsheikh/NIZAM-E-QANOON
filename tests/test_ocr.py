"""Lane E4 tests, against a PDF built to have no text layer at all.

The fixture is made the way the real scans were made: lay out text, render it to
an image, and put only the image in the PDF. `extract_pdf` must refuse it and
`ocr_pdf` must read it -- which is the whole routing decision in doc 02 §4.
"""
from __future__ import annotations

import shutil

import pytest

pymupdf = pytest.importorskip("pymupdf")

from nizam.corpus.extract import extract_pdf
from nizam.corpus.ocr import ocr_pdf
from nizam.shared.corpus_types import ExtractionRejected

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract not installed"
)

STATUTE = [
    "THE ZIARAT VALLEY DEVELOPMENT AUTHORITY ACT",
    "AN ACT",
    "to provide for the establishment of an Authority",
    "1. Short title and commencement.",
    "2. In this Act, unless there is anything repugnant",
    "the expression shall have the following meaning",
]


@pytest.fixture(scope="module")
def scanned_pdf() -> bytes:
    """A PDF whose pages are images of text, with no text layer."""
    typed = pymupdf.open()
    page = typed.new_page(width=612, height=792)
    y = 100
    for line in STATUTE:
        page.insert_text((72, y), line, fontsize=14, fontname="helv")
        y += 40

    # Render to an image and rebuild the document from the image alone. This is
    # what makes it a scan rather than a PDF with text drawn on it.
    pix = page.get_pixmap(dpi=200)
    typed.close()

    scan = pymupdf.open()
    out = scan.new_page(width=612, height=792)
    out.insert_image(out.rect, pixmap=pix)
    data = scan.tobytes()
    scan.close()
    return data


def test_lane_e2_refuses_a_scan(scanned_pdf):
    """The routing decision: no text layer means this is not E2's document."""
    with pytest.raises(ExtractionRejected) as exc:
        extract_pdf(scanned_pdf, "0" * 64)
    assert "no text layer" in str(exc.value)


@pytest.fixture(scope="module")
def ocred(scanned_pdf):
    return ocr_pdf(scanned_pdf, "0" * 64)


def test_ocr_reads_the_statute_back(ocred):
    text = " ".join(b.text for b in ocred.blocks).upper()
    assert "ZIARAT" in text
    assert "AUTHORITY" in text
    assert "SHORT TITLE" in text


def test_ocr_is_labelled_as_ocr(ocred):
    """Nothing downstream may mistake OCR output for a clean text layer."""
    assert ocred.lane == "E4"
    assert {p.lane for p in ocred.pages} == {"E4"}
    assert ocred.extractor.startswith("tesseract-")
    assert ocred.pdf_metadata["ocr_language"] in {"eng", "urd"}


def test_every_block_carries_a_real_confidence(ocred):
    """Lane E2 stores None -- a text layer is not a guess. E4 must store a number."""
    assert ocred.blocks
    for b in ocred.blocks:
        assert b.confidence is not None
        assert 0.0 <= b.confidence <= 1.0
    assert ocred.printable_ratio > 0.5, "clean synthetic text should OCR well"


def test_coordinates_come_back_in_pdf_points(ocred):
    """Rendered at 300 DPI, stored in 72-dpi user space.

    A citation has to point at the same rectangle whichever lane read the page,
    so the render scale must be divided back out.
    """
    page = ocred.pages[0]
    for b in ocred.blocks:
        assert 0 <= b.x0 < b.x1 <= page.width + 1
        assert 0 <= b.y0 < b.y1 <= page.height + 1


def test_reading_order_is_dense_and_monotonic(ocred):
    orders = [b.reading_order for b in ocred.blocks]
    assert orders == sorted(orders)
    assert orders == list(range(len(orders)))


def test_a_skipped_page_leaves_no_gap_in_reading_order():
    """Discarding an unreadable page must roll the counter back with it.

    A page that yields almost nothing is dropped, but _blocks_from_tsv has
    already advanced the shared reading_order counter by then. Without rolling it
    back the numbering develops holes -- which is exactly what happened to two
    OCR documents before this was caught by the integrity audit.
    """
    import pymupdf
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 100), "1. Short title and commencement of this Act.")
    doc.new_page()                                   # blank: will be skipped
    p3 = doc.new_page()
    p3.insert_text((72, 100), "2. In this Act unless there is anything repugnant.")
    data = doc.tobytes()
    doc.close()

    result = ocr_pdf(data, "2" * 64)
    orders = [b.reading_order for b in result.blocks]
    assert orders == list(range(len(orders))), f"holes in reading order: {orders}"
    assert result.empty_pages >= 1
