"""Rule J `schedule_paragraph_printed_heading` (doc 3611 Schedule para 5,
owner export j q3 'printed'; doc 3901 Schedule items 2, 6, 8, 12-15, owner export l q2 'margin').

Ported by builder BZ, 15 Oct 2026, from claude/agJD/tools/test_schedule_paragraph_heading_DRAFT.py, against the live module (export j group 7;
one combined full released A/B over T+J).
"""
import os
import pytest

from nizam.corpus import segment as S

OWNER = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-14-l.json", "document_id": 3901,
         "question_id": "q2"}


def _b(i, text, y0, page=1, x0=72.0):
    return {"id": i, "text": text, "page_no": page, "x0": x0, "x1": 480.0, "y0": y0, "page_height": 842.0}


def _blocks():
    return [_b(1, "1. \nShort title. \nThis Act may be called the Test Act. \n", 40.0),
            _b(2, "2. \nAmendments. \nThe said Act is amended as set out in the Schedule. \n", 100.0),
            _b(3, "THE SCHEDULE. \n", 40.0, page=2),
            _b(4, "1. \nAfter clause (e) of section 3 of the said Act the following shall be deemed to be inserted. \n",
               80.0, page=2),
            _b(5, "2. \nAfter section 17 of the said Act the following shall be deemed to be inserted, namely: - \n",
               140.0, page=2),
            _b(6, "Transfer of land to \ntrust. \n", 140.0, page=2, x0=414.0)]


def _sched_items(seg):
    return {n.label: n for n in seg.flatten() if n.kind == "clause" and n.parent is not None
            and n.parent.kind == "schedule"}


def _spec_for(label="2", block=6, heading="Transfer of land to trust.", owner=OWNER):
    return {"source_schedule_paragraph_headings": [{"label": label, "source_block_id": block, "heading": heading,
                                                    "owner_decision": owner}]}


def test_J_fixture_has_schedule_items():
    items = _sched_items(S.segment(_blocks(), profile="unreleased-v4"))
    assert {"1", "2"} <= set(items)


def test_J_inert_without_the_key():
    items = _sched_items(S.segment(_blocks(), profile="unreleased-v4"))
    assert items["2"].heading in (None, "")


def test_J_heads_the_named_item_only():
    items = _sched_items(S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_spec_for()))
    assert items["2"].heading == "Transfer of land to trust."
    assert items["1"].heading in (None, "")


def test_J_refuses_words_not_printed_in_the_block():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_spec_for(heading="Transfer of land."))


def test_J_refuses_a_label_with_no_schedule_item():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_spec_for(label="9"))


def test_J_refuses_a_malformed_owner_citation():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4",
                  structural_overrides=_spec_for(owner={"export": "x.json", "document_id": 3901}))


def test_J_needs_its_profile_rule():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v3", structural_overrides=_spec_for())
