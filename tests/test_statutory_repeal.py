"""Statutory repeal status from the corpus's own repealing clauses (migration 0066).

Pure tests pin the matcher and the decision rules; the database test needs 0066 applied and rolls back."""
from __future__ import annotations

import pytest

import datetime

from tools.record_statutory_repeals import norm, plan, printed_commencement, repeal_clauses, title_key


def test_a_repeal_is_dated_only_by_one_printed_date_and_at_once():
    head = "SINDH JUDICIAL ACADEMY ACT, 1993 [7th March, 1994] An Act to provide ..."
    assert printed_commencement(head, True)[0] == datetime.date(1994, 3, 7)
    assert printed_commencement(head, False) == (None, None)                      # no 'come into force at once'
    assert printed_commencement(head + " [1st May, 1995]", True) == (None, None)  # two dates: not established
    assert printed_commencement("no date here", True) == (None, None)

INST = [  # (id, jurisdiction, kind, title, year, observation, ordinal)
    ("A", "sindh", "act", "SINDH JUDICIAL ACADEMY ACT, 1993", 1993, 1, 0),
    ("B", "sindh", "ordinance", "Sind Judicial Academy Ordinance, 1993", 1993, 2, 0),
    ("C", "punjab", "act", "Punjab Health Foundation Act, 1992", 1992, 3, 0),
    ("D", "sindh", "ordinance", "Sindh Local Government Ordinance, 1979", 1979, 4, 0),
]


def test_titles_fold_case_punctuation_footnotes_and_sind():
    assert norm("The 1[Sind] Judicial Academy Ordinance") == norm("Sindh Judicial Academy Ordinance")
    assert norm("The 1Balochistan Kite Ordinance") == norm("Balochistan Kite Ordinance")
    assert title_key("SINDH JUDICIAL ACADEMY ACT, 1993") == "sindh judicial academy act"


def test_a_whole_repeal_is_found_and_a_partial_one_is_qualified():
    whole = repeal_clauses("18. Repeal.- The Sindh Judicial Academy Ordinance, 1993, is hereby repealed.")
    assert [(c["title"], c["year"], c["qualified"]) for c in whole] == [
        ("Sindh Judicial Academy Ordinance", 1993, False)]
    part = repeal_clauses("The Sindh Judicial Academy Ordinance, 1993, in its application to Karachi, is hereby repealed.")
    assert part and part[0]["qualified"]
    sect = repeal_clauses("section 4 of the Sindh Judicial Academy Ordinance, 1993 is hereby repealed.")
    assert sect and sect[0]["qualified"]
    after = repeal_clauses("The Trusts Act, 1882 (II of 1882) is hereby repealed in its application to the "
                           "Islamabad Capital Territory.")
    assert after and after[0]["qualified"]


def test_only_an_act_repeals_and_only_an_exact_unique_same_jurisdiction_match():
    provisions = [("A", "s_18", 10, "The Sindh Judicial Academy Ordinance, 1993, is hereby repealed."),
                  ("B", "s_9", 11, "The Sindh Judicial Academy Act, 1993 is hereby repealed."),     # an Ordinance
                  ("C", "s_20", 12, "The Sindh Judicial Academy Ordinance, 1993 is hereby repealed.")]  # other province
    rows, stats = plan(INST, provisions, [])
    assert [(r["repealed_instrument_id"], r["repealing_instrument_id"]) for r in rows] == [("B", "A")]
    assert stats["skipped: repealing instrument is not an Act"] == 1
    assert stats["skipped: not held"] == 1


def test_a_revived_enactment_is_not_marked_repealed():
    provisions = [("A", "s_3", 10, "The Sindh Local Government Ordinance, 1979 is hereby repealed.")]
    rows, stats = plan(INST, provisions, ["the Sindh Local Government Ordinance, 1979 shall stand revived"])
    assert rows == [] and stats["skipped: a revival names it"] == 1


@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("SELECT to_regclass('statutory_repeal')")
                if cur.fetchone()[0] is None:
                    pytest.skip("migration 0066 is not applied")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def test_the_record_is_append_only(conn):
    import psycopg
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM source_observation WHERE outcome='landed' ORDER BY id LIMIT 2")
        a, b = [r[0] for r in cur.fetchall()]
        cur.execute("""INSERT INTO statutory_repeal (repealed_observation_id, repealed_expression_ordinal,
                        repealing_observation_id, repealing_expression_ordinal, repealing_source_block_id,
                        repealing_relative_path, clause_text, matched_title, matched_year, assertion, method,
                        evidence, recorded_by)
                       VALUES (%s,0,%s,0,1,'s_1','x is hereby repealed','x',2000,'repealed','pytest',
                               '{"reviewer_type":"pytest"}','pytest') RETURNING id""", (a, b))
        rid = cur.fetchone()[0]
    for sql in ("UPDATE statutory_repeal SET clause_text='y' WHERE id=%s", "DELETE FROM statutory_repeal WHERE id=%s"):
        with pytest.raises(psycopg.Error, match="append-only"):
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(sql, (rid,))
