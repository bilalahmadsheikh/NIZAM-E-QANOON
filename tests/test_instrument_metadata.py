"""Instrument metadata from evidence (migration 0070) and the readers that record it.

Pure tests pin each reader's rule, including the failure it exists to prevent (a number cited in the body read as the
instrument's own, a contents line cutting the title region, a commencement by notification recorded as a date). The
database tests need 0070 applied and roll everything back.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import record_amendment_references as amend  # noqa: E402
import record_commencement as comm  # noqa: E402
import record_enacted_dates as enact  # noqa: E402
import record_instrument_numbers as nums  # noqa: E402
import record_text_language as lang  # noqa: E402


def region_of(*lines: str) -> str:
    return nums.title_region([(i + 1, 1, t) for i, t in enumerate(lines)])[0]


# --- numbers ------------------------------------------------------------------------------------------------------
def test_number_is_read_from_the_title_region():
    region = region_of("THE PROTECTION OF PAKISTAN ACT, 2014", "ACT NO. X OF 2014", "[14th July, 2014]",
                       "An Act to provide for protection against waging of war")
    assert {f[0] for f in nums.candidates(region, "act", 2014)} == {"X"}


def test_a_number_cited_after_the_long_title_is_never_read():
    region = region_of("THE X (AMENDMENT) ACT, 1990", "An Act further to amend the X Act, 1990 (XV of 1990)")
    assert nums.candidates(region, "act", 1990) == set()


def test_a_contents_line_does_not_cut_the_region_before_the_title():
    region = region_of("CONTENTS", "1. Short title and commencement", "2. Definitions",
                       "THE SEED ACT, 1976", "ACT No. XXIX OF 1976", "1. (1) This Act may be called")
    assert "ACT No. XXIX OF 1976" in region
    assert {f[0] for f in nums.candidates(region, "act", 1976)} == {"XXIX"}


def test_without_a_title_end_marker_the_body_is_not_read():
    # doc 6701: 'Election Commission Order, 2002 (C.E's Order No. I of 2002)' was cited in section 3
    blocks = ["GAZETTE OF PAKISTAN"] + ["filler"] * 25 + ["Election Commission Order, 2002 (C.E's Order No. I of 2002)"]
    region = region_of(*blocks)
    assert nums.candidates(region, "order", 2002) == set()


def test_ocr_noise_and_a_lone_one_are_refused():
    assert nums.normalise("XIl") is None
    assert nums.normalise("1") is None
    assert nums.normalise("XXVI") == "XXVI"
    assert nums.normalise("IIII") is None             # not canonical
    assert nums.normalise("18") == "18"


def test_a_number_glued_to_of_is_refused():
    # doc 5726: 'ACT NO.LOF 2010' is 'I OF', not L (50)
    assert nums.candidates(region_of("(ACT NO.LOF 2010)"), "act", 2010) == set()


def test_another_instruments_heading_just_before_is_refused():
    # doc 9449: '... ABAD ACT, 2009 SINDH ACT NO: XIX OF 2010' belongs to the Act printed before
    assert nums.candidates(region_of("ABAD ACT, 2009 SINDH ACT NO: XIX OF 2010"), "act", 2010) == set()


def test_kind_and_year_must_agree():
    region = region_of("ORDINANCE No. XII of 2001")
    assert nums.candidates(region, "act", 2001) == set()
    assert nums.candidates(region, "ordinance", 2002) == set()
    assert {f[0] for f in nums.candidates(region, "ordinance", 2001)} == {"XII"}


# --- enactment dates ----------------------------------------------------------------------------------------------
def test_bracket_and_assent_dates():
    assert enact.BRACKET.search("Act No. XXIX oF 1956 [18th April, 1956] An Act").groups() == ("18", "April", "1956")
    m = enact.ASSENT.search("received the assent of the Governor General on the 21st March, 1908, and")
    assert enact.to_date(*m.groups()).isoformat() == "1908-03-21"
    assert enact.to_date("30", "February", "1956") is None


def _dates(region: str, kind: str, year: int) -> set[str]:
    spans, pos = [], 0
    for i, line in enumerate(region.split("\n")):
        spans.append((pos, pos + len(line), i + 1, 1)); pos += len(line) + 1
    found = enact.printed_dates(region, spans, kind, enact.number_years(region, kind, year))
    return {f"{d.isoformat()} {how}" for d, how, _s, _e in found}


def test_v2_assented_and_promulgation_statements():
    sindh = ("NO.PAS/LEGIS-B-23/2021-The Sindh Zakat and Ushr (Amendment) Bill, 2021, having been passed by the "
             "Provincial Assembly of Sindh on 05th July, 2021 and assented to by the Governor of Sindh on 28th July, "
             "2021 is hereby published")
    assert _dates(sindh, "act", 2021) == {"2021-07-28 assent"}
    ajk = "The following Ordinance made by the President on the 26th day of August, 1979, is hereby published"
    assert _dates(ajk, "ordinance", 1979) == {"1979-08-26 promulgation"}
    assert _dates("assented to by the Governor of Sindh on 25™-July, 2018 is", "act", 2018) == {"2018-07-25 assent"}
    # a two-digit year is never read
    assert _dates("The following Ordinance made by the President on 3.5.75 is hereby", "ordinance", 1975) == set()


def test_v2_notification_date_only_for_subordinate_instruments():
    rules = "GOVERNMENT OF THE PUNJAB\nDated Lahore, the 15th November 2021\nNOTIFICATION No.SO(E-IV)5-14/2021"
    assert _dates(rules, "rules", 2021) == {"2021-11-15 notification_date"}
    kp = "Notification Peshawar, dated the 2.11.2004 No.SO(Tech)ED/V-105/2003"
    assert _dates(kp, "rules", 2004) == {"2004-11-02 notification_date"}
    # on an Act the Assembly's 'Dated Quetta, the ...' line is its publication, not its enactment
    act = "BALOCHISTAN PROVINCIAL ASSEMBLY SECRETARIAT Dated Quetta, the 05th May, 2021. NOTIFICATION."
    assert _dates(act, "act", 2021) == set()


def test_v2_a_gazette_masthead_or_publication_line_is_never_the_date():
    assert _dates("THE SIND GOVERNMENT GAZETTE KARACHI,11TH AUGUST, 1977.\nNOTIFICATION", "rules", 1977) == set()
    assert _dates("[Gazette of Sind (Extraordinary), dated the\n26th March, 1991].\nAN ACT", "act", 1991) == set()
    assert _dates("SECRETARIAT, MUZAFFARABAD.\nDated 24th September, 1984.\nNo. 1/LD/84", "ordinance", 1984) == set()


def test_v2_date_line_under_the_title():
    region = "SINDH ACT NO. XXV OF 2015.\nTHE SINDH FINANCE (AMENDMENT) ACT, 2015.\n18th May, 2015.\n"
    assert _dates(region, "act", 2015) == {"2015-05-18 date_line"}


def test_v2_year_of_the_printed_number_within_two_years_only():
    region = "SIND ORDINANCE NO.XIII OF 1971\nTHE WEST PAKISTAN CIVIL COURTS (SIND AMENDMENT) ORDINANCE, 1970\n" \
             "[8th December, 1971]"
    assert "1971-12-08 bracket" in _dates(region, "ordinance", 1970)
    far = "PRESIDENT'S ACT No. VI oF 1957.\n[4th July, 1957]"
    assert _dates(far, "act", 1931) == set()
    # an explicit assent statement outranks the consolidator's bracket (6027: assent 1 Feb, bracket 4 Feb)
    both = "ACT 1999 (II of 1999)\n[4th February, 1999]\nreceived the assent of the Governor on the 1st February, 1999"
    spans, pos = [], 0
    for i, line in enumerate(both.split("\n")):
        spans.append((pos, pos + len(line), i + 1, 1)); pos += len(line) + 1
    found = enact.printed_dates(both, spans, "act", {1999})
    top = min(enact.RANK[f[1]] for f in found)
    assert {f[0].isoformat() for f in found if enact.RANK[f[1]] == top} == {"1999-02-01"}
    # a rule's region cites its enabling Act's number: never a second year for a rule
    assert enact.number_years("under the Punjab Act No. XIII of 2002", "rules", 2005) == {2005}


# --- commencement -------------------------------------------------------------------------------------------------
def test_general_clauses_default_only_for_a_silent_act_with_its_date_form():
    silent = [("1", "Short title and extent", "(1) This Act may be called the Foo Act, 2010."),
              ("2", "Definitions", "In this Act, unless the context otherwise requires,")]
    # federal: only an explicit assent statement is the day of assent (s.5(1))
    assert comm.general_clauses_default("fed", "act", 2010, "2010-05-21", "printed_assent_statement", silent) == \
        ("2010-05-21", "general_clauses_s5_assent")
    assert comm.general_clauses_default("fed", "act", 2010, "2010-05-25", "printed_assent_date", silent)[0] is None
    # provincial: only the date printed under the title is the first publication (s.3)
    assert comm.general_clauses_default("punjab", "act", 1999, "1999-02-04", "printed_assent_date", silent) == \
        ("1999-02-04", "general_clauses_s3_first_publication")
    assert comm.general_clauses_default("punjab", "act", 1999, "1999-02-01", "printed_assent_statement",
                                        silent)[0] is None
    # never: Sindh / AJK (no general clauses section held), Ordinances, before the statute, or any text that speaks
    for jur, kind, year in (("sindh", "act", 2010), ("ajk", "act", 2010), ("punjab", "ordinance", 1999),
                            ("punjab", "act", 1950)):
        assert comm.general_clauses_default(jur, kind, year, "1999-02-04", "printed_assent_date", silent)[0] is None
    # a West Pakistan Act filed under fed is not a Central Act (9657, 9677)
    assert comm.general_clauses_default("fed", "act", 1958, "1958-03-31", "printed_assent_statement", silent,
                                        "West Pakistan Appropriation Act, 1958")[1] == "provincial_act_filed_fed"
    speaks = silent + [("3", None, "This section shall take effect from the 1st July.")]
    assert comm.general_clauses_default("punjab", "act", 1999, "1999-02-04", "printed_assent_date", speaks)[0] is None
    promises = [("1", "Short title, extent and commencement", "(1) This Act may be called the Foo Act, 1999.")]
    assert comm.general_clauses_default("punjab", "act", 1999, "1999-02-04", "printed_assent_date",
                                        promises)[1] == "section_1_promises_a_commencement"
    assert comm.general_clauses_default("punjab", "act", 1999, "1999-02-04", "printed_assent_date",
                                        silent[1:])[1] == "section_1_not_found"


def test_at_once_takes_the_printed_enactment_date():
    v, basis, _ = comm.classify("(3) It shall come into force at once.", "1959-04-29", 1959)
    assert (v, basis) == ("1959-04-29", "commences_at_once_on_printed_enactment_date")


def test_at_once_without_an_enactment_date_records_nothing():
    assert comm.classify("It shall come into force at once.", None, 1959)[0] is None


def test_a_printed_commencement_date():
    v, basis, _ = comm.classify("It shall come into force on the 1st day of July, 1957.", None, 1957)
    assert (v, basis) == ("1957-07-01", "commences_on_printed_date")


@pytest.mark.parametrize("text", [
    "It shall come into force on such date as the Federal Government may, by notification, appoint.",
    "It shall come into force at once, except section 5 which shall come into force on 1st July, 1990.",
    "(3) It shall come into force—(a) in the Federal Capital, at once; (b) elsewhere on notification.",
    "It shall be deemed to have come into force on the 1st day of July, 1955.",
])
def test_notified_partial_enumerated_or_deemed_commencement_is_never_recorded(text):
    assert comm.classify(text, "1990-01-01", 1990)[0] is None


# --- text language ------------------------------------------------------------------------------------------------
def test_language_measurement():
    assert lang.classify(1000, 10, 0) == "en"
    assert lang.classify(10, 1000, 0) == "ur"
    assert lang.classify(10, 1000, 50) == "sd"
    assert lang.classify(700, 300, 0) is None        # mixed: a person reads it
    assert lang.classify(5, 0, 0) is None            # too little text


# --- amendment footnotes ------------------------------------------------------------------------------------------
def test_footnote_entries_split_at_their_markers():
    entries = amend.split_entries("1 Subs. by Act IV of 2017, s. 4. 2Ins. by Act IX of 2004, s. 9.")
    assert [m for m, _ in entries] == ["1", "2"]


def test_footnote_parse():
    p = amend.parse_entry("Subs. by the Law Reforms Ordinance, 1972 (XII of 1972), s. 2, for \"x\".", 1960)
    assert p["operations"] == ["substituted"]
    assert (p["cited_title"], p["cited_kind"], p["cited_number"], p["cited_year"]) == \
           ("Law Reforms Ordinance", "ordinance", "XII", 1972)
    p = amend.parse_entry("Substituted for the figures “1500”, by Federal Act IX of 1993, effective from "
                          "1st July, 1992; published", 1980)
    assert (p["cited_number"], p["cited_year"], p["effective_from"]) == ("IX", 1993, "1992-07-01")
    p = amend.parse_entry("Added, subs & ins. by Act I of 05, s.11.", 1990)
    assert p["cited_year"] == 2005 and p["operations"] == ["added", "inserted", "substituted"]


def test_footnote_shapes_that_are_not_amendments_are_refused():
    assert amend.parse_entry("For Statement of Objects and Reasons, see Gazette of Pakistan", 1950) is None
    assert amend.parse_entry("Substituted, ibid.", 1950) is None


# --- the database -------------------------------------------------------------------------------------------------
@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("SELECT to_regclass('instrument_metadata_assertion'), to_regclass('operative_provision')")
                if None in cur.fetchone():
                    pytest.skip("migrations 0070/0071 are not applied")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def _any_landed_observation(cur) -> int:
    cur.execute("SELECT source_observation_id FROM instrument WHERE is_active AND duplicate_of IS NULL LIMIT 1")
    return cur.fetchone()[0]


def test_assertions_are_append_only(conn):
    with conn.cursor() as cur:
        cur.execute("SAVEPOINT s")
        cur.execute("SELECT min(id) FROM instrument_metadata_assertion")
        first = cur.fetchone()[0]
        if first is None:
            pytest.skip("no assertion recorded yet")
        with pytest.raises(Exception, match="append-only"):
            cur.execute("UPDATE instrument_metadata_assertion SET basis = basis WHERE id = %s", (first,))
        cur.execute("ROLLBACK TO SAVEPOINT s")
        with pytest.raises(Exception, match="append-only"):
            cur.execute("DELETE FROM instrument_metadata_assertion WHERE id = %s", (first,))
        cur.execute("ROLLBACK TO SAVEPOINT s")


def test_an_impossible_date_and_an_unquoted_printed_fact_are_refused(conn):
    with conn.cursor() as cur:
        obs = _any_landed_observation(cur)
        cur.execute("SAVEPOINT s")
        with pytest.raises(Exception):
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis, method,
                              evidence, recorded_by)
                           VALUES (%s, 97, 'enacted_on', '1956-02-30', 'asserted', 'x', 'test',
                                   '{"reviewer_type":"test"}', 'test')""", (obs,))
        cur.execute("ROLLBACK TO SAVEPOINT s")
        with pytest.raises(Exception):
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis, method,
                              evidence, recorded_by)
                           VALUES (%s, 97, 'number', 'IV', 'asserted', 'x', 'test', '{"reviewer_type":"test"}',
                                   'test')""", (obs,))
        cur.execute("ROLLBACK TO SAVEPOINT s")


def test_operative_view_refuses_a_read_without_as_of(conn):
    with conn.cursor() as cur:
        cur.execute("SAVEPOINT s")
        cur.execute("RESET nzq.as_of")
        with pytest.raises(Exception, match="nzq.as_of is not set"):
            cur.execute("SELECT 1 FROM operative_provision LIMIT 1")
        cur.execute("ROLLBACK TO SAVEPOINT s")


def test_urdu_text_is_never_served_as_english(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM instrument WHERE is_active AND duplicate_of IS NULL AND text_language = 'ur' "
                    "LIMIT 1")
        row = cur.fetchone()
        if row is None:
            pytest.skip("no Urdu expression recorded")
        cur.execute("SET LOCAL nzq.as_of = '2026-11-11'")
        cur.execute("""SELECT count(*), count(text_en), count(text_ur) FROM operative_provision
                        WHERE instrument_id = %s""", (row[0],))
        total, en, ur = cur.fetchone()
        assert en == 0 and ur == total


def test_a_repealed_instrument_is_not_operative_after_its_repeal(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, repealed_on FROM instrument WHERE is_active AND duplicate_of IS NULL "
                    "AND status = 'repealed' ORDER BY repealed_on DESC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            pytest.skip("no repealed instrument")
        cur.execute("SET LOCAL nzq.as_of = '2026-11-11'")
        cur.execute("SELECT count(*) FROM operative_provision WHERE instrument_id = %s", (row[0],))
        assert cur.fetchone()[0] == 0
