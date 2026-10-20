"""A same-blob twin observation is rebuilt from its canonical observation's plan (S8; materializer allowance).

The pure test pins the gate in prepare_from_plan; the database tests read the live S8 twins (observations 2233 and
2507 of document 3392, whose plan names 2224) and skip when the corpus is not reachable."""
from __future__ import annotations

import inspect

import pytest

import tools.materialize_multi_instrument as materializer


def test_only_a_twin_may_borrow_a_plan():
    source = inspect.getsource(materializer.prepare_from_plan)
    assert "twin_observation_problem(document_id,observation,plan.get(\"source_observation_id\"))" in source
    assert source.index("twin_observation_problem") < source.index("validate_plan(")
    gate = inspect.getsource(materializer.twin_observation_problem)
    assert "duplicate_of IS NULL" in gate and "o.sha256 = d.sha256" in gate


def _skip_unless_reachable():
    try:
        from nizam.storage.db import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM instrument WHERE document_id=3392 AND is_active")
            if cur.fetchone()[0] == 0:
                pytest.skip("document 3392 is not in this corpus")
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def test_the_canonical_observation_is_not_a_twin_of_itself_and_a_stranger_is_refused():
    _skip_unless_reachable()
    # the canonical observation's own instruments are not duplicates: it may never be rebuilt as a twin
    assert "recorded duplicate" in (materializer.twin_observation_problem(3392, 2224, 2233) or "")
    # an observation of another file is refused
    assert "own file" in (materializer.twin_observation_problem(3392, 616, 2224) or "")


def test_a_recorded_duplicate_twin_is_admitted():
    _skip_unless_reachable()
    assert materializer.twin_observation_problem(3392, 2233, 2224) is None
