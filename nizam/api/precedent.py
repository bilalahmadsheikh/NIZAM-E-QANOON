"""Precedent routes (docs/PRECEDENT-MODEL.md; D-116, D-119, D-122), typed for the app (D-184).

    GET /v1/precedent/search?q=&as_of=&court=&forum=&forum_territory=&limit=
    GET /v1/precedent/courts                                            every court, with what is held of it
    GET /v1/precedent/courts/{court}/judgments?as_of=&limit=&after=     a court's judgments, newest first
    GET /v1/precedent/judgments/{judgment_id}?as_of=
    GET /v1/precedent/judgments/{judgment_id}/cited-by?as_of=&limit=   later judgments citing its case (D-150)
    GET /v1/precedent/judgments/{judgment_id}/history?as_of=          what the courts above did with it (D-159)
    GET /v1/precedent/cases/{court}/{case_type}/{number}/{year}?as_of=   one case and every decision in it (D-125)
    GET /v1/law/provisions/{provision_id}/judgments?as_of=&order=&limit=&offset=   'decisions citing this section'
    GET /v1/law/instruments/{instrument_id}/judgments?as_of=&order=&limit=&offset= 'decisions citing this law'
    GET /v1/precedent/authority?deciding=&receiving=&receiving_territory=&as_of=
    GET /v1/precedent/coverage

Every response carries `as_of`: a judgment decided after it did not exist on that day and is never returned. Every
list states what it was drawn from (`coverage_note`), because missing judgments must never read as "no precedent"
(D-122). Search results are discovery, not answers: labelled `mode`, they pass no gate (INV-2). Citations are
rendered from records (INV-1). Withheld names are replaced in every text and party line returned (D-131). A machine
reading that a court reversed, overruled or set aside a decision is shown only once a lawyer verified it
(PRECEDENT-MODEL §2): until then it is withheld and marked.
"""
from __future__ import annotations

import base64
import json
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Path, Query
from pydantic import BaseModel

from nizam.retrieval import precedent as P
from nizam.storage import authority as A
from nizam.storage.case_key import case_key

COURTS = Literal['', 'FCC', 'SC', 'FSC', 'LHC', 'SHC', 'PHC', 'BHC', 'IHC', 'AJKSC', 'AJKHC', 'GBSAC', 'GBCC']
COURT = Literal['FCC', 'SC', 'FSC', 'LHC', 'SHC', 'PHC', 'BHC', 'IHC', 'AJKSC', 'AJKHC', 'GBSAC', 'GBCC']
# subject_matter v1 (nizam.storage.facets.VOCABULARY, D-163)
SUBJECTS = Literal['', 'civil_procedure', 'civil_service', 'constitutional', 'corporate_commercial', 'courts_judiciary',
                   'criminal', 'education', 'elections', 'energy_utilities', 'environment', 'family',
                   'finance_banking', 'health', 'intellectual_property', 'labour_employment', 'local_government',
                   'media_technology', 'police_public_order', 'property_land', 'religious_affairs', 'tax',
                   'transport']
