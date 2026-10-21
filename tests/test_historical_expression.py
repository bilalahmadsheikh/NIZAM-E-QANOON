"""A dated historical text, never current law (migration 0064; owner decision
decision-review-2026-10-12-k.json, document 4434, q3 'historical-expression';
schema review claude/schema-review-4434-q3.md).

The pure tests pin the migration text, the one version-writing statement, the
writers' refusals, the plan validator, the listed-path carry, the library SQL
and the API payload. The database tests (prefixed `test_db_`) need 0064
applied; they write inside one transaction, force the deferred guards with
SET CONSTRAINTS ... IMMEDIATE inside savepoints, and roll everything back
(the convention of tests/test_undated_instrument.py).
"""
from __future__ import annotations

import json
import re
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "infra/postgres/migrations/0064_historical_expression.sql"
CRITERIA = ROOT / "tools/audit/criteria.sql"
LEGAL_WRITE = ROOT / "nizam/storage/legal_write.py"
PLAN_4434 = ROOT / "tools/evidence/multi-instrument-plans/doc-4434.json"
EXPORT_K = ROOT / ".artifacts/decision-review/exports/decision-review-2026-10-12-k.json"
WINDOW = ("2016-06-08", "2017-01-07")
TODAY = date(2026, 10, 13)


def _inst(**kw):
    from nizam.shared.corpus_types import SegmentedInstrument
    base = dict(document_id=4434, source_observation_id=2810, sha256="0" * 64,
                jurisdiction="fed", kind="constitution", number=None, year=1973,
                short_title="CONSTITUTION OF PAKISTAN", long_title=None, preamble=None,
                source_url=None, as_at="2026-06-27", confidence=1.0)
    base.update(kw)
    return SegmentedInstrument(**base)


def _historical_manifest(**kw):
    manifest = {
        "expression_ordinal": 0, "start_block_id": 789886,
        "historical_validity": list(WINDOW),
        "current_source_observation_id": 507, "current_expression_ordinal": 0,
        "evidence": {"historical_basis": {"from": "x", "to": "y"},
                     "historical_owner_decision": {"export": "k.json", "document_id": 4434,
                                                   "question_id": "q3",
                                                   "choice": "historical-expression"}},
    }
    manifest.update(kw)
    return manifest


# --- pure: the migration ---------------------------------------------------------
def test_the_migration_pins_its_triggers_and_redefines_no_release_view():
    sql = MIGRATION.read_text(encoding="utf-8")
    body = sql.split("BEGIN;", 1)[1]
    assert "ADD COLUMN historical_validity           daterange" in body
    assert "current_source_observation_id bigint" in body
    assert "current_expression_ordinal    smallint" in body
    assert "NOT isempty(historical_validity)" in body
    assert "NOT lower_inf(historical_validity)" in body and "NOT upper_inf(historical_validity)" in body
    assert "->>'choice' = 'historical-expression'" in body
    assert body.count("CREATE CONSTRAINT TRIGGER") == 3
    assert body.count("DEFERRABLE INITIALLY DEFERRED") == 3
    for name in ("manifest_historical_versions_guard", "instrument_historical_versions_guard",
                 "manifest_historical_retention_guard"):
        assert f"CREATE CONSTRAINT TRIGGER {name}" in body
    # one function, both tables
    assert body.count("EXECUTE FUNCTION check_historical_versions()") == 2
    assert re.search(r"instrument_historical_versions_guard\s+AFTER INSERT OR UPDATE OF is_active, "
                     r"source_observation_id, expression_ordinal\s+ON instrument\s", body)
    assert "EXECUTE FUNCTION check_historical_retention()" in body
    assert "CREATE VIEW v_instrument_historical" in body
    view = body.split("CREATE VIEW v_instrument_historical", 1)[1].split(";", 1)[0]
    assert "materialized_instrument_id" not in view and "i.is_active" in view
    assert "v_release" not in body           # no release view redefined
    assert "DROP " not in body               # nothing dropped; no row rewritten


def test_the_audit_restricts_a7_and_adds_a13():
    sql = CRITERIA.read_text(encoding="utf-8")
    a7 = _block(sql, "A7")
    assert "v_instrument_historical" in a7 and "AS not_operative" in a7
    a13 = _block(sql, "A13")
    for name in ("historical", "bounded_unowned", "historical_outside", "historical_open",
                 "historical_target_unresolved", "historical_overlaps"):
        assert re.search(rf"AS {name}\b", a13), name
    assert "UNION ALL SELECT 'A13'" in sql
    assert len(re.findall(r"SELECT '([A-Z][0-9]+)'", sql)) == 36   # A14 added 20 Oct 2026 (0066)


