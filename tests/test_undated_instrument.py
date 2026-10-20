"""An instrument with no year, only on the owner's 'undated' (migration 0063).

The pure tests pin the migration text and the API's rendering. The database
tests need 0063 applied; they write inside one transaction, force the deferred
guard with SET CONSTRAINTS ... IMMEDIATE inside savepoints, and roll
everything back (the convention of tests/test_heading_census_gate.py).
"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "infra/postgres/migrations/0063_undated_instrument.sql"


# --- pure ---------------------------------------------------------------------
def test_the_migration_keeps_the_range_checks_and_defers_the_guard():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "ALTER TABLE instrument ALTER COLUMN year DROP NOT NULL" in sql
    assert "ALTER COLUMN detected_year DROP NOT NULL" in sql
    assert "DROP CONSTRAINT" not in sql          # the 1800-2100 CHECKs stay
    body = sql.split("BEGIN;", 1)[1]
    assert body.count("CREATE CONSTRAINT TRIGGER") == 3
    assert body.count("DEFERRABLE INITIALLY DEFERRED") == 3
    assert ("AFTER INSERT OR UPDATE OF year, is_active, source_observation_id, "
            "expression_ordinal") in sql
    assert "AFTER UPDATE OF is_active, detected_year OR DELETE ON instrument_expression_manifest" in sql
    assert "COMMENT ON COLUMN instrument.year IS NULL" in sql      # the reversal names it
    assert "evidence->'year_owner_decision'->>'choice' = 'undated'" in sql
    assert "v_release" not in sql.split("BEGIN;", 1)[1]   # no release view redefined


def test_the_api_shows_undated_and_never_a_year_it_was_not_given():
    pytest.importorskip("fastapi")
    from nizam.api.library import Instrument
    base = dict(id=uuid.uuid4(), title="West Pakistan notification", kind="notification",
                jurisdiction="punjab", status="unknown", source_url=None, document_id=1973,
                source_hash="0" * 64)
    assert Instrument(**base, year=None).year_display == "undated"
    assert Instrument(**base, year=None).model_dump()["year"] is None
    assert Instrument(**base, year=1932).year_display == "1932"


def test_segmented_instrument_admits_no_year():
    import typing
    from nizam.shared.corpus_types import SegmentedInstrument
    hints = typing.get_type_hints(SegmentedInstrument)
    assert type(None) in typing.get_args(hints["year"])


# --- the database ---------------------------------------------------------------
@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("""SELECT attnotnull FROM pg_attribute
                                WHERE attrelid = 'instrument'::regclass AND attname = 'year'""")
                if cur.fetchone()[0]:
                    pytest.skip("migration 0063 is not applied")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


ORDINAL = 97   # an expression ordinal no document uses; every row is rolled back


def _target(cur):
    """An active document with a landed observation and two blocks."""
    cur.execute("""
        SELECT i.document_id, i.source_observation_id, i.source_sha256,
               i.jurisdiction::text,
               (SELECT min(b.id) FROM text_block b WHERE b.document_id = i.document_id),
               (SELECT max(b.id) FROM text_block b WHERE b.document_id = i.document_id)
          FROM instrument i
         WHERE i.is_active AND i.expression_ordinal = 0
           AND NOT EXISTS (SELECT 1 FROM instrument x
                            WHERE x.source_observation_id = i.source_observation_id
                              AND x.expression_ordinal = %s)
         ORDER BY i.document_id LIMIT 1""", (ORDINAL,))
    row = cur.fetchone()
    if row is None:
        pytest.skip("no instrument to borrow provenance from")
    return dict(zip(("document", "observation", "sha", "jurisdiction", "first", "last"), row))


def _instrument(cur, t, *, year, number=None, ordinal=ORDINAL):
    cur.execute("""
        INSERT INTO instrument (jurisdiction, kind, number, year, short_title,
                                source_sha256, document_id, source_observation_id,
                                expression_ordinal, expression_role)
        VALUES (%s, 'notification', %s, %s, 'pytest undated', %s, %s, %s, %s, 'embedded')
        RETURNING id""", (t["jurisdiction"], number, year, t["sha"], t["document"],
                          t["observation"], ordinal))
    return cur.fetchone()[0]


def _manifest(cur, t, *, year, evidence, instrument=None, ordinal=ORDINAL):
    cur.execute("""
        INSERT INTO instrument_expression_manifest
            (source_observation_id, document_id, expression_ordinal, expression_role,
             start_block_id, end_block_id, detected_title, detected_kind,
             detected_year, review_basis, method, evidence, materialized_instrument_id)
        VALUES (%s, %s, %s, 'embedded', %s, %s, 'pytest undated', 'notification',
                %s, 'source_verified', 'pytest', %s, %s)""",
                (t["observation"], t["document"], ordinal, t["first"], t["first"],
                 year, json.dumps(evidence), instrument))


def _undated(t, **kw):
    decision = {"export": "x.json", "document_id": t["document"],
                "question_id": "q3", "choice": "undated"}
    decision.update(kw)
    return {"year_status": "undated", "year_owner_decision": decision}


# SET CONSTRAINTS lasts to the end of the transaction, not the savepoint, so
# each block restores the deferral the materialiser relies on.
GUARDS = ("instrument_undated_guard, manifest_undated_retirement_guard, "
          "manifest_undated_instrument_guard")
DEFERRED = f"SET CONSTRAINTS {GUARDS} DEFERRED"
IMMEDIATE = f"SET CONSTRAINTS {GUARDS} IMMEDIATE"


class _Undo(Exception):
    pass


@contextmanager
def _scratch(conn):
    """A savepoint whose rows are rolled back even when every check passes."""
    try:
        with conn.transaction(), conn.cursor() as cur:
            yield cur
            raise _Undo
    except _Undo:
        pass


def _refused(conn, action, match):
    import psycopg
    with pytest.raises(psycopg.Error, match=match):
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(DEFERRED)
            action(cur)
            cur.execute(IMMEDIATE)


def test_a_manifest_is_undated_only_on_the_owners_undated(conn):
    with conn.cursor() as cur:
        t = _target(cur)
    check = "undated_by_owner"
    _refused(conn, lambda cur: _manifest(cur, t, year=None, evidence={}), check)
    _refused(conn, lambda cur: _manifest(cur, t, year=None,
                                         evidence=_undated(t, choice="other")), check)
    _refused(conn, lambda cur: _manifest(cur, t, year=None,
                                         evidence=_undated(t, document_id=t["document"] + 1)),
             check)
    _refused(conn, lambda cur: _manifest(cur, t, year=None,
                                         evidence=_undated(t, question_id=None)), check)
    _refused(conn, lambda cur: _manifest(cur, t, year=None,
                                         evidence={"year_owner_decision": _undated(t)[
                                             "year_owner_decision"]}), check)
    _refused(conn, lambda cur: _manifest(cur, t, year=1799, evidence={}), "detected_year_check")


def test_an_instrument_has_no_year_only_beside_an_undated_manifest(conn):
    with conn.cursor() as cur:
        t = _target(cur)
    # no manifest at all: refused when the deferred guard runs
    _refused(conn, lambda cur: _instrument(cur, t, year=None), "no year")
    # a manifest that states a year does not license a NULL one
    _refused(conn, lambda cur: (_manifest(cur, t, year=1956, evidence={}),
                                _instrument(cur, t, year=None)), "no year")
    # the owner's undated manifest does -- instrument first, as the materialiser writes
    with _scratch(conn) as cur:
        cur.execute(DEFERRED)
        instrument = _instrument(cur, t, year=None)
        _manifest(cur, t, year=None, evidence=_undated(t), instrument=instrument)
        cur.execute(IMMEDIATE)
        cur.execute("SELECT year FROM instrument WHERE id = %s", (instrument,))
        assert cur.fetchone() == (None,)
        cur.execute("SELECT count(*) FROM v_instrument_duplicates WHERE %s = ANY(instrument_ids)",
                    (instrument,))
        assert cur.fetchone() == (0,)


def test_a_stored_year_cannot_be_blanked(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM instrument WHERE is_active AND year IS NOT NULL "
                    "ORDER BY id LIMIT 1")
        target = cur.fetchone()[0]
    _refused(conn, lambda cur: cur.execute("UPDATE instrument SET year = NULL WHERE id = %s",
                                           (target,)), "no year")


def test_undated_instruments_sharing_a_number_are_not_a_duplicate_citation(conn):
    with conn.cursor() as cur:
        t = _target(cur)
    with _scratch(conn) as cur:
        cur.execute(DEFERRED)
        first = _instrument(cur, t, year=None, number="PYTEST-1")
        _manifest(cur, t, year=None, evidence=_undated(t), instrument=first)
        second = _instrument(cur, t, year=None, number="PYTEST-1", ordinal=ORDINAL + 1)
        _manifest(cur, t, year=None, evidence=_undated(t), instrument=second,
                  ordinal=ORDINAL + 1)
        cur.execute(IMMEDIATE)
        cur.execute("SELECT count(*) FROM v_instrument_duplicates WHERE number = 'PYTEST-1'")
        assert cur.fetchone() == (0,)


def _undated_pair(cur, t):
    """An undated instrument and the owner's undated manifest naming it."""
    cur.execute(DEFERRED)
    instrument = _instrument(cur, t, year=None)
    _manifest(cur, t, year=None, evidence=_undated(t), instrument=instrument)
    cur.execute(IMMEDIATE)
    cur.execute(DEFERRED)
    return instrument


