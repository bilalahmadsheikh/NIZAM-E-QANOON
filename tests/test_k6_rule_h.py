"""Agent K6's rule H `reviewed_inline_margin_note` (doc 4529 SKAA Low-Cost Housing Scheme Regulations 2008: the anchor
variant; doc 4558 Balochistan Plastic Bags Act: the label variant). Ported by builder BZ (group 28, 17 Oct 2026) from
claude/agK6/test_k6_rule_h_DRAFT.py (78daf6cb). Pure: segment() over hand-made blocks, profile unreleased-v4."""
import pytest

from nizam.corpus.segment import segment


def _b(i, text, y=100.0, page=1, x0=50.0, x1=450.0):
    return {"id": i, "page_no": page, "y0": y, "page_height": 842.0, "x0": x0, "x1": x1, "text": text}


BLOCKS = [
    _b(1, '1. (1) These regulations may be called the "Test Regulations 2008." Short title and commencement.\n'
          "(2) They shall come into force at once.\n"
          "3. In these regulations, unless there is anything repugnant in the subject or context; Definition.\n"
          'i. "Authority" means the Test Authority;', 100),
    _b(2, "4. The Director General may delegate any of his powers under these regulations.\nDelegation of powers.\n"
          "5. Funds may be raised in the following ways:\nFund for the Scheme.\ni. By donation.", 300),
    _b(3, "6. The Authority shall exercise such powers as may be necessary.", 500),
    _b(4, "Powers of the Authority.", 500, x0=460.0, x1=540.0),
]
NOTES = [
    {"block_id": 1, "anchor": 'Test Regulations 2008."', "note": "Short title and commencement."},
    {"block_id": 1, "anchor": "repugnant in the subject or context;", "note": "Definition."},
    {"block_id": 2, "anchor": "any of his powers under these regulations.", "note": "Delegation of powers."},
    {"block_id": 2, "anchor": "in the following ways:", "note": "Fund for the Scheme."},
    {"block_id": 4, "anchor": "The Authority shall exercise such powers", "note": "Powers of the Authority."},
]


def _sections(seg):
    return {n.label: n for n in seg.flatten() if n.kind == "section"}


def _text(n):
    return " ".join(n.text_parts) + " " + " ".join(_text(c) for c in n.children)


def test_h_notes_leave_the_text_and_become_marginal_notes():
    seg = segment(BLOCKS, profile="unreleased-v4",
                  structural_overrides={"source_inline_margin_notes": NOTES, "source_apparatus_blocks": [4]})
    s = _sections(seg)
    assert s["1"].marginal_note == "Short title and commencement."
    assert s["3"].marginal_note == "Definition."
    assert s["4"].marginal_note == "Delegation of powers."
    assert s["5"].marginal_note == "Fund for the Scheme."
    assert s["6"].marginal_note == "Powers of the Authority."
    for label in ("1", "3", "4", "5", "6"):
        assert s[label].marginal_note not in _text(s[label])


def test_h_inert_without_the_key():
    s = _sections(segment(BLOCKS, profile="unreleased-v4"))
    assert "Delegation of powers." in _text(s["4"])
    assert not s["4"].marginal_note


def test_h_an_anchor_that_does_not_match_fails_closed():
    bad = [dict(NOTES[2], anchor="no such words in the block")]
    with pytest.raises(ValueError):
        segment(BLOCKS, profile="unreleased-v4", structural_overrides={"source_inline_margin_notes": bad})


def test_h_a_note_block_must_be_apparatus():
    with pytest.raises(ValueError):
        segment(BLOCKS, profile="unreleased-v4", structural_overrides={"source_inline_margin_notes": [NOTES[4]]})


HEADED = [
    _b(11, 'Short title and Commencement. 1. (1) This Act may be called the Test Act 2023.\n'
           "(2) It shall come into force at once.\nDefinitions. 2. In this Act, unless the context otherwise requires,"
           " the Act means this Act.", 100),
    _b(12, "Retrieval and Recycling.\n15.\nThe Department shall collect the waste.\nRemoval of Difficulties\n16.\n"
           "If any difficulty arises the Government may issue directions.", 300),
]
HEADS = [
    {"block_id": 11, "label": "1", "note": "Short title and Commencement."},
    {"block_id": 11, "label": "2", "note": "Definitions."},
    {"block_id": 12, "label": "15", "note": "Retrieval and Recycling."},
    {"block_id": 12, "label": "16", "note": "Removal of Difficulties"},
]


def test_h_label_variant_heading_before_the_number():
    s = _sections(segment(HEADED, profile="unreleased-v4", structural_overrides={"source_inline_margin_notes": HEADS}))
    assert s["1"].heading == "Short title and Commencement."
    assert s["2"].heading == "Definitions."
    assert s["15"].heading == "Retrieval and Recycling."
    assert s["16"].heading == "Removal of Difficulties"
    assert "Definitions." not in _text(s["1"])
    assert "Removal of Difficulties" not in _text(s["15"])


def test_h_label_variant_fails_closed_on_a_wrong_label():
    with pytest.raises(ValueError):
        segment(HEADED, profile="unreleased-v4",
                structural_overrides={"source_inline_margin_notes": [dict(HEADS[0], label="7")]})


def test_h_needs_the_profile_rule():
    with pytest.raises(ValueError):
        segment(BLOCKS, profile="default", structural_overrides={"source_inline_margin_notes": NOTES[:1]})


def test_the_key_and_profile_are_wired():
    import nizam.workers.segment as W
    from nizam.corpus.segment import SEGMENTATION_PROFILES
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    key = "source_inline_margin_notes"
    assert key in STRUCTURAL_KEYS and key in STRUCTURAL_PATCH_KEYS
    assert "reviewed_inline_margin_note" in SEGMENTATION_PROFILES["unreleased-v4"]
    assert "reviewed_inline_margin_note" not in SEGMENTATION_PROFILES["default"]
    a = {"block_id": 3, "anchor": "Regulations 2008.\"", "note": "Short title, and commencement."}
    b = {"block_id": 3, "label": "15", "note": "Retrieval and Recycling."}
    merged = W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: [a]}}},
                                                  {"evidence": {"structural_overrides": {key: [b, a]}}}])
    assert sorted(v["note"] for v in merged[key]) == sorted([a["note"], b["note"]])
    for bad in ([dict(a, anchor="short")], [dict(b, label="x5")], [{"block_id": 3, "note": "Retrieval and Recycling."}]):
        with pytest.raises(ValueError, match=key):
            W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: bad}}}])
