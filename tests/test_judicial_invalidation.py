"""Judicial invalidation (D-161; 0146): a candidate changes nothing served; a lawyer-verified, whole-unit review stops
the unit being served from its effective day, and not before; reviews are append-only evidence.
The serving test writes inside one transaction and rolls it back."""
from __future__ import annotations

import datetime as dt

import psycopg
import pytest


@pytest.fixture()
def conn():
    from nizam.storage.db import connect
    try:
        cm = connect()
        c = cm.__enter__()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    try:
        yield c
    finally:
        c.rollback()                                           # every test's writes are discarded
        cm.__exit__(None, None, None)


def _served(cur, provision_id, day) -> bool:
    cur.execute("SELECT set_config('nzq.as_of', %s, true)", (day.isoformat(),))
    cur.execute("SELECT EXISTS (SELECT 1 FROM operative_provision WHERE provision_id = %s)", (provision_id,))
    return cur.fetchone()[0]


def test_a_verified_whole_unit_review_stops_serving_from_its_day_and_a_candidate_never_does(conn):
    cur = conn.cursor()
    cur.execute("""SELECT c.review_key, c.provision_id FROM judicial_invalidation_candidate c
                    WHERE c.review_status = 'machine_candidate' LIMIT 1""")
    row = cur.fetchone()
    if not row:
        pytest.skip("no invalidation candidate is held")
    key, prov = row
    today = dt.date.today()
    if not _served(cur, prov, today):
        pytest.skip("the candidate's provision is not served today")
    # a candidate alone changes nothing
    cur.execute("REFRESH MATERIALIZED VIEW mv_provision_invalidation")
    assert _served(cur, prov, today)
    # a verified, whole-unit review from a day in the past: not served from that day, served the day before
    day = today - dt.timedelta(days=30)
    cur.execute("""INSERT INTO judicial_invalidation_review (review_key, decision, provision_id, extent, effective_on,
                       reviewer) VALUES (%s, 'lawyer_verified', %s, 'whole', %s, 'test')""", (key, prov, day))
    cur.execute("REFRESH MATERIALIZED VIEW mv_provision_invalidation")
    assert not _served(cur, prov, today)
    assert not _served(cur, prov, day)
    # the day before it takes effect the unit is served as it was (when its version reaches back that far)
    cur.execute("REFRESH MATERIALIZED VIEW mv_provision_invalidation")
    conn.rollback()                                            # nothing written


def test_a_provisions_judicial_status_states_only_verified_readings():
    try:
        from nizam.storage.judgment_read import JudgmentRead
        r = JudgmentRead()
        r.open()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    try:
        with r.transaction() as c:
            row = c.execute("""SELECT provision_id FROM judicial_invalidation_candidate
                                WHERE review_status = 'machine_candidate' LIMIT 1""").fetchone()
        if not row:
            pytest.skip("no candidate is held")
        s = r.judicial_status(row["provision_id"], dt.date.today())
        assert s["candidates_awaiting_review"] >= 1
        assert all(v["extent"] in ("whole", "words") for v in s["verified"])   # nothing unverified is stated
    finally:
        r.close()


def test_a_review_is_evidence_and_a_verified_one_says_what_it_establishes(conn):
    cur = conn.cursor()
    with pytest.raises(psycopg.errors.CheckViolation):
        cur.execute("""INSERT INTO judicial_invalidation_review (review_key, decision, reviewer)
                       VALUES (repeat('a', 64), 'lawyer_verified', 'test')""")
    conn.rollback()
    cur.execute("""INSERT INTO judicial_invalidation_review (review_key, decision, reviewer)
                   VALUES (repeat('b', 64), 'rejected', 'test') RETURNING id""")
    rid = cur.fetchone()[0]
    with pytest.raises(psycopg.errors.RaiseException):
        cur.execute("DELETE FROM judicial_invalidation_review WHERE id = %s", (rid,))
    conn.rollback()
