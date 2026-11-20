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


def test_one_place_under_several_names_folds_to_one_key():
    # the AJK Rent Restriction Act, 1986 s.26 names the law the corpus holds as 'The Azad Kashmir ... Act, 1952'
    assert norm("Azad Jammu and Kashmir Rent Restriction Act") == norm("The Azad Kashmir Rent Restriction Act")
    assert norm("N.W.F.P. Tenancy Act") == norm("Khyber Pakhtunkhwa Tenancy Act")
    assert norm("Baluchistan Levies Act") == norm("Balochistan Levies Act")


def test_every_title_of_a_list_repeal_is_a_clause():
    text = ("(1) The Canal and Drainage Act, 1873 (VIII of 1873) and the Punjab Soil Reclamation Act, 1952 (XXI of "
            "1952) are hereby repealed.")
    got = {(c["title"], c["year"]) for c in repeal_clauses(text) if not c["qualified"]}
    assert ("Punjab Soil Reclamation Act", 1952) in got
    three = ("The General Statistics Act, 1975 (LXIX of 1975), the Agricultural Census Act, 1958 (XLI of 1958) and the "
             "Census Ordinance, 1959 (X of 1959) are hereby repealed.")
    assert {("Agricultural Census Act", 1958), ("Census Ordinance", 1959)} <= {
        (c["title"], c["year"]) for c in repeal_clauses(three)}
    # a qualifier anywhere in the list reads nothing as a whole repeal
    part = ("The A Act, 1950 and the B Act, 1960 are hereby repealed in their application to the Province of Sindh.")
    assert all(c["qualified"] for c in repeal_clauses(part))


def test_an_ajk_title_matches_past_its_printed_citation_and_ampersand():
    assert title_key("The Azad Jammu & Kashmir Land Reforms Act, 1960 (Act No V of 1960)") == \
        norm("Azad Jammu and Kashmir Land Reforms Act")
    assert title_key("The Azad Jammu and Kashmir Land Reforms (Amendment) Act, 1972 (Act VI of 1972) "
                     "(Act No. VI Of 1972)") == "ajk land reforms amendment act"
    assert norm("AJ&K Board of Revenue Act") == norm("Azad Jammu and Kashmir Board of Revenue Act")
    # a bracket that is part of the name stays
    assert title_key("Civil Courts (Sind Amendment) Ordinance, 1970") == "civil courts sindh amendment ordinance"
    rows, _ = plan([("A", "ajk", "act", "The Azad Jammu and Kashmir Board of Revenue Act, 1993 (ACT III of 1993)",
                     1993, 1, 0),
                    ("B", "ajk", "ordinance", "The Azad Jammu and Kashmir Board of Revenue Ordinance, 1992 "
                     "(ORDINANCE XCVII of 1992)", 1992, 2, 0)],
                   [("A", "s_12", 10, "The Azad Jammu & Kashmir Board of Revenue Ordinance, 1992 (Ordinance XCVII "
                                      "of 1992) is hereby repealed.")], [])
    assert [(r["repealed_instrument_id"], r["repealing_instrument_id"]) for r in rows] == [("B", "A")]


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


def test_something_of_an_act_or_a_title_running_on_is_not_a_whole_repeal():
    # 2458 s.18(1)(g): the segmenter split '... under section 28 (1) (g) of the University of Karachi Act, 1972'
    of_it = repeal_clauses("of the University of Karachi Act, 1972 are hereby repealed.")
    assert of_it and of_it[0]["qualified"]
    # 5241: the 1955 Repeal Ordinance is what is repealed, not the 1890 Act
    runs = repeal_clauses("The Bombay District Police Act, 1890 (Repeal) Ordinance, 1955, is hereby repealed.")
    assert runs and all(c["qualified"] for c in runs if c["year"] == 1890)
    # a printed citation after the year is still a whole repeal
    cited = repeal_clauses("96. (1) The Balochistan Wildlife Protection Act, 1974 (Act No. XIX of 1974) is hereby repealed.")
    assert [(c["year"], c["qualified"]) for c in cited] == [(1974, False)]
    # a defined short name in between is not another enactment (600, 2119)
    named = repeal_clauses("The Balochistan Technical Education and Vocational Training Authority Act, 2011 (II of "
                           "2011), hereinafter called as repealed Act, shall stand repealed.")
    assert [(c["year"], c["qualified"]) for c in named] == [(2011, False)]


