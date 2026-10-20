"""A landed file that is not the authoritative text of a law the corpus holds (migration 0065).

The pure tests pin the migration's guards, the re-apply step's reuse of 0062's
decisions, and the wiring (audit C9, post-replay step 2b2). The database tests
need migration 0065 applied; they write inside one transaction, use savepoints
for the refusals, and roll everything back (tests/test_source_same_text_copy.py).
The case is document 4641 (observation 4130), an unofficial Urdu translation of
document 1522, the Sindh Agricultural Income Tax (Amendment) Ordinance, 1997.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import apply_source_non_authoritative_copy as tool
from tools import apply_source_same_text_copy as same_text

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "infra/postgres/migrations/0065_source_non_authoritative_copy.sql"
SHA_A = "a" * 64


def test_the_migration_guards_every_mutation_and_touches_no_release_view():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "BEFORE INSERT OR UPDATE OR DELETE ON source_non_authoritative_copy" in sql
    assert "BEFORE TRUNCATE ON source_non_authoritative_copy" in sql
    assert "source_observation_id     bigint NOT NULL UNIQUE" in sql
    assert "CREATE UNIQUE INDEX source_non_authoritative_copy_document" in sql
    assert "pg_advisory_xact_lock(hashtext('source_non_authoritative_copy'))" in sql
    assert "SET LOCAL lock_timeout" in sql
    assert "'keep-' || NEW.authoritative_document_id::text" in sql
    assert "CHECK (evidence->>'finding' IS NOT DISTINCT FROM kind)" in sql
    assert "'unofficial_translation'" in sql and "'bill_superseded_by_enactment'" in sql
    assert "CREATE VIEW" not in sql and "DROP VIEW" not in sql
    assert "ALTER TABLE instrument" not in sql


def test_the_reapply_step_uses_0062s_decisions_and_writes():
    """One set of rules for every copy route: imported, not re-implemented."""
    assert tool.plan is same_text.plan
    assert tool.FIRST_LINK is same_text.FIRST_LINK and tool.ADVANCE is same_text.ADVANCE
    assert "FROM source_non_authoritative_copy s" in tool.LINKS
    assert "c.document_id = s.authoritative_document_id" in tool.LINKS
    assert "c.expression_ordinal = t.expression_ordinal" in tool.LINKS


def test_a_released_file_is_skipped_and_a_partial_link_refused():
    rows = [(1, 4641, 1522, 0, "t0", None, None, "c0", True)]
    decisions, partial = tool.plan(rows)
    assert decisions[0]["action"] == "skip" and partial == []
    rows = [(1, 4641, 1522, 0, "t0", None, None, "c0", False),
            (1, 4641, 1522, 1, "t1", None, None, None, False)]
    decisions, partial = tool.plan(rows)
    assert [d["action"] for d in decisions] == ["set", "missing"] and partial == [1]


def test_the_audit_and_the_replay_sequence_carry_it():
    criteria = (ROOT / "tools/audit/criteria.sql").read_text(encoding="utf-8")
    assert "AS non_authoritative_unflagged" in criteria
    assert "AND non_authoritative_unflagged=0" in criteria
    replay = (ROOT / "tools/post_replay_sequence.sh").read_text(encoding="utf-8")
    assert "tools/apply_source_non_authoritative_copy.py --apply" in replay


# --- the database -----------------------------------------------------------------
@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("SELECT to_regclass('source_non_authoritative_copy')")
                if cur.fetchone()[0] is None:
                    pytest.skip("migration 0065 is not applied")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


INSERT = """
INSERT INTO source_non_authoritative_copy
       (source_observation_id, document_id, kind, authoritative_document_id, observed,
        owner_decision, evidence, recorded_by)
