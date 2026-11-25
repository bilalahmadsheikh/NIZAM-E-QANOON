"""Binding authority as at a date (migration 0118, DECISION-LOG D-116, docs/PRECEDENT-MODEL.md §1).

Pure tests run the resolver over the seeded rules as loaded from the database (so they test the real seeds, not a
copy). Database tests check the constraints that make a wrong rule impossible to insert, and roll back.
"""
from __future__ import annotations

import datetime as dt

import pytest

from nizam.storage.authority import Binding, NotBinding, NotRecorded, Subordinate, authority, load

D = dt.date


@pytest.fixture(scope="module")
def registry():
    try:
        from nizam.storage.db import connect
        with connect() as c, c.cursor() as cur:
            cur.execute("SELECT to_regclass('authority_rule')")
            if cur.fetchone()[0] is None:
                pytest.skip("migration 0118 is not applied")
            return load(cur)
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def ask(registry, deciding, receiving, day, subject="all"):
    courts, rules, sup = registry
    return authority(deciding, receiving, day, courts=courts, rules=rules, superintendence=sup, subject=subject)


TODAY = D(2026, 11, 22)


def test_after_the_27th_amendment_the_fcc_binds_the_supreme_court_and_not_the_reverse(registry):
    assert isinstance(ask(registry, "FCC", "SC", TODAY), Binding)
    r = ask(registry, "SC", "FCC", TODAY)
    assert isinstance(r, NotBinding)                       # Art. 189(2): "except the Federal Constitutional Court"
    assert isinstance(ask(registry, "SC", "LHC", TODAY), Binding)
    assert isinstance(ask(registry, "SC", Subordinate("sindh"), TODAY), Binding)


def test_the_rule_changes_on_the_commencement_day(registry):
    assert isinstance(ask(registry, "FCC", "SC", D(2025, 11, 13)), Binding)
    assert isinstance(ask(registry, "FCC", "SC", D(2025, 11, 12)), NotRecorded)


def test_the_2016_text_binds_every_court_and_the_unheld_years_are_not_recorded(registry):
    b = ask(registry, "SC", "LHC", D(2016, 7, 1))
    assert isinstance(b, Binding) and b.rule.basis == "dated_text" and b.rule.except_court is None
    # 2017-01-07 .. 2025-11-13: the 23rd and 24th Amendment Acts are not held, so continuity is not shown
    r = ask(registry, "SC", "LHC", D(2020, 1, 1))
    assert isinstance(r, NotRecorded) and "2020-01-01" in r.reason


def test_a_high_court_binds_only_the_courts_of_its_own_territory(registry):
    b = ask(registry, "LHC", Subordinate("punjab"), TODAY)
    assert isinstance(b, Binding) and b.subject_to == ("Article 189",)
    assert isinstance(ask(registry, "LHC", Subordinate("sindh"), TODAY), NotBinding)
    assert isinstance(ask(registry, "LHC", "SHC", TODAY), NotBinding)          # another High Court: not bound
    assert isinstance(ask(registry, "LHC", "SC", TODAY), NotBinding)


def test_the_federal_shariat_court_binds_under_chapter_3a_only(registry):
    assert isinstance(ask(registry, "FSC", "PHC", TODAY, subject="shariat_chapter_3A"), Binding)
    assert isinstance(ask(registry, "FSC", Subordinate("kp"), TODAY, subject="shariat_chapter_3A"), Binding)
    assert isinstance(ask(registry, "FSC", "SC", TODAY, subject="shariat_chapter_3A"), NotBinding)
    assert isinstance(ask(registry, "FSC", "PHC", TODAY), NotRecorded)        # outside Chapter 3A: no rule


def test_what_the_corpus_cannot_show_is_not_recorded_never_guessed(registry):
    assert isinstance(ask(registry, "XYZ", "SC", TODAY), NotRecorded)         # a court not in the registry
    r = ask(registry, "SC", "SC", TODAY)                                      # bench rules are case law
    assert isinstance(r, NotRecorded) and "case law" in r.reason


# --------------------------------------------- D-141: AJK and GB courts (0137), and the territories a rule reaches

def test_in_pakistan_does_not_answer_for_the_ajk_and_gb_courts(registry):
    # Art. 189 binds "all other courts in Pakistan"; whether an AJK or GB court is one (Art. 1(2)(c)) is not recorded
    for receiver in ("AJKSC", "AJKHC", "GBSAC", "GBCC", Subordinate("ajk"), Subordinate("gb")):
        r = ask(registry, "SC", receiver, TODAY)
        assert isinstance(r, NotRecorded) and "is not recorded" in r.reason, receiver
    assert isinstance(ask(registry, "FSC", "AJKHC", TODAY, subject="shariat_chapter_3A"), NotRecorded)


def test_ajk_rules_bind_inside_azad_jammu_and_kashmir_only(registry):
    b = ask(registry, "AJKSC", "AJKHC", TODAY)                                # Art. 42-B
    assert isinstance(b, Binding) and b.rule.source["source_unit"] == "42-B"
    assert isinstance(ask(registry, "AJKSC", Subordinate("ajk"), TODAY), Binding)   # "all other Courts in AJK"
    assert isinstance(ask(registry, "AJKSC", "LHC", TODAY), NotRecorded)      # its words do not speak of Punjab
    assert isinstance(ask(registry, "AJKSC", "AJKHC", D(2026, 5, 11)), NotRecorded)  # before the text is served


