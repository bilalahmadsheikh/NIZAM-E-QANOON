"""Agent K6's rule D `reviewed_fused_margin_tail` (doc 4645, the Surya revision of 4364, Sind Local Government Ordinance
1979). Ported by builder BZ (group 22, 16 Oct 2026) from claude/agK6/test_k6_rule_d_DRAFT.py; data-gated in every profile.
Pure: segment() over hand-made blocks."""
import pytest

from nizam.corpus.segment import segment

BLOCKS = [
    {"id": 1, "page_no": 1, "y0": 100.0, "page_height": 792.0, "x0": 70.0, "x1": 560.0,
     "text": "1. (1) This Ordinance may be called the Test Ordinance, 1979. Short title and commencement."},
    {"id": 2, "page_no": 1, "y0": 140.0, "page_height": 792.0, "x0": 140.0, "x1": 460.0,
     "text": "(2) It shall come into force at once."},
    {"id": 3, "page_no": 1, "y0": 180.0, "page_height": 792.0, "x0": 70.0, "x1": 560.0,
     "text": "2. Government may make rules for carrying out the purposes of this Ordinance. Rules."},
]


def _flat(seg):
    return {(n.kind, n.label): n for n in seg.flatten()}


def test_tail_becomes_marginal_note_and_leaves_the_text():
    tails = [{"block_id": 1, "tail": "Short title and commencement."}, {"block_id": 3, "tail": "Rules."}]
    seg = segment(BLOCKS, structural_overrides={"source_fused_margin_tails": tails})
    nodes = _flat(seg)
    s1, s2 = nodes[("section", "1")], nodes[("section", "2")]
    assert s1.marginal_note == "Short title and commencement."
    assert "Short title" not in " ".join(n.text or "" for n in seg.flatten() if n is s1 or n.parent is s1)
    assert s2.marginal_note == "Rules."
    assert (s2.text or "").rstrip().endswith("Ordinance.")


def test_inert_without_the_key():
    seg = segment(BLOCKS)
    assert "Short title and commencement." in " ".join(n.text or "" for n in seg.flatten())


def test_a_tail_that_does_not_end_a_line_fails_closed():
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_fused_margin_tails": [{"block_id": 1, "tail": "Test Ordinance"}]})


def test_a_missing_block_fails_closed():
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_fused_margin_tails": [{"block_id": 99, "tail": "Rules."}]})


def test_malformed_entry_fails_closed():
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_fused_margin_tails": [{"block_id": 3}]})


def test_the_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    from nizam.corpus.segment import SEGMENTATION_PROFILES
    assert "source_fused_margin_tails" in STRUCTURAL_KEYS and "source_fused_margin_tails" in STRUCTURAL_PATCH_KEYS
    assert not any("reviewed_fused_margin_tail" in rules for rules in SEGMENTATION_PROFILES.values())
    merged = W.reviewed_structural_overrides([], [
        {"evidence": {"structural_overrides": {"source_fused_margin_tails": [{"block_id": 3, "tail": "Rules."}]}}},
        {"evidence": {"structural_overrides": {"source_fused_margin_tails": [{"block_id": 1, "tail": "Short title."}]}}}])
    assert [t["block_id"] for t in merged["source_fused_margin_tails"]] == [1, 3]
    with pytest.raises(ValueError, match="source_fused_margin_tails"):
        W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {
            "source_fused_margin_tails": [{"block_id": 1, "tail": "ab"}]}}}])