# --- pure: the writer --------------------------------------------------------------
def test_one_statement_writes_every_version_at_both_sites():
    from nizam.storage import legal_write
    source = LEGAL_WRITE.read_text(encoding="utf-8")
    assert source.count("INSERT INTO provision_version") == 1
    assert "daterange(%s::date,%s::date,'[)')" in legal_write.VERSION_INSERT_SQL
    assert source.count('insert_version(cur, inst, ids[row["key"]], row)') == 2


class _Cursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))


@pytest.mark.parametrize("validity,bounds", [(None, ("2026-06-27", None)), (WINDOW, WINDOW)])
def test_the_helper_builds_the_window(validity, bounds):
    from nizam.storage import legal_write
    cur = _Cursor()
    row = {"text": "Article 1.", "operation": "original"}
    legal_write.insert_version(cur, _inst(version_validity=validity), "pid", row)
    sql, params = cur.calls[0]
    assert sql == legal_write.VERSION_INSERT_SQL
    assert params[:3] == ("pid", *bounds)


@pytest.mark.parametrize("bad", [("2017-01-07", "2016-06-08"), ("2016-06-08", "2016-06-08"),
                                 ("2016-06-08", None), ("08-06-2016", "2017-01-07")])
def test_an_empty_reversed_or_malformed_window_is_refused(bad):
    from nizam.storage import legal_write
    with pytest.raises(ValueError, match="version_validity"):
        legal_write.version_bounds(_inst(version_validity=bad))


def test_save_refuses_a_historical_window_before_touching_the_database():
    from nizam.storage import legal_write
    with pytest.raises(ValueError, match="current text only"):
        legal_write.save(_inst(version_validity=WINDOW))


def test_a_manifest_and_its_expression_agree():
    from nizam.storage.legal_write import check_historical_pair
    check_historical_pair(_inst(), {"evidence": {}})
    check_historical_pair(_inst(version_validity=WINDOW), _historical_manifest())
    with pytest.raises(ValueError, match="must agree"):
        check_historical_pair(_inst(), _historical_manifest())
    with pytest.raises(ValueError, match="must agree"):
        check_historical_pair(_inst(version_validity=WINDOW), {"evidence": {}})
    with pytest.raises(ValueError, match="must agree"):
        check_historical_pair(_inst(version_validity=("2016-06-08", "2017-03-30")),
                              _historical_manifest())
    with pytest.raises(ValueError, match="not itself"):
        check_historical_pair(_inst(version_validity=WINDOW),
                              _historical_manifest(current_source_observation_id=2810))
    with pytest.raises(ValueError, match="owner"):
        check_historical_pair(_inst(version_validity=WINDOW),
                              _historical_manifest(evidence={"historical_basis": {"a": 1}}))
    with pytest.raises(ValueError, match="names no current-expression"):
        check_historical_pair(_inst(), {"current_source_observation_id": 507,
                                        "current_expression_ordinal": 0, "evidence": {}})


def test_save_many_refuses_a_mismatched_pair_before_the_database():
    from nizam.storage import legal_write
    inst = _inst(version_validity=WINDOW, block_roles=[(1, "body", None, 3)])
    with pytest.raises(ValueError, match="must agree"):
        legal_write.save_many([inst], [{"id": 1, "text": "abc"}],
                              [{"expression_ordinal": 0, "evidence": {}}])


# --- pure: the plan validator ------------------------------------------------------
def _export(tmp_path, choice="historical-expression"):
    path = tmp_path / "decision-review-test.json"
    path.write_text(json.dumps({"answers": [
        {"document_id": 4434, "question_id": "q3", "choice": choice},
        {"document_id": 4434, "question_id": "q9", "choice": "other"}]}), encoding="utf-8")
    return str(path)


def _resolver(document_id, ordinal):
    known = {(4419, 0): {"instrument_id": "dbef70df", "source_observation_id": 507,
                         "earliest_version": "2026-06-19", "historical": False},
             (4400, 0): {"instrument_id": "self", "source_observation_id": 2810,
                         "earliest_version": "2026-06-19", "historical": False},
             (4401, 0): {"instrument_id": "old", "source_observation_id": 9,
                         "earliest_version": "2026-06-19", "historical": True},
             (4402, 0): {"instrument_id": "early", "source_observation_id": 10,
                         "earliest_version": "2016-12-01", "historical": False}}
    return known.get((document_id, ordinal))


