"""Agent K4's prototype rules R, S, U, V (doc 3730 E2, Annexures A-E; delegated export 2026-10-15 q2 'rows-by-group').

R `group_caption_cut_from_block` -- a reviewed group caption printed INSIDE its block is cut out as a unit of its own;
  one block may carry several captions (distinct texts); worker side: reviewed_structural_overrides merges captions
  keyed by (block, caption).
S `annexure_group_caption` -- a group caption may open under an open top-level ANNEXURE, not only a SCHEDULE.
U `reviewed_dotted_serial_rows_in_block` -- key source_dotted_serial_row_blocks: a listed block's pieces are cut
  before every line opening 'N.' (ditto rows '2. -do- -do- Ferash'); serials run +1 or restart at 1.
V `reviewed_division_unit_opener` -- key source_division_unit_openers: a division line INSIDE a block (its unit found
  by a page-read prefix) opens the division, or (label null) opens nothing.

Ported by builder BZ (group 17 G-M, 16 Oct; group 20 O-V, 16 Oct 2026) from claude/agK4/tools/test_k4_rules_rsuv_DRAFT.py.
"""
import pytest

from nizam.corpus import segment as S

OWNER = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-15-delegated.json",
         "document_id": 3730, "question_id": "q2"}


def _b(i, text, y0, page=1):
    return {"id": i, "text": text, "page_no": page, "x0": 72.0, "x1": 480.0, "y0": y0, "page_height": 842.0}


def _cap(block, caption):
    return {"source_block_id": block, "caption": caption, "level": 1, "owner_decision": OWNER}


def _annexure():
    return [_b(1, "1. \nSCARP Khairpur particulars as per Annexure A. Rs. 16.00 \n", 40.0),
            _b(2, "ANNEXURE A \n", 80.0),
            _b(3, "1.   Khairpur \n  Khairpur \n \n1.  Nizamani \n", 100.0),
            _b(4, "2.  Khairpur \n", 120.0),
            _b(5, "3.  Saidpur. \n \n Khairpur \n Kotdiji \n 1. Kotdiji \n", 140.0),
            _b(6, "2. Chanuro \n", 160.0)]


def test_RS_captions_in_blocks_under_an_annexure():
    seg = S.segment(_annexure(), profile="unreleased-v4", structural_overrides={
        "source_schedule_group_captions": [_cap(3, "1. Khairpur Khairpur"), _cap(5, "Khairpur Kotdiji")]})
    ann = next(n for n in seg.flatten() if n.kind == "annexure")
    caps = [n for n in ann.children if getattr(n, "group_caption", False)]
    assert [c.label for c in caps] == ["1. Khairpur Khairpur", "Khairpur Kotdiji"]
    assert [r.label for r in caps[0].children] == ["1", "2", "3"]
    assert [r.label for r in caps[1].children] == ["1", "2"]
    assert caps[0].children[2].text.strip().startswith("Saidpur")
    assert "Kotdiji" not in caps[0].children[2].text


def test_S_off_refuses_a_caption_under_an_annexure():
    S.SEGMENTATION_PROFILES["_s_off"] = S.SEGMENTATION_PROFILES["unreleased-v4"] - {"annexure_group_caption"}
    try:
        with pytest.raises(ValueError):
            S.segment(_annexure(), profile="_s_off", structural_overrides={
                "source_schedule_group_captions": [_cap(3, "1. Khairpur Khairpur"), _cap(5, "Khairpur Kotdiji")]})
    finally:
        del S.SEGMENTATION_PROFILES["_s_off"]


def test_R_refuses_a_caption_not_printed_in_its_block():
    with pytest.raises(ValueError):
        S.segment(_annexure(), profile="unreleased-v4", structural_overrides={
            "source_schedule_group_captions": [_cap(4, "Khairpur Kotdiji")]})


def _ditto():
    return [_b(1, "1. \nLarkana Shikarpur particulars as per Annexure D. Rs. 5.00 \n", 40.0),
            _b(2, "ANNEXURE D \n", 80.0),
            _b(3, "Sukkur \nSukkur \n1. Nasirabad \n2.      -d- \n   -do- \n   Ferash \n3.  \n  -d- \n -do- \n Old Sukkur \n"
                  "Shikarpur \nLakhi \n1. Goserji \n2.   -d- \n -do- \n Bhayo \n", 100.0)]


