"""Agent K6's reparent merge-key fix (group 33, 18 Oct 2026; docs 4575 p2, 4640 p25): reviewed_structural_overrides keys a
reviewed source reparent by (source_block_id, source_label, source_kind, source_ordinal). Pure."""
import pytest

import nizam.workers.segment as W


def _rep(ordinal=None, parent=20, label="i"):
    item = {"source_block_id": 10, "parent_block_id": parent, "kind": "clause", "source_label": label,
            "source_kind": "clause"}
    if ordinal is not None:
        item["source_ordinal"] = ordinal
    return item


def _merge(*items):
    patches = [{"evidence": {"structural_overrides": {"source_reparent_blocks": [it]}}} for it in items]
    return W.reviewed_structural_overrides([], patches)["source_reparent_blocks"]


def test_two_ordinals_of_one_label_in_one_block_are_two_specs():
    merged = _merge(_rep(2, parent=21), _rep(3, parent=22))
    assert sorted((m["source_ordinal"], m["parent_block_id"]) for m in merged) == [(2, 21), (3, 22)]


def test_same_ordinal_different_parent_still_conflicts():
    with pytest.raises(ValueError, match="conflicting reviewed source reparent"):
        _merge(_rep(2, parent=21), _rep(2, parent=22))


def test_identical_specs_without_ordinal_merge_to_one():
    assert len(_merge(_rep(), _rep())) == 1


def test_specs_without_ordinal_and_different_parents_still_conflict():
    with pytest.raises(ValueError, match="conflicting reviewed source reparent"):
        _merge(_rep(parent=21), _rep(parent=22))
