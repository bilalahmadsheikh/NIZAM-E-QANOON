"""A landed copy that prints the same text as a canonical document (migration 0062).

The pure tests pin the recorder's furniture-only diff, its mirror of the
trigger, and the re-apply step's decisions. The database tests need migration
0062 applied; they write inside one transaction, use savepoints for the
refusals, and roll everything back (tests/test_heading_census_gate.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.apply_source_same_text_copy import decide, plan
from tools.record_source_same_text_copy import (FURNITURE_TOKEN, answer_problem,
                                                compare, is_furniture_block,
                                                state_problem)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "infra/postgres/migrations/0062_source_same_text_copy.sql"
SHA_A, SHA_B = "a" * 64, "b" * 64


def block(block_id, page, text):
    return {"id": block_id, "page_no": page, "text": text}


# --- what counts as page furniture ---------------------------------------------
def test_furniture_tokens():
    for token in ("2", "13", "Cont…P/4", "…P/10", "Contd:", "Cont...P/12",
                  "Cont", "Contd."):
        assert FURNITURE_TOKEN.match(token), token
    for token in ("2.", "(2)", "rule", "1987", "P/", "Cont…", "a)"):
        assert not FURNITURE_TOKEN.match(token), token
    assert is_furniture_block("Contd: \n…P/10\n")
    assert not is_furniture_block("3 \n(2) The secretary shall")
    assert not is_furniture_block("")


def test_the_doc_2673_shapes_are_furniture_only():
    """2673 prints its page numbers (alone, or fused above the page's first
    line) and its page-turn lines number two higher than 2191's."""
    canonical = [block(1, 2, "Cont…P/3"),
                 block(2, 3, "(2) The secretary shall issue"),
                 block(3, 4, "Contd: \n…P/4")]
    copy = [block(11, 2, "2"), block(12, 2, "Cont…P/5"),
            block(13, 3, "3 \n(2) The secretary shall issue"),
            block(14, 4, "Contd: \n…P/6"), block(15, 4, "4")]
    result = compare(canonical, copy)
    assert result["differences"] and result["substantive"] == []


def test_a_word_split_at_a_space_is_spacing_only():
    """Doc 3525 reads the superscript ordinal of '[24th July, 2006]' as '24 th'
    where doc 3247 reads '24th': the same characters, split by a space."""
    canonical = [block(1, 4, "[24th July, 2006] the Governor of the Punjab is pleased")]
    copy = [block(11, 3, "[24 th July, 2006] the Governor of the Punjab is pleased")]
    result = compare(canonical, copy)
    assert result["substantive"] == []
    assert [d.get("kind") for d in result["differences"]] == ["spacing"]


def test_a_split_word_that_also_changes_a_character_is_refused():
    canonical = [block(1, 4, "[24th July, 2006]")]
    copy = [block(11, 3, "[25 th July, 2006]")]
    assert compare(canonical, copy)["substantive"]


def test_a_difference_of_law_is_refused():
    canonical = [block(1, 1, "4. The secretary shall issue notice within 7 days.")]
    copy = [block(11, 1, "4. The secretary may issue notice within 7 days.")]
    assert compare(canonical, copy)["substantive"]


def test_a_number_inside_text_is_not_furniture():
    """'rule 3' against 'rule 4' differs by a bare number -- inside text."""
    canonical = [block(1, 1, "Heading"), block(2, 1, "as provided in rule 3 of these rules")]
    copy = [block(11, 1, "Heading"), block(12, 1, "as provided in rule 4 of these rules")]
    assert compare(canonical, copy)["substantive"]


def test_a_head_number_that_is_not_the_page_number_is_law():
    canonical = [block(1, 3, "(2) The secretary shall issue")]
    copy = [block(11, 3, "5 \n(2) The secretary shall issue")]
    assert compare(canonical, copy)["substantive"]


def test_identical_text_has_no_differences():
    blocks = [block(1, 1, "1. Short title."), block(2, 2, "2. Definitions.")]
    result = compare(blocks, [dict(b, id=b["id"] + 10) for b in blocks])
    assert result["differences"] == [] and result["ratio"] == 1.0


# --- the recorder's mirror of the trigger ---------------------------------------
def doc(**kw):
    row = {"id": 2673, "sha256": SHA_B, "is_active": True, "landed_observations": [2598],
           "has_canonical_instrument": False, "recorded_as_copy": False,
           "recorded_as_canonical": False}
    row.update(kw)
    return row


CANONICAL = doc(id=2191, sha256=SHA_A, landed_observations=[2744],
                has_canonical_instrument=True)


def test_the_2673_2191_record_is_admitted():
    assert state_problem(doc(), CANONICAL, 2598, False, 2191, "keep-2191") is None
    assert state_problem(doc(), CANONICAL, 2598, False, 2673, "keep-2191") is None