TERRITORIES = Literal['', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb']
ORDER = Literal['recent', 'relevant']
NOTE = ('Judgments, as the courts published them. Legal information, not advice: read the judgment and its source '
        'before relying on it.')


# ------------------------------------------------------------------------------------------------ the contract

class CourtCoverage(BaseModel):
    code: str
    name: str
    court_class: str
    judgments: int
    first_decided: date | None
    last_decided: date | None


class CourtsPage(BaseModel):
    items: list[CourtCoverage]
    total_judgments: int
    coverage_note: str


class JudgmentCard(BaseModel):
    """One judgment in a list: what a reader needs to choose it, every field from records"""
    judgment_id: str
    citation: str
    court: str
    case_type: str | None
    case_key: str | None
    decided_on: date | None              # None: the judgment prints no usable decision date (D-124)
    undated: bool
    decided_no_later_than: date | None
    decided_not_before: date | None
    parties_display: str | None          # withheld names replaced (D-131)
    names_withheld: bool
    disposition: str | None
    reported: bool | None
    mentions: int | None                 # how often it cites the law or case listed for (None: not a citing list)
    roles: list[str]                     # how it cites it: interpreted, challenged, quoted, cited, charge ...
    treatments: list[str]                # cited-by only: how it treats the case, negative ones only when verified
    treatments_awaiting_review: int
    cited_as: str | None                 # cited-by only: the citation as the later judgment prints it


class JudgmentList(BaseModel):
    as_of: date
    items: list[JudgmentCard]
    next_cursor: str | None
    coverage_note: str


class VerifiedInvalidation(BaseModel):
    extent: str
    extent_note: str | None
    effective_on: date | None
    appeal_state: str | None
    reading: str | None
    judgment_id: str | None


class JudicialStatus(BaseModel):
    verified: list[VerifiedInvalidation]
    candidates_awaiting_review: int
    coverage: str


class CitingPage(BaseModel):
    """The decisions citing a section (or a unit inside it) or a whole law, and any copy of it (D-136, D-184)"""
    scope: str                           # 'provision' | 'instrument'
    id: str
    as_of: date
    order: str
    total: int
    items: list[JudgmentCard]
    next_offset: int | None
    judicial_status: JudicialStatus | None   # a section's verified validity readings (D-161); None for a whole law
    coverage_note: str


class JudgmentHead(BaseModel):
    id: str
    court_code: str
    court_name: str
    seat: str | None
    case_no_printed: str | None
    case_type_name: str | None
    case_number: str | None
    case_year: int | None
    decided_on: date | None
    undated: bool
    decided_no_later_than: date | None
    decided_not_before: date | None
    undated_reason: str | None
    hearing_on: date | None
    bench_printed: list[str]
    bench_size: int | None
    disposition: str | None
    disposition_printed: str | None
    reported_flag: bool | None
    neutral_citation: str | None
    parties_display: str | None
    jurisdiction_printed: str | None
    source_url: str | None


class JudgmentOpinion(BaseModel):
    ordinal: int
    kind: str | None
    heading_printed: str | None
    author_printed: str | None


class JudgmentParagraph(BaseModel):
    id: str
    kind: str
    printed_no: str | None
    page_first: int | None
    text: str
    opinion: int | None
    opinion_kind: str | None
    citation: str


class CitedProvision(BaseModel):
    """A provision the judgment cites, resolved to the corpus, with whether its text is still the operative text"""
    provision_id: str
    citation: str
    label: str | None
    kind: str | None
    law_title: str | None
    law_year: int | None
    law_kind: str | None                 # act, constitution ... (the unit's noun: section or Article)
    role: str | None
    mentions: int
    status_now: str                      # same_text | amended_since | not_operative | text_at_decision_not_held


class CitedCase(BaseModel):
    raw: str
    resolution: str
    judgment_id: str | None              # the judgment it names, when held
    case_key: str | None


class AppealFrom(BaseModel):
    relation: str | None
    court_below: str | None
    case_below: str | None
    decided_below: date | None
    outcome: str | None                  # only when a lawyer verified the reading
    outcome_withheld: bool


class CaseDecided(BaseModel):
    case_key: str
    role: str | None
    case_type_name: str | None
    case_number: str | None
    case_year: int | None


class CaseDecision(BaseModel):
    judgment_id: str
    citation: str
    decided_on: date | None
    undated: bool


class JudgmentCase(BaseModel):
    status: str
    cases_decided: list[CaseDecided]
    other_decisions: list[CaseDecision]
    copy_of_judgment_id: str | None


class PrivacyCategory(BaseModel):
    code: str
    name: str | None
    basis_kind: str | None
    basis: str | None


class JudgmentPrivacy(BaseModel):
    names_withheld: bool
    categories: list[PrivacyCategory]


class JudgmentPage(BaseModel):
    as_of: date
    citation: str
    judgment: JudgmentHead
    opinions: list[JudgmentOpinion]
    paragraphs: list[JudgmentParagraph]
    statutes_cited: list[CitedProvision]
    cases_cited: list[CitedCase]
    appeal_from: list[AppealFrom]
    case_record: JudgmentCase           # "case" is a keyword in the Dart client
    privacy: JudgmentPrivacy
    note: str


class HistoryItem(BaseModel):
    source: str                          # 'upper_judgment' | 'court_record'
    judgment_id: str | None
    court: str
    relation: str | None
    outcome: str | None
    outcome_withheld: bool
    outcome_printed: str | None
    decided_on: date | None
    citation: str | None
    upper_file_url: str | None


class HistoryPage(BaseModel):
    judgment_id: str
    as_of: date
    items: list[HistoryItem]
    coverage_note: str


class PrecedentHitOut(BaseModel):
    judgment_id: str
    paragraph_id: str
    citation: str
    court: str
    case_type: str | None
    case_key: str | None
    decided_on: date | None
    undated: bool
    decided_no_later_than: date | None
    disposition: str | None
    reported: bool | None
    text: str
    parties_display: str | None
    names_withheld: bool
    binding: str | None                  # binding | not_binding | not_recorded, for the forum asked (A24)
    subjects: list[str]


class PrecedentSearchPage(BaseModel):
    query: str
    as_of: date
    mode: str
    kind: str
    note: str
    hits: list[PrecedentHitOut]
    coverage_gap: str | None
    coverage_note: str


# ------------------------------------------------------------------------------------------------ mapping

def coverage_note(rows: list[dict]) -> str:
    """'From 64,273 judgments of 12 courts held, decided 1981-2026.' from v_judgment_coverage rows"""
    n = sum(int(r.get("judgments") or r.get("judgments_released") or 0) for r in rows)
    courts = len({r["court_code"] if "court_code" in r else r["code"] for r in rows
                  if (r.get("judgments") or r.get("judgments_released"))})
    years = [d for r in rows for d in (r.get("first_decided"), r.get("last_decided")) if d]
    span = f", decided {min(years).year}–{max(years).year}" if years else ""
    return (f"From {n:,} judgments of {courts} courts held{span}. A judgment not held is not shown, so a short "
            f"list is not proof that nothing else was decided.")


def card(d: dict) -> JudgmentCard:
    return JudgmentCard(judgment_id=str(d["judgment_id"]), citation=d["citation"], court=d["court"],
                        case_type=d.get("case_type"), case_key=d.get("case_key"), decided_on=d.get("decided_on"),
                        undated=bool(d.get("undated")), decided_no_later_than=d.get("decided_no_later_than"),
                        decided_not_before=d.get("decided_not_before"), parties_display=d.get("parties_display"),
                        names_withheld=bool(d.get("names_withheld")), disposition=d.get("disposition"),
                        reported=d.get("reported"), mentions=d.get("mentions"), roles=list(d.get("roles") or []),
                        treatments=list(d.get("treatments") or []),
                        treatments_awaiting_review=int(d.get("treatments_awaiting_review") or 0),
                        cited_as=d.get("cited_as"))


VERIFIED = "lawyer_verified"


def judgment_page(out: dict, day: date) -> JudgmentPage:
    j = out["judgment"]
    seen_cases: set = set()
    cases = []
    for c in out["cases_cited"]:
        key = (c["raw"] or "").strip()
        if not key or key in seen_cases:
            continue
        seen_cases.add(key)
        cases.append(CitedCase(raw=key, resolution=c["resolution"] or "unresolved",
                               judgment_id=str(c["dst_judgment_id"]) if c.get("dst_judgment_id") else None,
                               case_key=c.get("dst_case_key")))
    case = out["case"]
    return JudgmentPage(
        as_of=day, citation=out["citation"], note=NOTE,
        judgment=JudgmentHead(
            id=str(j["id"]), court_code=j["court_code"], court_name=j["court_name"], seat=j.get("seat"),
            case_no_printed=j.get("case_no_printed"), case_type_name=j.get("case_type_name"),
            case_number=j.get("case_number"), case_year=j.get("case_year"), decided_on=j.get("decided_on"),
            undated=bool(j.get("undated")), decided_no_later_than=j.get("decided_no_later_than"),
            decided_not_before=j.get("decided_not_before"), undated_reason=j.get("undated_reason"),
            hearing_on=j.get("hearing_on"), bench_printed=list(j.get("bench_printed") or []),
            bench_size=j.get("bench_size"), disposition=j.get("disposition"),
            disposition_printed=j.get("disposition_printed"), reported_flag=j.get("reported_flag"),
            neutral_citation=j.get("neutral_citation"), parties_display=j.get("parties_display"),
            jurisdiction_printed=j.get("jurisdiction_printed"), source_url=j.get("source_url")),
        opinions=[JudgmentOpinion(**o) for o in out["opinions"]],
        paragraphs=[JudgmentParagraph(id=str(p["id"]), kind=p["kind"], printed_no=p.get("printed_no"),
                                      page_first=p.get("page_first"), text=p["text"], opinion=p.get("opinion"),
                                      opinion_kind=p.get("opinion_kind"), citation=p["citation"])
                    for p in out["paragraphs"]],
        statutes_cited=[CitedProvision(provision_id=str(s["dst_provision_id"]), citation=s["citation"],
                                       label=s.get("label"), kind=s.get("kind"), law_title=s.get("short_title"),
                                       law_year=s.get("year"), law_kind=s.get("instrument_kind"),
                                       role=s.get("role"), mentions=int(s["mentions"]),
                                       status_now=s["status_now"]) for s in out["statutes_cited"]],
        cases_cited=cases,
        # what this judgment did to the decision below is a machine reading: its outcome waits for a lawyer
        appeal_from=[AppealFrom(relation=x.get("relation"), court_below=x.get("lower_court_printed"),
                                case_below=x.get("lower_case_printed"), decided_below=x.get("lower_decided_on"),
                                outcome=x["outcome"] if x.get("review_status") == VERIFIED else None,
                                outcome_withheld=bool(x.get("outcome")) and x.get("review_status") != VERIFIED)
                     for x in out["lineage"]],
        case_record=JudgmentCase(status=case["status"],
                          cases_decided=[CaseDecided(case_key=k["case_key"], role=k.get("role"),
                                                     case_type_name=k.get("case_type_name"),
                                                     case_number=k.get("case_number"), case_year=k.get("case_year"))
                                         for k in case["cases_decided"]],
                          other_decisions=[CaseDecision(judgment_id=str(d["judgment_id"]), citation=d["citation"],
                                                        decided_on=d.get("decided_on"), undated=bool(d.get("undated")))
                                           for d in case["other_decisions"]],
                          copy_of_judgment_id=(str(case["copy_of"]["judgment_id"]) if case.get("copy_of") else None)),
        privacy=JudgmentPrivacy(names_withheld=bool(out["privacy"]["names_withheld"]),
                                categories=[PrivacyCategory(code=c["code"], name=c.get("name"),
                                                            basis_kind=c.get("basis_kind"), basis=c.get("basis"))
                                            for c in out["privacy"]["categories"]]))


def _cursor_out(key: tuple | None) -> str | None:
    if key is None:
        return None
    return base64.urlsafe_b64encode(json.dumps([key[0], key[1].isoformat(), key[2]]).encode()).decode()


def _cursor_in(value: str | None) -> tuple | None:
    if not value:
        return None
    try:
        u, d, i = json.loads(base64.urlsafe_b64decode(value.encode()).decode())
        return bool(u), date.fromisoformat(d), str(UUID(i))
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, 'This list has expired. Refresh to continue.') from exc


