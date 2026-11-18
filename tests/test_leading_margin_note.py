"""Rule `reviewed_leading_margin_note` (D-080, doc 1336 p4): a page-read margin note the text layer set at the HEAD of
a law block leaves the text and becomes the marginal note of the section it is printed beside. Data-gated in every
profile; fails closed. Pure: segment() over hand-made blocks shaped like doc 1336's s.8."""
import pytest

from nizam.corpus.segment import segment

NOTE = 'Acquisition of right in or guardianship of a protected heritage of the government.'
BLOCKS = [
    {"id": 1, "page_no": 1, "y0": 100.0, "page_height": 792.0, "x0": 70.0, "x1": 460.0,
     "text": "7. Government may declare any premises to be protected heritage."},
    {"id": 2, "page_no": 1, "y0": 140.0, "page_height": 792.0, "x0": 70.0, "x1": 460.0,
     "text": "8. (1) The Committee with the sanction of the Government, may purchase any protected heritage."},
    # the margin note and the next sub-section's words in one block, as doc 1336's text layer gives them
    {"id": 3, "page_no": 1, "y0": 180.0, "page_height": 792.0, "x0": 67.0, "x1": 572.0,
     "text": "Acquisition of right in \nor guardianship of a \nprotected \nheritage \nof the government. \n \n"
             "      (2)  The Committee, may accept the gift or bequest of any \nprotected heritage. \n"},
    {"id": 4, "page_no": 1, "y0": 240.0, "page_height": 792.0, "x0": 70.0, "x1": 460.0,
     "text": "9. Government may make rules."},
]
SPEC = [{"block_id": 3, "note": NOTE, "label": "8"}]


def _flat(seg):
    return {(n.kind, n.label, n.parent.label if n.parent else None): n for n in seg.flatten()}


def _text(seg, label):
    s = next(n for n in seg.flatten() if n.kind == "section" and n.label == label)
    out, stack = [], [s]
    while stack:
        n = stack.pop()
        out.append(" ".join(n.text_parts) if getattr(n, "text_parts", None) else (n.text or ""))
        stack.extend(n.children)
    return " ".join(out)


def test_the_note_leaves_the_text_and_marks_its_section():
    seg = segment(BLOCKS, structural_overrides={"source_leading_margin_notes": SPEC})
    s8 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "8")
    assert s8.marginal_note == NOTE
    assert "guardianship" not in _text(seg, "8")
    assert "may accept the gift" in _text(seg, "8")       # the law words that shared the block stay, in s.8(2)
    assert [c.label for c in s8.children] == ["1", "2"]


def test_inert_without_the_key():
    seg = segment(BLOCKS)
    assert "guardianship" in _text(seg, "8")


def test_a_note_that_does_not_open_the_block_fails_closed():
    with pytest.raises(ValueError, match="does not open block"):
        segment(BLOCKS, structural_overrides={"source_leading_margin_notes": [
            {"block_id": 3, "note": "may accept the gift", "label": "8"}]})


def test_a_note_with_no_law_text_after_it_fails_closed():
    with pytest.raises(ValueError, match="does not open block"):
        segment(BLOCKS, structural_overrides={"source_leading_margin_notes": [
            {"block_id": 4, "note": "9. Government may make rules.", "label": "9"}]})


def test_an_owner_that_does_not_hold_the_block_fails_closed():
    with pytest.raises(ValueError, match="no owner section"):
        segment(BLOCKS, structural_overrides={"source_leading_margin_notes": [dict(SPEC[0], label="9")]})


def test_malformed_entry_fails_closed():
    with pytest.raises(ValueError, match="malformed"):
        segment(BLOCKS, structural_overrides={"source_leading_margin_notes": [{"block_id": 3, "note": NOTE}]})