def test_the_owners_choice_fixes_the_direction():
    """'keep-2191' keeps 2191: it cannot record 2191 as the copy of 2673."""
    why = state_problem(doc(), CANONICAL, 2598, False, 2191, "keep-2673")
    assert "does not keep document 2191" in why
    assert "keep-2191" in state_problem(doc(), CANONICAL, 2598, False, 2191, "other")


@pytest.mark.parametrize("copy,canonical,observation,released,decision,why", [
    (None, CANONICAL, 2598, False, 2191, "no such document"),
    (doc(sha256=SHA_A), CANONICAL, 2598, False, 2191, "same file"),
    (doc(), dict(CANONICAL, is_active=False), 2598, False, 2191, "not active"),
    (doc(), dict(CANONICAL, has_canonical_instrument=False), 2598, False, 2191,
     "in favour of nothing"),
    (doc(), dict(CANONICAL, recorded_as_copy=True), 2598, False, 2191, "itself recorded"),
    (doc(recorded_as_canonical=True), CANONICAL, 2598, False, 2191, "canonical of another"),
    (doc(recorded_as_copy=True), CANONICAL, 2598, False, 2191, "already recorded"),
    (doc(landed_observations=[2598, 2599]), CANONICAL, None, False, 2191, "name exactly one"),
    (doc(), CANONICAL, 2744, False, 2191, "did not land"),
    (doc(), CANONICAL, 2598, True, 2191, "released"),
    (doc(), CANONICAL, 2598, False, 510, "document 510"),
])
def test_the_recorder_refuses(copy, canonical, observation, released, decision, why):
    assert why in state_problem(copy, canonical, observation, released, decision,
                                "keep-2191")


def test_the_answer_must_say_what_the_record_claims():
    answer = {"choice": "keep-2191", "reviewed_page_images": True, "card_sha256": SHA_A}
    assert answer_problem(answer, "keep-2191") is None
    assert "'keep-2673'" in answer_problem(dict(answer, choice="keep-2673"), "keep-2191")
    assert "page images" in answer_problem(dict(answer, reviewed_page_images=False),
                                           "keep-2191")


# --- the re-apply step ----------------------------------------------------------
def test_reapply_decisions():
    assert decide("c", "k", None, False)[0] == "set"
    assert decide("c", "k", "k", False)[0] == "done"
    assert decide("c", None, None, False)[0] == "missing"
    # pointing at another document's instrument: left alone
    assert decide("c", "k", "x", False, already_is_canonical_document=False)[0] == "skip"
    # pointing at an earlier revision of the canonical document: advanced
    assert decide("c", "k", "old-k", False, already_is_canonical_document=True)[0] == "set"
    # a released copy is never withdrawn by this route
    action, reason = decide("c", "k", None, True)
    assert action == "skip" and "RELEASED" in reason


def _row(record, ordinal, canonical, already=None, already_doc=None, released=False):
    return (record, 2673, 2191, ordinal, f"copy-{ordinal}", already, already_doc,
            canonical, released)


def test_a_copy_linked_on_only_some_ordinals_is_refused_whole():
    decisions, partial = plan([_row(1, 0, "k0"), _row(1, 1, None)])
    assert partial == [1]
    # already linked on one ordinal and missing on another is still partial
    assert plan([_row(1, 0, "k0", already="k0", already_doc=2191),
                 _row(1, 1, None)])[1] == [1]
    # every ordinal missing is a plain skip, not a partial link
    assert plan([_row(1, 0, None), _row(1, 1, None)])[1] == []
    # every ordinal present links
    decisions, partial = plan([_row(1, 0, "k0"), _row(1, 1, "k1")])
    assert partial == [] and [d["action"] for d in decisions] == ["set", "set"]


def test_the_first_link_rechecks_the_release_view_in_the_update():
    from tools.apply_source_same_text_copy import FIRST_LINK
    assert "duplicate_of IS NULL" in FIRST_LINK
    assert "NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id = instrument.id)" in FIRST_LINK


def test_the_migration_guards_every_mutation_and_touches_no_release_view():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "BEFORE INSERT OR UPDATE OR DELETE ON source_same_text_copy" in sql
    assert "BEFORE TRUNCATE ON source_same_text_copy" in sql
    assert "source_observation_id bigint NOT NULL UNIQUE" in sql
    assert "CREATE UNIQUE INDEX source_same_text_copy_document" in sql
    assert "pg_advisory_xact_lock(hashtext('source_same_text_copy'))" in sql
    assert "SET LOCAL lock_timeout" in sql
    assert "'keep-' || NEW.canonical_document_id::text" in sql
    assert "CREATE VIEW" not in sql and "DROP VIEW" not in sql
    assert "ALTER TABLE instrument" not in sql


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
                cur.execute("SELECT to_regclass('source_same_text_copy')")
                if cur.fetchone()[0] is None:
                    pytest.skip("migration 0062 is not applied")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