def warm(repo, resolved) -> None:
    """one precedent search and the court index before the first reader asks (D-184): a cold first search took 15 s
    on the laptop (the encoder, the coverage cache, the judgment indexes). A failure only costs this warm-up."""
    try:
        repo.courts()
        P.search("bail", as_of=resolved(None), k=3, repo=repo)
    except Exception:                                           # noqa: BLE001
        pass


def _forum(code: str, territory: str):
    if code:
        return code
    if territory:
        return A.Subordinate(territory)
    return None


# ------------------------------------------------------------------------------------------------ routes

def register(app, repo, resolved) -> None:
    @app.get('/v1/precedent/search', response_model=PrecedentSearchPage)
    def precedent_search(q: str = Query(..., min_length=2, max_length=300), as_of: date | None = None,
                         court: COURTS = '', forum: COURTS = '', forum_territory: TERRITORIES = '',
                         subject: SUBJECTS = '', limit: int = Query(10, ge=1, le=25)):
        day = resolved(as_of)
        r = P.search(q.strip(), as_of=day, court=court or None, forum=_forum(forum, forum_territory), k=limit,
                     repo=repo, subject=subject or None)          # subject: an area read from the laws cited (D-163)
        gap = r.coverage_gap
        return PrecedentSearchPage(
            query=r.question, as_of=r.as_of, mode=r.mode, kind='precedent_discovery',
            note='Judgments that bear on the question, with the law they read. Not legal advice and not an answer: '
                 'binding status is from the recorded constitutional rules only, and the coverage below is all '
                 'that was searched.',
            coverage_gap=(f"No judgment of {gap.get('name') or gap.get('court')} is held." if gap else None),
            coverage_note=coverage_note(r.coverage),
            hits=[PrecedentHitOut(judgment_id=str(h.judgment_id), paragraph_id=str(h.paragraph_id),
                                  citation=h.citation, court=h.court, case_type=h.case_type, case_key=h.case_key,
                                  decided_on=h.decided_on, undated=h.undated,
                                  decided_no_later_than=h.decided_no_later_than, disposition=h.disposition,
                                  reported=h.reported, text=h.text, parties_display=h.parties_display,
                                  names_withheld=bool((h.privacy or {}).get("names_withheld")),
                                  binding=(h.authority or {}).get("status"),
                                  subjects=[str(s) for s in (h.subjects or [])])
                  for h in r.hits])

    @app.get('/v1/precedent/courts', response_model=CourtsPage)
    def courts():
        rows = repo.courts()
        return CourtsPage(items=[CourtCoverage(**r) for r in rows],
                          total_judgments=sum(r["judgments"] for r in rows), coverage_note=coverage_note(rows))

    @app.get('/v1/precedent/courts/{court}/judgments', response_model=JudgmentList)
    def court_judgments(court: COURT, as_of: date | None = None, limit: int = Query(20, ge=1, le=50),
                        after: str | None = Query(None, max_length=200)):
        day = resolved(as_of)
        items, nxt = repo.court_judgments(court, day, limit, _cursor_in(after))
        return JudgmentList(as_of=day, items=[card(i) for i in items], next_cursor=_cursor_out(nxt),
                            coverage_note=coverage_note([r for r in repo.courts() if r["code"] == court]))

    @app.get('/v1/precedent/judgments/{judgment_id}', response_model=JudgmentPage)
    def judgment(judgment_id: UUID, as_of: date | None = None):
        day = resolved(as_of)
        out = repo.judgment(judgment_id, as_of=day)
        if out is None:
            raise HTTPException(404, 'No released judgment with this id was decided on or before this date.')
        return judgment_page(out, day)

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

    @app.get('/v1/precedent/judgments/{judgment_id}/cited-by', response_model=JudgmentList)
    def cited_by(judgment_id: UUID, as_of: date | None = None, limit: int = Query(20, ge=1, le=50)):
        # later judgments citing this one's case, by number or by a reporter citation the court publishes (D-150);
        # a citation not resolved is not shown, so 'none' means none found among the judgments held (coverage)
        day = resolved(as_of)
        return JudgmentList(as_of=day, items=[card(i) for i in repo.citing_judgments(judgment_id, day, limit)],
                            next_cursor=None, coverage_note=coverage_note(repo.courts()))

    @app.get('/v1/precedent/judgments/{judgment_id}/history', response_model=HistoryPage)
    def history(judgment_id: UUID, as_of: date | None = None):
        # what the courts above did with this judgment's case, in their own words (D-159). Only appeals the corpus
        # holds are known, so an empty list says 'none held'; a machine-read reversal is withheld until verified
        day = resolved(as_of)
        items = [HistoryItem(source=h["source"], judgment_id=str(h["judgment_id"]) if h.get("judgment_id") else None,
                             court=h["court"], relation=h.get("relation"), outcome=h.get("outcome"),
                             outcome_withheld=bool(h.get("outcome_withheld")), outcome_printed=h.get("outcome_printed"),
                             decided_on=h.get("decided_on"), citation=h.get("citation"),
                             upper_file_url=h.get("upper_file_url"))
                 for h in repo.later_history(judgment_id, day)]
        return HistoryPage(judgment_id=str(judgment_id), as_of=day, items=items,
                           coverage_note=coverage_note(repo.courts()))

    def _citing(kind: str, ident: UUID, as_of: date | None, order: str, limit: int, offset: int) -> CitingPage:
        day = resolved(as_of)
        got = repo.citing((kind, ident), day, limit=limit, order=order, offset=offset)
        status = None
        if kind == 'provision':
            s = repo.judicial_status(ident, day)                         # D-161: lawyer-verified readings only
            status = JudicialStatus(
                verified=[VerifiedInvalidation(extent=v["extent"], extent_note=v.get("extent_note"),
                                               effective_on=v.get("effective_on"), appeal_state=v.get("appeal_state"),
                                               reading=v.get("reading"),
                                               judgment_id=str(v["judgment_id"]) if v.get("judgment_id") else None)
                          for v in s["verified"]],
                candidates_awaiting_review=int(s["candidates_awaiting_review"]), coverage=s["coverage"])
        end = offset + len(got["items"])
        return CitingPage(scope=kind, id=str(ident), as_of=day, order=order, total=got["total"],
                          items=[card(i) for i in got["items"]], judicial_status=status,
                          next_offset=end if end < got["total"] else None,
                          coverage_note=coverage_note(repo.courts()))

    @app.get('/v1/law/provisions/{provision_id}/judgments', response_model=CitingPage)
    def provision_judgments(provision_id: UUID, as_of: date | None = None, order: ORDER = 'recent',
                            limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=2000)):
        return _citing('provision', provision_id, as_of, order, limit, offset)

    @app.get('/v1/law/instruments/{instrument_id}/judgments', response_model=CitingPage)
    def instrument_judgments(instrument_id: UUID, as_of: date | None = None, order: ORDER = 'recent',
                             limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0, le=2000)):
        return _citing('instrument', instrument_id, as_of, order, limit, offset)

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
