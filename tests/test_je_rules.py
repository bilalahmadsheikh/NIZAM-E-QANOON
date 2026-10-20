"""Agent JE's rules for export j (13 Oct 2026; docs/SEGMENTATION-PROFILES.md). Each is data-gated; a full released A/B
(4,446 observations) read 0 differing with all four in place.

  reviewed_clause_section_reparent    `source_reparent_blocks` may move a numbered section the walk demoted to a clause
                                      back to the chapter/part that prints it (doc 4441 s.390), retyped section.
  printed_heading_reviewed_default    a reviewed `source_printed_headings` entry is honoured in any profile
                                      (tests/test_unreleased_v4.py::test_printed_heading_override_reviewed_in_any_profile).
  reviewed_figure_subsections         `source_figure_subsections`: bare figures printed beside one margin note are that
                                      section's sub-sections (doc 4521 s.1(1)-(3)); fail-closed.
  reviewed_margin_note_pieces         `source_margin_note_pieces`: a margin note printed over several apparatus blocks is
                                      the named rule's heading (doc 4426); fail-closed.
"""
import pytest

from nizam.corpus import segment as S
from nizam.workers.segment import reviewed_structural_overrides
from tools import materialize_multi_instrument as materializer
from tools.record_curation_patch import STRUCTURAL_KEYS

DECISION = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json",
            "document_id": 4521, "question_id": "q1"}


def _patch(**overrides):
    return {"evidence": {"structural_overrides": overrides}}


def blocks(*texts):
    return [{"id": 100 + i, "text": t, "page_no": 1, "y0": 100 + 40 * i, "page_height": 800, "x0": 50, "x1": 500}
            for i, t in enumerate(texts)]


SECTION_BACK = {"source_block_id": 12, "parent_block_id": 10, "kind": "section", "source_kind": "clause",
                "source_label": "390", "parent_kind": "chapter", "parent_label": "XVII"}


def test_clause_section_reparent_shape_is_narrow():
    assert reviewed_structural_overrides([], [_patch(source_reparent_blocks=[SECTION_BACK])])[
        "source_reparent_blocks"] == [SECTION_BACK]
    for bad in (dict(SECTION_BACK, source_kind="subsection"), dict(SECTION_BACK, parent_kind="schedule"),
                {k: v for k, v in SECTION_BACK.items() if k != "source_label"}, dict(SECTION_BACK, kind="article")):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            reviewed_structural_overrides([], [_patch(source_reparent_blocks=[bad])])


def test_clause_section_reparent_moves_the_subtree_to_the_chapter():
    root = S.Node("instrument", "", depth=0)
    chapter = S.Node("chapter", "XVII", depth=2, first_block=10, parent=root)
    section = S.Node("section", "389", depth=3, first_block=11, parent=chapter)
    clause = S.Node("clause", "390", depth=5, first_block=12, parent=section)
    item = S.Node("clause", "a", depth=6, first_block=13, parent=clause)
    root.children.append(chapter)
    chapter.children.append(section)
    section.children.append(clause)
    clause.children.append(item)
    S._apply_source_reparents(root, [SECTION_BACK], [], {})
    assert clause.parent is chapter and clause.kind == "section"
    assert [c.label for c in chapter.children] == ["389", "390"] and item.parent is clause


FIG = blocks("Short title, extent and commencement. 1. This Act shall be called the Test Act.",
             "2 It shall apply to the whole of the Province.",
             "3. It shall come into force at once.")
FIG_SPEC = {"section_block_id": 100, "section_label": "1", "heading": "Short title, extent and commencement.",
            "subsections": [{"source_block_id": 100, "figure": "1",
                             "printed_prefix": "Short title, extent and commencement. 1."},
                            {"source_block_id": 101, "figure": "2", "printed_prefix": "2"},
                            {"source_block_id": 102, "figure": "3", "printed_prefix": "3."}],
            "owner_decision": DECISION}


def test_figure_subsections_open_one_section_with_its_figures():
    seg = S.segment(FIG, structural_overrides={"source_figure_subsections": [FIG_SPEC]})
    tops = [n for n in seg.flatten() if n.parent is not None and n.parent.kind == "instrument"]
    s1 = [n for n in tops if n.kind == "section" and n.label == "1"]
    assert len(s1) == 1 and s1[0].heading == "Short title, extent and commencement."
    assert [(c.kind, c.label, " ".join(c.text_parts)) for c in s1[0].children] == [
        ("subsection", "1", "This Act shall be called the Test Act."),
        ("subsection", "2", "It shall apply to the whole of the Province."),
        ("subsection", "3", "It shall come into force at once.")]
    assert not [n for n in seg.flatten() if n.kind == "section" and n.label == "3"]


def test_figure_subsections_fail_closed_and_stay_inert_without_the_key():
    assert ([(n.kind, n.label) for n in S.segment(FIG).flatten()]
            == [(n.kind, n.label) for n in S.segment(FIG, structural_overrides={}).flatten()])
    for bad in (dict(FIG_SPEC, owner_decision=None),
                dict(FIG_SPEC, subsections=[dict(FIG_SPEC["subsections"][0]), dict(FIG_SPEC["subsections"][2])]),
                dict(FIG_SPEC, subsections=[dict(FIG_SPEC["subsections"][0], printed_prefix="Short title. 1.")]
                     + FIG_SPEC["subsections"][1:])):
        with pytest.raises(ValueError, match="figure subsections"):
            S.segment(FIG, structural_overrides={"source_figure_subsections": [bad]})


MARGIN = blocks("5. The Board shall meet.", "Joining of a", "political party", "6. A member may resign.")
PIECES = {"target_block_id": 103, "source_block_ids": [101, 102], "label": "6",
          "heading": "Joining of a political party"}


def test_margin_note_pieces_head_the_named_rule():
    seg = S.segment(MARGIN, structural_overrides={"source_apparatus_blocks": [101, 102],
                                                  "source_margin_note_pieces": [PIECES]})
    six = [n for n in seg.flatten() if n.kind == "section" and n.label == "6"]
    assert len(six) == 1 and six[0].heading == "Joining of a political party"
    with pytest.raises(ValueError, match="margin note pieces"):
        S.segment(MARGIN, structural_overrides={"source_apparatus_blocks": [101],      # one piece not apparatus
                                                "source_margin_note_pieces": [PIECES]})
    with pytest.raises(ValueError, match="margin note pieces"):
        S.segment(MARGIN, structural_overrides={"source_apparatus_blocks": [101, 102],
                                                "source_margin_note_pieces": [dict(PIECES, heading="Joining")]})


def test_je_keys_are_wired_through_worker_recorder_and_materializer():
    for key in ("source_figure_subsections", "source_margin_note_pieces"):
        assert key in STRUCTURAL_KEYS and key in materializer.STRUCTURAL_PATCH_KEYS
    merged = reviewed_structural_overrides([], [_patch(source_margin_note_pieces=[PIECES]),
                                                _patch(source_margin_note_pieces=[PIECES])])
    assert merged["source_margin_note_pieces"] == [PIECES]
    assert reviewed_structural_overrides([], [_patch(source_figure_subsections=[FIG_SPEC])])[
        "source_figure_subsections"] == [FIG_SPEC]
    with pytest.raises(ValueError, match="conflicting reviewed structural override source_figure_subsections"):
        reviewed_structural_overrides([], [_patch(source_figure_subsections=[FIG_SPEC]),
                                           _patch(source_figure_subsections=[dict(FIG_SPEC, section_label="2")])])