INSERT = """
INSERT INTO source_same_text_copy
       (source_observation_id, document_id, canonical_document_id, observed,
        owner_decision, evidence, recorded_by)
VALUES (%s, %s, %s, 'pytest', %s, %s, 'pytest') RETURNING id
"""
DECISION = json.dumps({"export": "x.json", "document_id": 2191, "question_id": "q2",
                       "choice": "keep-2191"})


def _evidence(copy_sha, canonical_sha, **kw):
    e = {"copy_sha256": copy_sha, "canonical_sha256": canonical_sha, "copy_words": 1,
         "canonical_words": 1, "finding": "page_furniture_only", "diff_tool": "t",
         "diff_tool_sha256": SHA_A, "export_sha256": SHA_A, "card_sha256": SHA_A}
    e.update(kw)
    return json.dumps(e)


def _refused(conn, sql, params, match):
    import psycopg
    with pytest.raises(psycopg.Error, match=match):
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(sql, params)


def _record(conn):
    """The 2673 -> 2191 record: the stored one, or one inserted and rolled back."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM source_same_text_copy WHERE source_observation_id = 2598")
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("SELECT id, sha256 FROM document WHERE id IN (2191, 2673)")
        sha = dict(cur.fetchall())
        if len(sha) != 2:
            pytest.skip("documents 2191/2673 are not in this corpus")
        try:
            with conn.transaction():
                cur.execute(INSERT, (2598, 2673, 2191, DECISION,
                                     _evidence(sha[2673], sha[2191])))
                return cur.fetchone()[0]
        except Exception as exc:                                # noqa: BLE001
            pytest.skip(f"2673 -> 2191 not recordable in this state: {exc}")


def test_a_record_is_append_only_and_one_per_observation(conn):
    record = _record(conn)
    _refused(conn, "UPDATE source_same_text_copy SET observed = 'x' WHERE id = %s",
             (record,), "append-only")
    _refused(conn, "DELETE FROM source_same_text_copy WHERE id = %s", (record,),
             "append-only")
    _refused(conn, "TRUNCATE source_same_text_copy", None, "append-only")
    with conn.cursor() as cur:
        cur.execute("SELECT source_observation_id, document_id, canonical_document_id, "
                    "evidence FROM source_same_text_copy WHERE id = %s", (record,))
        observation, document, canonical, evidence = cur.fetchone()
    _refused(conn, INSERT, (observation, document, canonical, DECISION,
                            json.dumps(evidence)), "duplicate key")


def test_the_trigger_refuses_what_the_record_must_not_say(conn):
    _record(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT id, sha256 FROM document WHERE id IN (2191, 2673)")
        sha = dict(cur.fetchall())
    good = _evidence(sha[2673], sha[2191])
    # the observation must have produced the document
    _refused(conn, INSERT, (2744, 2673, 2191, DECISION, good), "did not come from")
    # the evidence must name the two files' own hashes
    _refused(conn, INSERT, (2598, 2673, 2191, DECISION, _evidence(sha[2191], sha[2673])),
             "is not document")
    # the finding is fixed, and every key is required (a NULL CHECK must not pass)
    _refused(conn, INSERT, (2598, 2673, 2191, DECISION,
                            _evidence(sha[2673], sha[2191], finding="close")), "evidence_check")
    _refused(conn, INSERT, (2598, 2673, 2191, DECISION,
                            _evidence(sha[2673], sha[2191], diff_tool_sha256=None)),
             "evidence_check")
    # the owner decision is about one of the two documents
    _refused(conn, INSERT, (2598, 2673, 2191,
                            json.dumps({"export": "x.json", "document_id": 510,
                                        "question_id": "q2", "choice": "keep-2191"}), good),
             "owner_decision cites document 510|duplicate key")
    # the answer must keep the canonical: 'keep-2673' cannot retire 2673
    _refused(conn, INSERT, (2598, 2673, 2191,
                            json.dumps({"export": "x.json", "document_id": 2191,
                                        "question_id": "q2", "choice": "keep-2673"}), good),
             "does not keep document 2191|duplicate key")
    # no chains: the canonical cannot be recorded as a copy of its copy
    _refused(conn, INSERT, (2744, 2191, 2673, DECISION, _evidence(sha[2191], sha[2673])),
             "itself recorded as a copy|canonical of another|in favour of nothing")


def test_one_record_per_copy_document(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT indexdef FROM pg_indexes
                        WHERE indexname = 'source_same_text_copy_document'""")
        row = cur.fetchone()
    assert row and "UNIQUE" in row[0] and "(document_id)" in row[0]
