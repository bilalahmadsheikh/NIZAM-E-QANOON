"""L3's sufficiency gate and the retrieval port (D-102; docs/04 §8, §9.2; INV-2):

    retrieve(question, Filters(as_of=...)) -> GroundingContext | Abstention

Two values and no third: no retry at a lower threshold, no fallback to model knowledge, no "low confidence" answer.

Order of decisions, each recorded in the result's `gate` dict (INV-3):
  1. scope vetoes on the question, before any search (nizam.retrieval.scope): the law at a future date
     (NO_VALID_VERSION), a court's decision (CORPUS_GAP, no judgments yet), the law of a foreign place (CORPUS_GAP);
  2. the served retrieval (nizam.retrieval.rerank.ranked); nothing found -> INSUFFICIENT_EVIDENCE;
  3. the territory veto: no territory given or found, and the bundle's first 5 units hold provincial laws of two or
     more provinces -> JURISDICTION_UNRESOLVED (docs/04 §10.3: never guess a province);
  4. the calibration for the mode that actually ran -- the reranker that scored (by model and revision), or the
     unreranked mode (by the dense space its slate came from). None for it -> RETRIEVAL_DEGRADED (docs/04 §9.2:
     "if that calibration has not shipped, abstain");
  5. p = sigmoid(w . z + b) over the bundle's features (FEATURES); pass iff p >= tau. Below -> INSUFFICIENT_EVIDENCE,
     with the nearest units attached as NEAREST, never as evidence.

The calibration (gate_calibration.json beside this file) is written by evals/gate_fit.py under the rule fixed before
any score existed (evals/results/gate-rule-2026-11-20.json): logistic regression on dev, tau for answered precision
0.95. The file is data; nothing here chooses a threshold.

The gate judges identities and scores (INV-1, INV-4: units, never chunks): GroundingContext.items. A passing context
is then assembled (docs/04 §7, nizam.retrieval.assembly, D-107): whole units with their definitions, qualifications,
references, law facts and sources, in GroundingContext.evidence. Assembly changes nothing the gate decided.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from nizam.retrieval import scope
from nizam.retrieval.lexical import LexicalResult
from nizam.retrieval.query import QuerySpec, parse
from nizam.storage import unit_search
from nizam.storage.lexical import Filters

BUNDLE = 10                 # units admitted to assembly (the rule's bundle; the CPU reranker's depth, D-101)
CONC_OF = 5                 # the concentration feature and the territory veto read the bundle's first 5
AGREE_TOP = 10              # a generator "agrees" when it ranks the lead unit in its own first 10
CALIBRATION = Path(__file__).with_name("gate_calibration.json")

CODES = frozenset({"AMBIGUOUS_CITATION", "JURISDICTION_UNRESOLVED", "NO_VALID_VERSION", "SOURCE_UNVERIFIED",
                   "FORUM_UNRESOLVED", "ADVERSE_TREATMENT_UNRESOLVED", "MISSING_DELEGATED_AUTHORITY",
                   "COMMENCEMENT_UNKNOWN", "CORPUS_GAP", "INSUFFICIENT_EVIDENCE", "RETRIEVAL_DEGRADED"})  # docs/04 §8.1

PUBLIC = {   # what a reader is told, and what would let the question be answered (docs/04 §8.1: actionable)
    "NO_VALID_VERSION": ("The law at that date is not known: the library holds the law in force up to today.",
                         ("Ask about the law as it stands today.",)),
    "CORPUS_GAP:place": ("The library holds the law of Pakistan, its four provinces, Islamabad, Azad Jammu and Kashmir "
                         "and Gilgit-Baltistan, not the law of other countries.",
                         ("Ask how Pakistani law treats the matter.",)),
    "CORPUS_GAP:source": ("Court judgments are not in the library yet; it holds statutes, rules and orders only.",
                          ("Ask what the law itself says on the point.",)),
    "CORPUS_GAP:records": ("The library holds the law, not records about particular people, cases, property or "
                           "companies.", ("Ask the office that keeps the record; ask here what the law requires.",)),
    "CORPUS_GAP:statistics": ("The library holds the law, not statistics about cases or events.",
                              ("Ask what the law says on the matter.",)),
    "CORPUS_GAP:live": ("The library holds the law, not live rates, prices or readings.",
                        ("Ask what the law says, for example about how a rate is set.",)),
    "JURISDICTION_UNRESOLVED": ("The answer depends on the province or territory, and the question does not say which.",
                                ("Name the province or territory, for example Punjab, Sindh or Islamabad.",)),
    "RETRIEVAL_DEGRADED": ("Search is running in a reduced mode that has not been checked for accuracy, so no answer "
                           "is given.", ("Try again shortly.",)),
    "INSUFFICIENT_EVIDENCE": ("No provision in the library matches the question closely enough to answer it.",
                              ("Name the law or section if you know it.", "Say which province or territory.",
                               "Describe the situation in other words.")),
}


@dataclass(frozen=True)
class BundleItem:
    """one unit the gate judged, by identity and score (docs/04 §7's EvidenceItem is the ASSEMBLED item:
    nizam.retrieval.assembly.EvidenceItem)"""
    unit_id: str
    version_id: str
    instrument_id: str
    rank: int
    rerank_score: float | None
    fused_score: float
    via_citation: bool


@dataclass(frozen=True)
class GroundingContext:
    query: QuerySpec
    filters: Filters
    items: tuple                     # BundleItem, served order, at most BUNDLE: what the gate judged (INV-3)
    confidence: float
    threshold: float
    gate: dict                       # mode, calibration version, features, p, tau, decision
    trace: dict                      # the retrieval trace (INV-3)
    degraded: str | None = None
    evidence: tuple = ()             # assembly.EvidenceItem, legal order: what the generator reads (docs/04 §7)
    coverage: dict = field(default_factory=dict)   # what assembly admitted, skipped and why, and what it lacks
    conflicts: tuple = ()            # {prevails, over, kind, said_by} unit ids: one prevails over another (docs/04 §7)


@dataclass(frozen=True)
class Abstention:
    code: str
    public_reason: str
    missing: tuple = ()
    suggestions: tuple = ()
    confidence: float | None = None
    threshold: float | None = None
    nearest: tuple = ()              # the closest units, for "nearest results" shown APART from any answer
    gate: dict = field(default_factory=dict)
    trace: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.code not in CODES:
            raise ValueError(f"{self.code!r} is not an Abstention code (docs/04 §8.1)")


def _abstain(code: str, gate: dict, trace: dict | None = None, variant: str | None = None, **kw) -> Abstention:
    reason, suggestions = PUBLIC[f"{code}:{variant}" if variant else code]
    gate = {**gate, "decision": "abstain", "code": code}
    return Abstention(code, reason, suggestions=suggestions, gate=gate, trace=trace or {}, **kw)


def _items(cands) -> tuple:
    return tuple(BundleItem(c.unit_id, c.version_id, c.instrument_id, c.rank, c.rerank_score, c.score,
                              c.via_citation) for c in cands)


# --- features (the rule's F1-F3; evals/gate_features.py computes them with this same function) ---------------------
def features(r: LexicalResult, mode: str) -> dict:
    """top, margin, conc, cited over the bundle. Reranked modes read rerank_score; unreranked reads the fused score of
    the served order (the rule: the rank-1 unit's fused RRF score)."""
    bundle = r.candidates[:BUNDLE]
    if mode == "unreranked":
        scores = [c.score for c in bundle]
        lead = bundle[0] if bundle else None
    else:
        scored = [c for c in bundle if c.rerank_score is not None]
        scores = sorted((c.rerank_score for c in scored), reverse=True)
        lead = max(scored, key=lambda c: c.rerank_score) if scored else (bundle[0] if bundle else None)
    if not bundle or not scores:
        return {"top": None, "margin": None, "conc": None, "cited": 0, "agree": None}
    srt = sorted(scores, reverse=True)
    head = bundle[:CONC_OF]
    gr = lead.generator_ranks or {}
    return {"top": round(float(srt[0]), 6),
            "margin": round(float(srt[0] - srt[1]) if len(srt) > 1 else 0.0, 6),
            "conc": round(sum(1 for c in head if c.instrument_id == lead.instrument_id) / len(head), 6),
            "cited": int(any(c.via_citation for c in bundle)),
            # generators placing the lead unit in their own first 10 (docs/04 §8.1 "generator agreement"; addendum)
            "agree": int((gr.get("lexical") or 99) <= AGREE_TOP) + int((gr.get("dense") or 99) <= AGREE_TOP)
                     + int("citation" in gr)}


# --- calibration ---------------------------------------------------------------------------------------------------
@lru_cache(maxsize=4)
def _calibration(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"version": None, "modes": {}}


def calibration(path: Path | None = None) -> dict:
    return _calibration(str(path or CALIBRATION))


def mode_of(r: LexicalResult, cal: dict) -> tuple[str, dict | None]:
    """which calibrated mode this result ran in, and its calibration (None: this mode shipped none)"""
    modes = cal.get("modes", {})
    if r.degraded and "unreranked" in r.degraded:
        m = modes.get("unreranked")
        if m and m.get("dense_generation") == r.trace.get("dense_generation"):
            return "unreranked", m
        return "unreranked", None
    rr = r.trace.get("rerank") or {}
    ident = f"{rr.get('model')}@{rr.get('revision')}"
    for name, m in modes.items():
        if name != "unreranked" and m.get("reranker") == ident:
            return name, m
    return f"reranker {ident}", None


def probability(feats: dict, m: dict) -> float:
    z = sum(w * ((feats[f] - mu) / sd) for f, w, mu, sd in zip(m["features"], m["coef"], m["mean"], m["scale"]))
    z += m["intercept"]
    return 1.0 / (1.0 + math.exp(-z)) if z >= -700 else 0.0


def territory_veto(r: LexicalResult, connect_fn=None) -> list[str] | None:
    """the provinces whose laws lead the bundle, when no territory was given or found and there are two or more"""
    f = r.filters
    if f.territory or f.jurisdictions or r.spec.territory:
        return None
    head = r.candidates[:CONC_OF]
    kwargs = {"connect_fn": connect_fn} if connect_fn else {}
    with unit_search.session(f, **kwargs) as s:
        juris = s.instrument_jurisdictions([c.instrument_id for c in head])
    provinces = sorted({juris.get(c.instrument_id) for c in head} - {None, "fed"})
    return provinces if len(provinces) >= 2 else None


# --- the gate ------------------------------------------------------------------------------------------------------
def gate(r: LexicalResult, cal: dict | None = None, connect_fn=None, territory_check: bool = True):
    """a served (reranked or marked) result -> GroundingContext | Abstention"""
    cal = cal if cal is not None else calibration()
    g: dict = {"calibration": cal.get("version"), "bundle": BUNDLE}
    if not r.candidates:
        return _abstain("INSUFFICIENT_EVIDENCE", {**g, "stage": "empty"}, r.trace)
    nearest = _items(r.candidates[:5])
    if territory_check:
        provinces = territory_veto(r, connect_fn)
        if provinces:
            return _abstain("JURISDICTION_UNRESOLVED", {**g, "stage": "territory", "provinces": provinces}, r.trace,
                            missing=("territory",), nearest=nearest)
    mode, m = mode_of(r, cal)
    g["mode"] = mode
    if m is None:
        return _abstain("RETRIEVAL_DEGRADED", {**g, "stage": "calibration"}, r.trace, nearest=nearest)
    feats = features(r, mode)
    g["features"] = feats
    if feats["top"] is None:
        return _abstain("INSUFFICIENT_EVIDENCE", {**g, "stage": "unscored"}, r.trace, nearest=nearest)
    p, tau = probability(feats, m), float(m["tau"])
    g.update(p=round(p, 6), tau=tau)
    if p >= tau:
        return GroundingContext(r.spec, r.filters, _items(r.candidates[:BUNDLE]), round(p, 6), tau,
                                {**g, "decision": "pass"}, r.trace, r.degraded)
    return _abstain("INSUFFICIENT_EVIDENCE", {**g, "stage": "threshold"}, r.trace, confidence=round(p, 6),
                    threshold=tau, nearest=nearest)


def pre_veto(spec: QuerySpec, filters: Filters, today: date | None = None) -> scope.ScopeFinding | None:
    return scope.veto(spec.text, filters.as_of, cited=bool(spec.citations), today=today)


def retrieve(question, filters: Filters, k: int = 50, connect_fn=None, encoder=None, reranker=None,
             today: date | None = None, cal: dict | None = None, assemble: bool = True):
    """THE port (docs/04 §11.1): GroundingContext | Abstention, nothing else. A passing context is assembled
    (docs/04 §7, nizam.retrieval.assembly) before it is returned; `assemble=False` returns the gate's bare context
    (evaluation of the gate alone)."""
    from nizam.retrieval.rerank import ranked
    spec = question if isinstance(question, QuerySpec) else parse(question)
    finding = pre_veto(spec, filters, today)
    if finding:
        cal = cal if cal is not None else calibration()
        g = {"calibration": cal.get("version"), "stage": f"veto:{finding.kind}", "matched": finding.matched,
             "detail": finding.reason}
        variant = finding.kind if finding.code == "CORPUS_GAP" else None
        return _abstain(finding.code, g, {"query": spec.text}, variant=variant)
    r = ranked(spec, filters, k, connect_fn=connect_fn, encoder=encoder, reranker=reranker)
    out = gate(r, cal=cal, connect_fn=connect_fn)
    if not assemble or not isinstance(out, GroundingContext):
        return out
    from nizam.retrieval.assembly import assemble as _assemble
    full = _assemble(out, connect_fn=connect_fn)
    if full is None:      # no bundle unit is law at as_of any more (the corpus changed between the two reads)
        return _abstain("INSUFFICIENT_EVIDENCE", {**out.gate, "stage": "assembly"}, out.trace,
                        nearest=out.items[:5])
    return full
