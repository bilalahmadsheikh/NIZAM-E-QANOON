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
    repo._instrument=lambda conn,id:None
    assert repo.provision(ID,as_of=date(2026,9,14)) is None
    assert not any('provision_version' in q for q in queries)
