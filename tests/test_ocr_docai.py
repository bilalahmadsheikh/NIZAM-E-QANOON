"""Lane E4 with Document AI (D-114): the response mapping and the PDF splitter, without a network."""
from __future__ import annotations

import pymupdf
import pytest

from nizam.corpus.ocr_docai import DocAIClient, _segments_text, document_from_responses, split_pdf
from nizam.shared.corpus_types import ExtractionRejected


def _seg(start: int, end: int) -> dict:
    seg = {"endIndex": str(end)}
    if start:                       # proto3 JSON omits a zero startIndex
        seg["startIndex"] = str(start)
    return {"textSegments": [seg]}


def _layout(start, end, box, conf=0.95, normalized=True):
    if normalized:
        poly = {"normalizedVertices": [{"x": box[0], "y": box[1]}, {"x": box[2], "y": box[1]},
                                       {"x": box[2], "y": box[3]}, {"x": box[0], "y": box[3]}]}
    else:
        poly = {"vertices": [{"x": box[0], "y": box[1]}, {"x": box[2], "y": box[3]}]}
    return {"textAnchor": _seg(start, end), "confidence": conf, "boundingPoly": poly}


def _page(text: str, paras: list[tuple[str, tuple]], conf=0.9, normalized=True, dim=None, lang="en"):
    """A page whose paragraphs are found in `text`, with one token per word inside each paragraph box."""
    out_paras, tokens = [], []
    for para, box in paras:
        start = text.index(para)
        out_paras.append({"layout": _layout(start, start + len(para), box, normalized=normalized)})
        pos = start
        for word in para.split():
            ws = text.index(word, pos)
            pos = ws + len(word)
            tokens.append({"layout": _layout(ws, pos, box, conf=conf, normalized=normalized)})
    return {"dimension": dim or {"width": 1700, "height": 2200, "unit": "pixels"},
            "detectedLanguages": [{"languageCode": lang, "confidence": 0.99}],
            "paragraphs": out_paras, "tokens": tokens}


def test_text_anchor_reads_string_indices_and_a_missing_zero_start():
    assert _segments_text("1. Short title.\n", {"textAnchor": _seg(0, 3)}) == "1. "
    assert _segments_text("abcdef", {"textAnchor": {"textSegments": [{"startIndex": "2", "endIndex": "4"}]}}) == "cd"


def test_paragraphs_become_blocks_in_points_with_dense_reading_order_across_parts():
    t1 = "THE ACT\n1. Short title.-This Act may be called the Test Act.\n"
    p1 = _page(t1, [("THE ACT\n", (0.4, 0.05, 0.6, 0.08)),
                    ("1. Short title.-This Act may be called the Test Act.\n", (0.1, 0.1, 0.9, 0.2))])
    t2 = "2. Definitions.-In this Act, unless the context otherwise requires,\n"
    p2 = _page(t2, [(t2, (100, 200, 1600, 400))], normalized=False, conf=0.8)
    doc = document_from_responses([(612.0, 792.0), (612.0, 792.0)],
                                  [{"text": t1, "pages": [p1]}, {"text": t2, "pages": [p2]}],
                                  "ab" * 32, processor_version="pretrained-ocr-v2.0-2023-06-02")
    assert doc.lane == "E4" and doc.page_count == 2 and doc.empty_pages == 0
    assert [b.reading_order for b in doc.blocks] == [0, 1, 2]
    assert [b.page_no for b in doc.blocks] == [1, 1, 2]
    assert doc.blocks[0].text == "THE ACT"                     # trailing newline dropped
    b = doc.blocks[1]
    assert (round(b.x0, 1), round(b.y0, 1), round(b.x1, 1), round(b.y1, 1)) == (61.2, 79.2, 550.8, 158.4)
    c = doc.blocks[2]                                          # pixel vertices scaled by page.dimension
    assert (round(c.x0, 1), round(c.y0, 1)) == (round(100 / 1700 * 612, 1), round(200 / 2200 * 792, 1))
    assert c.confidence == 0.8 and b.confidence == 0.9
    words = 2 + 10 + 9
    assert doc.pdf_metadata["ocr_words"] == words
    assert doc.pdf_metadata["ocr_mean_confidence"] == round((12 * 0.9 + 9 * 0.8) / words, 4)
    assert doc.printable_ratio == doc.pdf_metadata["ocr_mean_confidence"]
    assert doc.extractor.startswith("google-documentai-ocr/pretrained-ocr-v2.0-2023-06-02+pymupdf-")
    assert doc.language == "en" and doc.pdf_metadata["needs_review"] is False


