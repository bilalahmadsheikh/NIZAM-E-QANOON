"""Agent K6's rule E `reviewed_digit_led_clause` (doc 4649 p2, s.6(1)(h), the Surya revision of 4556). Ported by builder
BZ (group 23, 17 Oct 2026) from claude/agK6/test_k6_rule_e_DRAFT.py; data-gated in every profile. Pure: segment()
over hand-made blocks."""
import pytest

from nizam.corpus.segment import segment

BLOCKS = [
    {"id": 1, "page_no": 1, "y0": 100.0, "page_height": 792.0, "x0": 70.0, "x1": 560.0,
     "text": "6. (1) The Board shall comprise of the following members:-"},
    {"id": 2, "page_no": 1, "y0": 140.0, "page_height": 792.0, "x0": 90.0, "x1": 560.0,
     "text": "(a) Chief Minister\nChairman\n(b) Secretary Health\nMember/Secretary\n"
             "(c) 3 Notables from the area to be nominated by Chairman (initially for 3 years)"},
    {"id": 3, "page_no": 1, "y0": 220.0, "page_height": 792.0, "x0": 70.0, "x1": 560.0,
     "text": "(2) No act of the Board shall be invalid merely on the ground of any vacancy."},
]


def _clauses(seg):
    return {n.label: n for n in seg.flatten() if n.kind == "clause"}


def test_digit_led_row_opens_its_own_clause():
    seg = segment(BLOCKS, structural_overrides={"source_digit_led_clause_labels": [{"block_id": 2, "label": "c"}]})
    cl = _clauses(seg)
    assert set(cl) == {"a", "b", "c"}
    assert (cl["c"].text or "").startswith("3 Notables from the area")
    assert "Notables" not in (cl["b"].text or "")
    assert cl["c"].parent is cl["a"].parent


def test_inert_without_the_key():
    cl = _clauses(segment(BLOCKS))
    assert "c" not in cl and "3 Notables" in (cl["b"].text or "")


def test_a_label_that_opens_no_digit_line_fails_closed():
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_digit_led_clause_labels": [{"block_id": 2, "label": "b"}]})


def test_a_missing_block_fails_closed():
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_digit_led_clause_labels": [{"block_id": 99, "label": "c"}]})


def test_malformed_entry_fails_closed():
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_digit_led_clause_labels": [{"block_id": 2, "label": "(c)"}]})


def test_the_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from nizam.corpus.segment import SEGMENTATION_PROFILES
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    key = "source_digit_led_clause_labels"
    assert key in STRUCTURAL_KEYS and key in STRUCTURAL_PATCH_KEYS
    assert not any("reviewed_digit_led_clause" in rules for rules in SEGMENTATION_PROFILES.values())
    merged = W.reviewed_structural_overrides([], [
        {"evidence": {"structural_overrides": {key: [{"block_id": 9, "label": "h"}]}}},
        {"evidence": {"structural_overrides": {key: [{"block_id": 2, "label": "c"}]}}}])
    assert [v["block_id"] for v in merged[key]] == [2, 9]
    for bad in ([{"block_id": 2, "label": "H"}], [{"block_id": "2", "label": "h"}], [{"block_id": 2}]):
        with pytest.raises(ValueError, match=key):
            W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: bad}}}])
