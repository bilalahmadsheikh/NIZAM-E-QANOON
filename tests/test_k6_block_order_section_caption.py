"""Agent K6's doc-4640 rules (segmenter group 33, 18 Oct 2026; owner decision-review-2026-10-18-4640.json),
from claude/agK6/work/test_k6_rules_lmn_DRAFT.py a1c3eb0b (K6's draft letters are not used):
  `reviewed_block_order` (key `source_block_order_moves`, q4 'reviewed-block-order'): a misbound page read in its
    printed order in the PARSER INPUT only;
  `section_group_caption` (key `source_section_group_captions`, q5 'section-group-captions'): a section's own
    printed divisions (roman level 1, lettered level 2), each holding its own (1), (2) ...;
  the reviewed reparent merge key carries source_ordinal (worker), so two reviewed specs naming the same
    (block, label, kind) at different ordinals do not read as one conflicting spec.
Pure: segment() over blocks; nizam.workers.segment.reviewed_structural_overrides for the merge key."""
import copy
import sys

import pytest

RULE_BO = "reviewed_block_order"
RULE_SGC = "section_group_caption"
KEY_BO = "source_block_order_moves"
KEY_SGC = "source_section_group_captions"


import nizam.corpus.segment as SEG  # noqa: E402
import nizam.workers.segment as W  # noqa: E402

OD = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-18-4640.json", "document_id": 4640,
      "question_id": "q5"}


def _b(i, text, page, y):
    return {"id": i, "page_no": page, "y0": y, "page_height": 792.0, "x0": 70.0, "x1": 560.0, "text": text}


# ---- reviewed_block_order: a misbound page -----------------------------------------------------------------------------------------
# page 1 (folio 103) ends rule 1(2); page 2 (folio 104) continues with (5); page 3 (folio 106) holds (3)-(4), bound last
MISBOUND = [
    _b(101, "103", 1, 40), _b(102, "1. (1) Payment from the Fund shall be made by cheque.", 1, 100),
    _b(103, "(2) Funds shall be drawn through cross cheques.", 1, 140),
    _b(201, "104", 2, 40), _b(202, "(5) All records shall be clear and self-contained.", 2, 100),
    _b(203, "2. Audit.-The accounts shall be audited annually.", 2, 140),
    _b(301, "106", 3, 40), _b(302, "(3) Cheques shall be written in indelible ink.", 3, 100),
    _b(303, "(4) No cheque shall be issued with corrections.", 3, 140),
]
MOVE = [{"first_block_id": 301, "last_block_id": 303, "after_block_id": 103}]


def _subs(seg, section):
    sec = next(n for n in seg.flatten() if n.kind == "section" and str(n.label) == section)
    return [str(c.label) for c in sec.children if c.kind == "subsection"]


def test_block_order_reads_the_misbound_page_in_printed_order():
    seg = SEG.segment(MISBOUND, profile="unreleased-v4", structural_overrides={KEY_BO: MOVE})
    assert _subs(seg, "1") == ["1", "2", "3", "4", "5"]


def test_block_order_keeps_the_extracted_evidence_untouched():
    before = copy.deepcopy(MISBOUND)
    SEG.segment(MISBOUND, profile="unreleased-v4", structural_overrides={KEY_BO: MOVE})
    assert MISBOUND == before                      # same list order, same dicts, same texts and pages
    seg = SEG.segment(MISBOUND, profile="unreleased-v4", structural_overrides={KEY_BO: MOVE})
    third = next(n for n in seg.flatten() if n.kind == "subsection" and str(n.label) == "3")
    assert third.first_page == 3 and third.first_block == 302   # the node still names its own block and page


def test_block_order_is_inert_without_the_key():
    on = SEG.segment(MISBOUND, profile="unreleased-v4")
    off = SEG.segment(MISBOUND, profile="default")
    assert _subs(on, "1") == _subs(off, "1")
    assert _subs(on, "1")[:3] == ["1", "2", "5"]    # the copy's order: the misbinding shows without the reading