def test_RU_two_captions_in_one_block_and_ditto_rows():
    seg = S.segment(_ditto(), profile="unreleased-v4", structural_overrides={
        "source_schedule_group_captions": [_cap(3, "Sukkur Sukkur"), _cap(3, "Shikarpur Lakhi")],
        "source_dotted_serial_row_blocks": [3]})
    ann = next(n for n in seg.flatten() if n.kind == "annexure")
    caps = [n for n in ann.children if getattr(n, "group_caption", False)]
    assert [c.label for c in caps] == ["Sukkur Sukkur", "Shikarpur Lakhi"]
    assert [r.label for r in caps[0].children] == ["1", "2", "3"]
    assert [r.label for r in caps[1].children] == ["1", "2"]
    assert "Ferash" in caps[0].children[1].text and "Old Sukkur" in caps[0].children[2].text


def test_U_refuses_a_block_that_is_not_a_run_of_rows():
    with pytest.raises(ValueError):
        S.segment(_ditto(), profile="unreleased-v4", structural_overrides={"source_dotted_serial_row_blocks": [2]})


def test_U_key_without_the_rule_raises():
    S.SEGMENTATION_PROFILES["_u_off"] = S.SEGMENTATION_PROFILES["unreleased-v4"] - {
        "reviewed_dotted_serial_rows_in_block"}
    try:
        with pytest.raises(ValueError):
            S.segment(_ditto(), profile="_u_off", structural_overrides={"source_dotted_serial_row_blocks": [3]})
    finally:
        del S.SEGMENTATION_PROFILES["_u_off"]


def _unit_lines():
    return [_b(1, "1. \nKotri Surface Drainage Project particulars as per Annexure E. Rs. 2.00 \n", 40.0),
            _b(2, "ANNEXURE D \n", 80.0),
            _b(3, "1. Nasirabad \n2. Ferash. \n \nAnnexure-E \n \n", 100.0),
            _b(4, "SCHEDULE OF AREAS UNDER KOTRI SURFACE DRAINAGE PROJECT \n", 140.0),
            _b(5, "1.  Udehjani \n", 160.0)]


def test_V_opens_an_annexure_inside_a_block():
    seg = S.segment(_unit_lines(), profile="unreleased-v4", structural_overrides={
        "source_division_unit_openers": [{"source_block_id": 3, "source_prefix": "Annexure-E", "kind": "annexure",
                                          "label": "ANNEXURE E"}],
        "source_division_openers": [{"source_block_id": 4, "kind": "schedule", "label": None}]})
    anns = [n.label for n in seg.flatten() if n.kind == "annexure"]
    assert anns == ["ANNEXURE D", "ANNEXURE E"]
    assert not [n for n in seg.flatten() if n.kind == "schedule"]


def test_V_refuses_a_label_that_is_not_the_print():
    with pytest.raises(ValueError):
        S.segment(_unit_lines(), profile="unreleased-v4", structural_overrides={
            "source_division_unit_openers": [{"source_block_id": 3, "source_prefix": "Annexure-E",
                                              "kind": "annexure", "label": "ANNEXURE F"}]})


def test_V_refuses_a_prefix_never_reached():
    with pytest.raises(ValueError):
        S.segment(_unit_lines(), profile="unreleased-v4", structural_overrides={
            "source_division_unit_openers": [{"source_block_id": 3, "source_prefix": "Annexure-Q",
                                              "kind": "annexure", "label": "ANNEXURE Q"}]})


def test_R_worker_merges_two_captions_of_one_block():
    import nizam.workers.segment as W
    patches = [{"evidence": {"structural_overrides": {"source_schedule_group_captions": [_cap(3, "Sukkur Sukkur")]}}},
               {"evidence": {"structural_overrides": {"source_schedule_group_captions": [_cap(3, "Shikarpur Lakhi")]}}}]
    out = W.reviewed_structural_overrides([], patches)
    assert sorted(c["caption"] for c in out["source_schedule_group_captions"]) == ["Shikarpur Lakhi", "Sukkur Sukkur"]


def test_V_glued_note_marker_before_the_division_word():
    # doc 4053 p38: '1SCHEDULE III' -- note marker 1 printed superscript, glued in the text layer
    blocks = [_b(1, "1. \nShort title. This Act may be called the Test Act. \n", 40.0),
              _b(2, "1SCHEDULE III \n", 80.0), _b(3, "(See section 19 I) \n", 100.0),
              _b(4, "2. I further say that I have set forth the items. \n", 120.0)]
    seg = S.segment(blocks, profile="unreleased-v4", structural_overrides={
        "source_division_unit_openers": [{"source_block_id": 2, "source_prefix": "1SCHEDULE III", "kind": "schedule",
                                          "label": "SCHEDULE III"}]})
    assert [n.label for n in seg.flatten() if n.kind == "schedule"] == ["SCHEDULE III"]
