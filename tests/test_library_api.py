"""Contract and safety tests for the mobile browse slice; no corpus mutation."""
from datetime import date
from uuid import UUID
import pytest
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from nizam.api.library import Cursor, create_app

ID = UUID('00000000-0000-0000-0000-000000000001')


class Repository:
    def open(self): pass
    def close(self): pass

    def instruments(self, **kwargs):
        assert isinstance(kwargs['as_of'], date)
        return [dict(id=ID, title='Fixture only', kind='act', year=2020,
                     jurisdiction='fed', status='unknown', source_url=None,
                     document_id=1, source_hash='a'*64)]

    def instrument(self, *args, **kwargs): return None
    def provision(self, *args, **kwargs): return None
    def children(self, *args, **kwargs): return None
    def unit_text(self, *args, **kwargs): return None

    def instruments_by_document(self, document_ids, **kwargs):
        return [dict(id=UUID(int=d), title=t, kind='act', year=1860, jurisdiction='fed', status='unknown',
                     source_url=None, document_id=d, source_hash='a' * 64)
                for d, t in ((4441, 'Pakistan Penal Code'), (4337, 'Something Else Entirely'))]

    def section_index(self, instrument_id, **kwargs):
        if instrument_id != ID:
            return None
        inst = dict(id=ID, title='Fixture Act', kind='act', year=2020, jurisdiction='fed', status='unknown',
                    source_url=None, document_id=1, source_hash='a' * 64)
        sections = [dict(id=UUID(int=n), kind='section', label=str(n), heading=f'Heading {n}', ordinal=n * 10,
                         first_page=1, preview=f'Words of {n}', group=None,
                         citation=f'Fixture Act, 2020, s. {n}') for n in range(1, 8)]
        return dict(instrument=inst, law=None, sections=sections)


def test_scope_and_preview_are_explicit():
    with TestClient(create_app(Repository())) as client:
        r = client.get('/v1/law/instruments?as_of=2020-01-01')
        assert r.status_code == 200
        assert r.json()['as_of'] == '2020-01-01'
        assert r.json()['mode'] == 'research_preview'
        assert r.json()['items'][0]['status'] == 'unknown'
        assert r.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('query', ['limit=0', 'limit=500', 'as_of=invalid', 'jurisdiction=moon', 'q='+'x'*121])
def test_unbounded_or_invalid_input_rejected(query):
    with TestClient(create_app(Repository())) as client:
        assert client.get('/v1/law/instruments?'+query).status_code == 422


def test_unavailable_identity_never_falls_back_to_another_law():
    with TestClient(create_app(Repository())) as client:
        assert client.get(f'/v1/law/provisions/{ID}').status_code == 404
        assert client.get(f'/v1/law/instruments/{ID}/children').status_code == 404


def test_cursor_cannot_change_scope_or_be_tampered():
    c = Cursor(b'test-secret')
    token = c.encode(['fed', '2020-01-01'], str(ID))
    assert c.decode(token, ['fed', '2020-01-01']) == str(ID)
    # The tamper case must actually CHANGE the token. Substituting a fixed
    # letter does not: `Cursor.encode` signs a payload carrying
    # `int(datetime.now().timestamp())`, so the signature -- and its first
    # base64 character -- is different every second. Roughly one second in 64
    # that character is already 'X', `'X' + token[1:]` is the untouched token,
    # it decodes correctly, and the test fails claiming the tamper check is
    # broken when nothing is wrong. That is exactly what happened on
    # 21 Sep 2026. Pick a replacement that cannot equal what is there.
    tampered = ('Y' if token[0] == 'X' else 'X') + token[1:]
    assert tampered != token
    for bad, scope in [(token, ['sindh', '2020-01-01']), (tampered, ['fed', '2020-01-01'])]:
        with pytest.raises(Exception):
            c.decode(bad, scope)


def test_post_is_not_a_corpus_write_interface():
    with TestClient(create_app(Repository())) as client:
        assert client.post('/v1/law/instruments', json={}).status_code == 405


def test_unreleased_provision_never_reads_version_text():
    from contextlib import contextmanager
    from nizam.storage.library_read import LibraryRead
    queries=[]
    class Connection:
        def execute(self,sql,args):
            queries.append(sql)
            return self
        def fetchone(self): return {'instrument_id':ID}
    repo=LibraryRead.__new__(LibraryRead)
    @contextmanager
    def transaction(): yield Connection()
    repo.transaction=transaction
    # _instrument(conn, id, as_of, *, resolve_current) since migration 0064's as_of gate.
    repo._instrument=lambda conn,id,*args,**kwargs:None
    assert repo.provision(ID,as_of=date(2026,9,14)) is None
    assert not any('provision_version' in q for q in queries)


