"""Fused lexical candidates over legal units (D-097; docs/04 §4.1, §5; R1's lexical half).

    from nizam.retrieval.lexical import lexical_candidates
    r = lexical_candidates("My landlord in Lahore wants me out ...", Filters(as_of=date.today()), k=50)
    r.candidates  -> [UnitCandidate(unit_id, version_id, instrument_id, score, rank, generator_ranks, via_citation)]

What it does, in order:
  1. parse the question (nizam.retrieval.query): citations, the territory a place names, the lexical words;
  2. a place sets the territory ONLY when the caller set neither territory nor jurisdictions -- an explicit scope
     always wins (docs/04: a territory or an explicit comparison, never a guess);
  3. citations are resolved from the database; a resolved unit is placed first (docs/04 R0 citation fast path);
  4. three cheap generators over L2 windows (nizam.storage.unit_search): body BM25 hits and heading/marginal-note hits,
     each collapsed to legal units with unitScore = max + 0.15 x second best (docs/04 §5), and title matches;
  5. reciprocal rank fusion, k = 60 (docs/04 §5), of the body and heading unit lists, plus a title term for units of
     instruments whose title matches -- the configuration measured on golden sets 1-4 before it was written here
     (recall@50 0.383 -> 0.564, D-097);
  6. THE INV-5 GATE: units pass operative_units (operative_provision as at the date, in the territory) in batches,
     best first, until k are operative or the list ends. Filtering never reorders, so the result is what ranking the
     operative units alone would give.

Candidates name legal units and the version that makes each operative (INV-4: no chunk ids). The trace records what
every stage did, for the replay record docs/04 and INV-3 require once answers exist.
"""
from __future__ import annotations

import collections
import time
from dataclasses import dataclass, field, replace

from nizam.retrieval import citations as _citations
from nizam.retrieval.query import QuerySpec, parse
from nizam.storage import unit_search
from nizam.storage.lexical import Filters

RRF_K = 60               # docs/04 §5
SECOND_WEIGHT = 0.15     # docs/04 §5: unitScore = max + 0.15 * secondBest
BODY_HITS = 150          # provisions read from the body window (~110-140 units)
HEADING_HITS = 100
TITLE_HITS = 20


@dataclass(frozen=True)
class UnitCandidate:
    unit_id: str
    version_id: str
    instrument_id: str
    score: float
    rank: int
    generator_ranks: dict
    via_citation: bool = False


@dataclass
class LexicalResult:
    candidates: list
    spec: QuerySpec
    filters: Filters
    truncated: bool
    trace: dict = field(default_factory=dict)


def effective_filters(spec: QuerySpec, filters: Filters) -> Filters:
    if filters.territory is None and filters.jurisdictions is None and spec.territory:
        return replace(filters, territory=spec.territory)
    return filters


def _collapse(session, hits) -> list:
    """[(Unit, unitScore)] best first"""
    if not hits:
        return []
    units = session.units_of([h.provision_id for h in hits])
    scores, by_id = collections.defaultdict(list), {}
    for h in hits:
        u = units[h.provision_id]
        scores[u.unit_id].append(h.score)
        by_id[u.unit_id] = u
    ranked = []
    for uid, ss in scores.items():
        ss.sort(reverse=True)
        ranked.append((by_id[uid], ss[0] + SECOND_WEIGHT * (ss[1] if len(ss) > 1 else 0.0)))
    ranked.sort(key=lambda x: (-x[1], x[0].unit_id))
    return ranked


def lexical_candidates(question, filters: Filters, k: int = 50, connect_fn=None) -> LexicalResult:
    spec = question if isinstance(question, QuerySpec) else parse(question)
    f = effective_filters(spec, filters)
    t0 = time.perf_counter()
    trace: dict = {"lexical": spec.lexical, "territory_from_question": spec.territory,
                   "territory_used": f.territory, "jurisdictions_used": f.jurisdictions}
    kwargs = {"connect_fn": connect_fn} if connect_fn else {}
    lap = time.perf_counter
    stages: dict[str, int] = {}

    def mark(name, since):
        stages[name] = round((lap() - since) * 1000)
        return lap()

    with unit_search.session(f, **kwargs) as s:
        t = lap()
        cited = []
        for c in spec.citations:
            _citations.resolve(s, c)
            if c.resolved_unit is not None:
                cited.append(c.resolved_unit)
                cited.extend(c.alternates)          # same-titled territorial copies, right after (typed ambiguity)
        trace["citations"] = [{"raw": c.raw, "law": c.resolved_law, "alternates": c.alternate_laws,
                               "unresolved": c.unresolved} for c in spec.citations]
        t = mark("citations", t)
        body_raw = s.body_hits(spec.lexical, BODY_HITS)
        t = mark("body_window", t)
        head_raw = s.heading_hits(spec.lexical, HEADING_HITS)
        t = mark("heading_window", t)
        body, heads = _collapse(s, body_raw), _collapse(s, head_raw)
        t = mark("units_of", t)
        windows_full = len(body_raw) >= BODY_HITS or len(head_raw) >= HEADING_HITS
        titles = {iid: r for r, (iid, _s) in enumerate(s.title_hits(spec.lexical, TITLE_HITS), 1)}
        t = mark("title_window", t)
        fused: dict[str, float] = collections.defaultdict(float)
        ranks: dict[str, dict] = collections.defaultdict(dict)
        units: dict[str, unit_search.Unit] = {}
        for name, lst in (("body", body), ("heading", heads)):
            for r, (u, _score) in enumerate(lst, 1):
                fused[u.unit_id] += 1.0 / (RRF_K + r)
                ranks[u.unit_id][name] = r
                units[u.unit_id] = u
        for uid, u in units.items():
            if u.instrument_id in titles:
                fused[uid] += 1.0 / (RRF_K + titles[u.instrument_id])
                ranks[uid]["title"] = titles[u.instrument_id]
        order = list(dict.fromkeys(u.unit_id for u in cited))
        for u in cited:
            units[u.unit_id] = u
            ranks[u.unit_id]["citation"] = 1
        order += [uid for uid in sorted(fused, key=lambda x: (-fused[x], x)) if uid not in set(order)]
        trace["generators"] = {"body_units": len(body), "heading_units": len(heads), "title_laws": len(titles),
                               "cited_units": len(cited), "fused_units": len(order)}
        # THE INV-5 GATE, best first, in batches, until k are operative
        out: list[UnitCandidate] = []
        batch = max(2 * k, 40)
        i = 0
        while len(out) < k and i < len(order):
            chunk = [units[uid] for uid in order[i:i + batch]]
            i += batch
            live = s.operative_units(chunk)
            for u in chunk:
                if u.unit_id in live and len(out) < k:
                    out.append(UnitCandidate(u.unit_id, live[u.unit_id], u.instrument_id,
                                             round(fused.get(u.unit_id, 1.0), 6), len(out) + 1,
                                             dict(ranks[u.unit_id]), "citation" in ranks[u.unit_id]))
        trace["gated_batches"] = (i + batch - 1) // batch if order else 0
        mark("gate", t)
        trace["stage_ms"] = stages
    trace["ms"] = round((time.perf_counter() - t0) * 1000)
    # fewer than k operative units while a window came back full: the window, not the corpus, bounded the result
    return LexicalResult(out, spec, f, truncated=len(out) < k and windows_full, trace=trace)
