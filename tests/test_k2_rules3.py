"""Agent K2's rule `reviewed_table_close` (doc 4489 Schedules; docs/SEGMENTATION-PROFILES.md). Data-gated.

Run against the live module once ported (copy to tests/); before the port, against the prototype:
    K2_RULE=<scratchpad>/agK2-rule3.py ./.venv/bin/python -m pytest <this file>
"""
import importlib.util
import os
import sys

import pytest

if os.environ.get("K2_RULE"):
    _spec = importlib.util.spec_from_file_location("k2_rule3_t", os.environ["K2_RULE"])
    _R = importlib.util.module_from_spec(_spec)
    sys.modules["k2_rule3_t"] = _R
    _spec.loader.exec_module(_R)
    W = _R.load_worker("k2_test_worker3")
    S = sys.modules["agk2_segment3"]
else:
    from nizam.corpus import segment as S
    import nizam.workers.segment as W


def _patch(**overrides):
    return {"evidence": {"structural_overrides": overrides}}


def blocks(*texts):
    return [{"id": 100 + i, "text": t, "page_no": 1, "y0": 100 + 40 * i, "page_height": 800, "x0": 50, "x1": 500}
            for i, t in enumerate(texts)]


TABLE = blocks("1. Short title.- This Act may be called the Test Act.",
               "2. Rates.- The tax shall be charged at the rates in the Table below:-", "TABLE",
               "1. Where the income does not exceed one lakh rupees, five per cent.",
               "2. Where the income exceeds one lakh rupees, ten per cent.",
               "3. Exemptions.- Nothing in this Act applies to the property of the State.")


def tops(seg):
    return [n for n in seg.flatten() if n.parent is not None and n.parent.kind == "instrument"]


def test_table_close_ends_the_rows_before_the_next_provision():
    on = S.segment(TABLE, structural_overrides={"source_table_close_blocks": [
        {"source_block_id": 105, "owner_block_id": None}]})
    assert [n.label for n in tops(on) if n.kind == "section"] == ["1", "2", "3"]
    off = S.segment(TABLE)
    assert [n.label for n in tops(off) if n.kind == "section"] == ["1", "2"]   # '3.' was the Table's third row


def test_table_close_fails_closed():
    for bad in ({"source_block_id": 105}, {"source_block_id": "105", "owner_block_id": None},
                {"source_block_id": 105, "owner_block_id": None, "source_prefix": "short"}):
        with pytest.raises(ValueError, match="malformed"):
            S.segment(TABLE, structural_overrides={"source_table_close_blocks": [bad]})
    with pytest.raises(ValueError, match="not reached"):
        S.segment(TABLE, structural_overrides={"source_table_close_blocks": [{"source_block_id": 999, "owner_block_id": None}]})
    with pytest.raises(ValueError, match="opened 0 provision"):
        S.segment(TABLE, structural_overrides={"source_table_close_blocks": [{"source_block_id": 105, "owner_block_id": 102}]})


def test_worker_unites_table_close_entries():
    e = {"source_block_id": 105, "owner_block_id": None}
    assert W.reviewed_structural_overrides([], [_patch(source_table_close_blocks=[e]),
                                                _patch(source_table_close_blocks=[e])])["source_table_close_blocks"] == [e]
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        W.reviewed_structural_overrides([], [_patch(source_table_close_blocks=[dict(e, owner_block_id="x")])])