@pytest.mark.parametrize("moves, why", [
    ([{"first_block_id": 302, "last_block_id": 303, "after_block_id": 103}], "not whole pages"),
    ([{"first_block_id": 301, "last_block_id": 303, "after_block_id": 102}], "not the last block of its page"),
    ([{"first_block_id": 301, "last_block_id": 999, "after_block_id": 103}], "not in the input"),
    ([{"first_block_id": 303, "last_block_id": 301, "after_block_id": 103}], "ends before it starts"),
    ([{"first_block_id": 301, "last_block_id": 303, "after_block_id": 302}], "inside the run"),
    (MOVE + [{"first_block_id": 301, "last_block_id": 303, "after_block_id": 203}], "moves a block twice"),
    ([{"first_block_id": 301, "last_block_id": 303}], "malformed"),
    ([], "non-empty"),
])
def test_block_order_fails_closed(moves, why):
    with pytest.raises(ValueError, match=why):
        SEG.segment(MISBOUND, profile="unreleased-v4", structural_overrides={KEY_BO: moves})


def test_block_order_needs_its_profile_rule():
    with pytest.raises(ValueError, match="needs profile rule"):
        SEG.segment(MISBOUND, profile="default", structural_overrides={KEY_BO: MOVE})


# ---- section_group_caption: a section's own printed divisions -----------------------------------------------------------------------
FUNDS = [
    _b(1, "38. FUNDS:", 1, 80),
    _b(2, "(1) There shall be a Fund called the Provincial Disaster Management Fund.", 1, 110),
    _b(3, "(2) All receipts of the Authority shall be credited to this Fund.", 1, 140),
    _b(4, "I. SOURCES OF FUND:", 1, 170),
    _b(5, "The Fund shall be financed from the following sources:-", 1, 200),
    _b(6, "(a) Grants made by the Government;\n(b) Donations received from any other source.", 1, 230),
    _b(7, "II. CONTROL OVER CASH:", 1, 260),
    _b(8, "a. REMITTANCE INTO ACCOUNT:", 1, 290),
    _b(9, "(1) All proceeds shall be credited to the bank account.", 1, 320),
    _b(10, "(2) Accounts of the funds shall be maintained by the Finance Wing.", 1, 350),
    _b(11, "b. PROCEDURE OF PAYMENT:", 1, 380),
    _b(12, "(1) The Director shall assist the Director General.", 1, 410),
    _b(13, "(2) The Director General shall be responsible for these procedures.", 1, 440),
    _b(14, "39. PUBLIC SERVANTS: Every employee of the Authority shall be deemed to be a public servant.", 1, 480),
]


def _cap(bid, caption, label, heading, level, od=OD):
    return {"source_block_id": bid, "caption": caption, "label": label, "heading": heading, "level": level,
            "owner_decision": od}


CAPS = [_cap(4, "I. SOURCES OF FUND:", "I", "SOURCES OF FUND", 1),
        _cap(7, "II. CONTROL OVER CASH:", "II", "CONTROL OVER CASH", 1),
        _cap(8, "a. REMITTANCE INTO ACCOUNT:", "a", "REMITTANCE INTO ACCOUNT", 2),
        _cap(11, "b. PROCEDURE OF PAYMENT:", "b", "PROCEDURE OF PAYMENT", 2)]


def _paths(seg):
    return [p for _n, p in SEG.assign_paths(seg, "t")]


def test_section_caption_captions_hold_their_own_numbered_items():
    seg = SEG.segment(FUNDS, profile="unreleased-v4", structural_overrides={KEY_SGC: CAPS})
    paths = _paths(seg)
    for p in ("t.s_38.ss_1", "t.s_38.ss_2", "t.s_38.pt_I__gc", "t.s_38.pt_I__gc.cl_a", "t.s_38.pt_II__gc",
              "t.s_38.pt_II__gc.pt_a__gc.ss_1", "t.s_38.pt_II__gc.pt_a__gc.ss_2",
              "t.s_38.pt_II__gc.pt_b__gc.ss_1", "t.s_38.pt_II__gc.pt_b__gc.ss_2", "t.s_39"):
        assert p in paths, p
    assert not any("_n" in p.rsplit(".", 1)[-1] for p in paths)          # no positional duplicates
    cap = next(n for n in seg.flatten() if n.kind == "part" and n.label == "I")
    assert cap.heading == "SOURCES OF FUND" and cap.parent.kind == "section"