def _plan(export, validity=None, current=None, **override):
    validity = validity if validity is not None else {
        "from": WINDOW[0], "to": WINDOW[1],
        "owner_decision": {"export": export, "document_id": 4434, "question_id": "q3"},
        "historical_basis": {"from": "22nd Amendment assent 8 June 2016",
                             "to": "23rd Amendment deemed 7 January 2017"}}
    validity = {**validity, **override}
    expression = {"ordinal": 0, "role": "primary", "title": "CONSTITUTION OF PAKISTAN",
                  "kind": "constitution", "year": 1973, "number": None,
                  "spans": [{"start_block_id": 1, "end_block_id": 2}],
                  "version_validity": validity,
                  "current_expression": current or {"document_id": 4419, "expression_ordinal": 0}}
    return {"schema": "nizam.multi_expression_plan/1", "document_id": 4434,
            "source_observation_id": 2810, "review_basis": "source_verified",
            "expressions": [expression]}


def _validate(plan):
    from tools.materialize_multi_instrument import validate_plan
    return validate_plan(plan, [{"id": 1}, {"id": 2}], 4434, 2810,
                         resolve_current=_resolver, today=TODAY)


def test_the_plan_validator_accepts_the_owners_window(tmp_path):
    spec = _validate(_plan(_export(tmp_path)))[0]["historical"]
    assert spec["version_validity"] == WINDOW
    assert spec["historical_owner_decision"]["choice"] == "historical-expression"
    assert spec["current_expression"] == {"document_id": 4419, "expression_ordinal": 0,
                                          "source_observation_id": 507,
                                          "instrument_id_at_review": "dbef70df"}


def test_a_plan_without_a_window_is_current_text(tmp_path):
    plan = _plan(_export(tmp_path))
    del plan["expressions"][0]["version_validity"], plan["expressions"][0]["current_expression"]
    assert _validate(plan)[0]["historical"] is None


@pytest.mark.parametrize("change,match", [
    (dict(owner_decision=None), "owner_decision must name"),
    (dict(to="2016-06-08"), "from < to <= today"),
    (dict(to="2016-01-01"), "from < to <= today"),
    (dict(to="2027-01-01"), "from < to <= today"),
    (dict(to="7 January 2017"), "not an ISO date"),
    (dict(historical_basis={}), "historical_basis"),
])
def test_the_plan_validator_refuses_a_bad_window(tmp_path, change, match):
    with pytest.raises(ValueError, match=match):
        _validate(_plan(_export(tmp_path), **change))


def test_the_plan_validator_refuses_another_choice(tmp_path):
    export = _export(tmp_path)
    plan = _plan(export, owner_decision={"export": export, "document_id": 4434, "question_id": "q9"})
    with pytest.raises(ValueError, match="not one of"):
        _validate(plan)


@pytest.mark.parametrize("current,match", [
    ({"document_id": 4419, "expression_ordinal": 5}, "does not resolve"),
    ({"document_id": 4434, "expression_ordinal": 0}, "names itself"),
    ({"document_id": 4400, "expression_ordinal": 0}, "resolves to itself"),
    ({"document_id": 4401, "expression_ordinal": 0}, "itself historical"),
    ({"document_id": 4402, "expression_ordinal": 0}, "inside the historical window"),
    ({"document_id": "4419", "expression_ordinal": 0}, "integer"),
])
def test_the_plan_validator_refuses_a_bad_target(tmp_path, current, match):
    with pytest.raises(ValueError, match=match):
        _validate(_plan(_export(tmp_path), current=current))


def test_a_window_and_a_target_come_together(tmp_path):
    plan = _plan(_export(tmp_path))
    del plan["expressions"][0]["current_expression"]
    with pytest.raises(ValueError, match="come together"):
        _validate(plan)


def test_the_4434_e0_validates_with_the_decided_window():
    from tools.materialize_multi_instrument import pending_owner_choices, validate_historical
    if not EXPORT_K.is_file():
        pytest.skip("export k is git-ignored and absent here")
    if not PLAN_4434.is_file():
        # 4434 is paused (doc-4434-DRAFT.json) pending the owner's boundary
        # corrections and the e0 end date; the e0 plan hunk is not applied yet.
        pytest.skip("paused pending owner: 4434 e0 plan not adopted")
    plan = json.loads(PLAN_4434.read_text(encoding="utf-8-sig"))
    e0 = next(e for e in plan["expressions"] if e["ordinal"] == 0)
    fields = validate_historical(e0, 0, 4434, 2810, resolve_current=_resolver, today=TODAY)
    assert fields["version_validity"] == ("2016-06-08", "2017-01-07")
    basis = fields["historical_basis"]
    assert basis["to"]["deeming_date"] == "2017-01-07" and basis["to"]["enactment_date"] == "2017-03-30"
    # decided (lead 15 Oct under the owner's delegation: the deeming date 2017-01-07); no owner choice is pending
    assert not pending_owner_choices([{"expression_ordinal": 0,
                                       "evidence": {"historical_basis": basis}}])


