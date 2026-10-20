"""S7 itemization: a materialised run records the itemized demotion count (17 Oct 2026, lead; agent BZ)."""
from types import SimpleNamespace

import pytest

import tools.materialize_multi_instrument as materializer


def test_settled_demotions_are_not_counted_as_candidates():
    # 3949 E0: two collisions, both settled by a recorded source reparent -> no candidate row, so 0 itemized
    seg = SimpleNamespace(repeated_labels_demoted=2)
    assert materializer.s7_itemization_detail(seg, []) == {
        "repeated_labels_demoted": 0, "repeated_labels_demoted_raw": 2}


def test_open_demotions_are_counted_one_per_candidate_row():
    # 3949 E2: seven open collisions, seven candidate rows
    seg = SimpleNamespace(repeated_labels_demoted=7)
    rows = [{"candidate_key": f"k{i}"} for i in range(7)]
    assert materializer.s7_itemization_detail(seg, rows)["repeated_labels_demoted"] == 7


def test_materializer_and_worker_write_the_same_s7_count():
    # the run detail field the criterion reads is the itemized count in both writers; neither writes the raw count there
    import inspect
    import nizam.workers.segment as worker
    assert '"repeated_labels_demoted":seg.repeated_labels_demoted' not in inspect.getsource(materializer)
    assert "**s7_itemization_detail(seg,inst.structural_decisions)" in inspect.getsource(materializer.main)
    assert '"repeated_labels_demoted": new_candidates' in inspect.getsource(worker)