def test_section_caption_is_inert_without_the_key():
    on = _paths(SEG.segment(FUNDS, profile="unreleased-v4"))
    off = _paths(SEG.segment(FUNDS, profile="default"))
    assert not any("__gc" in p for p in on)
    assert on == off


@pytest.mark.parametrize("caps, why", [
    ([_cap(5, "I. SOURCES OF FUND:", "I", "SOURCES OF FUND", 1)] + CAPS[1:], "not reached"),   # wrong block
    ([_cap(4, "I. SOURCES OF FUND:", "IV", "SOURCES OF FUND", 1)] + CAPS[1:], "lacks exact"),   # label not printed
    ([_cap(4, "I. SOURCES OF FUND:", "I", "USES OF FUND", 1)] + CAPS[1:], "lacks exact"),      # heading not printed
    ([_cap(8, "a. REMITTANCE INTO ACCOUNT:", "a", "REMITTANCE INTO ACCOUNT", 2)], "lacks exact"),  # no level 1 open
    ([CAPS[0], CAPS[1], CAPS[2], _cap(11, "b. PROCEDURE OF PAYMENT:", "a", "PROCEDURE OF PAYMENT", 2)],
     "lacks exact"),                                                                              # label repeated
    ([_cap(4, "I. SOURCES OF FUND:", "I", "SOURCES OF FUND", 1, od={"export": "x"})] + CAPS[1:], "lacks exact"),
])
def test_section_caption_fails_closed(caps, why):
    with pytest.raises(ValueError, match=why):
        SEG.segment(FUNDS, profile="unreleased-v4", structural_overrides={KEY_SGC: caps})


def test_section_caption_needs_its_profile_rule():
    with pytest.raises(ValueError, match="needs profile rule"):
        SEG.segment(FUNDS, profile="default", structural_overrides={KEY_SGC: CAPS})


def test_section_caption_refuses_a_caption_with_no_open_section():
    blocks = [_b(1, "I. SOURCES OF FUND:", 1, 80), _b(2, "1. Short title.-These rules may be called the T Rules.", 1, 110)]
    with pytest.raises(ValueError, match="lacks exact"):
        SEG.segment(blocks, profile="unreleased-v4", structural_overrides={KEY_SGC: [CAPS[0] | {"source_block_id": 1}]})


# ---- the reparent merge key carries source_ordinal -----------------------------------------------------------------
def _patch(spec):
    return {"id": "p", "evidence": {"structural_overrides": {"source_reparent_blocks": [spec]}}}


REP = {"source_block_id": 25, "source_label": "v", "source_kind": "clause", "parent_block_id": 24,
       "parent_label": "c", "parent_kind": "clause", "kind": "clause", "source_ordinal": 1}


def test_reparent_ordinal_key_two_ordinals_of_one_label_merge():
    other = dict(REP, source_ordinal=2, parent_block_id=25, parent_label="d")
    merged = W.reviewed_structural_overrides([], [_patch(REP), _patch(other)])
    assert len(merged["source_reparent_blocks"]) == 2


def test_reparent_ordinal_key_a_true_conflict_still_raises():
    other = dict(REP, parent_block_id=26)                  # same block, label, kind and ordinal; another parent
    with pytest.raises(ValueError, match="conflicting reviewed source reparent"):
        W.reviewed_structural_overrides([], [_patch(REP), _patch(other)])


# ---- key wiring ------------------------------------------------------------------------------------------------------
def test_keys_are_wired_in_worker_recorder_and_materializer():
    sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon/tools")
    import materialize_multi_instrument as MM
    import record_curation_patch as R
    for key in (KEY_BO, KEY_SGC):
        assert key in R.STRUCTURAL_KEYS
        assert key in MM.STRUCTURAL_PATCH_KEYS
        assert key in W._BZ_KEYED_LIST_KEYS
    ok_l, id_l = W._BZ_KEYED_LIST_KEYS[KEY_BO]
    ok_m, id_m = W._BZ_KEYED_LIST_KEYS[KEY_SGC]
    assert ok_l(MOVE[0]) and not ok_l({"first_block_id": 1}) and id_l == "first_block_id"
    assert ok_m(CAPS[0]) and not ok_m(dict(CAPS[0], level=3)) and id_m == "source_block_id"
