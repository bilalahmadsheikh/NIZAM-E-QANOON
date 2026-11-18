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


def test_a_constitution_is_cited_by_article():
    from nizam.storage.library_read import render_citation
    # the segmenter stores the Constitution's numbered units as `section`; the instrument kind decides the word
    assert render_citation('Constitution of the Islamic Republic of Pakistan', 1973, 'section', '199', 'constitution') \
        == 'Constitution of the Islamic Republic of Pakistan, 1973, Art. 199'
    assert render_citation('Pakistan Penal Code', 1860, 'section', '302', 'act') == 'Pakistan Penal Code, 1860, s. 302'
    assert render_citation('Constitution of the Islamic Republic of Pakistan', 1973, 'schedule', 'FIRST SCHEDULE',
                           'constitution').endswith('Schedule FIRST SCHEDULE')


def _row(doc, title, year, jurisdiction='punjab', amends=0, n=None):
    return dict(id=UUID(int=n or doc), title=title, kind='act', year=year, jurisdiction=jurisdiction,
                status='in_force', source_url=None, document_id=doc, source_hash='a' * 64, amends_units=amends)


def test_constitution_page_groups_and_orders_the_family():
    from nizam.api import collections as c
    assert c.amendment_number('The Constitution (Eighteenth Amendment) Act, 2010') == 18
    assert c.amendment_number('The Constitution (Twenty-First Amendment) Act, 2015') == 21
    assert c.amendment_number('Constitution (Amendment) Order, 1980') is None
    rows = [
        _row(4419, 'Constitution of the Islamic Republic of Pakistan', 1973, 'fed'),
        _row(4434, 'The Constitution (Eighteenth Amendment) Act, 2010', 2010, amends=41, n=1),
        _row(4434, 'The Constitution (First Amendment) Act, 1974', 1974, amends=1, n=2),
        _row(4434, 'The Constitution (Second Amendment) Order, 1980', 1980, n=3),
        _row(9287, 'The Revival of the Constitution of 1973 Order, 1985', 1985, 'fed', amends=24),
        _row(6541, 'The Pakistan (Provisional Constitution) Order, 1948', 1948, 'fed'),
        _row(10000, 'The Azad Jammu and Kashmir Interim Constitution (Fifteenth Amendment) Act, 2023', 2023, 'ajk'),
        # a pinned document whose title no longer matches is dropped, never shown as another law
        _row(8093, 'Something Else Entirely', 1960, 'fed'),
    ]
    page = c.constitution_page(rows)
    assert page['constitution']['document_id'] == 4419
    groups = {g['key']: g['items'] for g in page['groups']}
    assert [i['short_name'] for i in groups['amendments']] == \
        ['1st Amendment', '2nd Amendment Order', 'Revival Order', '18th Amendment']
    assert groups['amendments'][-1]['amends_units'] == 41
    assert [i['short_name'] for i in groups['before_1973']] == ['Provisional Constitution Order']
    assert [i['short_name'] for i in groups['ajk']] == ['AJK 15th Amendment']
    assert 'edition' not in groups          # the 2016 edition is absent unless the historical gate returns it


def test_constitution_endpoint_serves_codes_not_prose():
    class Family(Repository):
        def constitution_family(self, **kwargs):
            assert kwargs['constitution_document'] == 4419 and isinstance(kwargs['as_of'], date)
            return [_row(4419, 'Constitution of the Islamic Republic of Pakistan', 1973, 'fed'),
                    _row(4434, 'The Constitution (First Amendment) Act, 1974', 1974, amends=1, n=2)]
    with TestClient(create_app(Family())) as client:
        body = client.get('/v1/law/collections/constitution?as_of=2026-11-17').json()
        assert body['constitution']['title'] == 'Constitution of the Islamic Republic of Pakistan'
        assert [g['key'] for g in body['groups']] == ['amendments']
        assert body['groups'][0]['items'][0]['amends_units'] == 1


def _heritage_rows():
    return [
        _row(3468, 'Antiquities Act, 1975', 1975, 'fed'),
        _row(3157, 'Antiquities Act, 1975', 1975, 'punjab'),
        _row(6288, 'Walled City of Lahore Act, 2012', 2012, 'punjab'),
        _row(1336, 'Sindh Cultural Heritage (Perservation) Act, 1994', 1994, 'sindh'),
        # a pinned document whose title no longer matches is dropped, never shown as another law
        _row(5133, 'Something Else Entirely', 2016, 'kp'),
        _row(4419, 'Constitution of the Islamic Republic of Pakistan', 1973, 'fed'),
        _row(3433, 'Geographical Indications (Registration and Protection) Act, 2020', 2020, 'fed'),
        _row(4338, 'Trade Marks Ordinance, 2001', 2001, 'fed'),
    ]


