"""Rule `reviewed_head_boundary` (D-089, doc 3243 p5): a page-read running head that is set aside still ENDS the
sentence before it, as the printed page header did.

Doc 3243 prints s.2's last definition at the foot of p4, ending in a colon ("... of the Institute:"), then p5's running
head ("5 / THE HANDS INSTITUTE ... ACT, 2023 / SINDH ACT NO. XXXIX OF 2023") and "CHAPTER-II / THE INSTITUTE". With the
head in the text the chapter opened. With the head set aside (D-085), `previous_content` skips to the colon,
`_continues_previous` reads the chapter line as a cross-reference, and Chapter II is swallowed into clause (xxiii).

Data-gated in every profile and fails closed: the named block must also be set aside. Pure: segment() over hand-made
blocks shaped like doc 3243 pp4-5."""
import pytest

from nizam.corpus.segment import segment

HEAD = "5 \n \nTHE HANDS INSTITUTE OF DEVELOPMENT STUDIES ACT, 2023 \n \nSINDH ACT NO. XXXIX OF 2023 \n"
BLOCKS = [
    {"id": 1, "page_no": 4, "y0": 100.0, "page_height": 842.0, "x0": 70.0, "x1": 520.0,
     "text": "2. In this Act, unless there is anything repugnant in the subject or context,-"},
    {"id": 2, "page_no": 4, "y0": 140.0, "page_height": 842.0, "x0": 90.0, "x1": 520.0,
     "text": "(i) “Institute” means the HANDS Institute of Development Studies;"},
    {"id": 3, "page_no": 4, "y0": 700.0, "page_height": 842.0, "x0": 90.0, "x1": 520.0,
     "text": "(ii) “Vice-Rector” means the Vice-Rector of the Institute:"},
    {"id": 4, "page_no": 5, "y0": 18.0, "page_height": 842.0, "x0": 150.0, "x1": 450.0, "text": HEAD},
    {"id": 5, "page_no": 5, "y0": 128.0, "page_height": 842.0, "x0": 200.0, "x1": 400.0,
     "text": " \nCHAPTER-II \nTHE INSTITUTE \n"},
    {"id": 6, "page_no": 5, "y0": 178.0, "page_height": 842.0, "x0": 70.0, "x1": 520.0,
     "text": "3. (1) There shall be established an Institute to be called the HANDS Institute."},
]


def _chapters(seg):
    return [n.label for n in seg.flatten() if n.kind == "chapter"]


def _all_text(seg):
    return " ".join(" ".join(getattr(n, "text_parts", None) or [n.text or ""]) for n in seg.flatten())


def test_head_in_the_text_opens_the_chapter_as_released():
    assert _chapters(segment(BLOCKS)) == ["II"]


def test_head_set_aside_alone_swallows_the_chapter():
    # the defect the rule exists for: the colon now ends p4, and the chapter line reads as a cross-reference
    seg = segment(BLOCKS, structural_overrides={"source_apparatus_blocks": [4]})
    assert _chapters(seg) == []


def test_reviewed_boundary_keeps_the_chapter_and_drops_the_head():
    seg = segment(BLOCKS, structural_overrides={"source_apparatus_blocks": [4], "source_head_boundary_blocks": [4]})
    assert _chapters(seg) == ["II"]
    sec3 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "3")
    assert sec3.parent.kind == "chapter" and sec3.parent.label == "II"
    assert "HANDS INSTITUTE OF DEVELOPMENT STUDIES ACT" not in _all_text(seg)


def test_a_boundary_block_that_is_not_set_aside_is_refused():
    with pytest.raises(ValueError, match="head boundary"):
        segment(BLOCKS, structural_overrides={"source_head_boundary_blocks": [4]})


def test_a_boundary_block_not_in_the_document_is_refused():
    with pytest.raises(ValueError, match="head boundary"):
        segment(BLOCKS, structural_overrides={"source_apparatus_blocks": [4, 99], "source_head_boundary_blocks": [99]})


def test_the_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import GENERIC_STRUCTURAL_KEYS, STRUCTURAL_KEYS
    key = "source_head_boundary_blocks"
    assert key in STRUCTURAL_KEYS and key in GENERIC_STRUCTURAL_KEYS and key in STRUCTURAL_PATCH_KEYS
    # one reading per page; the worker unions the pages' blocks
    merged = W.reviewed_structural_overrides([], [
        {"evidence": {"structural_overrides": {key: [4]}}},
        {"evidence": {"structural_overrides": {key: [9, 4]}}}])
    assert merged[key] == [4, 9]
    with pytest.raises(ValueError, match=key):
        W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: ["4"]}}}])
