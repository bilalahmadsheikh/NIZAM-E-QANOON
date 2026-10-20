"""Agent JF's rule D `reviewed_schedule_row_cells` (doc 3949 E3, the Schedule of posts; key source_schedule_row_cells).
Ported by builder BZ (group 27, 17 Oct 2026) from claude/agJF/test_jf_rule_d_DRAFT.py. Pure: segment() over hand-made
blocks shaped like doc 3949 pp20-21 (cells emitted column by column), under the DEFAULT profile."""
import pytest

from nizam.corpus.segment import segment


def _b(i, text, y, x, page=1):
    return {"id": i, "page_no": page, "y0": y, "page_height": 792.0, "x0": x, "x1": x + 70.0, "text": text}


BLOCKS = [
    _b(1, "1. \nShort title \n", 60.0, 72.0),
    _b(2, "These rules may be called the Service Rules 2006. \n", 80.0, 72.0),
    _b(3, "SCHEDULE \n", 120.0, 300.0),
    _b(4, "Name of the Department Functional Unit Name of the post Qualifications Age \n", 140.0, 72.0),
    # row 6: its Unit and Age cells come first, then the Department, then the post cell with the serial
    _b(10, "Punjab \n", 200.0, 154.0),
    _b(11, " \ndo \n30 \n45 \n \n", 200.0, 631.0),
    _b(12, "Education \nDepartment \n", 200.0, 72.0),
    _b(13, "6. Finance \nOfficer \n", 200.0, 230.0),
    _b(14, "MBA Finance from a recognized university. \n", 200.0, 393.0),
    # row 7: serial printed with no stop; its cells again come first
    _b(20, "Punjab \n", 300.0, 154.0),
    _b(21, " \ndo \n25 \n45 \n \n", 300.0, 631.0),
    _b(22, "Education \nDepartment \n", 300.0, 72.0),
    _b(23, "7Accounts \nOfficer \n", 300.0, 230.0),
    _b(24, "B.Com with eight years experience. \n", 300.0, 393.0),
]
SPEC = [{"row_block_id": 13, "row_prefix": "6. Finance", "label": "6", "cell_block_ids": [12, 10, 14, 11]},
        {"row_block_id": 23, "row_prefix": "7Accounts", "label": "7", "cell_block_ids": [22, 20, 24, 21]}]


def _rows(seg):
    sch = next(n for n in seg.flatten() if n.kind == "schedule")
    return {c.label: c for c in sch.children}


def test_rows_gather_their_own_cells_and_open_at_a_stopless_serial():
    rows = _rows(segment(BLOCKS, structural_overrides={"source_schedule_row_cells": SPEC}))
    assert set(rows) == {"6", "7"}
    six = " ".join((rows["6"].text or "").split())
    seven = " ".join((rows["7"].text or "").split())
    assert six.startswith("Finance Officer Education Department Punjab MBA Finance")
    assert six.endswith("do 30 45")
    assert seven.startswith("Accounts Officer Education Department Punjab B.Com")
    assert seven.endswith("do 25 45")
    assert "B.Com" not in six and "25" not in six


def test_inert_without_the_key():
    rows = _rows(segment(BLOCKS))
    assert "7" not in rows
    assert "Accounts" in (rows["6"].text or "")


def test_a_cell_on_another_page_fails_closed():
    blocks = BLOCKS + [_b(30, "Foundation \n", 60.0, 154.0, page=2)]
    spec = [dict(SPEC[0], cell_block_ids=[12, 10, 14, 11, 30]), SPEC[1]]
    with pytest.raises(ValueError):
        segment(blocks, structural_overrides={"source_schedule_row_cells": spec})


def test_a_prefix_not_printed_fails_closed():
    spec = [dict(SPEC[0], row_prefix="6. Accounts"), SPEC[1]]
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_schedule_row_cells": spec})


def test_a_cell_named_twice_fails_closed():
    spec = [SPEC[0], dict(SPEC[1], cell_block_ids=[22, 20, 24, 21, 12])]
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_schedule_row_cells": spec})


def test_a_row_outside_a_schedule_fails_closed():
    spec = [{"row_block_id": 1, "row_prefix": "1. \nShort title", "label": "1", "cell_block_ids": []}]
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_schedule_row_cells": spec})


def test_the_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from nizam.corpus.segment import SEGMENTATION_PROFILES
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    key = "source_schedule_row_cells"
    assert key in STRUCTURAL_KEYS and key in STRUCTURAL_PATCH_KEYS
    assert not any(n in rules for rules in SEGMENTATION_PROFILES.values()
                   for n in ("reviewed_schedule_row_cells", "bare_half_paren_subrule_reviewed_default",
                             "form_code_opener_reviewed_default"))
    row = {"row_block_id": 9, "row_prefix": "7Accounts Officer", "label": "7", "cell_block_ids": [5, 6]}
    merged = W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: [row]}}},
                                                  {"evidence": {"structural_overrides": {key: [row]}}}])
    assert merged[key] == [row]
    with pytest.raises(ValueError, match=key):
        W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: [dict(row, label="A")]}}}])
