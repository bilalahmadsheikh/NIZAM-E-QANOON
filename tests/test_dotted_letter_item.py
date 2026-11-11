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


def test_reviewed_dotted_rows_survive_recursive_tail_before_half_paren_clause():
    labels='abcdefghijkl'
    rows='\n'.join(f'{c}. Book record {c}.'for c in labels)
    blocks=[_b(1,'62. Financial Rules.',40),
            _b(2,'(6) Accounting.\n'+rows+'\nb) Reconciliation.\nThe accounts shall be reconciled.',100)]
    seg=S.segment(blocks,profile='unreleased-v5',detect_contents=False,
                  structural_overrides={'source_dotted_letter_item_blocks':[2],
                                        'source_half_paren_clause_blocks':[2]})
    dotted=[n for n in seg.flatten()if n.kind=='clause'and(n.text or'').startswith('Book record')]
    assert [n.label for n in dotted]==list(labels)
    assert [n.text for n in dotted]==[f'Book record {c}.'for c in labels]
    assert any(n.kind=='clause'and n.label=='b'and'Reconciliation'in(n.text or'')for n in seg.flatten())


def test_recursive_dotted_cut_still_requires_reviewed_block_data():
    blocks=[_b(1,'62. Financial Rules.',40),
            _b(2,'(6) Accounting.\na. Cash book.\nb. Bank book.\nc. Ledger book.\nb) Reconciliation.',100)]
    seg=S.segment(blocks,profile='unreleased-v5',detect_contents=False,
                  structural_overrides={'source_half_paren_clause_blocks':[2]})
    assert not any(n.kind=='clause'and(n.text or'').startswith('Bank book')for n in seg.flatten())
