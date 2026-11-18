"""Local research preview. Not the qualified production public API.

Run: uv run --extra api uvicorn nizam.api.library:create_app --factory --port 8080
Docs 07 §2/3/8; 08 §2/4; 13 §3. No generated answers or invented citations.
"""
import base64
import bisect
from contextlib import asynccontextmanager
from datetime import date, datetime
import hashlib
import hmac
import json
import os
import secrets
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, computed_field

from nizam.api import collections
from nizam.storage.library_read import LibraryRead


class Instrument(BaseModel):
    id: UUID
    title: str | None
    kind: str
    year: int | None
    jurisdiction: str
    status: str
    source_url: str | None
    document_id: int
    source_hash: str
    # Migration 0064. True for an owner-declared historical expression, which
    # the library returns only for an as_of inside [valid_from, valid_to);
    # clients render it as "historical text in force <valid_from> to
    # <valid_to>, not current law" and link current_instrument_id (resolved on
    # single opens only). All four default to None, so a row without them --
    # a repository predating 0064 -- still validates.
    historical: bool | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    current_instrument_id: UUID | None = None
    # The serving record (mv_instrument_serving, 0093-0103): current | not_current | historical, and why --
    # e.g. 'owner_presumption_in_force' is in force by the owner's presumption, not by verified evidence. NULL for
    # an as-made text served through its consolidated twin. Clients word it; `status` alone overstated presumed law.
    currency: str | None = None
    currency_reason: str | None = None
    # How many other released laws cite this one by title (law_citation_count, 0107, D-075): a measured reliance
    # signal that orders lists. None where unmeasured.
    cited_by_laws: int | None = None

    @computed_field
    @property
    def year_display(self) -> str:
        """The year as a client shows it. A NULL year is an owner-declared
        undated instrument (migration 0063 admits no other), shown 'undated';
        a year is never inferred (INV-1)."""
        return str(self.year) if self.year is not None else 'undated'


class Node(BaseModel):
    id: UUID
    instrument_id: UUID
    parent_id: UUID | None
    label: str | None
    heading: str | None
    marginal_note: str | None
    kind: str
    ordinal: int
    first_page: int | None
    has_children: bool
    # A Part, Chapter, Schedule or Annex's title: its heading, else its own short served words where the parser kept
    # the printed title line as text ('PART I' / 'INTRODUCTORY'). Read as at as_of; never generated (D-070).
    caption: str | None = None


class Ancestor(BaseModel):
    id: UUID
    label: str | None
    heading: str | None
    kind: str
    caption: str | None = None


class Provision(Node):
    text_en: str | None
    text_ur: str | None
    # Language of the expression's released text, measured (migration 0070); 'ur'/'sd' text arrives as text_ur.
    text_language: str | None = None
    operation: str | None
    valid_from: str | None
    valid_to: str | None
    instrument: Instrument
    ancestors: list[Ancestor]


class UnitNode(BaseModel):
    """One served unit inside the opened unit's subtree, in printed order; depth 0 is the opened unit itself."""
    id: UUID
    parent_id: UUID | None
    kind: str
    label: str | None
    heading: str | None
    marginal_note: str | None
    depth: int
    first_page: int | None
    text_en: str | None
    text_ur: str | None
    text_language: str | None = None
    operation: str | None
    # 0103: the law has gone at as_of and this unit stays law because the repeal expressly excepts it
    survives_repeal: bool = False


class LawStatus(BaseModel):
    """The law-level serving record (mv_instrument_serving). Codes, not prose: the client words them (docs/13)."""
    currency: str
    currency_reason: str | None
    not_current_from: str | None
    repealed_on: str | None
    enacted_on: str | None
    commenced_on: str | None
    territory_reach: list[str]
    extent_basis: str | None


class SectionItem(BaseModel):
    """One section-level unit of a law for the law page: name, its Part/Chapter, the first words it serves, and a
    citation rendered from the records (INV-1). `preview` is the start of the served text, never a summary."""
    id: UUID
    kind: str
    label: str | None
    heading: str | None
    ordinal: int
    first_page: int | None
    preview: str
    group: str | None
    citation: str | None
    survives_repeal: bool = False


class Meta(BaseModel):
    as_of: date
    mode: Literal['research_preview'] = 'research_preview'
    notice: str = 'Corpus qualification is ongoing. Check the official source; status may be unknown.'


class InstrumentPage(Meta):
    items: list[Instrument]
    next_cursor: str | None


class NodePage(Meta):
    items: list[Node]
    next_cursor: str | None


class InstrumentResult(Meta):
    item: Instrument


class ProvisionResult(Meta):
    item: Provision


