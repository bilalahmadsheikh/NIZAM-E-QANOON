"""Rule `reviewed_schedule_chapter_reparent` (stage 3, agent DG, doc 4236; owner 12 Oct 2026).

A CHAPTER and a SCHEDULE share depth 2, so the walk closes an open schedule at each of its printed chapters and the
chapter opens at the Act root (doc 4236: the Warsaw, Hague and Montreal conventions' chapters became root-level
ch_I_n20_1 ...). The fix is reading-only: the existing key `source_reparent_blocks` may carry kind 'chapter', but only
as {kind: chapter, source_kind: chapter, parent_kind: schedule}. `_apply_source_reparents` (unchanged) moves the
chapter with its subtree. Inert without a reading; the worker refuses any other chapter-shaped spec.
"""
import pytest

from nizam.corpus import segment as S
from nizam.workers.segment import reviewed_structural_overrides


def _patch(specs):
    return {"evidence": {"structural_overrides": {"source_reparent_blocks": specs}}}


CHAPTER_SPEC = {"source_block_id": 104, "parent_block_id": 103, "kind": "chapter",
                "source_kind": "chapter", "source_label": "I", "parent_kind": "schedule"}


def test_the_worker_admits_a_chapter_only_into_a_schedule():
    merged = reviewed_structural_overrides([], [_patch([CHAPTER_SPEC])])
    assert merged["source_reparent_blocks"] == [CHAPTER_SPEC]
    for bad in ({**CHAPTER_SPEC, "parent_kind": "part"}, {k: v for k, v in CHAPTER_SPEC.items() if k != "parent_kind"},
                {**CHAPTER_SPEC, "source_kind": "section"}, {**CHAPTER_SPEC, "kind": "part", "source_kind": "part"}):
        with pytest.raises(ValueError, match="source_reparent_blocks"):
            reviewed_structural_overrides([], [_patch([bad])])
    # the kinds admitted before are admitted as before
    ss = {"source_block_id": 5, "parent_block_id": 4, "kind": "subsection"}
    assert reviewed_structural_overrides([], [_patch([ss])])["source_reparent_blocks"] == [ss]


def _blocks(*texts):
    return [{"id": 100 + i, "text": t, "page_no": 1 + i // 6, "y0": 100.0 + 20 * (i % 6), "page_height": 792.0,
             "x0": 72.0, "x1": 480.0} for i, t in enumerate(texts)]


BLOCKS = _blocks(
    "1. Short title. This Act may be called the Test Carriage Act.",       # 100
    "2. Application. The rules in the First Schedule shall apply.",       # 101
    "3. Repeal. The old Act is repealed.",                                # 102
    "THE FIRST SCHEDULE",                                                 # 103
    "CHAPTER I",                                                          # 104
    "SCOPE",                                                              # 105
    "1. (1) These rules apply to all international carriage.",           # 106
    "(2) In these rules a Party means a Party to the Convention.",       # 107
    "CHAPTER II",                                                         # 108
    "DOCUMENTS",                                                          # 109
    "2. The carrier must deliver a ticket.",                              # 110
    "THE SECOND SCHEDULE",                                                # 111
    "CHAPTER I",                                                          # 112
    "SCOPE",                                                              # 113
    "1. These rules apply to carriage as amended.",                       # 114
)


def _chapters(seg):
    out = []
    for node in seg.flatten():
        if node.kind == "chapter":
            out.append((node.label, node.parent.kind if node.parent is not None else None,
                        node.parent.label if node.parent is not None else None,
                        [c.label for c in node.children]))
    return out


def test_without_a_reading_the_schedule_chapters_escape_to_the_root():
    seg = S.segment(BLOCKS)
    assert {(lab, pk) for lab, pk, _pl, _c in _chapters(seg)} == {("I", "instrument"), ("II", "instrument")}


def test_the_reviewed_reparent_keeps_each_chapter_in_its_schedule():
    specs = [{"source_block_id": b, "parent_block_id": p, "kind": "chapter", "source_kind": "chapter",
              "source_label": lab, "parent_kind": "schedule"}
             for b, p, lab in ((104, 103, "I"), (108, 103, "II"), (112, 111, "I"))]
    overrides = reviewed_structural_overrides([], [_patch(specs)])
    seg = S.segment(BLOCKS, structural_overrides=overrides)
    chapters = _chapters(seg)
    assert [(lab, pk, pl) for lab, pk, pl, _c in chapters] == [
        ("I", "schedule", "FIRST SCHEDULE"), ("II", "schedule", "FIRST SCHEDULE"), ("I", "schedule", "SECOND SCHEDULE")]
    assert [c for *_x, c in chapters] == [["1"], ["2"], ["1"]]          # the rules move with their chapter
    assert [n.label for n in seg.root.children] == ["1", "2", "3", "FIRST SCHEDULE", "SECOND SCHEDULE"]


def test_a_chapter_spec_that_names_no_schedule_fails_closed():
    spec = {"source_block_id": 104, "parent_block_id": 102, "kind": "chapter", "source_kind": "chapter",
            "source_label": "I", "parent_kind": "schedule"}                # block 102 is section 3
    with pytest.raises(ValueError, match="source reparent must resolve one node"):
        S.segment(BLOCKS, structural_overrides={"source_reparent_blocks": [spec]})
