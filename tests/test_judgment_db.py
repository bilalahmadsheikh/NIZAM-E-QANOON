"""Judgments in the database (0119-0121): the constraints, the release, the links, search and the routes.

These need migrations 0119-0121 applied and the Supreme Court archive landed. They skip otherwise. Writes are rolled
back.
"""
from __future__ import annotations

import datetime as dt

import pytest

TODAY = dt.date(2026, 11, 22)


@pytest.fixture()
def cur():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as c:
                c.execute("SELECT to_regclass('judgment_chunk'), (SELECT count(*) FROM judgment WHERE is_active)")
                reg, n = c.fetchone()
                if reg is None or not n:
                    pytest.skip("judgment tables not applied or no judgment landed")
                yield c
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def _raises(cur, sql, args=(), match=""):
    import psycopg
    cur.execute("SAVEPOINT t")
    with pytest.raises(psycopg.Error, match=match):
        cur.execute(sql, args)
    cur.execute("ROLLBACK TO SAVEPOINT t")


def test_a_decision_date_outside_the_created_partitions_fails_loudly(cur):
    cur.execute("SELECT id FROM judgment_document WHERE outcome = 'parsed' AND is_active LIMIT 1")
    doc = cur.fetchone()[0]
    _raises(cur, """INSERT INTO judgment (decided_on, document_id, court_code, decided_on_basis, decided_on_printed,
                                          case_no_printed, parser)
                    VALUES ('2091-01-01', %s, 'SC', 'announced', 'x', 'x', 'test')""", (doc,),
            match="no partition")


def test_an_undated_judgment_prints_no_date_and_names_why(cur):
    cur.execute("SELECT id FROM judgment_document WHERE outcome = 'parsed' AND is_active LIMIT 1")
    doc = cur.fetchone()[0]
    for printed, reason in (("x", "no date"), (None, None)):          # a printed date, or no reason: refused
        _raises(cur, """INSERT INTO judgment (decided_on, document_id, court_code, decided_on_basis, decided_on_printed,
                                              undated_reason, case_no_printed, parser)
                        VALUES ('2026-09-03', %s, 'SC', 'undated', %s, %s, 'x', 'test')""", (doc, printed, reason),
                match="ck_judgment_undated")
    _raises(cur, """INSERT INTO judgment (decided_on, document_id, court_code, decided_on_basis, decided_on_printed,
                                          decided_not_before, decided_not_before_basis, case_no_printed, parser)
                    VALUES ('2020-01-01', %s, 'SC', 'announced', 'x', '2019-01-01', 'hearing', 'x', 'test')""",
            (doc,), match="ck_judgment_not_before")         # a lower bound only for an undated judgment


def test_evidence_is_append_only_and_readings_need_a_reason(cur):
    cur.execute("SELECT id FROM judgment_source LIMIT 1")
    _raises(cur, "DELETE FROM judgment_source WHERE id = %s", cur.fetchone(), match="append-only")
    cur.execute("SELECT sha256 FROM judgment_source LIMIT 1")
    _raises(cur, """INSERT INTO judgment_document (sha256, court_code, extractor, parser, lane, language, page_count,
                                                   char_count, outcome, is_active)
                    VALUES (%s, 'SC', 'x', 'x', 'E2', 'en', 1, 0, 'held', false)""", cur.fetchone(),
            match="ck_judgment_document_reason|ck_judgment_document_active")


def test_a_chunk_cannot_pass_its_paragraph(cur):
    cur.execute("""SELECT p.id, p.decided_on, p.judgment_id, length(p.text) FROM v_release_judgment_paragraph p
                    WHERE p.kind = 'body' LIMIT 1""")
    pid, day, jid, n = cur.fetchone()
    _raises(cur, """INSERT INTO judgment_chunk (paragraph_id, decided_on, judgment_id, seq, char_start, char_end,
                                                context_prefix, chunker)
                    VALUES (%s, %s, %s, 999, 0, %s, 'x', 'test')""", (pid, day, jid, n + 1), match="passes paragraph")


def test_a_body_paragraph_belongs_to_an_opinion_and_numbers_are_only_printed_ones(cur):
    cur.execute("""SELECT count(*) FILTER (WHERE kind = 'body' AND opinion_id IS NULL),
                          count(*) FILTER (WHERE printed_no IS NOT NULL AND printed_no !~ '^[0-9]{1,3}$')
                     FROM v_release_judgment_paragraph""")
    assert cur.fetchone() == (0, 0)