def test_twin_texts_of_one_law_are_both_repealed_and_a_kind_word_settles_a_mislabel():
    from tools.record_statutory_repeals import resolve_hits
    meta = {"a": ("fed", "act", "X Act", 1, 0), "b": ("fed", "act", "X Act", 2, 0),
            "c": ("fed", "regulation", "Y Act", 3, 0), "d": ("fed", "act", "Y Act", 4, 0)}
    assert sorted(resolve_hits(["a", "b"], "The X Act", meta, frozenset({frozenset(("a", "b"))}))) == ["a", "b"]
    assert resolve_hits(["a", "b"], "The X Act", meta, frozenset()) == []          # same kind, not linked: refused
    assert resolve_hits(["c", "d"], "The Y Act", meta, frozenset()) == ["d"]        # the clause names an Act


def test_a_portal_repeal_note_in_a_catalogue_title_is_not_part_of_the_title():
    assert title_key("Boilers Act, 1923(Repeal by Ord. 52 of 2001, S, 610)") == norm("Boilers Act")
    assert title_key("Agricultural Census Act, 1958)") == norm("Agricultural Census Act")
    assert title_key("(Repealed vide Act XVIII of 2020) THE AZAD JAMMU AND KASHMIR FOO ACT, 1970") == \
        norm("Azad Jammu and Kashmir Foo Act")


def test_only_an_act_repeals_and_only_an_exact_unique_same_jurisdiction_match():
    provisions = [("A", "s_18", 10, "The Sindh Judicial Academy Ordinance, 1993, is hereby repealed."),
                  ("B", "s_9", 11, "The Sindh Judicial Academy Act, 1993 is hereby repealed."),     # an Ordinance
                  ("C", "s_20", 12, "The Sindh Judicial Academy Ordinance, 1993 is hereby repealed.")]  # other province
    rows, stats = plan(INST, provisions, [])
    assert [(r["repealed_instrument_id"], r["repealing_instrument_id"]) for r in rows] == [("B", "A")]
    assert stats["skipped: repealing instrument is not an Act"] == 1
    assert stats["skipped: not held"] == 1


def test_a_title_equal_but_for_a_plural_matches_only_when_the_exact_title_does_not():
    # D-103: the Balochistan Maternity Benefits Act, 2022 repeals 'the West Pakistan Maternity Benefits Ordinance,
    # 1958', held as '... Maternity Benefit Ordinance 1958' -- it stayed served where it was repealed
    inst = [("A", "balochistan", "act", "The Balochistan Maternity Benifits Act, 2022", 2022, 1, 0),
            ("B", "balochistan", "ordinance", "The West Pakistan Maternity Benefit Ordinance 1958", 1958, 2, 0)]
    rows, stats = plan(inst, [("A", "s_20", 10, "The West Pakistan Maternity Benefits Ordinance, 1958 (Ordinance No. "
                                                "XXXII of 1958) is hereby repealed.")], [])
    assert [(r["repealed_instrument_id"], r["repealing_instrument_id"]) for r in rows] == [("B", "A")]
    assert stats["matched but for a plural"] == 1


def test_a_qualifier_naming_only_the_repealers_own_province_repeals_its_own_copy():
    inst = [("A", "balochistan", "act", "The Balochistan Maternity Benifits Act, 2022", 2022, 1, 0),
            ("B", "balochistan", "ordinance", "The West Pakistan Maternity Benefit Ordinance 1958", 1958, 2, 0)]
    own = ("The West Pakistan Maternity Benefits Ordinance, 1958 (Ordinance No. XXXII of 1958) is hereby repealed in "
           "its application to the Balochistan Province.")
    rows, stats = plan(inst, [("A", "s_20", 10, own)], [])
    assert [r["repealed_instrument_id"] for r in rows] == ["B"]
    assert stats["qualifier names only the repealer's own province"] == 1
    # another province, or a non-territorial qualifier, is still skipped
    for other in (own.replace("the Balochistan Province", "the Province of Sindh"),
                  own.replace("in its application to the Balochistan Province", "except section 4")):
        rows, stats = plan(inst, [("A", "s_20", 10, other)], [])
        assert rows == [] and stats["skipped: partial or qualified"] == 1, other


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