class CollectionItem(BaseModel):
    short_name: str
    instrument: Instrument


class CollectionPage(Meta):
    """An editorial collection (nizam/api/collections.py): a starting point, not a claim of completeness."""
    name: str
    items: list[CollectionItem]


class Neighbours(Meta):
    """The units either side of an opened unit in its law's printed order (the law page's index), at as_of in
    territory. `position` is 1-based; null, with no neighbours, when the opened unit is not itself listed."""
    previous: SectionItem | None
    next: SectionItem | None
    position: int | None
    total: int


class SubjectUnit(BaseModel):
    """A unit whose heading or marginal note matched the subject; its label and heading come from the record."""
    id: UUID
    kind: str
    label: str | None
    heading: str | None


class SubjectHit(BaseModel):
    instrument: Instrument
    matches: int
    units: list[SubjectUnit]


class SubjectPage(Meta):
    """Laws dealing with a subject, read from section headings and marginal notes (D-075): the closest matches in
    the laws the corpus relies on most first, current law first. A browse aid, not an answer."""
    query: str
    items: list[SubjectHit]


class FamilyItem(BaseModel):
    short_name: str
    instrument: Instrument
    # recorded `amends` edges from this law into the Constitution's text (legal_edge); 0 where none is recorded,
    # which is not evidence that it amends nothing
    amends_units: int


class FamilyGroup(BaseModel):
    """A group of the Constitution's page. `key` is a code the client words: amendments | edition | before_1973 | ajk."""
    key: str
    items: list[FamilyItem]


class ConstitutionPage(Meta):
    """The Constitution and the texts around it (nizam/api/collections.py, D-070). `constitution` is null only when
    its document is not released at as_of."""
    constitution: Instrument | None
    groups: list[FamilyGroup]


class HeritageLaw(BaseModel):
    short_name: str
    instrument: Instrument


class HeritageUnit(BaseModel):
    """`preview` is the opening of the unit's served text (the section index's own preview): the client shows it
    where the source prints no heading (the Balochistan and AJK Acts print theirs in the margin or inline)."""
    id: UUID
    kind: str
    label: str | None
    heading: str | None
    citation: str | None
    preview: str | None = None


class HeritageQuestion(BaseModel):
    """A question people bring to heritage law, answered by opening `units` of `instrument`. `key` is a code the
    client words; the units' identity, heading and citation are records (INV-1)."""
    key: str
    instrument: Instrument
    units: list[HeritageUnit]


class HeritageRegion(BaseModel):
    """One region of the Heritage tab. `laws_from` is the jurisdiction whose laws are listed and asked: 'fed' for
    Islamabad Capital Territory, which is served federal law. An empty `laws` means the library holds none for it
    yet. `questions` are answered by the region's own law, read in its territory (D-078), then the Constitution's
    where it is served there; empty when nothing is."""
    jurisdiction: str
    laws_from: str
    laws: list[HeritageLaw]
    questions: list[HeritageQuestion]


class HeritagePage(Meta):
    """Pakistan's heritage law region by region, each with the questions its own law answers (D-077, D-078)."""
    regions: list[HeritageRegion]


class SectionPage(Meta):
    """A page of a law's served sections, in printed order. `total` is the law's served section count at as_of in
    territory (cheap: the index is computed once per law and date); `law` is its serving record."""
    instrument: Instrument
    law: LawStatus | None
    territory: str | None
    items: list[SectionItem]
    total: int
    next_cursor: str | None


class UnitText(Meta):
    """A unit with its served subtree, read through operative_provision (INV-5). Empty `nodes` with a
    `not_served` code means the unit is not law at `as_of` (in `territory`); the code says which record decides."""
    item: Provision
    law: LawStatus | None
    territory: str | None
    nodes: list[UnitNode]
    truncated: bool
    not_served: str | None
    not_served_from: str | None


class Cursor:
    """Tamper-evident, scope-bound, one-hour continuation; never an offset."""
    def __init__(self, key: bytes):
        self.key = key

    def encode(self, scope, last):
        raw = json.dumps([scope, last, int(datetime.now().timestamp())], separators=(',', ':')).encode()
        signature = hmac.digest(self.key, raw, 'sha256')
        return base64.urlsafe_b64encode(signature + raw).decode().rstrip('=')

    def decode(self, token, scope):
        if not token:
            return None
        try:
            raw = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
            if not hmac.compare_digest(raw[:32], hmac.digest(self.key, raw[32:], 'sha256')):
                raise ValueError()
            saved_scope, last, created = json.loads(raw[32:])
            if saved_scope != scope or not 0 <= datetime.now().timestamp() - created < 3600:
                raise ValueError()
            return last
        except (ValueError, TypeError, KeyError):
            raise HTTPException(400, 'Invalid or expired cursor. Refresh this list.') from None


