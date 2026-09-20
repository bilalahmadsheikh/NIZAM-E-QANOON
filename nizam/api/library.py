"""Local research preview. Not the qualified production public API.

Run: uv run --extra api uvicorn nizam.api.library:create_app --factory --port 8080
Docs 07 §2/3/8; 08 §2/4; 13 §3. No generated answers or invented citations.
"""
import base64
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
from pydantic import BaseModel

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


class Ancestor(BaseModel):
    id: UUID
    label: str | None
    heading: str | None
    kind: str


class Provision(Node):
    text_en: str | None
    text_ur: str | None
    operation: str | None
    valid_from: str | None
    valid_to: str | None
    instrument: Instrument
    ancestors: list[Ancestor]


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


def create_app(repository=None):
    repo = repository or LibraryRead()
    cursor = Cursor(os.environ.get('NIZAM_CURSOR_SECRET', secrets.token_hex(32)).encode())

    @asynccontextmanager
    async def lifespan(app):
        repo.open()
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
                                after=cursor.decode(after, scope), limit=limit+1, as_of=day)
        next_cursor = cursor.encode(scope, str(rows[limit-1]['id'])) if len(rows)>limit else None
        return dict(items=rows[:limit], next_cursor=next_cursor, as_of=day)

    @app.get('/v1/law/instruments/{instrument_id}', response_model=InstrumentResult)
    def instrument(instrument_id: UUID, as_of: date | None = None):
        day = resolved(as_of)
        row = repo.instrument(instrument_id, as_of=day)
        if not row:
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

    return app
