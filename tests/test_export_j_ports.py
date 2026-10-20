"""Export j rule ports of agents JB, JC and JA (14 Oct 2026, builder BZ; docs/SEGMENTATION-PROFILES.md). One combined full
released A/B covers the whole group. Each rule is either a v4 profile rule whose collateral sweep read SAME everywhere
(JB A-C; JC namely_lead_not_heading, apparatus_contents_rows, amount_cell_not_label) or data-gated by a reviewed key
(JB D-I, JA C-H). JB's rule D statute_row_headings is DATA-GATED by the observation flag source_statute_row_headings,
not a profile rule (lead 13 Oct: released doc 2731 must not change)."""
import pathlib

import pytest

from nizam.corpus import segment as S
from nizam.workers.segment import reviewed_structural_overrides
from tools import materialize_multi_instrument as materializer
from tools.record_curation_patch import GENERIC_STRUCTURAL_KEYS, STRUCTURAL_KEYS

V4_NAMES = {"reviewed_link_in_division", "number_line_half_paren_subrule", "order_suffix_after_reparent",
            "namely_lead_not_heading", "apparatus_contents_rows", "amount_cell_not_label"}
NEW_KEYS = {"source_statute_row_headings", "source_explanation_of_heading", "source_no_cut_blocks",
            "source_margin_heading_owners", "source_root_reparent_blocks", "source_chapter_over_part",
            "source_contents_schedule_rows", "source_form_text_blocks", "source_lettered_part_blocks",
            "source_unheaded_section_blocks", "source_list_text_sections", "source_text_units",
            "source_division_openers", "source_division_captions"}


def _patch(**overrides):
    return {"evidence": {"structural_overrides": overrides}}


def blocks(*texts):
    return [{"id": 100 + i, "text": t, "page_no": 1, "y0": 100 + 40 * i, "page_height": 800, "x0": 50, "x1": 500}
            for i, t in enumerate(texts)]


def labels(seg):
    return [(n.kind, n.label) for n in seg.flatten()]


def test_profile_rules_and_the_data_gated_statute_row_headings():
    assert V4_NAMES <= S.SEGMENTATION_PROFILES["unreleased-v4"]
    assert not any("statute_row_headings" in rules for rules in S.SEGMENTATION_PROFILES.values())
    src = pathlib.Path(S.__file__).read_text(encoding="utf-8")
    assert 'profile_rule("statute_row_headings")' not in src
    assert '_df_over.get("source_statute_row_headings") is True' in src


def test_keys_are_wired_through_worker_recorder_and_materializer():
    assert NEW_KEYS <= STRUCTURAL_KEYS and NEW_KEYS <= set(materializer.STRUCTURAL_PATCH_KEYS)
    # every new key is recorded by the generic branch except the margin-heading owners (own page-checked branch)
    assert NEW_KEYS - GENERIC_STRUCTURAL_KEYS == {"source_margin_heading_owners"}


def test_worker_merges_flags_lists_and_keyed_entries_and_refuses_disagreement():
    merged = reviewed_structural_overrides([], [
        _patch(source_statute_row_headings=True, source_no_cut_blocks=[7, 5]),
        _patch(source_explanation_of_heading=True, source_no_cut_blocks=[5, 9], source_chapter_over_part=True)])
    assert merged["source_statute_row_headings"] is True and merged["source_explanation_of_heading"] is True
    assert merged["source_chapter_over_part"] is True and merged["source_no_cut_blocks"] == [7, 5, 9]
    for bad in ({"source_statute_row_headings": False}, {"source_no_cut_blocks": [5, 5]},
                {"source_form_text_blocks": []}, {"source_lettered_part_blocks": ["5"]},
                {"source_margin_heading_owners": [{"heading_block_id": 1, "owner_block_id": 2, "owner_label": "2"}]},
                {"source_root_reparent_blocks": [{"source_block_id": 1, "source_label": "9", "source_kind": "clause"}]},
                {"source_contents_schedule_rows": {"schedule_block_id": 4}}):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            reviewed_structural_overrides([], [_patch(**bad)])
    owner = {"heading_block_id": 11, "owner_block_id": 12, "owner_label": "ii", "owner_kind": "clause"}
    merged = reviewed_structural_overrides([], [_patch(source_margin_heading_owners=[owner]),
                                                _patch(source_margin_heading_owners=[owner])])
    assert merged["source_margin_heading_owners"] == [owner]
    with pytest.raises(ValueError, match="conflicting reviewed source_margin_heading_owners 11"):
        reviewed_structural_overrides([], [_patch(source_margin_heading_owners=[owner]),
                                           _patch(source_margin_heading_owners=[dict(owner, owner_label="iii")])])
    decl = {"schedule_block_id": 40, "owner_decision": {"export": "x.json", "document_id": 2556, "question_id": "q1"}}
    assert reviewed_structural_overrides([], [_patch(source_contents_schedule_rows=decl)])[
        "source_contents_schedule_rows"] == decl
    with pytest.raises(ValueError, match="conflicting reviewed structural override source_contents_schedule_rows"):
        reviewed_structural_overrides([], [_patch(source_contents_schedule_rows=decl),
                                           _patch(source_contents_schedule_rows=dict(decl, schedule_block_id=41))])


