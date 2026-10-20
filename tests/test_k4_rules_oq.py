"""Agent K4's prototype rules O and Q (doc 3696).

O `order_suffix_one_block_section` -- an order-suffix group of SECTIONS may name one block once per print (both prints
  of regulation 17 in one block, owner q3 'keep-both'); the worker's shape check admits it.
Q `reviewed_part_line` -- key source_part_line_blocks: 'PART-IV' after a sentence ending in a colon opens Part IV.

Ported by builder BZ (group 17 G-M, 16 Oct; group 20 O-V, 16 Oct 2026) from claude/agK4/tools/test_k4_rules_oq_DRAFT.py.
"""
import pytest

from nizam.corpus import segment as S

OWNER = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-15-delegated.json",
         "document_id": 3696, "question_id": "q3"}


def _b(i, text, y0, page=1):
    return {"id": i, "text": text, "page_no": page, "x0": 72.0, "x1": 480.0, "y0": y0, "page_height": 842.0}


def _two_17():
    return [_b(1, "1. \nShort title:- These regulations may be called the Test Regulations. \n", 40.0),
            _b(2, "16. \nDrawls:- Any amount shall be drawn through a cheque. \n \n17. \n(1) The accounts shall be kept in "
                  "rupees. \n(2) The accounts shall be audited annually. \n \n17. \nNo appeal shall lie against any "
                  "decision of the Committee. \n", 60.0)]


def test_O_keeps_both_prints_in_one_block():
    seg = S.segment(_two_17(), profile="unreleased-v4", structural_overrides={"source_order_suffix_labels": [
        {"kind": "section", "label": "17", "source_block_ids": [2, 2], "owner_decision": OWNER}]})
    sections = [n for n in seg.flatten() if n.kind == "section" and n.label == "17"]
    assert len(sections) == 2 and [n.print_occurrence for n in sections] == [1, 2]
    assert not [d for d in seg.repeated_label_decisions if not d.get("settled_by_review")]


def test_O_is_data_gated_in_every_profile():
    # group 21 (16 Oct 2026; owner: release 3696 under default): the reviewed one-block group is honoured in the
    # DEFAULT profile too -- the spec naming one block for every print is the reviewed evidence; no profile name
    assert "order_suffix_one_block_section" not in S.SEGMENTATION_PROFILES["unreleased-v4"]
    seg = S.segment(_two_17(), structural_overrides={"source_order_suffix_labels": [
        {"kind": "section", "label": "17", "source_block_ids": [2, 2], "owner_decision": OWNER}]})
    sections = [n for n in seg.flatten() if n.kind == "section" and n.label == "17"]
    assert len(sections) == 2 and [n.print_occurrence for n in sections] == [1, 2]
    # a group naming one block for only SOME prints is still refused
    with pytest.raises(ValueError):
        S.segment(_two_17(), structural_overrides={"source_order_suffix_labels": [
            {"kind": "section", "label": "17", "source_block_ids": [2, 1], "owner_decision": OWNER}]})


def _part_after_colon():
    return [_b(1, "PART-III \n", 40.0), _b(2, "CONFIRMATION \n \n10. \nDeferment:- If an employee is due, the authority "
                                              "defers his confirmation: \n", 60.0),
            _b(3, "PART-IV \n", 100.0), _b(4, " \nSENIORITY \n \n11. \nSeniority list:- In each cadre there shall be a "
                                            "list. \n", 120.0)]


def test_Q_opens_the_part_after_a_colon():
    seg = S.segment(_part_after_colon(), profile="unreleased-v4", structural_overrides={"source_part_line_blocks": [3]})
    parts = [n.label for n in seg.flatten() if n.kind == "part"]
    assert "IV" in parts
    s11 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "11")
    assert s11.parent.kind == "part" and s11.parent.label == "IV"


def test_Q_is_data_gated_in_every_profile():
    # group 21: source_part_line_blocks is honoured in DEFAULT too, and inert without the key
    assert "reviewed_part_line" not in S.SEGMENTATION_PROFILES["unreleased-v4"]
    seg = S.segment(_part_after_colon(), structural_overrides={"source_part_line_blocks": [3]})
    s11 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "11")
    assert s11.parent.kind == "part" and s11.parent.label == "IV"
    plain = S.segment(_part_after_colon())
    assert plain.flatten() and [n.label for n in plain.flatten()] == [n.label for n in S.segment(_part_after_colon()).flatten()]
    with pytest.raises(ValueError):
        S.segment(_part_after_colon(), structural_overrides={"source_part_line_blocks": [4]})


def test_Q_refuses_a_block_that_prints_no_part():
    with pytest.raises(ValueError):
        S.segment(_part_after_colon(), profile="unreleased-v4", structural_overrides={"source_part_line_blocks": [4]})