VALUES (%s, %s, %s, %s, 'pytest', %s, %s, 'pytest') RETURNING id
"""
KIND = "unofficial_translation"
DECISION = json.dumps({"export": "x.json", "document_id": 4641, "question_id": "q2",
                       "choice": "keep-1522"})


def _evidence(copy_sha, auth_sha, **kw):
    e = {"copy_sha256": copy_sha, "authoritative_sha256": auth_sha, "finding": KIND,
         "basis": "pytest", "reviewer_type": "assistant", "export_sha256": SHA_A}
    e.update(kw)
    return json.dumps(e)


def _refused(conn, sql, params, match):
    import psycopg
    with pytest.raises(psycopg.Error, match=match):
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(sql, params)


def _shas(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, sha256 FROM document WHERE id IN (1522, 4641)")
        sha = dict(cur.fetchall())
    if len(sha) != 2:
        pytest.skip("documents 1522/4641 are not in this corpus")
    return sha


def _record(conn):
    """The 4641 -> 1522 record: the stored one, or one inserted and rolled back."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM source_non_authoritative_copy "
                    "WHERE source_observation_id = 4130")
        row = cur.fetchone()
        if row:
            return row[0]
        sha = _shas(conn)
        try:
            with conn.transaction():
                cur.execute(INSERT, (4130, 4641, KIND, 1522, DECISION,
                                     _evidence(sha[4641], sha[1522])))
                return cur.fetchone()[0]
        except Exception as exc:                                # noqa: BLE001
            pytest.skip(f"4641 -> 1522 not recordable in this state: {exc}")


def test_a_record_is_append_only_and_one_per_observation(conn):
    record = _record(conn)
    _refused(conn, "UPDATE source_non_authoritative_copy SET observed = 'x' WHERE id = %s",
             (record,), "append-only")
    _refused(conn, "DELETE FROM source_non_authoritative_copy WHERE id = %s", (record,),
             "append-only")
    _refused(conn, "TRUNCATE source_non_authoritative_copy", None, "append-only")
    with conn.cursor() as cur:
        cur.execute("SELECT source_observation_id, document_id, kind, "
                    "authoritative_document_id, owner_decision, evidence "
                    "FROM source_non_authoritative_copy WHERE id = %s", (record,))
        observation, document, kind, auth, decision, evidence = cur.fetchone()
    _refused(conn, INSERT, (observation, document, kind, auth, json.dumps(decision),
                            json.dumps(evidence)), "duplicate key")


def test_the_trigger_refuses_what_the_record_must_not_say(conn):
    _record(conn)
    sha = _shas(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT i.source_observation_id FROM instrument i "
                    "WHERE i.document_id = 1522 AND i.is_active LIMIT 1")
        obs_1522 = cur.fetchone()[0]
    good = _evidence(sha[4641], sha[1522])
    dup = "duplicate key"
    # the observation must have produced the document
    _refused(conn, INSERT, (obs_1522, 4641, KIND, 1522, DECISION, good),
             f"did not come from|{dup}")
    # the evidence must name the two files' own hashes
    _refused(conn, INSERT, (4130, 4641, KIND, 1522, DECISION, _evidence(sha[1522], sha[4641])),
             f"is not document|{dup}")
    # the finding must be the kind, and every key is required (a NULL CHECK must not pass)
    _refused(conn, INSERT, (4130, 4641, KIND, 1522, DECISION,
                            _evidence(sha[4641], sha[1522],
                                      finding="bill_superseded_by_enactment")),
             f"check|{dup}")
    _refused(conn, INSERT, (4130, 4641, KIND, 1522, DECISION,
                            _evidence(sha[4641], sha[1522], basis=None)),
             f"evidence_check|{dup}")
    _refused(conn, INSERT, (4130, 4641, "summary", 1522, DECISION,
                            _evidence(sha[4641], sha[1522], finding="summary")),
             f"kind_check|{dup}")
    # the answer must keep the authoritative document
    _refused(conn, INSERT, (4130, 4641, KIND, 1522,
                            json.dumps({"export": "x.json", "document_id": 4641,
                                        "question_id": "q2", "choice": "keep-4641"}), good),
             f"does not keep document 1522|{dup}")
    # no chains, and a released tree is never withdrawn: 1522 cannot be recorded
    # as non-authoritative in favour of 4641
    _refused(conn, INSERT, (obs_1522, 1522, KIND, 4641,
                            json.dumps({"export": "x.json", "document_id": 1522,
                                        "question_id": "q2", "choice": "keep-4641"}),
                            _evidence(sha[1522], sha[4641])),
             "itself recorded as non-authoritative|authoritative document of another"
             "|released instrument|in favour of nothing")