# --- pure: the listed-path carry ---------------------------------------------------
def _active(start=789886):
    return {0: {"ordinal": 0, "id": "m-1", "start_block_id": start, "valid_from": WINDOW[0],
                "valid_to": WINDOW[1], "current_source_observation_id": 507,
                "current_expression_ordinal": 0,
                "evidence": _historical_manifest()["evidence"]}}


def test_a_listed_replay_carries_the_window_forward():
    from nizam.storage.legal_write import check_historical_pair
    from tools.materialize_multi_instrument import carry_historical
    manifests = [{"expression_ordinal": 0, "start_block_id": 789886, "evidence": {}},
                 {"expression_ordinal": 1, "start_block_id": 900000, "evidence": {}}]
    insts = carry_historical([_inst(), _inst(expression_ordinal=1)], manifests, _active())
    assert insts[0].version_validity == WINDOW and insts[1].version_validity is None
    assert manifests[0]["historical_validity"] == list(WINDOW)
    assert manifests[0]["evidence"]["historical_carried_from_manifest_id"] == "m-1"
    assert "historical_validity" not in manifests[1]
    check_historical_pair(insts[0], manifests[0])


def test_a_listed_replay_refuses_rather_than_guess():
    from tools.materialize_multi_instrument import carry_historical
    with pytest.raises(ValueError, match="now starts at block"):
        carry_historical([_inst()], [{"expression_ordinal": 0, "start_block_id": 1,
                                      "evidence": {}}], _active())
    with pytest.raises(ValueError, match="not rebuilt"):
        carry_historical([_inst(expression_ordinal=1)],
                         [{"expression_ordinal": 1, "start_block_id": 5, "evidence": {}}], _active())


# --- pure: the library and the API --------------------------------------------------
class _Conn:
    def __init__(self, row=None):
        self.queries, self.row = [], row

    def execute(self, sql, args=None):
        self.queries.append((sql, args))
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return [self.row] if self.row else []


def test_every_instrument_read_carries_the_as_of_gate():
    from nizam.storage.library_read import HISTORICAL_GATE, LibraryRead
    day = date(2016, 6, 8)
    conn = _Conn()
    LibraryRead._instruments(conn, q="", jurisdiction="", kind="", after=None, limit=5, as_of=day)
    LibraryRead._instrument(conn, uuid.uuid4(), day)
    LibraryRead._instrument(conn, uuid.uuid4(), day, resolve_current=True)
    for sql, args in conn.queries:
        assert HISTORICAL_GATE in sql and "LEFT JOIN v_instrument_historical h" in sql
        assert args["as_of"] == day
    assert "c.source_observation_id = h.current_source_observation_id" in conn.queries[2][0]
    assert "current_source_observation_id" not in conn.queries[1][0]
    # children and provision inherit the gate through _instrument
    repo = LibraryRead.__new__(LibraryRead)
    repo._instrument = lambda *a, **k: None
    assert repo._children(_Conn({"id": 1}), uuid.uuid4(), parent=None, after=None, limit=5,
                          as_of=day) is None
    assert repo._provision(_Conn({"instrument_id": uuid.uuid4()}), uuid.uuid4(), as_of=day) is None


BASE = dict(title="CONSTITUTION OF PAKISTAN", kind="constitution", year=1973, jurisdiction="fed",
            status="unknown", source_url=None, document_id=4434, source_hash="0" * 64)


def test_the_instrument_payload_accepts_rows_without_the_new_keys():
    pytest.importorskip("fastapi")
    from nizam.api.library import Instrument
    plain = Instrument(id=uuid.uuid4(), **BASE).model_dump()
    assert (plain["historical"], plain["valid_from"], plain["valid_to"],
            plain["current_instrument_id"]) == (None, None, None, None)
    current = uuid.uuid4()
    historical = Instrument(id=uuid.uuid4(), **BASE, historical=True, valid_from=WINDOW[0],
                            valid_to=WINDOW[1], current_instrument_id=current).model_dump()
    assert historical["historical"] is True and historical["current_instrument_id"] == current


