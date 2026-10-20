"""Agent K2's rules (docs 4431, 4369, 4489; docs/SEGMENTATION-PROFILES.md). Each is data-gated.

Run against the live module once ported (copy to tests/). Before the port, run against the prototype chain:
    K2_RULE=<scratchpad>/agK2-rule2.py ./.venv/bin/python -m pytest <this file>
"""
import importlib.util
import os
import sys

import pytest

if os.environ.get("K2_RULE"):
    _spec = importlib.util.spec_from_file_location("k2_rule_t", os.environ["K2_RULE"])
    _R = importlib.util.module_from_spec(_spec)
    sys.modules["k2_rule_t"] = _R
    _spec.loader.exec_module(_R)
    W = _R.load_worker("k2_test_worker")
    S = sys.modules["agk2_segment2"]
else:
    from nizam.corpus import segment as S
    import nizam.workers.segment as W

NEW_KEYS = ("source_quoted_insertion_spans", "source_label_moves", "source_half_paren_subrule_blocks",
            "source_contents_page_column", "source_unstopped_contents_rows")


def _patch(**overrides):
    return {"evidence": {"structural_overrides": overrides}}


def blocks(*texts, page=1):
    return [{"id": 100 + i, "text": t, "page_no": page, "y0": 100 + 40 * i, "page_height": 800, "x0": 50, "x1": 500}
            for i, t in enumerate(texts)]


def tops(seg):
    return [n for n in seg.flatten() if n.parent is not None and n.parent.kind == "instrument"]


@pytest.mark.skipif(bool(os.environ.get("K2_RULE")), reason="recorder/materializer keys are a port item")
def test_new_keys_are_recorded_and_materialized():
    from tools import materialize_multi_instrument as materializer
    from tools.record_curation_patch import GENERIC_STRUCTURAL_KEYS, STRUCTURAL_KEYS
    for key in NEW_KEYS:
        assert key in STRUCTURAL_KEYS and key in GENERIC_STRUCTURAL_KEYS and key in materializer.STRUCTURAL_PATCH_KEYS, key


def test_worker_unites_k2_keys_and_refuses_bad_shapes():
    span = {"first_block_id": 1, "first_prefix": "2. In rule 7", "last_block_id": 2, "last_prefix": "shall be inserted"}
    move = {"label_block_id": 5, "label": "(a)", "target_block_id": 6, "target_prefix": "the first item"}
    row = {"source_block_id": 9, "label": "31-A"}
    merged = W.reviewed_structural_overrides([], [
        _patch(source_quoted_insertion_spans=[span]), _patch(source_quoted_insertion_spans=[span]),
        _patch(source_label_moves=[move]), _patch(source_half_paren_subrule_blocks=[30, 10]),
        _patch(source_half_paren_subrule_blocks=[20]), _patch(source_contents_page_column=True),
        _patch(source_unstopped_contents_rows=[row])])
    assert merged["source_quoted_insertion_spans"] == [span]
    assert merged["source_label_moves"] == [move]
    assert merged["source_half_paren_subrule_blocks"] == [10, 20, 30]
    assert merged["source_contents_page_column"] is True
    assert merged["source_unstopped_contents_rows"] == [row]
    for bad in (_patch(source_quoted_insertion_spans=[dict(span, extra=1)]),
                _patch(source_label_moves=[{k: v for k, v in move.items() if k != "label"}]),
                _patch(source_half_paren_subrule_blocks=["10"]),
                _patch(source_contents_page_column=1),
                _patch(source_unstopped_contents_rows=[dict(row, heading="x")])):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            W.reviewed_structural_overrides([], [bad])


def test_label_move_reads_a_detached_label_on_its_printed_line():
    bl = [{"id": 100, "text": "(a)  \n", "page_no": 1}, {"id": 101, "text": "the first item; and\n", "page_no": 1}]
    move = {"label_block_id": 100, "label": "(a)", "target_block_id": 101, "target_prefix": "the first item"}
    loc = {"page_no": 1, "match_text": "the first item; and", "before_text": "the first item; and",
           "after_text": "the first item; and"}
    out, _ = S._apply_curation_patches(bl, [dict(loc, **_patch(source_label_moves=[move]))])
    assert out[0]["text"].strip() == "" and out[1]["text"].startswith("(a) the first item")
    assert bl[0]["text"] == "(a)  \n"   # the extracted evidence is not touched
    with pytest.raises(ValueError, match="label move"):
        S._apply_curation_patches(bl, [dict(loc, **_patch(source_label_moves=[dict(move, target_prefix="no such words")]))])


def test_half_paren_subrules_open_in_reviewed_blocks_only():
    bl = blocks("1. Short title.- (1) These rules may be called the Test Rules.\n2) They shall come into force at once.")
    on = S.segment(bl, structural_overrides={"source_half_paren_subrule_blocks": [100]})
    r1 = [n for n in tops(on) if n.label == "1"][0]
    assert [(c.kind, c.label) for c in r1.children] == [("subsection", "1"), ("subsection", "2")]
    off = S.segment(bl)
    assert [c.label for c in [n for n in tops(off) if n.label == "1"][0].children] != ["1", "2"]


OPENER_PART = {"source_block_id": 102, "label": "II", "source_prefix": "PART II \nGENERAL", "kind": "part"}


def test_part_opener_validates_its_label_by_kind():
    bl = blocks("1. Short title.- This Act may be called the Test Act.",
                "2. Definitions.- In this Act the expression includes", "PART II \nGENERAL PROVISIONS",
                "3. Application.- This Act applies to all persons.")
    seg = S.segment(bl, structural_overrides={"source_printed_rule_openers": [OPENER_PART]})
    part = [n for n in seg.flatten() if n.kind == "part" and n.label == "II"]
    assert len(part) == 1 and [c.label for c in part[0].children] == ["3"]
    for bad in (dict(OPENER_PART, label="2"), dict(OPENER_PART, label="B2", source_prefix="PART B2 \nGENERAL")):
        with pytest.raises(ValueError, match="malformed"):
            S.segment(bl, structural_overrides={"source_printed_rule_openers": [bad]})


def test_section_opener_takes_two_letter_and_hyphen_labels():
    bl = blocks("4A. Rates.- (1) Tax shall be charged.", "4[(4AB) Subject to this Act, a tax shall be charged.")
    seg = S.segment(bl, structural_overrides={"source_printed_rule_openers": [
        {"source_block_id": 101, "label": "4AB", "source_prefix": "4[(4AB) Subject to this Act"}]})
    assert [n.label for n in tops(seg)] == ["4A", "4AB"]


def test_bracket_led_schedule_heading_opens_when_reviewed():
    bl = blocks("1. Short title.- This Act may be called the Test Act.",
                "2. Rules.- The rules in the Eighth Schedule apply to every person who is", "[THE EIGHTH SCHEDULE \n",
                "[Section 2] \n", "1. Manner of computation.- Capital gains shall be computed as prescribed.")
    seg = S.segment(bl, structural_overrides={"source_schedule_heading_blocks": [102]})
    sch = [n for n in tops(seg) if n.kind == "schedule"]
    assert [n.label for n in sch] == ["EIGHTH SCHEDULE"] and sch[0].first_block == 102