RETIRE = ("UPDATE instrument_expression_manifest SET is_active = false, retired_at = now() "
          "WHERE source_observation_id = %s AND expression_ordinal = %s AND is_active")


def test_the_undated_manifest_cannot_be_retired_from_under_its_instrument(conn):
    with conn.cursor() as cur:
        t = _target(cur)
    key = (t["observation"], ORDINAL)
    _refused(conn, lambda cur: (_undated_pair(cur, t), cur.execute(RETIRE, key)),
             "no active undated manifest")
    _refused(conn, lambda cur: (_undated_pair(cur, t), cur.execute(
        "DELETE FROM instrument_expression_manifest WHERE source_observation_id = %s "
        "AND expression_ordinal = %s", key)), "no active undated manifest")
    # re-dating the manifest leaves the NULL-year instrument unvouched too
    _refused(conn, lambda cur: (_undated_pair(cur, t), cur.execute(
        "UPDATE instrument_expression_manifest SET detected_year = 1956 "
        "WHERE source_observation_id = %s AND expression_ordinal = %s", key)),
        "no active undated manifest|undated_by_owner")
    with _scratch(conn) as cur:
        # a re-materialisation: retire the manifest, insert its successor
        instrument = _undated_pair(cur, t)
        cur.execute(RETIRE, key)
        _manifest(cur, t, year=None, evidence=_undated(t), instrument=instrument)
        cur.execute(IMMEDIATE)
    with _scratch(conn) as cur:
        # retiring the instrument with its manifest is not an orphan either
        instrument = _undated_pair(cur, t)
        cur.execute(RETIRE, key)
        cur.execute("UPDATE instrument SET is_active = false, retired_at = now() "
                    "WHERE id = %s", (instrument,))
        cur.execute(IMMEDIATE)


def test_an_undated_manifest_cannot_name_a_dated_instrument(conn):
    with conn.cursor() as cur:
        t = _target(cur)

    def name_dated(cur):
        dated = _instrument(cur, t, year=1956)
        _manifest(cur, t, year=None, evidence=_undated(t), instrument=dated)
    _refused(conn, name_dated, "names instrument")


def test_reactivating_an_undated_instrument_is_judged_again(conn):
    with conn.cursor() as cur:
        t = _target(cur)
    key = (t["observation"], ORDINAL)

    def reactivate(cur):
        instrument = _undated_pair(cur, t)
        cur.execute(RETIRE, key)
        cur.execute("UPDATE instrument SET is_active = false, retired_at = now() "
                    "WHERE id = %s", (instrument,))
        cur.execute(IMMEDIATE)
        cur.execute(DEFERRED)
        cur.execute("UPDATE instrument SET is_active = true, retired_at = NULL "
                    "WHERE id = %s", (instrument,))
    _refused(conn, reactivate, "has no year")