def test_a_closed_door_open_says_why():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from nizam.api.library import create_app

    class Plain:                     # a repository predating 0064: no historical_window
        def open(self): pass
        def close(self): pass
        def instrument(self, *a, **k): return None

    class Repository(Plain):
        def historical_window(self, _id): return {"valid_from": WINDOW[0], "valid_to": WINDOW[1]}

    with TestClient(create_app(Repository())) as client:
        response = client.get(f"/v1/law/instruments/{uuid.uuid4()}")
        detail = response.json()["detail"]
        assert response.status_code == 404
        assert "historical text" in detail and WINDOW[0] in detail and WINDOW[1] in detail
    with TestClient(create_app(Plain())) as client:
        response = client.get(f"/v1/law/instruments/{uuid.uuid4()}")
        assert response.status_code == 404 and "release view" in response.json()["detail"]


# --- the database ---------------------------------------------------------------------
def _block(sql: str, name: str) -> str:
    return sql.split(f"-- >>> {name} measures", 1)[1].split(f"-- <<< {name} measures", 1)[0] \
        .split("\n", 1)[1]


@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("""SELECT 1 FROM pg_attribute
                                WHERE attrelid = 'instrument_expression_manifest'::regclass
                                  AND attname = 'historical_validity'""")
                if cur.fetchone() is None:
                    pytest.skip("migration 0064 is not applied")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


ORDINAL = 96   # expression ordinals no document uses; every row is rolled back
GUARDS = ("manifest_historical_versions_guard, instrument_historical_versions_guard, "
          "manifest_historical_retention_guard")
DEFERRED = f"SET CONSTRAINTS {GUARDS} DEFERRED"
IMMEDIATE = f"SET CONSTRAINTS {GUARDS} IMMEDIATE"
RETIRE = ("UPDATE instrument_expression_manifest SET is_active = false, retired_at = now() "
          "WHERE source_observation_id = %s AND expression_ordinal = %s AND is_active")


class _Undo(Exception):
    pass


@contextmanager
def _scratch(conn):
    """A savepoint whose rows are rolled back even when every check passes."""
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(DEFERRED)
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


def _target(cur):
    """A quality-passed document to borrow provenance from, and the current
    expression 4419 e0 (canonical, released) as the target."""
    cur.execute("""
        SELECT i.document_id, i.source_observation_id, i.source_sha256,
               (SELECT min(b.id) FROM text_block b WHERE b.document_id = i.document_id)
          FROM instrument i
          JOIN v_document_quality_status q ON q.document_id = i.document_id
                                           AND q.overall_outcome = 'passed'
         WHERE i.is_active AND i.expression_ordinal = 0 AND i.duplicate_of IS NULL
           AND NOT EXISTS (SELECT 1 FROM instrument x
                            WHERE x.source_observation_id = i.source_observation_id
                              AND x.expression_ordinal IN (%s, %s))
           AND i.document_id NOT IN (4419, 4434)
         ORDER BY i.document_id LIMIT 1""", (ORDINAL, ORDINAL - 1))
    row = cur.fetchone()
    cur.execute("""SELECT id, source_observation_id, expression_ordinal FROM instrument
                    WHERE document_id = 4419 AND expression_ordinal = 0 AND is_active
                      AND duplicate_of IS NULL""")
    current = cur.fetchone()
    if row is None or current is None:
        pytest.skip("no instrument to borrow provenance from, or no 4419 e0")
    return dict(zip(("document", "observation", "sha", "block"), row),
                current_id=current[0], current=(current[1], current[2]))


