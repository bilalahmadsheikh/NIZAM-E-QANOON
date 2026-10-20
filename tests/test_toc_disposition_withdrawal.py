"""Withdrawing a recorded contents disposition (migration 0061).

The pure tests pin the recording tool's refusals and the payload it writes.
The database tests need migration 0061 applied; they write inside one
transaction, use savepoints for the refusals, and roll everything back, so
nothing is recorded (the convention of tests/test_heading_census_gate.py).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools.withdraw_toc_disposition import (answer_problem, assertion_problem,
                                            build_record)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "infra/postgres/migrations/0061_toc_disposition_withdrawal.sql"
SHA = "a" * 64


def assertion(**kw):
    """Assertion 17 (doc 1457, contents row '15 Repealed.') as the tool reads it."""
    row = {"id": 17, "source_observation_id": 3253, "expression_ordinal": 0,
           "printed_label": "15", "printed_heading": "Repealed.",
           "disposition": "repealed", "source_block_id": 86063, "source_page": 1,
           "reviewed_by": "openai.codex/rendered-source-review/1",
           "reviewed_at": "2026-09-11 12:50:47+00", "governing_id": 17,
           "withdrawal_id": None, "released": False, "document_ids": [1457]}
    row.update(kw)
    return row


ANSWER = {"document_id": 1457, "question_id": "q1", "card_sha256": "b" * 64,
          "choice": "body", "note": "", "reviewed_page_images": True}


# --- the tool's refusals ----------------------------------------------------
def test_the_standing_assertion_on_an_unreleased_document_is_accepted():
    assert assertion_problem(assertion(), 1457) is None


def test_a_missing_assertion_is_refused():
    assert "no such" in assertion_problem(None, 1457)


def test_an_assertion_is_withdrawn_once():
    assert "already withdrawn" in assertion_problem(assertion(withdrawal_id=4), 1457)


def test_a_superseded_assertion_is_refused_and_the_governing_one_named():
    why = assertion_problem(assertion(governing_id=202), 1457)
    assert "superseded by 202" in why


def test_a_released_observation_is_refused():
    assert "released" in assertion_problem(assertion(released=True), 1457)


def test_the_owner_decision_must_be_about_the_assertions_document():
    why = assertion_problem(assertion(), 510)
    assert "document 510" in why and "3253" in why


def test_the_answer_must_say_what_the_withdrawal_claims():
    assert answer_problem(ANSWER, "body") is None
    assert "'contents'" in answer_problem(dict(ANSWER, choice="contents"), "body")
    assert "page images" in answer_problem(dict(ANSWER, reviewed_page_images=False), "body")
    assert "card_sha256" in answer_problem(dict(ANSWER, card_sha256=None), "body")


def test_the_export_must_hold_exactly_one_answer(tmp_path):
    from nizam.workers.segment import owner_decision_answer
    export = tmp_path / "decision-review.json"
    export.write_text(json.dumps({"answers": [ANSWER]}), encoding="utf-8")
    citation = {"export": str(export), "document_id": 1457, "question_id": "q1"}
    assert owner_decision_answer(citation, 1457)["choice"] == "body"
    with pytest.raises(ValueError, match="holds 0 answers"):
        owner_decision_answer(dict(citation, question_id="q9"), 1457)
    with pytest.raises(ValueError, match="does not exist"):
        owner_decision_answer(dict(citation, export=str(tmp_path / "x.json")), 1457)


# --- the payload satisfies the table's CHECKs -------------------------------
def test_the_written_payload_satisfies_the_migration_checks():
    citation = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-08-f.json",
                "document_id": 1457, "question_id": "q1"}
    references = [{"provision_version_id": "79e5", "in_active_tree": True},
                  {"provision_version_id": "7697", "in_active_tree": False}]
    owner, evidence = build_record(
        assertion=assertion(), citation=citation, choice="body", answer=ANSWER,
        export={"reviewer_name": "Bilal Ahmad", "exported_at": "2026-10-08T00:07:30Z"},
        export_sha256=SHA, references=references, note=None)
    # the CHECK on owner_decision, in Python
    assert set(owner) == {"export", "document_id", "question_id", "choice"}
    assert owner["export"].endswith(".json")
    assert type(owner["document_id"]) is int and owner["document_id"] > 0
    assert re.fullmatch(r"q[0-9]+", owner["question_id"])
    assert owner["choice"].strip()
    # the CHECK on evidence
    assert re.fullmatch(r"[0-9a-f]{64}", evidence["export_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", evidence["card_sha256"])
    assert evidence["provision_versions_citing"] == {"active_tree": ["79e5"],
                                                     "superseded_trees": 1}
    assert evidence["assertion"]["printed_heading"] == "Repealed."


def test_the_migration_keeps_the_view_columns_and_guards_every_mutation():
    sql = MIGRATION.read_text(encoding="utf-8")
    # CREATE OR REPLACE (not DROP) keeps the column list a replace requires
    assert "CREATE OR REPLACE VIEW v_toc_disposition_assertion_latest" in sql
    assert "DROP VIEW" not in sql
    assert "BEFORE INSERT OR UPDATE OR DELETE ON toc_disposition_withdrawal" in sql
    assert "BEFORE TRUNCATE ON toc_disposition_withdrawal" in sql
    # 0052's guard is not redefined
    assert "FUNCTION check_toc_disposition_assertion" not in sql


# --- the database -------------------------------------------------------------
@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("SELECT to_regclass('toc_disposition_withdrawal')")
                if cur.fetchone()[0] is None:
                    pytest.skip("migration 0061 is not applied")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


GOVERNING = """
SELECT l.id, (SELECT min(i.document_id) FROM instrument i
               WHERE i.source_observation_id = l.source_observation_id)
  FROM v_toc_disposition_assertion_latest l
 WHERE NOT EXISTS (SELECT 1 FROM v_release_instrument r
                    WHERE r.source_observation_id = l.source_observation_id)
 ORDER BY l.id LIMIT 1
