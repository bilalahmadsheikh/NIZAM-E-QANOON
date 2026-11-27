"""Law search for the app (docs/07 §B2 "legal read: law + search"; the contract's `search` group: POST /search and
POST /citations/resolve, "search returns scope and degradation"; D-179).

    POST /v1/search             {"q", "as_of"?, "territory"?, "limit"?}
    POST /v1/citations/resolve  {"citation", "as_of"?, "territory"?}

Search is DISCOVERY, not an answer (INV-2 governs answers, which are POST /v1/answers, L4 onwards). It serves L3's
ranked units (nizam.retrieval.rerank.ranked: the profile's slate, then its cross-encoder): the 8B path when the GPU
service is configured (NIZAM_GPU_ENCODER_URL, NIZAM_GPU_RERANKER_URL), else the CPU path, and it says which, and any
degradation, in `mode`. Every unit is served through operative_provision at `as_of` in `territory` (INV-5), and its
citation is rendered from the record's fields (INV-1); provisions are the unit returned, never chunks (INV-4).

A question that asks what a court decided is not a law search: the response carries `refer_to: "precedent"` and no
statutory results (the statute veto's own route, D-170), so the app sends it to /v1/precedent/search.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from nizam.retrieval import gate as G
from nizam.retrieval.query import parse
from nizam.storage import unit_search
from nizam.storage.lexical import Filters
from nizam.storage.library_read import render_citation

TERRITORY = Literal['', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb']
SNIPPET_CHARS = 420


class SearchIn(BaseModel):
    q: str = Field(..., min_length=2, max_length=300)
    as_of: date | None = None
    territory: TERRITORY = ''
    limit: int = Field(10, ge=1, le=20)


class CitationIn(BaseModel):
    citation: str = Field(..., min_length=2, max_length=200)
    as_of: date | None = None
    territory: TERRITORY = ''


# response models: the app's Dart contract is generated from these (tools/generate_library_contract.py)
class SearchScope(BaseModel):
    as_of: date
    territory: str | None
    jurisdictions: list[str] | None = None


class SearchMode(BaseModel):
    searched: bool                       # False: a scope finding left nothing to search (see scope_findings)
    degraded: str | None = None          # 'lexical_only', 'dense_cpu', 'unreranked' ... (docs/04 §9.2)
    dense_generation: int | None = None
    reranker: str | None = None          # model@revision
    reranker_device: str | None = None


class ScopeNotice(BaseModel):
    code: str
    kind: str
    matched: str
    reason: str
    suggestions: list[str]


class LawHit(BaseModel):
    rank: int
    provision_id: str
    version_id: str
    instrument_id: str
    citation: str                        # rendered from the record (INV-1)
    heading: str | None
    law: str
    law_kind: str
    year: int | None
    jurisdiction: str
    snippet: str
    via_citation: bool
    score: float


class SearchPage(BaseModel):
    query: str
    kind: str
    scope: SearchScope
    mode: SearchMode
    refer_to: str | None
    note: str
    scope_findings: list[ScopeNotice]
    results: list[LawHit]


class ResolvedCitation(BaseModel):
    raw: str
    resolved: bool
    provision_id: str | None
    version_id: str | None
    citation: str | None
    heading: str | None
    law: str | None
    unresolved: str | None
    candidates: list[str]
    alternates: list[str]


class CitationPage(BaseModel):
    query: str
    scope: SearchScope
    citations: list[ResolvedCitation]


NOT_SEARCHED = ('source', 'place')     # the statute veto's findings that leave no statutory search to show (D-179)


def public_finding(finding) -> dict:
    """a scope finding as the reader is told it: the gate's public reason and suggestions (docs/04 §8.1), with the
    code, kind and matched words for the trace (INV-3)"""
    key = f"{finding.code}:{finding.kind}" if f"{finding.code}:{finding.kind}" in G.PUBLIC else finding.code
    reason, suggestions = G.PUBLIC.get(key, (finding.reason, ()))
    return dict(code=finding.code, kind=finding.kind, matched=finding.matched, reason=reason,
                suggestions=list(suggestions))


def filters_for(day: date, territory: str) -> Filters:
    """the scope a reader asks for: a territory's own law plus federal law; none given: every place's law"""
    if not territory:
        return Filters(as_of=day)
    if territory == 'ict':
        return Filters(as_of=day, territory='ict', jurisdictions=('fed',))
    return Filters(as_of=day, territory=territory, jurisdictions=(territory, 'fed'))


def describe(session, units: list[tuple[str, str]]) -> dict:
    """{unit id: {citation, heading, law, law_kind, year, jurisdiction, snippet}} rendered from records"""
    if not units:
        return {}
    session.cur.execute("""
        SELECT p.id::text, p.kind::text, p.label, p.heading, i.id::text, i.short_title, i.year, i.kind::text,
               i.jurisdiction::text
          FROM provision p JOIN instrument i ON i.id = p.instrument_id
         WHERE p.id = ANY(%s::uuid[])""", ([u for u, _ in units],))
    meta = {r[0]: r for r in session.cur.fetchall()}
    texts = session.unit_passages(units, max_chars=SNIPPET_CHARS)
    out = {}
    for uid, _ in units:
        m = meta.get(uid)
        if not m:
            continue
        _, kind, label, heading, inst, title, year, ikind, juris = m
        out[uid] = dict(citation=render_citation(title, year, kind, label, ikind), heading=heading, law=title,
                        law_kind=ikind, year=year, jurisdiction=juris, instrument_id=inst,
                        snippet=texts.get(uid, ''))
    return out


def register(app, resolved, ranked_fn=None) -> None:
    """`ranked_fn` is injected by tests; serving uses L3's ranked()"""

    @app.post('/v1/search', response_model=SearchPage)
    def search(body: SearchIn):
        from nizam.retrieval.rerank import ranked
        day = resolved(body.as_of)
        f = filters_for(day, body.territory)
        spec = parse(body.q.strip())
        finding = G.pre_veto(spec, f)
        scope = dict(as_of=day, territory=body.territory or None, jurisdictions=list(f.jurisdictions or []) or None)
        findings = [public_finding(finding)] if finding else []
        if finding and finding.kind in NOT_SEARCHED:
            # a court-decision question goes to precedent search (D-170); another country's law is not held, and
            # Pakistani sections listed for it would read as its answer
            return dict(query=body.q, kind='law_discovery', scope=scope, mode=dict(searched=False),
                        refer_to='precedent' if finding.kind == 'source' else None,
                        note=findings[0]['reason'], scope_findings=findings, results=[])
        r = (ranked_fn or ranked)(spec, f, max(body.limit, 10))
        head = r.candidates[:body.limit]
        with unit_search.session(r.filters) as s:
            info = describe(s, [(c.unit_id, c.version_id) for c in head])
        rr = r.trace.get('rerank') or {}
        results = []
        for c in head:
            d = info.get(c.unit_id)
            if not d or not d['citation']:
                continue                           # no record-rendered citation: the unit is not shown (INV-1)
            results.append(dict(rank=len(results) + 1, provision_id=c.unit_id, version_id=c.version_id, via_citation=c.via_citation,
                                score=c.rerank_score if c.rerank_score is not None else c.score, **d))
        return dict(query=body.q, kind='law_discovery', scope=scope,
                    mode=dict(searched=True, degraded=r.degraded, dense_generation=r.trace.get('dense_generation'),
                              reranker=f"{rr.get('model')}@{(rr.get('revision') or '')[:12]}" if rr else None,
                              reranker_device=rr.get('device')),
                    refer_to=None,
                    note='Sections that bear on the question, at the date and place shown. Not legal advice and '
                         'not an answer.',
                    scope_findings=findings,
                    results=results)

    @app.post('/v1/citations/resolve', response_model=CitationPage)
    def resolve(body: CitationIn):
        from nizam.storage import citations as C
        day = resolved(body.as_of)
        f = filters_for(day, body.territory)
        found = C.find(body.citation)
        if not found:
            raise HTTPException(422, 'No citation was recognised in that text.')
        out = []
        with unit_search.session(f) as s:
            for cit in found:
                cit = C.resolve(s, cit)
                u = cit.resolved_unit
                # a resolved unit is shown only when the view serves it at this date and place (INV-5)
                vid = s.operative_units([u]).get(u.unit_id) if u else None
                d = describe(s, [(u.unit_id, vid)]).get(u.unit_id) if vid else None
                why = cit.unresolved or (None if d else ('not_operative' if u else 'unresolved'))
                out.append(dict(raw=cit.raw, resolved=bool(d), provision_id=u.unit_id if d else None,
                                version_id=vid if d else None,
                                citation=d['citation'] if d else None, heading=d['heading'] if d else None,
                                law=cit.resolved_law, unresolved=why, candidates=list(cit.candidates[:5]),
                                alternates=[a.unit_id for a in cit.alternates if hasattr(a, 'unit_id')]))
        return dict(query=body.citation, scope=dict(as_of=day, territory=body.territory or None), citations=out)


def warm(resolved) -> None:
    """load the question encoder and the reranker (and the GPU service's checks) before the first search, in the
    background: a cold first search took 14.6 s on the laptop against ~2 s warm (27 Nov 2026). A failure here only
    costs that warm-up; the first real search then reports its own degradation."""
    try:
        from nizam.retrieval.rerank import ranked
        ranked(parse("punishment for theft"), Filters(as_of=resolved(None)), 10)
    except Exception:                                           # noqa: BLE001
        pass