def _instrument(cur, t, *, validity, ordinal=ORDINAL, title=None, text="Fixture article."):
    """An active instrument at `ordinal` with one provision and one version."""
    title = title or f"pytest historical {uuid.uuid4().hex}"
    cur.execute("""
        INSERT INTO instrument (jurisdiction, kind, number, year, short_title, source_sha256,
                                document_id, source_observation_id, expression_ordinal,
                                expression_role)
        VALUES ('fed', 'constitution', NULL, 1973, %s, %s, %s, %s, %s, 'embedded')
        RETURNING id""", (title, t["sha"], t["document"], t["observation"], ordinal))
    instrument = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO provision (instrument_id, parent_id, path, kind, label, ordinal,
                               first_page, last_page, first_block)
        VALUES (%s, NULL, %s::ltree, 'article', '1', 1, 1, 1, %s) RETURNING id""",
                (instrument, f"pytest_hx_{uuid.uuid4().hex}.art_1", t["block"]))
    provision = cur.fetchone()[0]
    cur.execute("""INSERT INTO provision_version (provision_id, validity, text_en, text_normalised)
                   VALUES (%s, %s::daterange, %s, %s)""", (provision, validity, text, text))
    return instrument, provision, title


def _decision(t, **kw):
    decision = {"export": "decision-review-2026-10-12-k.json", "document_id": t["document"],
                "question_id": "q3", "choice": "historical-expression"}
    decision.update(kw)
    return decision


def _manifest(cur, t, *, window, target=None, evidence=None, ordinal=ORDINAL):
    target = target if target is not None else t["current"]
    if evidence is None:
        evidence = {"historical_basis": {"from": "fixture", "to": "fixture"},
                    "historical_owner_decision": _decision(t)} if window else {}
    cur.execute("""
        INSERT INTO instrument_expression_manifest
            (source_observation_id, document_id, expression_ordinal, expression_role,
             start_block_id, end_block_id, detected_title, detected_kind, detected_year,
             review_basis, method, evidence, historical_validity,
             current_source_observation_id, current_expression_ordinal)
        VALUES (%s, %s, %s, 'embedded', %s, %s, 'pytest historical', 'constitution', 1973,
                'source_verified', 'pytest', %s, %s::daterange, %s, %s) RETURNING id""",
                (t["observation"], t["document"], ordinal, t["block"], t["block"],
                 json.dumps(evidence), window,
                 target[0] if window else None, target[1] if window else None))
    return cur.fetchone()[0]


GOOD = "[2016-06-08,2017-01-07)"


def test_db_the_window_shape_is_checked(conn):
    with conn.cursor() as cur:
        t = _target(cur)
    shape = "historical_shape"
    for window in ("empty", "(,)", "[2016-06-08,)", "(,2017-01-07)"):
        _refused(conn, lambda cur, w=window: _manifest(cur, t, window=w), shape)
    _refused(conn, lambda cur: _manifest(cur, t, window=GOOD, evidence={
        "historical_owner_decision": _decision(t)}), shape)                       # no basis
    _refused(conn, lambda cur: _manifest(cur, t, window=GOOD, evidence={
        "historical_basis": {"a": 1}, "historical_owner_decision": _decision(t, choice="other")}),
        shape)
    _refused(conn, lambda cur: _manifest(cur, t, window=GOOD, evidence={
        "historical_basis": {"a": 1},
        "historical_owner_decision": _decision(t, document_id=t["document"] + 1)}), shape)
    _refused(conn, lambda cur: _manifest(cur, t, window=GOOD,
                                         target=(t["observation"], ORDINAL)), shape)  # itself


def test_db_an_open_ended_version_under_a_window_is_refused_from_both_sides(conn):
    with conn.cursor() as cur:
        t = _target(cur)
    # manifest side: the materialiser's order, instrument first
    _refused(conn, lambda cur: (_instrument(cur, t, validity="[2026-06-27,)"),
                                _manifest(cur, t, window=GOOD)), "never written as open-ended")
    _refused(conn, lambda cur: (_instrument(cur, t, validity="[2016-01-01,2017-01-07)"),
                                _manifest(cur, t, window=GOOD)), "never written as open-ended")

    # instrument side: an exact-tree overlay copies the row and never touches the manifest
    def overlay(cur):
        old, _p, _t = _instrument(cur, t, validity=GOOD)
        _manifest(cur, t, window=GOOD)
        cur.execute(IMMEDIATE)
        cur.execute(DEFERRED)
        cur.execute("UPDATE instrument SET is_active = false, retired_at = now() WHERE id = %s", (old,))
        _instrument(cur, t, validity="[2026-06-27,)")
    _refused(conn, overlay, "never written as open-ended")
    with _scratch(conn) as cur:                                       # the good pair passes
        _instrument(cur, t, validity=GOOD)
        _manifest(cur, t, window=GOOD)
        cur.execute(IMMEDIATE)


def _pair(cur, t):
    instrument, _p, _t = _instrument(cur, t, validity=GOOD)
    manifest = _manifest(cur, t, window=GOOD)
    cur.execute(IMMEDIATE)
    cur.execute(DEFERRED)
    return instrument, manifest


def test_db_a_window_is_carried_or_withdrawn_never_dropped(conn):
    with conn.cursor() as cur:
        t = _target(cur)
    key = (t["observation"], ORDINAL)
    _refused(conn, lambda cur: (_pair(cur, t), cur.execute(RETIRE, key)), "read as current law")
    _refused(conn, lambda cur: (_pair(cur, t), cur.execute(RETIRE, key),
                                _manifest(cur, t, window=None)), "read as current law")
    _refused(conn, lambda cur: (_pair(cur, t), cur.execute(
        "DELETE FROM instrument_expression_manifest WHERE source_observation_id = %s "
        "AND expression_ordinal = %s", key)), "read as current law")
    with _scratch(conn) as cur:                   # a replay carries the window forward
        _pair(cur, t)
        cur.execute(RETIRE, key)
        _manifest(cur, t, window=GOOD)
        cur.execute(IMMEDIATE)
    with _scratch(conn) as cur:                   # an explicit withdrawal
        _instrument_id, manifest = _pair(cur, t)
        cur.execute(RETIRE, key)
        _manifest(cur, t, window=None, evidence={"historical_withdrawal": {
            "withdraws_manifest_id": str(manifest), "reason": "pytest withdrawal",
            "owner_decision": _decision(t, question_id="q9", choice="withdraw")}})
        cur.execute(IMMEDIATE)
    _refused(conn, lambda cur: _manifest(cur, t, window=GOOD, evidence={
        "historical_basis": {"a": 1}, "historical_owner_decision": _decision(t),
        "historical_withdrawal": {"withdraws_manifest_id": str(uuid.uuid4()), "reason": "x",
                                  "owner_decision": _decision(t)}}), "withdrawal_shape")


def test_db_the_exclusion_constraint_still_holds(conn):
    with conn.cursor() as cur:
        t = _target(cur)

    def overlap(cur):
        _i, provision, _t = _instrument(cur, t, validity=GOOD)
        cur.execute("""INSERT INTO provision_version (provision_id, validity, text_normalised)
                       VALUES (%s, '[2016-12-01,2017-01-07)'::daterange, '')""", (provision,))
    _refused(conn, overlap, "no_overlap")


def test_db_the_view_and_the_release_proof(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*) FROM v_instrument_historical h
                        JOIN instrument_expression_manifest m ON m.id = h.manifest_id
                       WHERE m.historical_validity IS NULL OR NOT m.is_active""")
        assert cur.fetchone() == (0,)
        cur.execute("""SELECT count(*) FROM v_instrument_historical h
                        WHERE NOT EXISTS (SELECT 1 FROM instrument_expression_manifest m
                                           WHERE m.source_observation_id = h.source_observation_id
                                             AND m.expression_ordinal = h.expression_ordinal
                                             AND m.is_active AND m.historical_validity IS NOT NULL)""")
        assert cur.fetchone() == (0,)
        cur.execute("SELECT pg_get_viewdef('v_release_instrument'::regclass)")
        assert "historical" not in cur.fetchone()[0]
        cur.execute("""SELECT duplicate_of FROM instrument
                        WHERE document_id = 4434 AND expression_ordinal = 0 AND is_active""")
        assert all(row[0] is None for row in cur.fetchall())   # 4434 e0 is not a duplicate of 4419


