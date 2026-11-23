"""Precedent search: which judgments bear on a question (docs/PRECEDENT-MODEL.md §4, §6; docs/04 §6).

    search(question, as_of=date, court=None, forum=None, k=10) -> PrecedentResult

Three generators, fused by reciprocal rank (RRF, k = 60, docs/04 §3), then grouped so a judgment appears once, by its
best paragraph:
1. **BM25** over released judgment paragraphs (ix_judgment_paragraph_bm25).
2. **Dense:** the question's bge-m3 sign bits against judgment chunks (the statutes' own generation, D-121).
3. **Cited:** when the question names a provision ('s.497 CrPC', 'Article 199'), the judgments that cite it or a
   unit inside it (judgment_statute_reference, D-119), through the same citation grammar as statute retrieval.

What a result carries, and what it never does:
- **Citations from records only (INV-1):** court, case as printed, decision date, printed paragraph number.
- **Decided on or before `as_of`:** a later judgment did not exist on that date. An undated judgment (D-124) is
  returned only once `as_of` reaches the latest day it can have been decided, and carries decided_on None.
- **Binding status** for the forum the user names (a court code, or Subordinate(territory)), from authority_rule as
  at `as_of` (D-116): Binding, NotBinding or NotRecorded. It is never inferred from a court's name.
- **The law it read:** for each provision the judgment cites, whether that text is still the operative text on
  `as_of` (amended since, no longer operative, same text, or the decision-date text not held).
- **Coverage:** the courts and years searched (D-122). "Nothing found" is always "nothing found in this coverage".
- **The case** each hit decides (D-125), and whether the hit gives the reasons for the court's short order. A
  second copy of one decision is never a hit beside the copy kept.

This is precedent discovery, not an answer. It returns evidence for a reader or for L4/L5. It is not a
GroundingContext and passes no gate (INV-2). L5's citator owns treatment and "good law" (docs/04 §6.5).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date

from nizam.storage import authority as A
from nizam.storage import citations as C
from nizam.storage import privacy as PV
from nizam.storage import unit_search
from nizam.storage.judgment_read import JudgmentRead
from nizam.storage.lexical import Filters

RRF_K = 60
WINDOW = 50


@dataclass
class PrecedentHit:
    judgment_id: str
    paragraph_id: str
    citation: str
    court: str
    case_type: str | None
    decided_on: date | None           # None: the judgment prints no usable decision date (D-124)
    disposition: str | None
    reported: bool | None
    text: str
    score: float
    generators: list[str]
    authority: dict | None = None
    statutes_cited: list[dict] = field(default_factory=list)
    undated: bool = False
    decided_no_later_than: date | None = None
    decided_not_before: date | None = None
    parties_display: str | None = None  # 'A v. B', withheld names replaced (D-131)
    privacy: dict = field(default_factory=dict)  # names_withheld, and each category's recorded basis
    case_key: str | None = None       # the case it decides, as printed ('SC/CA/1507/2024'); None if not placed (D-125)
    gives_reasons: bool = False       # it gives the reasons for the court's short order in that case
    short_order_on: date | None = None  # that short order's printed date, when printed


@dataclass
class PrecedentResult:
    question: str
    as_of: date
    hits: list[PrecedentHit]
    cited_provisions: list[dict]
    coverage: list[dict]
    mode: str                         # 'hybrid' | 'lexical_only' (no encoder on this host)
    trace: dict


def _authority(deciding: str, forum, as_of: date, registry) -> dict | None:
    if forum is None:
        return None
    courts, rules, sup = registry
    r = A.authority(deciding, forum, as_of, courts=courts, rules=rules, superintendence=sup)
    if isinstance(r, A.Binding):
        return dict(status="binding", basis=r.rule.basis, subject_to=list(r.subject_to),
                    source_unit=r.rule.source.get("source_unit"), source_quote=r.rule.source.get("source_quote"))
    if isinstance(r, A.NotBinding):
        return dict(status="not_binding", rules_considered=[x.id for x in r.rules_considered])
    return dict(status="not_recorded", reason=r.reason)


def search(question: str, *, as_of: date, court: str | None = None, forum=None, k: int = 10,
           repo: JudgmentRead | None = None, encoder=None) -> PrecedentResult:
    if type(as_of) is not date:
        raise ValueError("as_of is mandatory (INV-5) and is a date")
    t0 = time.time()
    trace: dict = {}
    own = repo is None
    repo = repo or JudgmentRead()
    if own:
        repo.open()
    try:
        with repo.transaction() as conn:
            cur = repo.tuple_cursor(conn)
            # 3. the provisions the question names, resolved from records (D-097)
            cited = []
            session = unit_search.Session(cur, Filters(as_of=as_of))
            for c in C.find(question):
                r = C.resolve(session, c)
                if r.resolved_unit:
                    cited.append(dict(raw=c.raw, provision_id=r.resolved_unit.unit_id, law=r.resolved_law))
            lists = {}
            lists["bm25"] = repo.bm25_paragraphs(conn, question, WINDOW, as_of, court)
            mode = "lexical_only"
            try:
                enc = encoder
                if enc is None:
                    from nizam.inference.encoder import encoder as _encoder
                    enc = _encoder()
                lists["dense"] = repo.dense_paragraphs(conn, enc.bits(question), WINDOW, as_of, court)
                mode = "hybrid"
            except Exception as exc:                            # noqa: BLE001  no encoder bundle on this host
                trace["dense_unavailable"] = type(exc).__name__
            if cited:
                lists["cited"] = repo.citing_paragraphs(conn, [c["provision_id"] for c in cited], WINDOW, as_of,
                                                        court)
            fused: dict = {}
            for name, rows in lists.items():
                for rank, r in enumerate(rows, 1):
                    f = fused.setdefault(r["id"], dict(score=0.0, gens=[], judgment_id=r["judgment_id"]))
                    f["score"] += 1.0 / (RRF_K + rank)
                    f["gens"].append(name)
            best: dict = {}
            for pid, f in sorted(fused.items(), key=lambda x: -x[1]["score"]):
                if f["judgment_id"] not in best:
                    best[f["judgment_id"]] = (pid, f)
                if len(best) >= k:
                    break
            details = repo.paragraph_hits(conn, [pid for pid, _ in best.values()])
            statutes = repo.statutes_cited(conn, list(best), as_of)
            registry = A.load(cur) if forum is not None else None
            hits = []
            withheld_queries = 0
            for jid, (pid, f) in best.items():
                d = details.get(pid)
                if not d:
                    continue
                if d["_names_withheld"] and PV.names_queried(question, d["_names_withheld"]):
                    # a search that names a person whose name this judgment withholds never finds it (D-131)
                    withheld_queries += 1
                    continue
                hits.append(PrecedentHit(
                    judgment_id=str(jid), paragraph_id=str(pid), citation=d["citation"], court=d["court_name"],
                    case_type=d["case_type_name"], decided_on=d["decided_on"], disposition=d["disposition"],
                    reported=d["reported_flag"], text=d["text"], score=round(f["score"], 6), generators=f["gens"],
                    authority=_authority(d["court_code"], forum, as_of, registry),
                    statutes_cited=[dict(citation=s["citation"], provision_id=str(s["dst_provision_id"]),
                                         role=s["role"], status_now=s["status_now"], mentions=s["mentions"])
                                    for s in statutes.get(jid, [])][:12],
                    undated=d["undated"], decided_no_later_than=d["decided_no_later_than"],
                    decided_not_before=d["decided_not_before"], case_key=d["case_key"],
                    parties_display=d["parties_display"], privacy=d["privacy"],
                    gives_reasons=d["gives_reasons"], short_order_on=d["reasons_for_short_order_on"]))
            coverage = conn.execute("""SELECT v.court_code, min(first_decided) AS first_decided,
                                              max(last_decided) AS last_decided, sum(judgments_released) AS judgments,
                                              coalesce(sum(judgments_released) FILTER (WHERE year IS NULL), 0)
                                                  AS undated,
                                              (SELECT count(*) FROM judicial_case k
                                                WHERE k.court_code = v.court_code) AS cases
                                         FROM v_judgment_coverage v GROUP BY v.court_code
                                        ORDER BY v.court_code""").fetchall()
        trace.update(generators={n: len(v) for n, v in lists.items()}, ms=int((time.time() - t0) * 1000),
                     withheld_by_name=withheld_queries)
        return PrecedentResult(question=question, as_of=as_of, hits=hits, cited_provisions=cited,
                               coverage=[dict(c) for c in coverage], mode=mode, trace=trace)
    finally:
        if own:
            repo.close()
