"""save_many() now carries accepted S7 judgements and guards the release like save() (lead decision, 12 Oct 2026).

Before, the multi-expression path (tools/materialize_multi_instrument.py) inserted fresh S7 candidates and carried
nothing, and it had no release gate: re-materialising doc 4497 dropped released e12 and e25 out of the release
(their accepted decisions came back pending) with no error. Both paths now share `_carry_prior_s7_acceptance` and
`_release_gate_failure`.
"""
import inspect

from nizam.storage import legal_write as LW


class Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.rows.pop(0)


CARRIED = {"candidate_id": "old-cand", "id": "old-adj", "resolution": "accept_non_citable",
           "review_basis": "source_verified", "rationale": "page read", "evidence": {"observed": "p68"}}


def inserts(cur):
    return [p for sql, p in cur.executed if "INSERT INTO segmentation_structural_adjudication" in sql]


def test_an_exact_match_is_carried_without_upgrade(monkeypatch):
    monkeypatch.setattr(LW, "_matching_prior_acceptance", lambda _c, _p, _n: dict(CARRIED))
    cur = Cursor()
    assert LW._carry_prior_s7_acceptance(cur, "prev", "new-cand") is True
    (row,) = inserts(cur)
    assert row[0] == "new-cand" and row[1] == "accept_non_citable" and row[2] == "source_verified"
    assert row[3] == "carried_by_exact_candidate_subtree/1"


def test_an_equivalent_match_is_carried_under_its_own_method(monkeypatch):
    monkeypatch.setattr(LW, "_matching_prior_acceptance",
                        lambda _c, _p, _n: dict(CARRIED, equivalence={"candidate": "exact"}))
    cur = Cursor()
    assert LW._carry_prior_s7_acceptance(cur, "prev", "new-cand") is True
    assert inserts(cur)[0][3] == "carried_by_equivalent_candidate_subtree/1"


def test_no_match_or_no_previous_tree_carries_nothing(monkeypatch):
    monkeypatch.setattr(LW, "_matching_prior_acceptance", lambda _c, _p, _n: None)
    cur = Cursor()
    assert LW._carry_prior_s7_acceptance(cur, "prev", "new-cand") is False
    assert LW._carry_prior_s7_acceptance(cur, None, "new-cand") is False
    assert inserts(cur) == []


def test_the_release_gate_reports_why_an_expression_would_drop_out():
    assert LW._release_gate_failure(Cursor([(True,)]), "iid", 4497) is None
    reason = LW._release_gate_failure(Cursor([(False,), (0, 3, 0, "passed")]), "iid", 4497)
    assert reason == "TOC=0, S7=3, boundary=0, quality=passed"


def test_save_many_uses_the_carry_and_the_gate():
    source = inspect.getsource(LW.save_many)
    assert "_carry_prior_s7_acceptance(" in source
    assert "_release_gate_failure(" in source and "released_before" in source
    assert "_carry_toc_gap_decisions(" in source
    # deferred until the block ledger exists: the subtree identity includes each provision's source blocks
    # (doc 4497, 13 Oct: carried inline, every accepted decision failed the identity and the gate rolled back)
    assert source.index("pending_carries.append(") < source.index("COPY provision_block")         < source.index("for previous_id, new_candidate_id, carried in pending_carries")
    assert "_carry_prior_s7_acceptance(" in inspect.getsource(LW.save)
