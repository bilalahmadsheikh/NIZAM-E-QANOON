"""Precedent routes (docs/PRECEDENT-MODEL.md; D-116, D-119, D-122).

    GET /v1/precedent/search?q=&as_of=&court=&forum=&forum_territory=&limit=
    GET /v1/precedent/judgments/{judgment_id}?as_of=
    GET /v1/precedent/judgments/{judgment_id}/cited-by?as_of=&limit=   later judgments citing its case (D-150)
    GET /v1/precedent/judgments/{judgment_id}/history?as_of=          what the courts above did with it (D-159)
    GET /v1/precedent/cases/{court}/{case_type}/{number}/{year}?as_of=   one case and every decision in it (D-125)
    GET /v1/law/provisions/{provision_id}/judgments?as_of=&limit=      'cases on this section'
    GET /v1/precedent/authority?deciding=&receiving=&receiving_territory=&as_of=
    GET /v1/precedent/coverage

Every response carries `as_of`. A precedent search also returns its coverage: the courts and years held, because
missing judgments must never read as "no precedent" (D-122). Search results are discovery, not answers. They are
labelled `mode` and pass no gate (INV-2).
"""
from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Path, Query

from nizam.retrieval import precedent as P
from nizam.storage import authority as A
from nizam.storage.case_key import case_key

COURTS = Literal['', 'FCC', 'SC', 'FSC', 'LHC', 'SHC', 'PHC', 'BHC', 'IHC', 'AJKSC', 'AJKHC', 'GBSAC', 'GBCC']
# subject_matter v1 (nizam.storage.facets.VOCABULARY, D-163)
SUBJECTS = Literal['', 'civil_procedure', 'civil_service', 'constitutional', 'corporate_commercial', 'courts_judiciary',
                   'criminal', 'education', 'elections', 'energy_utilities', 'environment', 'family',
                   'finance_banking', 'health', 'intellectual_property', 'labour_employment', 'local_government',
                   'media_technology', 'police_public_order', 'property_land', 'religious_affairs', 'tax',
                   'transport']
TERRITORIES = Literal['', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb']


def _forum(code: str, territory: str):
    if code:
        return code
    if territory:
        return A.Subordinate(territory)
    return None


def register(app, repo, resolved) -> None:
    @app.get('/v1/precedent/search')
    def precedent_search(q: str = Query(..., min_length=2, max_length=300), as_of: date | None = None,
                         court: COURTS = '', forum: COURTS = '', forum_territory: TERRITORIES = '',
                         subject: SUBJECTS = '', limit: int = Query(10, ge=1, le=25)):
        day = resolved(as_of)
        r = P.search(q.strip(), as_of=day, court=court or None, forum=_forum(forum, forum_territory), k=limit,
                     repo=repo, subject=subject or None)          # subject: an area read from the laws cited (D-163)
        return dict(query=r.question, as_of=r.as_of, mode=r.mode, kind='precedent_discovery',
                    note='Judgments that bear on the question, with the law they read. Not legal advice and not '
                         'an answer: binding status is from the recorded constitutional rules only, and the coverage '
                         'below is all that was searched.',
                    cited_provisions=r.cited_provisions, coverage=r.coverage,
                    hits=[h.__dict__ for h in r.hits], trace=r.trace)

    @app.get('/v1/precedent/judgments/{judgment_id}')
    def judgment(judgment_id: UUID, as_of: date | None = None):
        day = resolved(as_of)
        out = repo.judgment(judgment_id, as_of=day)
        if out is None:
            raise HTTPException(404, 'No released judgment with this id was decided on or before this date.')
        return dict(out, as_of=day)

    @app.get('/v1/precedent/cases/{court}/{case_type}/{number}/{year}')
    def case(court: COURTS, case_type: str = Path(..., pattern=r'^[A-Z]{1,12}$'),
             number: str = Path(..., pattern=r'^[0-9]{1,6}(-[A-Za-z])?$'), year: int = Path(..., ge=1947, le=2100),
             as_of: date | None = None):
        day = resolved(as_of)
        if not court:
            raise HTTPException(422, 'Name the court.')
        out = repo.case(case_key(court, f'{court}:{case_type}', number, year), as_of=day)
        if out is None:
            raise HTTPException(404, 'No case with this number is held with a decision on or before this date.')
        return dict(out, as_of=day)

    @app.get('/v1/precedent/judgments/{judgment_id}/cited-by')
    def cited_by(judgment_id: UUID, as_of: date | None = None, limit: int = Query(20, ge=1, le=50)):
        # later judgments citing this one's case, by number or by a reporter citation the court publishes (D-150);
        # a citation not resolved is not shown, so 'none' means none found among the judgments held (coverage)
        day = resolved(as_of)
        return dict(judgment_id=judgment_id, as_of=day, items=repo.citing_judgments(judgment_id, day, limit),
                    coverage=repo.coverage())

    @app.get('/v1/precedent/judgments/{judgment_id}/history')
    def history(judgment_id: UUID, as_of: date | None = None):
        # what the courts above did with this judgment's case, in their own words (D-159): affirmed, set aside,
        # remanded, leave refused. Only appeals the corpus holds are known, so an empty list says 'none held', and
        # the coverage says which courts and years that covers
        day = resolved(as_of)
        return dict(judgment_id=judgment_id, as_of=day, items=repo.later_history(judgment_id, day),
                    coverage=repo.coverage())

    @app.get('/v1/law/provisions/{provision_id}/judgments')
    def provision_judgments(provision_id: UUID, as_of: date | None = None, limit: int = Query(20, ge=1, le=50)):
        day = resolved(as_of)
        return dict(provision_id=provision_id, as_of=day, items=repo.provision_judgments(provision_id, day, limit),
                    judicial_status=repo.judicial_status(provision_id, day),       # D-161: verified only
                    coverage=repo.coverage())

    @app.get('/v1/precedent/authority')
    def authority(deciding: COURTS, receiving: COURTS = '', receiving_territory: TERRITORIES = '',
                  as_of: date | None = None):
        day = resolved(as_of)
        forum = _forum(receiving, receiving_territory)
        if not deciding or forum is None:
            raise HTTPException(422, 'Name the deciding court and a receiving court or territory.')
        with repo.transaction() as conn:
            registry = A.load(repo.tuple_cursor(conn))
        return dict(deciding=deciding, receiving=receiving or None, receiving_territory=receiving_territory or None,
                    as_of=day, result=P._authority(deciding, forum, day, registry))

    @app.get('/v1/precedent/coverage')
    def coverage():
        return dict(items=repo.coverage())