def test_unit_text_is_unavailable_rather_than_another_law_and_rejects_unknown_territory():
    with TestClient(create_app(Repository())) as client:
        assert client.get(f'/v1/law/provisions/{ID}/text').status_code == 404
        assert client.get(f'/v1/law/provisions/{ID}/text?territory=moon').status_code == 422


def test_unit_text_reads_the_serving_view_never_the_version_table():
    """INV-5: the reader's text comes from operative_provision, with as_of and territory set in the transaction."""
    from contextlib import contextmanager
    from nizam.storage.library_read import LibraryRead
    queries = []

    class Result:
        def __init__(self, rows): self.rows = rows
        def fetchone(self): return self.rows[0] if self.rows else None
        def fetchall(self): return self.rows

    class Connection:
        def execute(self, sql, args=None):
            queries.append(sql)
            if 'FROM operative_provision' in sql:
                return Result([dict(id=ID, parent_id=None, kind='section', label='1', heading='h', marginal_note=None,
                                    depth=0, first_page=1, text_en='t', text_ur=None, text_language='en',
                                    operation='enacted', survives_repeal=False)])
            if 'SELECT path::text' in sql:
                return Result([dict(path='fed.act.y2020.s_1')])
            if 'mv_instrument_serving' in sql:
                return Result([dict(currency='current', currency_reason='commenced_on_established',
                                    not_current_from=None, repealed_on=None, enacted_on=None, commenced_on=None,
                                    territory_reach=['punjab'], extent_basis='jurisdiction_default',
                                    territory_exits=None)])
            return Result([])

    repo = LibraryRead.__new__(LibraryRead)

    @contextmanager
    def transaction(): yield Connection()
    repo.transaction = transaction
    seen = {}

    def head(conn, pid, as_of, with_version=True):
        seen['with_version'] = with_version
        return dict(id=ID, instrument_id=ID)
    repo._provision = head
    out = repo.unit_text(ID, as_of=date(2026, 11, 17), territory='punjab')
    assert out['nodes'][0]['text_en'] == 't' and out['not_served'] is None
    assert any("set_config('nzq.as_of'" in q for q in queries)
    assert not any('provision_version' in q for q in queries)
    assert seen['with_version'] is False


def test_sections_page_in_printed_order_with_signed_scope_bound_continuation():
    with TestClient(create_app(Repository())) as client:
        first = client.get(f'/v1/law/instruments/{ID}/sections?limit=3&as_of=2026-11-17').json()
        assert [s['label'] for s in first['items']] == ['1', '2', '3'] and first['total'] == 7
        second = client.get(f'/v1/law/instruments/{ID}/sections?limit=3&as_of=2026-11-17'
                            f'&after={first["next_cursor"]}').json()
        assert [s['label'] for s in second['items']] == ['4', '5', '6']
        last = client.get(f'/v1/law/instruments/{ID}/sections?limit=3&as_of=2026-11-17'
                          f'&after={second["next_cursor"]}').json()
        assert [s['label'] for s in last['items']] == ['7'] and last['next_cursor'] is None
        # a continuation is bound to its date and territory: reusing it elsewhere is refused, not misapplied
        assert client.get(f'/v1/law/instruments/{ID}/sections?limit=3&as_of=2026-11-17&territory=sindh'
                          f'&after={first["next_cursor"]}').status_code == 400
        assert client.get(f'/v1/law/instruments/{UUID(int=99)}/sections').status_code == 404


def test_citation_is_rendered_from_fields_and_never_guessed():
    from nizam.storage.library_read import render_citation
    assert render_citation('Pakistan Penal Code', 1860, 'section', '302') == 'Pakistan Penal Code, 1860, s. 302'
    assert render_citation('Qanun-e-Shahadat Order, 1984', 1984, 'article', '129') == \
        'Qanun-e-Shahadat Order, 1984, Art. 129'
    assert render_citation('Pakistan Penal Code', 1860, 'section', None) is None
    assert render_citation(None, 1860, 'section', '302') is None
    # a preamble is cited by name, whatever its stored label
    assert render_citation('Pakistan Penal Code', 1860, 'preamble', 'Preamble') == 'Pakistan Penal Code, 1860, Preamble'
    assert render_citation('Pakistan Penal Code', 1860, 'preamble', None) == 'Pakistan Penal Code, 1860, Preamble'


def test_popular_collection_keeps_order_and_drops_a_document_whose_title_changed():
    with TestClient(create_app(Repository())) as client:
        body = client.get('/v1/law/collections/popular').json()
        # 4441 still carries the PPC title and is listed; 4337 no longer carries 'Contract Act' and is dropped
        assert [i['short_name'] for i in body['items']] == ['PPC']
        assert body['items'][0]['instrument']['title'] == 'Pakistan Penal Code'
