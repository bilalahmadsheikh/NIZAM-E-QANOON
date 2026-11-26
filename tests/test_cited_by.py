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


def test_cited_by_is_as_at_a_date(repo):
    row = _most_cited(repo)
    before = repo.citing_judgments(row["judgment_id"], row["first_cited"] - timedelta(days=1), 50)
    dated = [i for i in before if i.get("decided_on")]
    assert all(i["decided_on"] < row["first_cited"] for i in dated)