"""

INSERT = """
INSERT INTO toc_disposition_withdrawal
       (assertion_id, reason, owner_decision, evidence, withdrawn_by)
VALUES (%s, 'pytest', %s, %s, 'pytest') RETURNING id
"""


def _decision(document_id):
    return json.dumps({"export": "x.json", "document_id": document_id,
                       "question_id": "q1", "choice": "body"})


EVIDENCE = json.dumps({"export_sha256": SHA, "card_sha256": SHA})


def _refused(conn, sql, params, match):
    import psycopg
    with pytest.raises(psycopg.Error, match=match):
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(sql, params)


def _unreleased_governing(cur):
    cur.execute(GOVERNING)
    row = cur.fetchone()
    if row is None:
        pytest.skip("no standing disposition on an unreleased observation")
    return row


def test_a_withdrawn_assertion_drops_out_of_the_view_and_stays_on_record(conn):
    with conn.cursor() as cur:
        assertion_id, document_id = _unreleased_governing(cur)
        cur.execute("SELECT count(*) FROM v_toc_disposition_assertion_latest")
        before = cur.fetchone()[0]
        cur.execute(INSERT, (assertion_id, _decision(document_id), EVIDENCE))
        cur.execute("SELECT count(*) FROM v_toc_disposition_assertion_latest")
        assert cur.fetchone()[0] == before - 1
        cur.execute("SELECT count(*) FROM v_toc_disposition_assertion_latest "
                    "WHERE id = %s", (assertion_id,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM toc_disposition_assertion WHERE id = %s",
                    (assertion_id,))
        assert cur.fetchone()[0] == 1


def test_a_withdrawal_is_append_only_and_made_once(conn):
    with conn.cursor() as cur:
        assertion_id, document_id = _unreleased_governing(cur)
        cur.execute(INSERT, (assertion_id, _decision(document_id), EVIDENCE))
        withdrawal_id = cur.fetchone()[0]
    _refused(conn, "UPDATE toc_disposition_withdrawal SET reason = 'x' WHERE id = %s",
             (withdrawal_id,), "append-only")
    _refused(conn, "DELETE FROM toc_disposition_withdrawal WHERE id = %s",
             (withdrawal_id,), "append-only")
    _refused(conn, "TRUNCATE toc_disposition_withdrawal", None, "append-only")
    _refused(conn, INSERT, (assertion_id, _decision(document_id), EVIDENCE),
             "duplicate key")
    _refused(conn, "DELETE FROM toc_disposition_assertion WHERE id = %s",
             (assertion_id,), "foreign key")


def test_a_withdrawal_needs_a_well_formed_citation_and_evidence(conn):
    with conn.cursor() as cur:
        assertion_id, document_id = _unreleased_governing(cur)
    bad_decision = json.dumps({"export": "x.json", "document_id": str(document_id),
                               "question_id": "q1", "choice": "body"})
    _refused(conn, INSERT, (assertion_id, bad_decision, EVIDENCE), "owner_decision_check")
    no_choice = json.dumps({"export": "x.json", "document_id": document_id,
                            "question_id": "q1", "choice": None})
    _refused(conn, INSERT, (assertion_id, no_choice, EVIDENCE), "owner_decision_check")
    _refused(conn, INSERT, (assertion_id, _decision(document_id), "{}"), "evidence_check")
    _refused(conn, INSERT, (assertion_id, _decision(document_id + 999_999_999), EVIDENCE),
             "never built from")


def test_a_superseded_or_released_assertion_cannot_be_withdrawn(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.supersedes_id, min(i.document_id)
              FROM toc_disposition_assertion s
              JOIN instrument i ON i.source_observation_id = s.source_observation_id
             WHERE s.supersedes_id IS NOT NULL
             GROUP BY 1 ORDER BY 1 LIMIT 1""")
        superseded = cur.fetchone()
        cur.execute("""
            SELECT l.id, r.document_id
              FROM v_toc_disposition_assertion_latest l
              JOIN v_release_instrument r
                ON r.source_observation_id = l.source_observation_id
             ORDER BY l.id LIMIT 1""")
        released = cur.fetchone()
    if superseded is None or released is None:
        pytest.skip("corpus has no superseded or no released disposition")
    _refused(conn, INSERT, (superseded[0], _decision(superseded[1]), EVIDENCE),
             "superseded by|released")
    _refused(conn, INSERT, (released[0], _decision(released[1]), EVIDENCE), "released")


