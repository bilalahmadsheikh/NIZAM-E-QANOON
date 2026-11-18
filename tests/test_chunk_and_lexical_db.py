"""Migration 0108 / D-095 against the corpus: the chunk table refuses a bad span, audit A20 sees a chunk outside the
release, and the lexical port (both implementations) finds law only as it is operative at the date asked."""
from datetime import date

import pytest

THEFT = ("Whoever, intending to take dishonestly any moveable property out of the possession of any person "
         "without that person's consent, moves that property in order to such taking")
PPC_378 = "fed.act.y1860_o147.ch_XVII.s_378"
RENT_S15 = "874d4c34-6c75-478d-982d-ea3e4d0acb9c"       # Punjab Rented Premises Act, 2009, s.15 (golden S1-C01)
PPC_462I = "d3fc4b4f-b9be-45de-8ab9-81b9e185cb2d"       # printed '462 I' (D-094)
TODAY = date(2026, 11, 19)


@pytest.fixture()
def conn():
    try:
        from nizam.storage.db import connect
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        with connect(autocommit=False) as handle:
            with handle.cursor() as cur:
                cur.execute("SELECT to_regclass('chunk'), (SELECT count(*) FROM chunk)")
                reg, n = cur.fetchone()
                if reg is None:
                    pytest.skip("migration 0108 is not applied")
                if not n:
                    pytest.skip("chunks are not built (python -m nizam.workers.chunk --apply)")
            yield handle
            handle.rollback()
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")


def test_a_span_past_its_version_text_is_refused(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT version_id, length(v.text_normalised) FROM chunk c JOIN provision_version v "
                    "ON v.id = c.version_id LIMIT 1")
        vid, n = cur.fetchone()
        with pytest.raises(Exception, match="beyond its text"):
            cur.execute("INSERT INTO chunk (version_id, seq, char_start, char_end, context_prefix, chunker) "
                        "VALUES (%s, 999, 0, %s, 'x', 'test')", (vid, n + 1))


def test_audit_a20_sees_a_chunk_outside_the_release(conn):
    q = """SELECT count(*) FROM chunk c
            WHERE NOT EXISTS (SELECT 1 FROM v_release_provision_version r WHERE r.id = c.version_id)"""
    with conn.cursor() as cur:
        cur.execute(q)
        before = cur.fetchone()[0]
        cur.execute("""SELECT v.id FROM provision_version v
                        WHERE length(v.text_normalised) > 5
                          AND NOT EXISTS (SELECT 1 FROM v_release_provision_version r WHERE r.id = v.id) LIMIT 1""")
        row = cur.fetchone()
        if row is None:
            pytest.skip("every version is released")
        cur.execute("INSERT INTO chunk (version_id, seq, char_start, char_end, context_prefix, chunker) "
                    "VALUES (%s, 0, 0, 5, 'x', 'nizam.chunking/1')", (row[0],))
        cur.execute(q)
        assert cur.fetchone()[0] == before + 1


def _paths(cands):
    from nizam.storage.db import connect
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT id::text, path::text FROM provision WHERE id = ANY(%s::uuid[])",
                    ([x.provision_id for x in cands],))
        p = dict(cur.fetchall())
    return [p[x.provision_id] for x in cands]


@pytest.mark.parametrize("impl", ["Bm25LexicalSearch", "TsRankLexicalSearch"])
def test_both_implementations_find_the_definition_of_theft(conn, impl):
    import nizam.storage.lexical as L
    got = getattr(L, impl)().search(THEFT, L.Filters(as_of=TODAY, jurisdictions=("fed",)), 10)
    assert got and [c.rank for c in got] == list(range(1, len(got) + 1))
    assert PPC_378 in _paths(got[:5])


def test_every_candidate_is_operative_at_the_date(conn):
    import nizam.storage.lexical as L
    got = L.Bm25LexicalSearch().search("bail non-bailable offence", L.Filters(as_of=TODAY), 40)
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', '', true)",
                    (TODAY.isoformat(),))
        cur.execute("SELECT count(*) FROM operative_provision WHERE version_id = ANY(%s::uuid[])",
                    ([c.version_id for c in got],))
        assert cur.fetchone()[0] == len(got) == 40


def test_as_of_excludes_a_law_not_yet_made(conn):
    import nizam.storage.lexical as L
    s = L.Bm25LexicalSearch()
    now = s.headings("grounds for eviction", L.Filters(as_of=TODAY, jurisdictions=("punjab",)), 50)
    assert RENT_S15 in {c.provision_id for c in now}
    before = s.headings("grounds for eviction", L.Filters(as_of=date(2000, 1, 1), jurisdictions=("punjab",)), 50)
    assert RENT_S15 not in {c.provision_id for c in before}


def test_a_label_lookup_folds_the_printed_space(conn):
    import nizam.storage.lexical as L
    for asked in ("462I", "462 I", "462i"):
        got = L.Bm25LexicalSearch().labels(asked, L.Filters(as_of=TODAY, jurisdictions=("fed",)))
        assert PPC_462I in {c.provision_id for c in got}, asked


def test_contract_edges(conn):
    import nizam.storage.lexical as L
    assert L.Bm25LexicalSearch().search("   ", L.Filters(as_of=TODAY), 10) == []
    with pytest.raises(ValueError, match="INV-5"):
        L.Bm25LexicalSearch().search("theft", L.Filters(as_of="2026-11-18"), 10)


def test_the_any_term_fallback_stems_each_term_once(conn):
    # review 18 Nov 2026: re-parsing plainto_tsquery's output stemmed 'provisions' to 'provi', which no index holds
    with conn.cursor() as cur:
        cur.execute("SELECT replace(plainto_tsquery('english', 'provisions purpose otherwise')::text, ' & ', ' | ')"
                    "::tsquery::text")
        assert cur.fetchone()[0] == "'provis' | 'purpos' | 'otherwis'"
    import nizam.storage.lexical as L
    got = L.TsRankAnyLexicalSearch().search("provisions purpose", L.Filters(as_of=TODAY), 5)
    assert len(got) == 5 and not got.truncated


def test_a_datetime_is_not_an_as_of_date(conn):
    from datetime import datetime
    import nizam.storage.lexical as L
    with pytest.raises(ValueError, match="not a datetime"):
        L.Bm25LexicalSearch().search("theft", L.Filters(as_of=datetime(2026, 11, 18, 12, 0)), 5)


def test_labels_can_be_confined_to_a_law_and_come_in_printed_order(conn):
    import nizam.storage.lexical as L
    s = L.Bm25LexicalSearch()
    with conn.cursor() as cur:
        cur.execute("SELECT instrument_id::text FROM provision WHERE id = %s", (PPC_462I,))
        ppc = cur.fetchone()[0]
    only = s.labels("462I", L.Filters(as_of=TODAY), instruments=(ppc,))
    assert [c.provision_id for c in only] == [PPC_462I]
    many = s.labels("302", L.Filters(as_of=TODAY), 30)
    assert all(c.score == 1.0 for c in many) and isinstance(many, L.Candidates)