def test_the_lifted_note_is_evidence_for_a_printed_heading():
    decision = {"export": ".artifacts/x.json", "document_id": 1336, "question_id": "q2"}
    seg = segment(BLOCKS, structural_overrides={
        "source_leading_margin_notes": SPEC,
        "source_printed_headings": [{"label": "8", "source_block_id": 3, "heading": NOTE, "use": "heading",
                                     "owner_decision": decision}]})
    s8 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "8")
    assert s8.heading == NOTE


# doc 4986 s.20: 'Restriction on' sits at the head of the law block at the foot of p10; 'use of protected / immovable /
# antiquity.' is a margin block at the top of p11
CROSS = [
    {"id": 11, "page_no": 10, "y0": 600.0, "page_height": 792.0, "x0": 159.0, "x1": 556.0,
     "text": "19. A place of worship shall not be used for any purpose inconsistent with its character."},
    {"id": 12, "page_no": 10, "y0": 700.0, "page_height": 792.0, "x0": 59.0, "x1": 556.0,
     "text": "Restriction on \n20. \nA protected immovable antiquity shall not be used for any purpose \ninconsistent "
             "with its character. \n"},
    {"id": 13, "page_no": 11, "y0": 72.0, "page_height": 792.0, "x0": 59.0, "x1": 143.0,
     "text": "use of protected \nimmovable \nantiquity. \n"},
    {"id": 14, "page_no": 11, "y0": 140.0, "page_height": 792.0, "x0": 159.0, "x1": 556.0,
     "text": "21. No person shall destroy any antiquity."},
]
CROSS_SPEC = {
    "source_leading_margin_notes": [{"block_id": 12, "note": "Restriction on", "label": "20"}],
    "source_apparatus_blocks": [13],
    "source_margin_note_pieces": [{"label": "20", "target_block_id": 12, "source_block_ids": [12, 13],
                                   "heading": "Restriction on use of protected immovable antiquity."}],
}


def test_a_note_across_a_page_break_heads_its_section_from_a_lifted_piece_and_a_margin_block():
    seg = segment(CROSS, structural_overrides=CROSS_SPEC)
    s20 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "20")
    assert s20.heading == "Restriction on use of protected immovable antiquity."
    assert not s20.marginal_note                  # the lifted words are a piece of the heading, not a second note
    text = " ".join(" ".join(n.text_parts) for n in [s20, *s20.children])
    assert "Restriction" not in text and "use of protected immovable antiquity." not in text


def test_pieces_two_pages_on_still_fail_closed():
    far = [dict(b, page_no=12) if b["id"] == 13 else b for b in CROSS]
    with pytest.raises(ValueError, match="margin note pieces"):
        segment(far, structural_overrides=CROSS_SPEC)


def test_a_one_word_note_followed_by_the_law_on_its_line():
    blocks = [{"id": 1, "page_no": 1, "y0": 100.0, "page_height": 792.0, "x0": 70.0, "x1": 560.0,
               "text": "1. This Act may be called the Test Act."},
              {"id": 2, "page_no": 1, "y0": 140.0, "page_height": 792.0, "x0": 114.0, "x1": 537.0,
               "text": "Definitions. 2. In this Act, unless there is anything repugnant in the subject or context,"}]
    seg = segment(blocks, structural_overrides={"source_leading_margin_notes": [
        {"block_id": 2, "note": "Definitions.", "label": "2"}]})
    s2 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "2")
    assert s2.marginal_note == "Definitions." and "Definitions" not in " ".join(s2.text_parts)


def test_the_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    assert "source_leading_margin_notes" in STRUCTURAL_KEYS and "source_leading_margin_notes" in STRUCTURAL_PATCH_KEYS
    merged = W.reviewed_structural_overrides([], [
        {"evidence": {"structural_overrides": {"source_leading_margin_notes": SPEC}}}])
    assert merged["source_leading_margin_notes"] == SPEC
    with pytest.raises(ValueError, match="source_leading_margin_notes"):
        W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {
            "source_leading_margin_notes": [{"block_id": 3, "note": "x", "label": "8"}]}}}])
