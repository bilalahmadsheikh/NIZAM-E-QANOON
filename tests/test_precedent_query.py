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


def test_a_reporter_citation_reads_to_the_case_the_court_lists_for_it(conn):
    # D-150: the Supreme Court's own listing prints '2026 SCMR 54' beside C.P. 4649 of 2022
    from nizam.retrieval.precedent import cases_named
    held = conn.execute("SELECT count(*) AS n FROM reporter_citation").fetchone()["n"]
    if not held:
        pytest.skip("the law-report index is not built")
    assert cases_named(conn, "what was held in 2026 SCMR 54?") == ["SC/CP/4649/2022"]
    # a report of the same judgment in a second series reads to the same case
    assert cases_named(conn, "2026 PLC (CS) 247") == cases_named(conn, "2026 SCMR 42") == ["SC/CP/1242-K/2024"]
    assert cases_named(conn, "2026 SCMR 999999") == []                                # not indexed: nothing invented


def test_for_a_forum_the_judgments_binding_it_take_a_vote_and_none_is_removed(conn):
    # D-154: asked from a KP court, Supreme Court and Peshawar judgments take one more vote; Lahore stays
    from datetime import date

    from nizam.retrieval.precedent import search
    from nizam.storage.authority import Subordinate
    q, day = "bail in a cheque dishonour case under section 489-F PPC", date(2026, 11, 24)
    plain = search(q, as_of=day, k=500, encoder=False)
    kp = search(q, as_of=day, k=500, forum=Subordinate("kp"), encoder=False)
    assert not any("binding" in h.generators for h in plain.hits)
    voted = [h for h in kp.hits if "binding" in h.generators]
    assert voted and all((h.authority or {}).get("status") == "binding" for h in voted)
    assert all((h.authority or {}).get("status") != "binding" for h in kp.hits if h not in voted)
    assert {h.judgment_id for h in plain.hits} == {h.judgment_id for h in kp.hits}        # a vote, not a filter

    def share(r):
        return sum(1 for h in r.hits[:10] if h.court in {x.court for x in voted})
    assert share(kp) >= share(plain)


def test_a_court_not_held_is_a_coverage_gap_with_no_hits(conn):
    from datetime import date

    from nizam.retrieval.precedent import search
    # the Islamabad High Court was the example until it was landed (D-156); the Federal Shariat Court is not held
    held = conn.execute("SELECT EXISTS (SELECT 1 FROM v_release_judgment WHERE court_code = 'FSC') AS h").fetchone()
    if held["h"]:
        pytest.skip("Federal Shariat Court judgments are now held")
    r = search("What has the Federal Shariat Court ruled on riba in banking?", as_of=date(2026, 11, 24), encoder=False)
    assert r.hits == [] and r.coverage_gap and r.coverage_gap["court"] == "FSC"


def test_islamabad_high_court_judgments_are_found_when_asked_for(conn):
    # D-156: once landed, a question naming the court narrows the search to it
    from datetime import date

    from nizam.retrieval.precedent import search
    r = search("What has the Islamabad High Court held on regularization of contract employees?",
               as_of=date(2026, 11, 26), encoder=False)
    assert r.coverage_gap is None and r.hits and {h.court for h in r.hits} == {"Islamabad High Court"}
