"""Appeal chains linked to the judgments below (D-159): the court below, the case line read in its own forms, and a
judgment's later history as at a date."""
from __future__ import annotations

from datetime import timedelta

import pytest

from nizam.workers.lineage_links import case_key_of, court_below

FORMS = {"LHC": [("criminal appeal", "LHC:CRLA"), ("cr a", "LHC:CRLA"), ("writ petition", "LHC:WP"),
                 ("civil revision", "LHC:CR")],
         "AJKHC": [("writ petition", "AJKHC:WP")]}


def test_the_court_below_is_the_one_printed_or_an_apex_courts_only_high_court():
    assert court_below("SC", "LHC", "Lahore High Court, Multan Bench") == ("LHC", "printed")
    assert court_below("AJKSC", None, "the High Court") == ("AJKHC", "sole_court_below")
    assert court_below("AJKSC", None, "the Shariat Appellate Bench of the High Court") == ("AJKHC", "sole_court_below")
    assert court_below("GBSAC", None, "passed by the High Court") == ("GBCC", "sole_court_below")
    # the Supreme Court has five High Courts below it: 'the High Court' names none of them
    assert court_below("SC", None, "the High Court") == (None, "none")
    assert court_below("AJKSC", None, "the Service Tribunal") == (None, "none")


def test_the_case_line_is_read_in_the_court_belows_own_forms():
    assert case_key_of("LHC", "Cr.A. No.652-J of 2016 and M.R. No.147 of 2013", FORMS) == "LHC/CRLA/652-J/2016"
    assert case_key_of("LHC", "Civil Revision No. 383/2010", FORMS) == "LHC/CR/383/2010"
    assert case_key_of("AJKHC", "Writ Petition No. 2117 of 2017", FORMS) == "AJKHC/WP/2117/2017"
    assert case_key_of("LHC", "LPA No.169 of 1968", FORMS) is None              # not a form of this court: not read
    assert case_key_of("LHC", "Writ Petition No. 12", FORMS) is None             # no year: not read
    assert case_key_of("LHC", None, FORMS) is None


@pytest.fixture(scope="module")
def repo():
    try:
        from nizam.storage.judgment_read import JudgmentRead
        r = JudgmentRead()
        r.open()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    yield r
    r.close()


def test_a_judgment_below_shows_what_the_court_above_did_as_at_a_date(repo):
    with repo.transaction() as conn:
        row = conn.execute("""SELECT k.lower_judgment_id, k.upper_judgment_id, k.upper_decided_on
                                FROM judgment_lineage_link k WHERE k.resolution = 'resolved'
                               ORDER BY k.upper_decided_on LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no appeal chain is linked to a held judgment")
    items = repo.later_history(row["lower_judgment_id"], row["upper_decided_on"])
    assert any(str(i["judgment_id"]) == str(row["upper_judgment_id"]) and i["matched"] == "judgment" for i in items)
    assert all(str(i["judgment_id"]) != str(row["lower_judgment_id"]) for i in items)       # never itself
    assert all(i["citation"] for i in items)                                                # rendered from records
    before = repo.later_history(row["lower_judgment_id"], row["upper_decided_on"] - timedelta(days=1))
    assert all(str(i["judgment_id"]) != str(row["upper_judgment_id"]) for i in before)      # not yet decided


def test_a_reversal_read_by_machine_is_withheld_until_a_lawyer_verifies_it(repo):
    # PRECEDENT-MODEL §2 / docs/06 §5.1: lineage reversals are displayed only when lawyer_verified
    with repo.transaction() as conn:
        row = conn.execute("""SELECT k.lower_judgment_id, k.upper_decided_on FROM judgment_lineage_link k
                                JOIN judgment_lineage l ON l.id = k.lineage_id
                               WHERE k.resolution = 'resolved' AND l.outcome IN ('set_aside', 'reversed', 'remanded')
                                 AND l.review_status <> 'lawyer_verified' LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no unverified reversal is linked")
    items = [i for i in repo.later_history(row["lower_judgment_id"], row["upper_decided_on"])
             if i["source"] == "upper_judgment"]
    assert items and all(i["outcome"] not in ("set_aside", "reversed", "remanded", "modified") for i in items)
    assert any(i["outcome_withheld"] for i in items)


def test_the_court_belows_own_record_is_a_labelled_second_source_as_at_a_date(repo):
    # D-159: the Islamabad High Court's listing records the Supreme Court's later outcome (0144)
    with repo.transaction() as conn:
        row = conn.execute("""SELECT judgment_id, outcome, upper_decided_on FROM judgment_recorded_outcome
                               WHERE upper_decided_on IS NOT NULL LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no recorded outcome is held")
    items = repo.later_history(row["judgment_id"], row["upper_decided_on"])
    rec = [i for i in items if i["source"] == "court_record"]
    assert rec and rec[0]["outcome"] == row["outcome"] and rec[0]["citation"] is None     # no citation invented
    before = repo.later_history(row["judgment_id"], row["upper_decided_on"] - timedelta(days=1))
    assert not [i for i in before if i["source"] == "court_record" and i["decided_on"] == row["upper_decided_on"]]