def test_an_unread_page_gives_back_its_reading_order_slots():
    t = "1. Short title.-This Act may be called the Test Act.\n"
    good = _page(t, [(t, (0.1, 0.1, 0.9, 0.2))])
    blank = {"dimension": {"width": 1700, "height": 2200}, "paragraphs": [], "tokens": []}
    doc = document_from_responses([(612, 792)] * 3, [{"text": t, "pages": [blank, good]}, {"text": "", "pages": [blank]}],
                                  "cd" * 32, processor_version="v")
    assert doc.empty_pages == 2
    assert [(b.page_no, b.reading_order) for b in doc.blocks] == [(2, 0)]


def test_urdu_pages_are_labelled_urdu():
    t = "قانون نافذ ہوگا\n"
    p = _page(t, [(t, (0.1, 0.1, 0.9, 0.2))], lang="ur")
    doc = document_from_responses([(612, 792)], [{"text": t, "pages": [p]}], "ef" * 32, processor_version="v")
    assert doc.language == "ur" and doc.blocks[0].script == "arabic"


def test_low_confidence_is_flagged_for_review_and_page_count_mismatch_is_refused():
    t = "1. Short title.-This Act may be called the Test Act.\n"
    p = _page(t, [(t, (0.1, 0.1, 0.9, 0.2))], conf=0.5)
    doc = document_from_responses([(612, 792)], [{"text": t, "pages": [p]}], "01" * 32, processor_version="v")
    assert doc.pdf_metadata["needs_review"] is True
    with pytest.raises(ExtractionRejected):
        document_from_responses([(612, 792)] * 2, [{"text": t, "pages": [p]}], "01" * 32, processor_version="v")
    with pytest.raises(ExtractionRejected):
        document_from_responses([(612, 792)], [{"text": "", "pages": [{"paragraphs": [], "tokens": []}]}],
                                "01" * 32, processor_version="v")


def test_split_pdf_cuts_fifteen_page_parts_and_keeps_the_original_rectangles():
    src = pymupdf.open()
    for i in range(32):
        page = src.new_page(width=612 if i % 2 else 595, height=792 if i % 2 else 842)
        page.insert_text((72, 72), f"page {i + 1}")
    rects, parts = split_pdf(src.tobytes())
    assert len(rects) == 32 and rects[0] == (595.0, 842.0) and rects[1] == (612.0, 792.0)
    counts = [pymupdf.open(stream=p, filetype="pdf").page_count for p in parts]
    assert counts == [15, 15, 2]
    assert pymupdf.open(stream=parts[2], filetype="pdf")[1].get_text().strip() == "page 32"


def test_split_pdf_halves_a_part_over_the_byte_limit():
    src = pymupdf.open()
    for i in range(4):
        src.new_page().insert_text((72, 72), f"page {i + 1} " + "x" * 200)
    data = src.tobytes()
    whole = len(split_pdf(data, pages_per_part=4)[1][0])
    rects, parts = split_pdf(data, pages_per_part=4, max_bytes=whole - 1)
    assert sum(pymupdf.open(stream=p, filetype="pdf").page_count for p in parts) == 4 and len(parts) >= 2


def test_client_reads_a_stored_part_without_a_network(tmp_path):
    client = DocAIClient(processor="projects/1/locations/us/processors/abc", cache_dir=tmp_path)
    client._version = "v1"
    t = "1. Short title.-This Act may be called the Test Act.\n"
    stored = {"text": t, "pages": [_page(t, [(t, (0.1, 0.1, 0.9, 0.2))])]}
    import gzip, json
    path = tmp_path / "v1" / ("aa" * 32) / "0000.json.gz"
    path.parent.mkdir(parents=True)
    path.write_bytes(gzip.compress(json.dumps(stored).encode()))
    src = pymupdf.open(); src.new_page().insert_text((72, 72), "x")
    doc = client.ocr_pdf(src.tobytes(), "aa" * 32)        # no session is ever created
    assert client._session is None and doc.blocks[0].text.startswith("1. Short title")
    assert client.endpoint == "https://us-documentai.googleapis.com/v1/projects/1/locations/us/processors/abc"
    with pytest.raises(ValueError):
        DocAIClient(processor="not/a/processor", cache_dir=tmp_path)
