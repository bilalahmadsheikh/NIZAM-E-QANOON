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


def _ordinal_schedules():
    # doc 8637 shape: the Ordinance's sections, then 'THE FIRST SCHEDULE' printed inside a block with its rows
    return [_b(1, "1. Short title.—This Ordinance may be called the Test Ordinance. \n", 40.0),
            _b(2, "2. Repeal of certain laws.—The laws specified in the First Schedule are hereby repealed. \n", 60.0),
            _b(3, "made\n\" THE FIRST/SCHEDULE\nLAWS TO BE REPEALED\n(See section 2)\n", 80.0),
            _b(4, "1. XV of 1864 The Tolls Act, 1864. \n", 100.0),
            _b(5, "2. XVI of 1867 The Acting Judges Act, 1867. \n", 120.0)]


def test_V_ordinal_schedule_heading_inside_a_block():
    seg = S.segment(_ordinal_schedules(), profile="unreleased-v4", structural_overrides={
        "source_division_unit_openers": [{"source_block_id": 3, "source_prefix": "THE FIRST/SCHEDULE",
                                          "kind": "schedule", "label": "FIRST SCHEDULE"}]})
    assert [n.label for n in seg.flatten() if n.kind == "schedule"] == ["FIRST SCHEDULE"]
    assert [n.label for n in seg.root.children if n.kind == "section"] == ["1", "2"]


def test_V_ordinal_schedule_refuses_the_wrong_ordinal():
    with pytest.raises(ValueError):
        S.segment(_ordinal_schedules(), profile="unreleased-v4", structural_overrides={
            "source_division_unit_openers": [{"source_block_id": 3, "source_prefix": "THE FIRST/SCHEDULE",
                                              "kind": "schedule", "label": "SECOND SCHEDULE"}]})


def test_V_ordinal_schedule_without_the():
    blocks = _ordinal_schedules()
    blocks[2] = _b(3, "made\nSECOND SCHEDULE\nLAWS TO BE AMENDED\n", 80.0)
    seg = S.segment(blocks, profile="unreleased-v4", structural_overrides={
        "source_division_unit_openers": [{"source_block_id": 3, "source_prefix": "SECOND SCHEDULE",
                                          "kind": "schedule", "label": "SECOND SCHEDULE"}]})
    assert [n.label for n in seg.flatten() if n.kind == "schedule"] == ["SECOND SCHEDULE"]


def test_v5_toc_promised_next_section_survives_a_lost_heading():
    # doc 9127 shape: contents promise 15; section 14 opens a garbled '(4)'; '15.' (heading lost, indented) follows
    blocks = [_b(1, "CONTENTS\n14. Power to enter, arrest and seize.\n15. Power to seize opium in open places.\n", 40.0),
              _b(2, "It is hereby enacted as follows:—\n", 60.0),
              _b(3, "14. Any officer of the said departments may enter any place\n", 80.0),
              _b(4, "(4) in case of resistance break open any door\n", 100.0),
              {**_b(5, "15. Any officer of any of the said departments may seize\n", 120.0), "x0": 110.0}]
    v4 = [n for n in S.segment(blocks, profile="unreleased-v4").flatten() if n.label == "15"]
    v5 = [n for n in S.segment(blocks, profile="unreleased-v5").flatten() if n.label == "15"]
    assert v5 and v5[0].kind == "section"
    assert v4 and v4[0].kind in ("clause", "section")


def _glued_appendix():
    # doc 6029 pp7-8: the rules end, then 'APPENDIX' with its note marker 3 glued on as printed superscript
    return [_b(1, "13.\nDelegation.- Government may delegate all or any of its powers under these rules.\n", 40.0),
            _b(2, "BY ORDER OF\n", 80.0),
            _b(3, "3APPENDIX\n", 20.0, page=2),
            _b(4, "{ See Rule 2 (a), 3 (3), 5 and 7 (1) }\n", 40.0, page=2),
            _b(5, "1.\nCamera Man\n", 60.0, page=2),
            _b(6, "2.\n4[Omitted]\n", 80.0, page=2)]


def test_division_opener_reads_a_glued_note_marker_on_the_default_profile():
    seg = S.segment(_glued_appendix(), structural_overrides={
        "source_division_openers": [{"source_block_id": 3, "kind": "appendix", "label": "APPENDIX"}]})
    apps = [n for n in seg.flatten() if n.kind == "appendix"]
    assert [n.label for n in apps] == ["APPENDIX"]
    def texts(node):
        return [node.text or ""] + [t for c in node.children for t in texts(c)]
    s13 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "13")
    assert not any("Camera Man" in t for t in texts(s13))
    assert any("Camera Man" in t for t in texts(apps[0]))