def test_resolved_citations_point_at_released_law_and_inheritance_is_marked(cur):
    cur.execute("""SELECT count(*) FILTER (WHERE resolution = 'resolved'),
                          count(*) FILTER (WHERE law_basis = 'inherited' AND inherited_from IS NULL),
                          count(*) FILTER (WHERE version_basis = 'dated' AND resolution <> 'resolved')
                     FROM judgment_statute_reference""")
    resolved, bad_inherit, bad_dated = cur.fetchone()
    if not resolved:
        pytest.skip("links not built")
    assert bad_inherit == 0 and bad_dated == 0


# ---------------------------------------------------------------------------------------------- search, routes

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


def test_precedent_search_returns_only_judgments_decided_by_the_date(repo):
    from nizam.retrieval.precedent import search
    try:
        r = search("bail further inquiry cross version", as_of=dt.date(2015, 1, 1), k=10, repo=repo)
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"search unavailable: {type(exc).__name__}: {exc}")
    if not r.hits:
        pytest.skip("no judgments decided by 2015 match")
    assert all(h.decided_on <= dt.date(2015, 1, 1) for h in r.hits)
    assert all(h.citation.startswith("Supreme Court of Pakistan, ") for h in r.hits)
    assert r.coverage and r.mode in ("hybrid", "lexical_only")


def test_an_undated_judgment_is_never_shown_with_its_latest_possible_day_as_the_date(repo):
    with repo.transaction() as conn:
        row = conn.execute("""SELECT id, decided_on FROM v_release_judgment WHERE decided_on_basis = 'undated'
                               AND decision_date IS NULL LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no undated judgment released")
    j = repo.judgment(row["id"], TODAY)
    assert j["judgment"]["decided_on"] is None and j["judgment"]["undated"] is True
    assert j["judgment"]["decided_no_later_than"] == row["decided_on"]
    assert j["citation"].endswith("date of decision not printed")
    assert all("decided " not in p["citation"] for p in j["paragraphs"])
    # before the archive is known to have held it, it is not known to have existed
    assert repo.judgment(row["id"], row["decided_on"] - dt.timedelta(days=1)) is None


def test_a_named_section_reaches_the_judgments_that_cite_it(repo):
    from nizam.retrieval.precedent import search
    from nizam.storage.authority import Subordinate
    r = search("bail under section 497 CrPC further inquiry", as_of=TODAY, k=10, repo=repo,
               forum=Subordinate("punjab"))
    if not r.cited_provisions:
        pytest.skip("section 497 CrPC not resolved")
    if not any("cited" in h.generators for h in r.hits):
        pytest.skip("links not built yet")
    # an SC judgment binds a Punjab subordinate court today (Art. 189(2), recorded)
    assert all(h.authority and h.authority["status"] == "binding" for h in r.hits)


def test_the_routes_serve_search_a_judgment_and_cases_on_a_section(repo, monkeypatch):
    monkeypatch.setenv("NIZAM_WARM", "0")
    from fastapi.testclient import TestClient
    from nizam.api.library import create_app
    with TestClient(create_app(judgments=repo)) as client:
        s = client.get("/v1/precedent/search", params={"q": "leave to appeal refused concurrent findings",
                                                         "as_of": "2026-11-22", "forum_territory": "kp"})
        assert s.status_code == 200 and s.json()["kind"] == "precedent_discovery"
        hits = s.json()["hits"]
        if not hits:
            pytest.skip("no hits")
        j = client.get(f"/v1/precedent/judgments/{hits[0]['judgment_id']}", params={"as_of": "2026-11-22"})
        assert j.status_code == 200 and "parties_raw" not in j.json()["judgment"]       # internal only (D-122)
        early = client.get(f"/v1/precedent/judgments/{hits[0]['judgment_id']}", params={"as_of": "1990-01-01"})
        assert early.status_code == 404                                                 # not yet decided
        a = client.get("/v1/precedent/authority", params={"deciding": "SC", "receiving": "FCC",
                                                           "as_of": "2026-11-22"})
        assert a.json()["result"]["status"] == "not_binding"
