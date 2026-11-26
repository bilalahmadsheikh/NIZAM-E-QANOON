"""'Cited by' (D-150): later judgments citing a judgment's case, by its number or a reporter citation the court
publishes for it. Database tests over the released corpus."""
from __future__ import annotations

from datetime import date, timedelta

import pytest


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


def _most_cited(repo):
    with repo.transaction() as conn:
        row = conn.execute("""
            SELECT c.judgment_id, min(r.decided_on) AS first_cited, count(DISTINCT r.judgment_id) AS citers
              FROM judgment_case_reference r
              JOIN judgment_case c ON c.case_key = r.dst_case_key
              JOIN v_shown_judgment j ON j.id = c.judgment_id AND j.decided_on = c.decided_on
             WHERE r.resolution = 'resolved' AND r.judgment_id <> c.judgment_id
             GROUP BY 1 ORDER BY 3 DESC LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no resolved case citation is held")
    return row


def test_a_cited_judgment_lists_the_judgments_citing_it(repo):
    row = _most_cited(repo)
    items = repo.citing_judgments(row["judgment_id"], date.today(), 50)
    assert items, "the most-cited judgment shows no citing judgment"
    assert all(str(i["judgment_id"]) != str(row["judgment_id"]) for i in items)      # never itself
    assert all(i["citation"] for i in items)                                          # rendered from records


def test_a_citing_judgment_carries_its_treatment_and_a_negative_one_waits_for_review(repo):
    # D-160: treatments read from the citing court's own words; negative ones only when lawyer_verified
    with repo.transaction() as conn:
        # a case with few citers, so the citing judgment is inside the first 50 the list returns
        row = conn.execute("""SELECT c.judgment_id, t.judgment_id AS citing, t.treatment, t.decided_on
                                FROM case_treatment t
                                JOIN judgment_case c ON c.case_key = t.dst_case_key
                                JOIN v_shown_judgment j ON j.id = c.judgment_id AND j.decided_on = c.decided_on
                               WHERE t.review_status = 'machine_candidate'
                                 AND (SELECT count(DISTINCT r.judgment_id) FROM judgment_case_reference r
                                       WHERE r.dst_case_key = t.dst_case_key AND r.resolution = 'resolved') < 20
                               LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no case treatment is held")
    items = repo.citing_judgments(row["judgment_id"], row["decided_on"], 50)
    mine = [i for i in items if str(i["judgment_id"]) == str(row["citing"])]
    assert mine
    if row["treatment"] in ("overruled", "per_incuriam", "disapproved"):
        assert row["treatment"] not in mine[0]["treatments"] and mine[0]["treatments_awaiting_review"] >= 1
    else:
        assert row["treatment"] in mine[0]["treatments"]


def test_cases_on_a_section_list_the_judgments_construing_it_first(repo):
    # D-161: interpreted, challenged or quoted before cited, before charged under
    with repo.transaction() as conn:
        row = conn.execute("""SELECT r.dst_provision_id FROM judgment_statute_reference r
                               WHERE r.resolution = 'resolved' AND r.role = 'interpreted'
                               GROUP BY 1 HAVING count(DISTINCT r.judgment_id) BETWEEN 5 AND 200
                               ORDER BY count(*) DESC LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no interpreted provision is held")
    items = repo.provision_judgments(row["dst_provision_id"], date.today(), 50)

    def weight(roles):
        return 3 if set(roles) & {"interpreted", "challenged", "quoted"} else (1 if set(roles) == {"charge"} else 2)
    w = [weight(i["roles"]) for i in items]
    assert w and w == sorted(w, reverse=True) and w[0] == 3


def test_cited_by_is_as_at_a_date(repo):
    row = _most_cited(repo)
    before = repo.citing_judgments(row["judgment_id"], row["first_cited"] - timedelta(days=1), 50)
    dated = [i for i in before if i.get("decided_on")]
    assert all(i["decided_on"] < row["first_cited"] for i in dated)
