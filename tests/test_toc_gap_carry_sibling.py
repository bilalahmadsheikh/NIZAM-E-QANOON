"""A contents-gap decision naming a sibling expression follows it through a multi-expression replay (doc 3782).

Doc 3782 E0's contents rows 24-25 are decided `other_instrument`, naming E1. A replay of the document retires every
expression in one transaction, so the named instrument is no longer active when E0's decisions are carried; before
this, the carry refused them and the identical rebuild failed the release gate. The pure tests pin the sibling
branch of nizam.storage.legal_write._carried_gap_target, which needs no database."""
from nizam.storage.legal_write import _carried_gap_target

ROW = {"resolution": "other_instrument", "evidence": {"other_instrument_id": "old-e1"}}


def test_a_decision_naming_a_replaced_sibling_follows_it():
    ok, rewrites = _carried_gap_target(None, ROW, "old-e0", "new-e0", {"old-e0": "new-e0", "old-e1": "new-e1"})
    assert ok
    assert rewrites == {"other_instrument_id_before_replay": "old-e1", "other_instrument_id": "new-e1"}


def test_a_sibling_that_resolves_to_the_tree_itself_is_refused():
    assert _carried_gap_target(None, ROW, "old-e0", "new-e0", {"old-e1": "new-e0"}) == (False, {})


def test_other_resolutions_ignore_the_sibling_map():
    row = {"resolution": "parser_defect", "evidence": {"defect_class": "x"}}
    assert _carried_gap_target(None, row, "a", "b", {"a": "b"}) == (True, {})
