"""Agent K4's prototype rules K-M (docs 4222, 4264).

K `schedule_group_caption_in_part`  -- a level-1 group caption read while a Part of the schedule is open hangs under the
  Part (doc 4222 First Schedule Part I: 'A: BIRDS' / 'Category one–' ...).
L `reviewed_inserted_row_label`     -- key source_inserted_row_blocks: '33(i). Psittacidae ...' is row 33(i).
M `reviewed_bare_serial_rows_in_block` -- key source_bare_serial_row_blocks: a block of rows '161 Sanitary Worker ...',
  '162 Office Attendant ...' is cut at each row, each row N.

Ported by builder BZ (group 17 G-M, 16 Oct; group 20 O-V, 16 Oct 2026) from claude/agK4/tools/test_k4_rules_klm_DRAFT.py.
"""
import pytest

from nizam.corpus import segment as S

OWNER = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-15-delegated.json",
         "document_id": 4222, "question_id": "q2"}


def _b(i, text, y0, page=1, x0=72.0, x1=480.0):
    return {"id": i, "text": text, "page_no": page, "x0": x0, "x1": x1, "y0": y0, "page_height": 842.0}


def _body():
    return [_b(1, "1. \nShort title.-- This Act may be called the Test Act. \n", 40.0),
            _b(2, "2. \nDefinitions.-- In this Act, unless the context otherwise requires, game means a wild bird. \n", 60.0)]


# ---- K ------------------------------------------------------------------------------------------------------------
def _schedule_with_part():
    return _body() + [
        _b(10, "FIRST SCHEDULE \n", 100.0, page=2), _b(11, "[See Section 2 (d)] \n", 115.0, page=2),
        _b(12, "PART-I \n", 130.0, page=2), _b(13, "Wild birds which may be hunted on a licence. \n", 145.0, page=2),
        _b(14, "A: BIRDS \n", 160.0, page=2), _b(15, "Category one– \n", 175.0, page=2),
        _b(16, "1. All the ducks within the family anatidae Ten per day 1st October to 31st March \n", 190.0, page=2),
        _b(17, "2. Cotton teal Two per day Ditto \n", 205.0, page=2)]


CAPS = [{"source_block_id": 14, "caption": "A: BIRDS", "level": 1, "owner_decision": OWNER},
        {"source_block_id": 15, "caption": "Category one–", "level": 2, "owner_decision": OWNER}]


def _parent_of(seg, label):
    return next(n for n in seg.flatten() if n.label == label).parent


def test_K_caption_hangs_under_the_open_part():
    seg = S.segment(_schedule_with_part(), profile="unreleased-v4",
                    structural_overrides={"source_schedule_group_captions": CAPS})
    assert _parent_of(seg, "A: BIRDS").kind == "part" and _parent_of(seg, "A: BIRDS").label == "I"
    assert _parent_of(seg, "Category one–").label == "A: BIRDS"


def test_K_off_the_caption_hangs_on_the_schedule():
    profile = S.SEGMENTATION_PROFILES["unreleased-v4"] - {"schedule_group_caption_in_part"}
    S.SEGMENTATION_PROFILES["_k_off"] = profile
    try:
        seg = S.segment(_schedule_with_part(), profile="_k_off",
                        structural_overrides={"source_schedule_group_captions": CAPS})
        assert _parent_of(seg, "A: BIRDS").kind == "schedule"
    finally:
        del S.SEGMENTATION_PROFILES["_k_off"]


# ---- L ------------------------------------------------------------------------------------------------------------
def _inserted_rows():
    return _body() + [
        _b(10, "FIRST SCHEDULE \n", 100.0, page=2),
        _b(11, "33. Jorrden Courser (Cursorius bitorquatus) Two only per day Ditto \n", 120.0, page=2),
        _b(12, "33(i). Psittacidae (Parakeets) Three birds per day 1st August to 31 January \n", 140.0, page=2),
        _b(13, "34. Hawks Three birds per day 1st November to 31st March \n", 160.0, page=2)]


def test_L_opens_the_inserted_row():
    seg = S.segment(_inserted_rows(), profile="unreleased-v4",
                    structural_overrides={"source_inserted_row_blocks": [12]})
    assert "33(i)" in [n.label for n in seg.flatten()]


def test_L_inert_without_the_key():
    seg = S.segment(_inserted_rows(), profile="unreleased-v4")
    assert "33(i)" not in [n.label for n in seg.flatten()]


def test_L_refuses_a_block_without_an_inserted_label():
    with pytest.raises(ValueError):
        S.segment(_inserted_rows(), profile="unreleased-v4", structural_overrides={"source_inserted_row_blocks": [11]})


# ---- M ------------------------------------------------------------------------------------------------------------
def _bare_rows():
    return _body() + [
        _b(10, "SCHEDULE \n", 100.0, page=2),
        _b(11, "161 Sanitary Worker 2 Literate 18-30 Direct recruitment Vice Chancellor \n"
               "162 Office Attendant 2 Literate 18-30 Direct recruitment Vice Chancellor \n"
               "163 Mali/Baildar 2 Literate 18-30 Direct recruitment Vice Chancellor \n", 120.0, page=2)]


def test_M_cuts_a_block_of_bare_serial_rows():
    seg = S.segment(_bare_rows(), profile="unreleased-v4",
                    structural_overrides={"source_bare_serial_row_blocks": [11]})
    labels = [n.label for n in seg.flatten()]
    assert {"161", "162", "163"} <= set(labels)
    row = next(n for n in seg.flatten() if n.label == "162")
    assert row.text.startswith("Office Attendant")


def test_M_refuses_a_block_that_is_not_a_run_of_rows():
    blocks = _bare_rows()
    blocks[-1] = _b(11, "161 Sanitary Worker \n163 Mali/Baildar \n", 120.0, page=2)
    with pytest.raises(ValueError):
        S.segment(blocks, profile="unreleased-v4", structural_overrides={"source_bare_serial_row_blocks": [11]})