BOUNDARY = [(date(2016, 6, 7), False), (date(2016, 6, 8), True), (date(2017, 1, 6), True),
            (date(2017, 1, 7), False), (date.today(), False)]


def test_db_the_library_boundary_table(conn):
    pytest.importorskip("psycopg_pool")
    from psycopg.rows import dict_row
    from nizam.api.library import Instrument
    from nizam.storage.library_read import LibraryRead
    repo = LibraryRead.__new__(LibraryRead)
    with conn.cursor() as cur:
        t = _target(cur)
    with _scratch(conn) as cur:
        instrument, provision, title = _instrument(cur, t, validity=GOOD, text="Historical text.")
        _manifest(cur, t, window=GOOD)
        cur.execute("""INSERT INTO segmentation_run (document_id, source_observation_id, instrument_id,
                                                     segmenter, outcome)
                       VALUES (%s, %s, %s, 'pytest', 'segmented')""",
                    (t["document"], t["observation"], instrument))
        cur.execute(IMMEDIATE)
        conn.row_factory = dict_row
        try:
            for day, listed in BOUNDARY:
                rows = LibraryRead._instruments(conn, q=title, jurisdiction="", kind="", after=None,
                                                limit=5, as_of=day)
                opened = LibraryRead._instrument(conn, instrument, day, resolve_current=True)
                children = repo._children(conn, instrument, parent=None, after=None, limit=5, as_of=day)
                read = repo._provision(conn, provision, as_of=day)
                # all four reads agree
                assert ([r["id"] for r in rows] == [instrument]) is listed, day
                assert (opened is not None) is listed, day
                assert (children is not None) is listed, day
                assert (read is not None) is listed, day
                if listed:
                    assert read["text_en"] == "Historical text."
                    payload = Instrument(**opened).model_dump()
                    assert payload["historical"] is True
                    assert (payload["valid_from"], payload["valid_to"]) == WINDOW
                    assert payload["current_instrument_id"] == t["current_id"]
                    assert Instrument(**rows[0]).model_dump()["current_instrument_id"] is None
                # a plain instrument is unchanged at every date
                plain = LibraryRead._instrument(conn, t["current_id"], day)
                assert plain is not None and plain["historical"] is False and plain["valid_to"] is None
            assert LibraryRead._historical_window(conn, instrument) == {
                "valid_from": WINDOW[0], "valid_to": WINDOW[1]}
        finally:
            from psycopg.rows import tuple_row
            conn.row_factory = tuple_row


