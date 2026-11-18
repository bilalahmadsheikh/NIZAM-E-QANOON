"""D-097 against the corpus: citation resolution from records only, the pg_search generic-plan guard, and the fused
lexical search's INV-5 gate and scope rules."""
from datetime import date, datetime

import pytest

TODAY = date(2026, 11, 19)


@pytest.fixture()
def db():
    try:
        from nizam.storage import unit_search
        from nizam.storage.lexical import Filters
        with unit_search.session(Filters(as_of=TODAY)) as s:
            s.cur.execute("SELECT to_regclass('chunk')")
            if s.cur.fetchone()[0] is None:
                pytest.skip("migration 0108 is not applied")
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    return True


def _resolve(q, territory=None):
    from nizam.retrieval import citations as C
    from nizam.storage import unit_search
    from nizam.storage.lexical import Filters
    with unit_search.session(Filters(as_of=TODAY, territory=territory)) as s:
        return C.resolve(s, C.find(q)[0])


def test_a_citation_resolves_to_the_unit_the_records_hold(db):
    c = _resolve("s. 302 PPC")
    assert c.resolved_law == "Pakistan Penal Code" and c.resolved_unit.path.endswith(".s_302")


def test_civil_procedure_never_falls_through_to_criminal_procedure(db):
    c = _resolve("section 96 of the Code of Civil Procedure, 1908")
    assert c.resolved_law.startswith("Code of Civil Procedure") and ".y1908_" in c.resolved_unit.path


def test_a_printed_spelling_of_the_label_is_found(db):
    c = _resolve("section 17-A of the Family Courts Act, 1964", territory="punjab")
    assert c.resolved_unit is not None
    assert c.resolved_unit.path.endswith("s_17_A") or any(a.path.endswith("s_17_A") for a in c.alternates)


def test_a_law_the_corpus_does_not_hold_is_unresolved_with_a_reason(db):
    c = _resolve("section 4 of the Imaginary Widgets Regulation Act, 1999")
    assert c.resolved_unit is None and "no served law" in c.unresolved


def test_pg_search_keeps_its_filter_past_the_tenth_execution(db):
    # 18 Nov 2026: under a generic plan pg_search dropped its match filter from the 11th run on one connection
    from nizam.storage import unit_search
    from nizam.storage.lexical import Filters
    with unit_search.session(Filters(as_of=TODAY)) as s:
        assert [len(s.instruments_titled("zzqx nonexistent title words", 5, ("fed",))) for _ in range(14)] == [0] * 14


def test_every_fused_candidate_is_operative_at_the_date(db):
    from nizam.retrieval.lexical import lexical_candidates
    from nizam.storage.db import connect
    from nizam.storage.lexical import Filters
    r = lexical_candidates("bail in a non-bailable offence", Filters(as_of=TODAY), 30)
    assert len(r.candidates) == 30 and [c.rank for c in r.candidates] == list(range(1, 31))
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', '', true)",
                    (TODAY.isoformat(),))
        cur.execute("SELECT count(DISTINCT version_id) FROM operative_provision WHERE version_id = ANY(%s::uuid[])",
                    ([c.version_id for c in r.candidates],))
        assert cur.fetchone()[0] == len({c.version_id for c in r.candidates})
        # candidates are provisions (INV-4): every id is a provision row
        cur.execute("SELECT count(*) FROM provision WHERE id = ANY(%s::uuid[])", ([c.unit_id for c in r.candidates],))
        assert cur.fetchone()[0] == 30


def test_a_place_sets_the_territory_and_an_explicit_scope_wins(db):
    from nizam.retrieval.lexical import lexical_candidates
    from nizam.storage.lexical import Filters
    q = "My landlord in Lahore wants me out of the house I rent. On what grounds can he get me evicted?"
    r = lexical_candidates(q, Filters(as_of=TODAY), 10)
    assert r.filters.territory == "punjab"
    assert any(c.unit_id == "874d4c34-6c75-478d-982d-ea3e4d0acb9c" for c in r.candidates[:3])   # PRPA 2009 s.15
    explicit = lexical_candidates(q, Filters(as_of=TODAY, jurisdictions=("sindh", "fed")), 10)
    assert explicit.filters.territory is None and explicit.filters.jurisdictions == ("sindh", "fed")


def test_a_resolved_citation_comes_first(db):
    from nizam.retrieval.lexical import lexical_candidates
    from nizam.storage.lexical import Filters
    r = lexical_candidates("What is the punishment under s. 302 PPC?", Filters(as_of=TODAY), 10)
    assert r.candidates[0].via_citation and r.trace["citations"][0]["law"] == "Pakistan Penal Code"


def test_as_of_must_be_a_date(db):
    from nizam.retrieval.lexical import lexical_candidates
    from nizam.storage.lexical import Filters
    with pytest.raises(ValueError, match="INV-5"):
        lexical_candidates("theft", Filters(as_of=datetime(2026, 11, 19, 9, 0)), 5)