AMOUNT = blocks("1. Short title. These rules may be called the Test Rules.",
                "2. Delegation. The powers are delegated as follows:",
                "1.000 Million (Ten Lac)")


def test_amount_cell_is_no_label_under_v4_only():
    assert ("paragraph", "1.000") not in labels(S.segment(AMOUNT, profile="unreleased-v4"))


CHAPTERS = blocks("CHAPTER I", "1. Short title. These rules may be called the Test Rules.",
                  "CHAPTER II", "PART I", "2. Licence. A licence is required.",
                  "PART II", "3. Fee. A fee is payable.",
                  "CHAPTER III", "PART I", "4. Appeal. An appeal lies.")


def test_chapter_over_part_nests_parts_in_chapters_and_fails_closed():
    seg = S.segment(CHAPTERS, structural_overrides={"source_chapter_over_part": True})
    tops = [(n.kind, n.label) for n in seg.flatten() if n.parent is not None and n.parent.kind == "instrument"]
    assert tops == [("chapter", "I"), ("chapter", "II"), ("chapter", "III")]
    parts = [(n.parent.label, n.label) for n in seg.flatten() if n.kind == "part"]
    assert parts == [("II", "I"), ("II", "II"), ("III", "I")]
    with pytest.raises(ValueError, match="no part opened inside a chapter"):
        S.segment(blocks("CHAPTER I", "1. Short title. Text.", "CHAPTER II", "2. Licence. Text."),
                  structural_overrides={"source_chapter_over_part": True})


LETTERED = blocks("A. ADMISSION.- These regulations govern admission.",
                  "1. Short title. These regulations may be called the Test Regulations.",
                  "2. Eligibility. A candidate shall hold a certificate.",
                  "B. REGISTRATION:",
                  "1. Registration. Every student shall register.")


def test_lettered_part_blocks_open_parts_in_order_and_fail_closed():
    seg = S.segment(LETTERED, structural_overrides={"source_lettered_part_blocks": [100, 103]})
    assert [n.label for n in seg.flatten() if n.kind == "part"] == ["A", "B"]
    with pytest.raises(ValueError, match="source_lettered_part_blocks"):
        S.segment(LETTERED, structural_overrides={"source_lettered_part_blocks": [101]})


NO_CUT = blocks("1. Short title. This Act may be called the Test Act.",
                "2. Rates. The duty is levied at 149 F.\n(65C) and 162 F. on distillation.")


def test_no_cut_block_is_one_piece_and_fails_closed():
    assert ("subsection", "65C") not in labels(S.segment(NO_CUT, structural_overrides={"source_no_cut_blocks": [101]}))
    with pytest.raises(ValueError, match="source_no_cut_blocks not found"):
        S.segment(NO_CUT, structural_overrides={"source_no_cut_blocks": [999]})


def test_unheaded_section_blocks_refuse_a_guessed_heading():
    b = blocks("1. Short title. These regulations may be called the Test Regulations.",
               "2. Candidates holding an FA/F. Sc. Certificate shall be admitted.")
    plain = {n.label: n for n in S.segment(b).flatten()}
    if plain["2"].heading:
        cut = {n.label: n for n in S.segment(b, structural_overrides={"source_unheaded_section_blocks": [101]}).flatten()}
        assert not cut["2"].heading
    with pytest.raises(ValueError, match="source_unheaded_section_blocks"):
        S.segment(b, structural_overrides={"source_unheaded_section_blocks": [999]})