SHELF = [doc for _s, doc, _p in collections.POPULAR]   # the editorial shelf stays on top of ranked lists


def create_app(repository=None):
    repo = repository or LibraryRead()
    cursor = Cursor(os.environ.get('NIZAM_CURSOR_SECRET', secrets.token_hex(32)).encode())

    def warm():
        """Pre-build the section index of the home page's laws for today, in the background, so the first tap on
        a carousel card reads from memory. One connection at a time; a failure here only costs that warm-up."""
        try:
            day = resolved(None)
            rows = repo.instruments_by_document([d for _s, d, _p in collections.POPULAR], as_of=day)
            for entry in collections.resolve(rows):
                repo.section_index(entry['instrument']['id'], as_of=day)
        except Exception:                                       # noqa: BLE001
            pass

    @asynccontextmanager
    async def lifespan(app):
        repo.open()
        if isinstance(repo, LibraryRead) and os.environ.get('NIZAM_WARM', '1') != '0':
            import threading
            threading.Thread(target=warm, name='warm-popular', daemon=True).start()
        yield
        repo.close()

    app = FastAPI(title='Nizam Library — research preview', version='0.1.0', lifespan=lifespan)
    # Explicit development origin. Never a wildcard public/authenticated policy.
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173'],
                       allow_methods=['GET'], allow_headers=['If-None-Match'],
                       expose_headers=['ETag'])

    @app.middleware('http')
    async def representation(request: Request, call_next):
        response = await call_next(request)
        # Live qualification can change. No long-lived public cache claim.
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(Exception)
    async def unavailable(request, exc):
        # Do not expose SQL, DSNs or source text through error messages.
        return JSONResponse(status_code=503, content={
            'detail': 'The library is temporarily unavailable. Please try again.'})

    def resolved(value):
        return value or datetime.now(ZoneInfo('Asia/Karachi')).date()

    @app.get('/v1/law/instruments', response_model=InstrumentPage)
    def instruments(q: str = Query('', max_length=120),
                    jurisdiction: Literal['', 'fed', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'] = '',
                    kind: Literal['', 'constitution', 'act', 'ordinance', 'rules', 'regulation', 'order', 'sro', 'notification'] = '',
                    as_of: date | None = None, limit: int = Query(30, ge=1, le=50),
                    after: str | None = Query(None, max_length=2048)):
        day = resolved(as_of)
        scope = ['instruments', q.strip(), jurisdiction, kind, day.isoformat()]
        rows = repo.instruments(q=q.strip(), jurisdiction=jurisdiction, kind=kind,
                                after=cursor.decode(after, scope), limit=limit+1, as_of=day, shelf=SHELF)
        last = rows[limit-1] if len(rows) > limit else None
        # keyset on (title rank, reliance, sort title, id): the order the reader sees (0104, D-075)
        next_cursor = cursor.encode(scope, [last.get('sort_rank', 1), int(last.get('reliance', 0) or 0),
                                            last.get('sort_title', ''), str(last['id'])]) if last else None
        return dict(items=rows[:limit], next_cursor=next_cursor, as_of=day)

    @app.get('/v1/law/search', response_model=SubjectPage)
    def subject(q: str = Query(..., min_length=2, max_length=120),
                jurisdiction: Literal['', 'fed', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'] = '',
                kind: Literal['', 'constitution', 'act', 'ordinance', 'rules', 'regulation', 'order', 'sro', 'notification'] = '',
                as_of: date | None = None, limit: int = Query(20, ge=1, le=40)):
        day = resolved(as_of)
        items = repo.subject_search(q=q.strip(), jurisdiction=jurisdiction, kind=kind, as_of=day, limit=limit,
                                    shelf=SHELF)
        return dict(query=q.strip(), items=items, as_of=day)

    @app.get('/v1/law/instruments/{instrument_id}', response_model=InstrumentResult)
    def instrument(instrument_id: UUID, as_of: date | None = None):
        day = resolved(as_of)
        row = repo.instrument(instrument_id, as_of=day)
        if not row:
            # A released historical text outside its window (0064) gets its own
            # answer: the dates come from the manifest record, never generated.
            window = getattr(repo, 'historical_window', lambda _id: None)(instrument_id)
            if window:
                raise HTTPException(404, f"This is a historical text, in force from {window['valid_from']} "
                                         f"until it was superseded on {window['valid_to']}; it is not current "
                                         'law. Open it with an as_of date inside that period, or return to '
                                         'the library.')
            raise HTTPException(404, 'This revision is not available in the release view. Return to the library.')
        return dict(item=row, as_of=day)

    @app.get('/v1/law/instruments/{instrument_id}/children', response_model=NodePage)
    def children(instrument_id: UUID, parent: UUID | None = None, as_of: date | None = None,
                 limit: int = Query(30, ge=1, le=50), after: str | None = Query(None, max_length=2048)):
        day = resolved(as_of)
        scope = ['children', str(instrument_id), str(parent), day.isoformat()]
        rows = repo.children(instrument_id, parent=parent, after=cursor.decode(after, scope),
                             limit=limit+1, as_of=day)
        if rows is None:
            raise HTTPException(404, 'This revision is no longer available. Return to the library.')
        next_cursor = cursor.encode(scope, [rows[limit-1]['ordinal'], str(rows[limit-1]['id'])]) if len(rows)>limit else None
        return dict(items=rows[:limit], next_cursor=next_cursor, as_of=day)

    @app.get('/v1/law/provisions/{provision_id}', response_model=ProvisionResult)
    def provision(provision_id: UUID, as_of: date | None = None):
        day = resolved(as_of)
        row = repo.provision(provision_id, as_of=day)
        if not row:
            raise HTTPException(404, 'This revision is no longer available. Return to the library.')
        return dict(item=row, as_of=day)

    @app.get('/v1/law/collections/popular', response_model=CollectionPage)
    def popular(as_of: date | None = None):
        day = resolved(as_of)
        rows = repo.instruments_by_document([doc for _s, doc, _p in collections.POPULAR], as_of=day)
        return dict(name='Most consulted laws', items=collections.resolve(rows), as_of=day)

    @app.get('/v1/law/collections/constitution', response_model=ConstitutionPage)
    def constitution(as_of: date | None = None):
        day = resolved(as_of)
        rows = repo.constitution_family(documents=collections.FAMILY_DOCUMENTS,
                                        title_pattern=collections.FAMILY_TITLE_PATTERN,
                                        constitution_document=collections.CONSTITUTION_DOCUMENT, as_of=day)
        return dict(collections.constitution_page(rows), as_of=day)

    @app.get('/v1/law/collections/heritage', response_model=HeritagePage)
    def heritage(as_of: date | None = None):
        day = resolved(as_of)
        rows = repo.instruments_by_document(collections.HERITAGE_DOCUMENTS, as_of=day)

        def sections_of(instrument_id, territory):
            index = repo.section_index(instrument_id, as_of=day, territory=territory)
            return index['sections'] if index else None
        return dict(collections.heritage_page(rows, sections_of), as_of=day)

    @app.get('/v1/law/instruments/{instrument_id}/sections', response_model=SectionPage)
    def sections(instrument_id: UUID, as_of: date | None = None,
                 territory: Literal['', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'] = '',
                 limit: int = Query(40, ge=1, le=100), after: str | None = Query(None, max_length=2048)):
        day = resolved(as_of)
        index = repo.section_index(instrument_id, as_of=day, territory=territory or None)
        if not index:
            raise HTTPException(404, 'This revision is not available in the release view. Return to the library.')
        scope = ['sections', str(instrument_id), day.isoformat(), territory]
        last = cursor.decode(after, scope)
        rows = index['sections']
        # keyset on the printed ordinal: the next page starts after the last section the client holds
        start = 0 if last is None else bisect.bisect_right([s['ordinal'] for s in rows], last)
        page = rows[start:start + limit]
        more = start + limit < len(rows)
        return dict(instrument=index['instrument'], law=index['law'], territory=territory or None,
                    items=page, total=len(rows), as_of=day,
                    next_cursor=cursor.encode(scope, page[-1]['ordinal']) if more and page else None)

    @app.get('/v1/law/provisions/{provision_id}/text', response_model=UnitText)
    def unit_text(provision_id: UUID, as_of: date | None = None,
                  territory: Literal['', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'] = ''):
        day = resolved(as_of)
        result = repo.unit_text(provision_id, as_of=day, territory=territory or None)
        if not result:
            raise HTTPException(404, 'This revision is no longer available. Return to the library.')
        return dict(result, as_of=day, territory=territory or None)

    @app.get('/v1/law/provisions/{provision_id}/neighbours', response_model=Neighbours)
    def neighbours(provision_id: UUID, as_of: date | None = None,
                   territory: Literal['', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'] = ''):
        day = resolved(as_of)
        result = repo.neighbours(provision_id, as_of=day, territory=territory or None)
        if result is None:
            raise HTTPException(404, 'This revision is no longer available. Return to the library.')
        return dict(result, as_of=day)

    return app
