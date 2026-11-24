"""Precedent query understanding (D-137): the court a question asks for, and the case it prints.

Database tests: the court names and case types are records (court, court_alias, case_type, judicial_case)."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def conn():
    try:
        from nizam.storage.judgment_read import JudgmentRead
        r = JudgmentRead()
        r.open()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    with r.transaction() as c:
        yield c
    r.close()


def test_a_court_is_asked_for_only_when_its_judgments_are_the_question(conn):
    from nizam.retrieval.precedent import courts_named
    assert courts_named(conn, "What has the Sindh High Court held on bona fide need?") == ["SHC"]
    assert courts_named(conn, "What has the High Court of Baluchistan held about levies?") == ["BHC"]
    assert courts_named(conn, "Lahore High Court Writ Petition No. 12505 of 2020") == ["LHC"]
    assert courts_named(conn, "What did the Supreme Court decide on the transfer of judges?") == ["SC"]
    assert courts_named(conn, "What was the Supreme Court's precedent on further inquiry?") == ["SC"]
    assert courts_named(conn, "judgments of the Peshawar High Court on talb") == ["PHC"]
    # mentioned in passing, not asked for
    assert courts_named(conn, "Is there still a ceiling after the Federal Shariat Court's decision?") == []
    assert courts_named(conn, "Can a High Court quash an FIR under section 561-A CrPC?") == []


def test_a_printed_case_number_reads_to_a_held_case_key(conn):
    from nizam.retrieval.precedent import cases_named
    assert cases_named(conn, "Supreme Court Civil Appeal No. 415 of 2018", ["SC"]) == ["SC/CA/415/2018"]
    assert cases_named(conn, "Lahore High Court Writ Petition No. 12505 of 2020", ["LHC"]) == ["LHC/WP/12505/2020"]
    assert cases_named(conn, "Civil Appeal No. 999999 of 2018") == []                # not held: nothing invented
    assert cases_named(conn, "bail on the ground of further inquiry") == []


def test_a_court_not_held_is_a_coverage_gap_with_no_hits(conn):
    from datetime import date

    from nizam.retrieval.precedent import search
    held = conn.execute("SELECT EXISTS (SELECT 1 FROM v_release_judgment WHERE court_code = 'IHC') AS h").fetchone()
    if held["h"]:
        pytest.skip("Islamabad High Court judgments are now held")
    r = search("What has the Islamabad High Court held on section 20 PECA?", as_of=date(2026, 11, 24), encoder=False)
    assert r.hits == [] and r.coverage_gap and r.coverage_gap["court"] == "IHC"
