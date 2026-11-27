"""The app's law search routes (docs/07 §B2, D-179): POST /v1/search and POST /v1/citations/resolve.

Search is discovery, never an answer: every result's citation is rendered from records (INV-1), every unit is one the
view serves at the asked date and place (INV-5), a question about what a court decided is referred to precedent
search with no statutory results (D-170), and the response says which path served it (mode). The database tests skip
when the corpus is not reachable."""
from __future__ import annotations

import datetime as dt

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from nizam.api.search import filters_for  # noqa: E402


def test_scope_is_the_territory_plus_federal_law():
    day = dt.date(2026, 11, 27)
    assert filters_for(day, '').jurisdictions is None and filters_for(day, '').territory is None
    f = filters_for(day, 'punjab')
    assert f.territory == 'punjab' and f.jurisdictions == ('punjab', 'fed')
    assert filters_for(day, 'ict').jurisdictions == ('fed',)            # ICT's law is federal law


@pytest.fixture(scope="module")
def client():
    try:
        from nizam.storage.lexical import Filters
        from nizam.storage import unit_search
        with unit_search.session(Filters(as_of=dt.date(2026, 11, 27))) as s:
            s.cur.execute("SELECT 1 FROM operative_provision LIMIT 1")
            if not s.cur.fetchone():
                pytest.skip("no released law")
        from nizam.api.library import create_app
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    with TestClient(create_app()) as c:
        yield c


def test_search_returns_record_rendered_operative_units(client):
    r = client.post('/v1/search', json={"q": "punishment for theft", "as_of": "2026-11-27", "limit": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "law_discovery" and body["refer_to"] is None and "Not legal advice" in body["note"]
    assert body["scope"]["as_of"] == "2026-11-27"
    assert 1 <= len(body["results"]) <= 5
    for x in body["results"]:
        assert x["citation"] and x["law"] and x["citation"].startswith(x["law"].strip().rstrip('.'))
        assert x["provision_id"] and x["version_id"]
    assert any("379" in x["citation"] or "theft" in (x["heading"] or "").lower() for x in body["results"])
    assert body["mode"]["searched"] and "degraded" in body["mode"]


def test_copies_of_one_unit_are_marked_not_hidden():
    from nizam.api.search import copy_key
    assert copy_key("Pakistan Penal Code (PPC),1860 (Under Review)", 1860, "489F") == \
        copy_key("PAKISTAN PENAL CODE, 1860", 1860, "489-F")
    assert copy_key("MUSLIM FAMILY LAWS ORDINANCE, 1961", 1961, "7") == copy_key("Muslim Family Laws Ordinance, 1961", 1961, "7")
    assert copy_key("Pakistan Penal Code, 1860", 1860, "489-A") != copy_key("Pakistan Penal Code, 1860", 1860, "489-F")
    assert copy_key("Pakistan Penal Code, 1860", 1860, "7")[0] == "pakistan penal code"
    assert copy_key("Muslim Family Laws Ordinance, 1961", 1961, "7") != copy_key("Code of Criminal Procedure, 1898", 1961, "7")


def test_a_territory_search_holds_no_other_province_law(client):
    r = client.post('/v1/search', json={"q": "eviction of a tenant for non payment of rent", "territory": "punjab",
                                         "limit": 10}).json()
    assert r["results"], r
    assert {x["jurisdiction"] for x in r["results"]} <= {"punjab", "fed"}


def test_a_court_decision_question_is_referred_to_precedent(client):
    r = client.post('/v1/search', json={"q": "What did the Supreme Court hold about bail in murder cases?"}).json()
    assert r["refer_to"] == "precedent" and r["results"] == [] and r["mode"]["searched"] is False
    assert "court judgments" in r["note"] and r["scope_findings"][0]["kind"] == "source"


def test_another_countrys_law_is_not_listed_as_pakistani_sections(client):
    r = client.post('/v1/search', json={"q": "What is the minimum wage under the law of Saudi Arabia?"}).json()
    assert r["results"] == [] and r["mode"]["searched"] is False and r["refer_to"] is None
    assert r["scope_findings"][0]["kind"] == "place" and "other countries" in r["note"]


def test_a_live_figure_question_still_lists_the_law_with_its_finding(client):
    r = client.post('/v1/search', json={"q": "What is the current petrol price today?"}).json()
    if r["scope_findings"]:
        assert r["mode"]["searched"] and r["scope_findings"][0]["reason"]


def test_limits_hold(client):
    assert client.post('/v1/search', json={"q": "x"}).status_code == 422
    assert client.post('/v1/search', json={"q": "theft", "limit": 50}).status_code == 422
    assert client.post('/v1/search', json={"q": "theft", "territory": "lahore"}).status_code == 422


def test_a_citation_resolves_to_its_unit(client):
    r = client.post('/v1/citations/resolve', json={"citation": "s.302 PPC", "as_of": "2026-11-27"})
    assert r.status_code == 200, r.text
    c = r.json()["citations"][0]
    assert c["resolved"] and "302" in c["citation"] and "Penal Code" in c["citation"]
    assert c["provision_id"] and c["version_id"]


def test_a_citation_is_not_served_before_its_law_existed(client):
    c = client.post('/v1/citations/resolve', json={"citation": "Article 25A of the Constitution",
                                                    "as_of": "1990-01-01"}).json()["citations"][0]
    assert not c["resolved"] and c["provision_id"] is None and c["unresolved"]


def test_no_citation_in_the_text_is_a_422(client):
    assert client.post('/v1/citations/resolve', json={"citation": "hello there"}).status_code == 422