def test_class_rules_of_the_constitution_do_not_govern_the_ajk_high_court(registry):
    # Art. 201's "a High Court" is not the AJK High Court; its own rule (Art. 44-B) needs a superintendence record
    # the AJK text does not print, so its subordinate courts stay not recorded
    r = ask(registry, "AJKHC", Subordinate("ajk"), TODAY)
    assert isinstance(r, NotRecorded) and "no High Court is recorded" in r.reason
    assert isinstance(ask(registry, "AJKHC", Subordinate("punjab"), TODAY), NotRecorded)
    assert isinstance(ask(registry, "AJKHC", "AJKSC", TODAY), NotBinding)     # its rule reaches only subordinates


def test_gb_rules_bind_inside_gilgit_baltistan_only(registry):
    b = ask(registry, "GBSAC", "GBCC", TODAY)                                 # s.78
    assert isinstance(b, Binding) and b.rule.source["source_unit"] == "78"
    assert isinstance(ask(registry, "GBSAC", "SC", TODAY), NotRecorded)
    assert ask(registry, "GBCC", Subordinate("gb"), TODAY).__class__ is NotRecorded


# ------------------------------------------------------------------------------------------- database constraints

@pytest.fixture()
def cur():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as c:
                c.execute("SELECT to_regclass('authority_rule')")
                if c.fetchone()[0] is None:
                    pytest.skip("migration 0118 is not applied")
                yield c
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def _raises(cur, sql, *args, match):
    import psycopg
    cur.execute("SAVEPOINT t")
    with pytest.raises(psycopg.Error, match=match):
        cur.execute(sql, args)
    cur.execute("ROLLBACK TO SAVEPOINT t")


INSERT = """INSERT INTO authority_rule (deciding_court, receiving, validity, basis, source_observation_id,
                                        source_expression_ordinal, source_unit, source_quote, territories, recorded_by)
            VALUES ('SC', 'all_other_courts', %s, 'dated_text', 507, 0, '189', 'x', '{fed}', 'test')"""


def test_a_rule_names_the_territories_it_reaches(cur):
    _raises(cur, """INSERT INTO authority_rule (deciding_court, receiving, validity, basis, source_observation_id,
                        source_expression_ordinal, source_unit, source_quote, recorded_by)
                    VALUES ('SC', 'all_other_courts', '[2030-01-01,)', 'dated_text', 507, 0, '189', 'x', 'test')""",
            match="territories")
    _raises(cur, INSERT.replace("'{fed}'", "'{}'"), "[2030-01-01,)", match="ck_authority_territories")


def test_two_rules_for_one_court_cannot_overlap_in_time(cur):
    _raises(cur, INSERT, "[2026-01-01,)", match="authority_rule_no_overlap")


def test_a_rule_without_a_source_cannot_be_inserted(cur):
    _raises(cur, """INSERT INTO authority_rule (deciding_court, receiving, validity, basis, territories, recorded_by)
                    VALUES ('SC', 'all_other_courts', '[2030-01-01,)', 'dated_text', '{fed}', 'test')""",
            match="ck_authority_one_source")
    _raises(cur, """INSERT INTO authority_rule (deciding_court, receiving, validity, basis, source_observation_id,
                        source_expression_ordinal, source_unit, source_quote, territories, recorded_by)
                    VALUES ('SC', 'same_court_smaller_bench', '[2030-01-01,)', 'dated_text', 507, 0, '189', 'x',
                            '{fed}', 'test')""", match="ck_authority")


def test_rules_are_append_only_and_withdrawn_once(cur):
    cur.execute("SELECT id FROM authority_rule WHERE withdrawn_at IS NULL ORDER BY id LIMIT 1")
    rid = cur.fetchone()[0]
    _raises(cur, "UPDATE authority_rule SET basis='commencement' WHERE id=%s", rid, match="append-only|only permitted")
    _raises(cur, "DELETE FROM authority_rule WHERE id=%s", rid, match="append-only")
    _raises(cur, "UPDATE authority_rule SET withdrawn_at=now() WHERE id=%s", rid, match="only permitted")
    cur.execute("UPDATE authority_rule SET withdrawn_at=now(), withdrawn_reason='test' WHERE id=%s", (rid,))
    _raises(cur, "UPDATE authority_rule SET withdrawn_reason='again' WHERE id=%s", rid, match="only permitted")


def test_every_seeded_record_is_printed_where_it_says(cur):
    cur.execute("SELECT count(*), count(*) FILTER (WHERE NOT found) FROM v_court_record_source")
    total, missing = cur.fetchone()
    assert total > 0 and missing == 0
    assert cur.execute("SELECT law_unit_quote_found(507, 0, '189', 'binding on all other courts in Pakistan "
                       "including the Supreme Court')").fetchone()[0]
    assert not cur.execute("SELECT law_unit_quote_found(507, 0, '189', 'binding on no court')").fetchone()[0]