REASSERT = """
INSERT INTO toc_disposition_assertion
       (source_observation_id, expression_ordinal, toc_entry_ordinal,
        reviewed_toc_entry_id, printed_label, printed_heading, disposition,
        source_block_id, source_page, render_artifact, render_sha256, evidence,
        reviewed_by, supersedes_id)
SELECT a.source_observation_id, a.expression_ordinal, e.ordinal, e.id,
       a.printed_label, a.printed_heading, a.disposition, a.source_block_id,
       a.source_page, a.render_artifact, a.render_sha256, a.evidence, 'pytest', %s
  FROM toc_disposition_assertion a
  JOIN instrument i ON i.source_observation_id = a.source_observation_id
                   AND i.expression_ordinal = a.expression_ordinal
                   AND i.is_active AND i.duplicate_of IS NULL
  JOIN instrument_toc_entry e ON e.instrument_id = i.id
                             AND e.source_block_id = a.source_block_id
                             AND e.printed_label = a.printed_label
                             AND e.printed_heading = a.printed_heading
                             AND e.source_page = a.source_page
 WHERE a.id = %s
RETURNING id
"""


def test_a_withdrawn_entry_is_reasserted_only_by_superseding_the_withdrawal(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT l.id, (SELECT min(i.document_id) FROM instrument i
                           WHERE i.source_observation_id = l.source_observation_id)
              FROM v_toc_disposition_assertion_latest l
              JOIN instrument i ON i.source_observation_id = l.source_observation_id
                               AND i.expression_ordinal = l.expression_ordinal
                               AND i.is_active AND i.duplicate_of IS NULL
              JOIN instrument_toc_entry e ON e.instrument_id = i.id
                                         AND e.source_block_id = l.source_block_id
                                         AND e.printed_label = l.printed_label
                                         AND e.printed_heading = l.printed_heading
                                         AND e.source_page = l.source_page
             WHERE NOT EXISTS (SELECT 1 FROM v_release_instrument r
                                WHERE r.source_observation_id = l.source_observation_id)
             ORDER BY l.id LIMIT 1""")
        row = cur.fetchone()
        if row is None:
            pytest.skip("no standing disposition whose live contents entry still matches")
        assertion_id, document_id = row
        cur.execute(INSERT, (assertion_id, _decision(document_id), EVIDENCE))
    _refused(conn, REASSERT, (None, assertion_id), "was withdrawn")
    with conn.cursor() as cur:
        cur.execute(REASSERT, (assertion_id, assertion_id))
        new_id = cur.fetchone()[0]
        cur.execute("SELECT supersedes_id FROM v_toc_disposition_assertion_latest "
                    "WHERE id = %s", (new_id,))
        assert cur.fetchone() == (assertion_id,)
