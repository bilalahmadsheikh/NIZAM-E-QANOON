"""Rule T `reviewed_dotted_letter_item` (doc 3757: items printed 'b.',
'c.', a bare 'c.' line).

Ported by builder BZ, 15 Oct 2026, from claude/agJD/tools/test_dotted_letter_item_DRAFT.py, against the live module (export j group 7;
one combined full released A/B over T+J).
"""
import os
import pytest

from nizam.corpus import segment as S


def _b(i, text, y0):
    return {"id": i, "text": text, "page_no": 1, "x0": 72.0, "x1": 480.0, "y0": y0, "page_height": 842.0}


def _blocks():
    return [_b(1, "1. \nShort title: \nThese Regulations may be called the Test Regulations. \n", 40.0),
            _b(2, "2. \nRealization of the Subscriptions: \n \nb. Recovery of subscriptions shall be made from the "
                  "salary. \nc. When salary is drawn from any other source, the subscriber shall forward his dues. \n",
               100.0),
            _b(3, "3. \nAdvance from the fund: \n", 200.0),
            _b(4, "To purchase a conveyance. \nc.  \n", 230.0)]


def _clauses(seg):
    return [(n.kind, n.label, n.parent.label) for n in seg.flatten() if n.kind == "clause"]


def test_T_inert_without_the_key():
    assert _clauses(S.segment(_blocks(), profile="unreleased-v4")) == []


def test_T_opens_lettered_lines_and_a_bare_letter_line():
    seg = S.segment(_blocks(), profile="unreleased-v4",
                    structural_overrides={"source_dotted_letter_item_blocks": [2, 4]})
    got = _clauses(seg)
    assert ("clause", "b", "2") in got and ("clause", "c", "2") in got
    assert ("clause", "c", "3") in got
    b = [n for n in seg.flatten() if n.kind == "clause" and n.label == "b"][0]
    assert b.text.startswith("Recovery of subscriptions")


def test_T_unlisted_block_stays_text():
    seg = S.segment(_blocks(), profile="unreleased-v4", structural_overrides={"source_dotted_letter_item_blocks": [4]})
    assert not any(label in ("b",) for _k, label, _p in _clauses(seg))


def test_T_refuses_a_listed_block_without_a_lettered_line():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4", structural_overrides={"source_dotted_letter_item_blocks": [1]})


def test_T_needs_its_profile_rule():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v3", structural_overrides={"source_dotted_letter_item_blocks": [2]})
