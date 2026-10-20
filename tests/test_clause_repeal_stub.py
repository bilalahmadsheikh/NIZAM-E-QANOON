"""Rule A `reviewed_clause_repeal_stub` (doc 3581 s.19 p18, owner export j
q2 'keep-both').

Ported by builder BZ, 15 Oct 2026, from claude/agJD/tools/test_clause_repeal_stub_DRAFT.py, against the live module (export j/l group 14;
one combined full released A/B over the 16 Oct groups).
"""
import os
import pytest

from nizam.corpus import segment as S

LIST = ("(i) \nPower-of-attorney to institute or defend a suit. \n(ii) \n[Rep. by the Amending Act, 1891 (XII of 1891)]. "
        "\n(iii) \nWritten statements called for by the Court. \n(iv) \n[Rep, by the Cantonments Act, 1889]. (v) [Rep. "
        "\nby A. O., 1949, Sch]. \n(v) \n[Rep. ibid].  \n(vi) \n[Rep. ibid]. \n(vii) \nProbate of a will. \n")


def _b(i, text, y0):
    return {"id": i, "text": text, "page_no": 1, "x0": 100.0, "x1": 520.0, "y0": y0, "page_height": 842.0}


def _blocks():
    return [_b(1, "18. \nThe Court may order the fee to be paid. \n", 40.0),
            _b(2, "19. \nNothing contained in this Act shall render the following documents chargeable:— \n", 80.0),
            _b(3, LIST, 120.0)]


def _clauses(seg):
    s19 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "19")
    return [c.label for c in s19.children if c.kind == "clause"]


def test_A_opens_every_stub_including_the_inline_one():
    got = _clauses(S.segment(_blocks(), profile="unreleased-v4",
                             structural_overrides={"source_clause_repeal_stub_blocks": [3]}))
    assert got == ["i", "ii", "iii", "iv", "v", "v", "vi", "vii"]


def test_A_inert_without_the_key():
    got = _clauses(S.segment(_blocks(), profile="unreleased-v4"))
    assert "ii" not in got and "vi" not in got


def test_A_refuses_a_listed_block_without_a_stub():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4", structural_overrides={"source_clause_repeal_stub_blocks": [1]})


def test_A_needs_its_profile_rule():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v3", structural_overrides={"source_clause_repeal_stub_blocks": [3]})