def _measures(conn, name):
    sql = CRITERIA.read_text(encoding="utf-8")
    block = _block(sql, name).strip()
    if name == "A7":
        query = ("WITH live_instrument AS (SELECT * FROM instrument WHERE is_active), "
                 "live_provision AS (SELECT p.* FROM provision p JOIN live_instrument i "
                 "ON i.id=p.instrument_id), live_version AS (SELECT v.* FROM provision_version v "
                 "JOIN live_provision p ON p.id=v.provision_id) SELECT " + block.rstrip(","))
    else:
        query = "SELECT 0 AS _\n" + block
    with conn.cursor() as cur:
        cur.execute(query)
        return dict(zip([d.name for d in cur.description], cur.fetchone()))


A13 = ("bounded_unowned", "historical_outside", "historical_open",
       "historical_target_unresolved", "historical_overlaps")


def _delta(before, after):
    return {k: after[k] - before[k] for k in after if k != "_"}


def _live_overlaps(conn, t, window):
    """Active manifests already in the corpus whose window over the same current expression overlaps `window`. Since
    16 Oct 2026 doc 4434 e0 (the 2016 historical text, released) points at 4419 e0 with the decided window GOOD, so a
    fixture over the same target overlaps it once (builder BZ: the fixture counts it rather than assuming none)."""
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*) FROM instrument_expression_manifest
                        WHERE is_active AND historical_validity IS NOT NULL
                          AND current_source_observation_id = %s AND current_expression_ordinal = %s
                          AND historical_validity && %s::daterange""", (t["current"][0], t["current"][1], window))
        return cur.fetchone()[0]


def test_db_audit_a13_and_a7_fixtures(conn):
    with conn.cursor() as cur:
        t = _target(cur)
    late = "[2016-12-01,2017-01-07)"
    live_good, live_late = _live_overlaps(conn, t, GOOD), _live_overlaps(conn, t, late)
    base13, base7 = _measures(conn, "A13"), _measures(conn, "A7")
    with _scratch(conn) as cur:                                        # a good fixture
        _instrument(cur, t, validity=GOOD)
        _manifest(cur, t, window=GOOD)
        cur.execute(IMMEDIATE)
        d13, d7 = _delta(base13, _measures(conn, "A13")), _delta(base7, _measures(conn, "A7"))
        assert d13 == {"historical": 1, **{k: 0 for k in A13}, "historical_overlaps": live_good}
        assert (d7["not_operative"], d7["versions"], d7["historical_versions"]) == (0, 0, 1)
    with _scratch(conn) as cur:                                        # bounded, no manifest
        _instrument(cur, t, validity=GOOD)
        assert _delta(base13, _measures(conn, "A13"))["bounded_unowned"] == 1
        d7 = _delta(base7, _measures(conn, "A7"))
        assert (d7["not_operative"], d7["historical_versions"]) == (1, 0)
    with _scratch(conn) as cur:                                        # outside the window
        _instrument(cur, t, validity="[2026-06-27,)")
        _manifest(cur, t, window=GOOD)
        assert _delta(base13, _measures(conn, "A13"))["historical_outside"] == 1
    with _scratch(conn) as cur:                                        # not yet closed
        _instrument(cur, t, validity="[2016-06-08,2999-01-01)")
        _manifest(cur, t, window="[2016-06-08,2999-01-01)")
        assert _delta(base13, _measures(conn, "A13"))["historical_open"] == 1
    with _scratch(conn) as cur:                                        # target does not resolve
        _instrument(cur, t, validity=GOOD)
        _manifest(cur, t, window=GOOD, target=(t["current"][0], 95))
        assert _delta(base13, _measures(conn, "A13"))["historical_target_unresolved"] == 1
    with _scratch(conn) as cur:                                        # two windows of one work overlap
        _instrument(cur, t, validity=GOOD)
        _manifest(cur, t, window=GOOD)
        _instrument(cur, t, validity=late, ordinal=ORDINAL - 1)
        _manifest(cur, t, window=late, ordinal=ORDINAL - 1)
        assert _delta(base13, _measures(conn, "A13"))["historical_overlaps"] == 1 + live_good + live_late