def test_division_opener_glued_marker_still_checks_the_word():
    blocks = _glued_appendix()
    blocks[2] = _b(3, "3 PERSONS\n", 20.0, page=2)
    with pytest.raises(ValueError, match="does not print"):
        S.segment(blocks, structural_overrides={
            "source_division_openers": [{"source_block_id": 3, "kind": "appendix", "label": "APPENDIX"}]})


OD_4807 = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-24-delegated-r9.json",
           "document_id": 4807, "question_id": "q1"}


def _form_in_one_block():
    # doc 4807 p9: the leave rules end, then one block prints the form's heading, its note and items 1-2
    return [_b(1, "4. \nAdmissibility of Leave\nLeave shall be applied for on the prescribed format appended to these rules.\n", 40.0),
            _b(2, "APPLICATION FORMAT FOR LEAVE\n\nNote: Item 1 to 2 must be filled in by all applicants.\n\n"
                  "1.\nName of Applicant:\n\n2.\nID Card No.:\n", 20.0, page=2)]


@pytest.mark.parametrize("source_text", ["APPLICATION FORMAT FOR LEAVE", _form_in_one_block()[1]["text"]])
def test_unlabelled_opener_reads_later_units_of_its_block_in_the_appendix(source_text):
    # the first unit's text, or (as the recorder holds it) the whole block's text
    seg = S.segment(_form_in_one_block(), profile="unreleased-v5", structural_overrides={
        "source_unlabelled_schedule_openers": [{"source_block_id": 2, "label": "APPENDIX",
                                                "source_text": source_text, "owner_decision": OD_4807}]})
    app = next(n for n in seg.flatten() if n.kind == "appendix")
    assert app.label == "APPENDIX"
    assert [c.label for c in app.children] == ["1", "2"]
    assert not [n for n in seg.flatten() if n.kind == "section" and n.label in ("1", "2")]


def test_unlabelled_opener_still_checks_its_first_unit():
    with pytest.raises(ValueError, match="lacks exact source evidence"):
        S.segment(_form_in_one_block(), profile="unreleased-v5", structural_overrides={
            "source_unlabelled_schedule_openers": [{"source_block_id": 2, "label": "APPENDIX",
                                                    "source_text": "LEAVE FORM", "owner_decision": OD_4807}]})


def _amending_rows():
    # doc 9673 pp1-2: paragraph (a)'s table rows end on p2 in the same block as amending paragraph (b)
    return [_b(1, "In the aforesaid rules, in Appendix:\n", 20.0),
            _b(2, "(a) against Serial No. 6 and 7, for the existing entries, the following shall be substituted, namely,-\n", 40.0),
            _b(3, "6.\nAssistant Director, (BPS-17).\n(a) 50% by promotion; and\n", 60.0),
            _b(4, "(b) 50% by initial recruitment.\n7.\nAccounts Officer, (BPS-17).\n(a) Master's Degree; or\n(b) CA.\n"
                  "(b) after Serial No.8, as so amended the following new entries shall be inserted, namely,-\n", 20.0, page=2)]


def test_printed_opener_takes_an_amending_paragraph_in_lower_case_and_beats_a_text_unit():
    seg = S.segment(_amending_rows(), structural_overrides={
        "source_table_row_blocks": [3, 4], "source_no_cut_blocks": [3, 4],
        "source_printed_rule_openers": [{"source_block_id": 4, "kind": "clause", "label": "b",
                                         "source_prefix": "(b) after Serial No.8, as so amended"}],
        "source_text_units": [{"source_block_id": 3, "kind": "clause", "label": "6"},
                              {"source_block_id": 4, "kind": "clause", "label": "b"}]})
    top = [(n.kind, n.label) for n in seg.root.children if n.kind == "clause"]
    assert top == [("clause", "a"), ("clause", "b")]
    b = [n for n in seg.root.children if n.label == "b"][0]
    assert (b.text or "").startswith("after Serial No.8")
    a = [n for n in seg.root.children if n.label == "a"][0]
    assert "Accounts Officer" in (a.text or "")


def test_printed_opener_lower_case_still_needs_the_letter():
    with pytest.raises(ValueError):
        S.segment(_amending_rows(), structural_overrides={
            "source_printed_rule_openers": [{"source_block_id": 4, "kind": "clause", "label": "c",
                                             "source_prefix": "(b) after Serial No.8, as so amended"}]})