# Which territories serve each fixture law, as the corpus's territorial model does (None: no filter). The federal
# Antiquities Act is repealed in Balochistan by its 2014 Act (D-078) and, like the Constitution, does not reach AJK/GB.
_HERITAGE_SERVED = {3468: {None, 'punjab', 'sindh', 'kp', 'ict'}, 3157: {None, 'punjab'}, 1336: {None, 'sindh'},
                    4419: {None, 'punjab', 'sindh', 'kp', 'balochistan', 'ict'}, 3433: {None}, 4338: {None}}


def _heritage_sections(instrument_id, territory=None):
    doc = instrument_id.int
    if territory not in _HERITAGE_SERVED.get(doc, set()):
        return None
    labels = {3468: ['2', '5A', '13A', '20', '22', '26'], 3157: ['5-A', '13A', '31'], 1336: ['5', '6', '7', '19'],
              4419: ['1', '28'], 3433: ['11', '26', '28', '30', '41'], 4338: ['22']}[doc]
    return [dict(id=UUID(int=doc * 1000 + i), kind='section', label=l, heading='' if l == '7' else f'Heading {l}',
                 citation=f'law {doc} s. {l}', preview=f'(2) words of {l}') for i, l in enumerate(labels)]


def test_heritage_page_lists_each_regions_own_law_and_answers_by_units():
    from nizam.api import collections as c
    page = c.heritage_page(_heritage_rows(), _heritage_sections)
    regions = {r['jurisdiction']: r for r in page['regions']}
    assert list(regions) == ['fed', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb']
    assert [l['short_name'] for l in regions['punjab']['laws']] == ['Antiquities Act', 'Walled City of Lahore']
    assert regions['kp']['laws'] == []                       # its document no longer carries the expected title
    assert regions['ict']['laws_from'] == 'fed'              # Islamabad is served federal law
    assert regions['ict']['laws'] == regions['fed']['laws']
    assert regions['gb']['laws_from'] == 'gb' and regions['gb']['laws'] == []   # none held: never another region's

    def asked(j):
        return {q['key']: q for q in regions[j]['questions']}
    # each region asks its own law: the federal Act for fed, Punjab's own copy (label '5-A') for Punjab
    assert [u['label'] for u in asked('fed')['found_object']['units']] == ['5A', '13A']
    assert asked('fed')['found_object']['instrument']['document_id'] == 3468
    assert [u['label'] for u in asked('punjab')['found_object']['units']] == ['5-A', '13A']
    assert asked('punjab')['visit']['instrument']['document_id'] == 3157
    # Sindh's 1994 Act: s.7 carries no printed heading, and it is null, not ''
    assert [(u['label'], u['heading']) for u in asked('sindh')['declared_protected']['units']] == [
        ('6', 'Heading 6'), ('7', None)]
    # ...so the client can show its served opening words instead
    assert asked('sindh')['declared_protected']['units'][1]['preview'] == '(2) words of 7'
    assert 'repair' not in asked('sindh') and 'export' not in asked('sindh')   # Sindh's Act has no such section
    # Islamabad asks the federal law, read in ICT
    assert asked('ict')['found_object']['units'] == asked('fed')['found_object']['units']
    # a question whose units are not served (s.10/11, s.19/23 absent from the fixture index) is left out
    assert 'declared_protected' not in asked('fed') and 'damage_signs' not in asked('fed')
    # the Constitution's culture question is asked where the Constitution is served -- not AJK or GB
    assert asked('punjab')['culture_right']['units'][0]['citation'] == 'law 4419 s. 28'
    assert 'culture_right' in asked('balochistan') and 'found_object' not in asked('balochistan')  # its law: unheld
    assert regions['ajk']['questions'] == [] and regions['gb']['questions'] == []
    # makers (D-079): the federal laws held, in MAKER_LAWS order; a law not held (designs, copyright) is absent, and so
    # are its questions; a question keeps only its served units (s.39 is not in the fixture index)
    makers = page['makers']
    assert [l['short_name'] for l in makers['laws']] == ['Geographical indications', 'Trade marks']
    asked_makers = {q['key']: [u['label'] for u in q['units']] for q in makers['questions']}
    assert asked_makers == {'gi_place': ['11', '26'], 'gi_logo': ['28'], 'gi_fake': ['30', '41'], 'brand': ['22']}


def test_heritage_endpoint_reads_units_at_the_page_date_in_each_regions_territory():
    seen = []

    class Heritage(Repository):
        def instruments_by_document(self, document_ids, **kwargs):
            assert {3468, 3157, 1336, 4986, 10935, 4419} <= set(document_ids)
            return _heritage_rows()

        def section_index(self, instrument_id, **kwargs):
            seen.append((kwargs['as_of'], instrument_id.int, kwargs['territory']))
            return dict(sections=_heritage_sections(instrument_id, kwargs['territory']) or [])
    with TestClient(create_app(Heritage())) as client:
        body = client.get('/v1/law/collections/heritage?as_of=2026-11-18').json()
    assert body['as_of'] == '2026-11-18' and {d for d, _, _ in seen} == {date(2026, 11, 18)}
    assert (3468, None) in {(d, t) for _, d, t in seen} and (3468, 'ict') in {(d, t) for _, d, t in seen}
    assert (1336, 'sindh') in {(d, t) for _, d, t in seen}
    assert 'questions' not in body
    sindh = next(r for r in body['regions'] if r['jurisdiction'] == 'sindh')
    assert sindh['questions'][0]['key'] == 'found_object'
    assert sindh['questions'][0]['units'][0]['heading'] == 'Heading 5'


def test_neighbours_follow_the_printed_index_and_never_borrow_another_law():
    from nizam.storage.library_read import neighbours_in

    class Index(Repository):
        def neighbours(self, provision_id, **kwargs):
            # the real lookup over the fixture law's index; an unknown unit is a law that is not released
            return None if provision_id == UUID(int=99) else \
                neighbours_in(Repository().section_index(ID)['sections'], provision_id)
    # a unit not listed (a sub-section, a Part) has no neighbours rather than a guessed one
    assert neighbours_in(Repository().section_index(ID)['sections'], UUID(int=50)) == \
        dict(previous=None, next=None, position=None, total=7)
    with TestClient(create_app(Index())) as client:
        body = client.get(f'/v1/law/provisions/{UUID(int=1)}/neighbours?as_of=2026-11-17').json()
        assert body['previous'] is None and body['next']['label'] == '2' and body['position'] == 1
        last = client.get(f'/v1/law/provisions/{UUID(int=7)}/neighbours').json()
        assert last['next'] is None and last['previous']['label'] == '6' and last['total'] == 7
        assert client.get(f'/v1/law/provisions/{UUID(int=99)}/neighbours').status_code == 404


def test_subject_search_returns_laws_with_their_matching_units_and_the_shelf():
    class Subject(Repository):
        def subject_search(self, **kwargs):
            assert kwargs['q'] == 'robbery' and isinstance(kwargs['as_of'], date)
            assert 4441 in kwargs['shelf']                      # the editorial shelf rides along for ranking
            return [dict(instrument=dict(id=ID, title='Pakistan Penal Code', kind='act', year=1860, jurisdiction='fed',
                                         status='in_force', source_url=None, document_id=4441, source_hash='a' * 64,
                                         cited_by_laws=1160),
                         matches=3, units=[dict(id=str(UUID(int=392)), kind='section', label='392',
                                                heading='Punishment for robbery')])]
    with TestClient(create_app(Subject())) as client:
        body = client.get('/v1/law/search?q=robbery&as_of=2026-11-18').json()
        assert body['query'] == 'robbery'
        hit = body['items'][0]
        assert hit['instrument']['cited_by_laws'] == 1160
        assert hit['units'][0]['label'] == '392' and hit['units'][0]['heading'] == 'Punishment for robbery'
        assert client.get('/v1/law/search?q=r').status_code == 422          # one letter is not a subject


def test_catalogue_continuation_carries_the_reliance_order():
    class Ranked(Repository):
        def instruments(self, **kwargs):
            after = kwargs['after']
            rows = [dict(id=UUID(int=n), title=f'Law {n}', kind='act', year=2000, jurisdiction='fed',
                         status='in_force', source_url=None, document_id=n, source_hash='a' * 64,
                         sort_rank=1, reliance=100 - n, sort_title=f'law {n}') for n in range(1, 40)]
            if after:
                assert len(after) == 4 and after[1] == rows[29]['reliance']   # [rank, reliance, title, id]
                rows = rows[30:]
            return rows[:kwargs['limit']]
    with TestClient(create_app(Ranked())) as client:
        first = client.get('/v1/law/instruments?limit=30').json()
        assert first['next_cursor']
        second = client.get(f"/v1/law/instruments?limit=30&after={first['next_cursor']}").json()
        assert second['items'][0]['title'] == 'Law 31'


def test_popular_collection_keeps_order_and_drops_a_document_whose_title_changed():
    with TestClient(create_app(Repository())) as client:
        body = client.get('/v1/law/collections/popular').json()
        # 4441 still carries the PPC title and is listed; 4337 no longer carries 'Contract Act' and is dropped
        assert [i['short_name'] for i in body['items']] == ['PPC']
        assert body['items'][0]['instrument']['title'] == 'Pakistan Penal Code'
