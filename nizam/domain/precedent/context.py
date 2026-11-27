"""The precedent context for an answer: IPrecedent.contextFor (D-173; docs/ANSWER-COMPOSITION.md §5 stage 3).

    from nizam.domain.precedent import context_for, seed_from
    law = retrieve(question, Filters(as_of=d, territory="punjab"))          # L3: GroundingContext | Abstention
    ctx = context_for(question, as_of=d, forum=Subordinate("punjab"), **seed_from(law))
    ctx -> PrecedentContext(items=[PrecedentItem ...]) | PrecedentAbstention

What it adds to precedent search (nizam.retrieval.precedent.search, L3), which it calls once:
  1. the statute units the answer stands on (the seed) mark which of them each judgment cites (`interprets`). The
     LAW JOIN -- the seed choosing judgments, as a generator or a vote -- is off by default (`law_join`): measured on
     precedent dev v2 it lowered the results in all nine forms tried (D-173);
  2. the forum's authority for every judgment (binding / not_binding / not_recorded), from the recorded rules
     (A24), never from a court's name (docs/05 §2);
  3. adverse status as at `as_of` (JudgmentRead.adverse_status): a lawyer-verified overruling, per incuriam,
     disapproval, or reversal on appeal EXCLUDES the judgment, recorded in the trace; a machine reading is carried
     as `awaiting_review`, never as fact (docs/06 §5.1);
  4. a version note per cited unit (JudgmentRead.version_notes): the court read a text since replaced
     (`earlier_text`), the same text (`same_text`), or it cannot be told (`not_dated`);
  5. coverage, always: "nothing found" is "nothing found in these courts and years" (PRECEDENT-MODEL §5).

The seed (seed_from): the units of a PASSED statute context; when the statute gate abstained on its threshold, the
units it found nearest. The seed only chooses which judgments to look at; no statutory claim is ever made from a
seed the statute gate did not pass (INV-2 governs answers). A vetoed question (a court's decision, a foreign place)
has no seed.

Whether the judgments are good enough to cite is the precedent gate's decision (S2, D-174; nizam.domain.precedent
.gate): by default context_for applies it, and only a `gated` context may be cited (INV-2). `gate=False` gives the
ungated context, which is discovery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from nizam.retrieval.precedent import search
from nizam.storage.judgment_read import JudgmentRead

ABSTENTION_CODES = frozenset({"COURT_NOT_HELD", "NO_PRECEDENT_FOUND", "INSUFFICIENT_PRECEDENT",
                              "PRECEDENT_GATE_UNCALIBRATED"})
PUBLIC = {   # what a reader is told (docs/04 §8.1: actionable); the coverage always goes with it
    "INSUFFICIENT_PRECEDENT": "No judgment in the library answers this clearly enough to rely on. The closest judgments are listed apart, as research leads, not as authority.",
    "PRECEDENT_GATE_UNCALIBRATED": "Judgments cannot be relied on in this mode yet. The closest judgments are listed apart, as research leads, not as authority.",
    "NO_PRECEDENT_FOUND": "No judgment in the library was found on this point. The library's courts and years are listed with this result.",
}


@dataclass(frozen=True)
class PrecedentItem:
    judgment_id: str
    paragraph_id: str
    citation: str                      # rendered from records (INV-1)
    court: str
    decided_on: date | None            # None: undated (D-124); see decided_no_later_than
    decided_no_later_than: date | None
    text: str
    score: float
    generators: tuple                  # which of bm25 / dense / cited / case / law / binding found it
    authority: dict | None             # {status: binding | not_binding | not_recorded, ...} for the forum at as_of
    interprets: dict                   # {unit id: earlier_text | same_text | not_dated}: seed units this judgment cites
    awaiting_review: tuple             # machine-read negative treatments or reversals, never shown as fact
    case_key: str | None = None
    names_withheld: bool = False


@dataclass(frozen=True)
class PrecedentContext:
    question: str
    as_of: date
    forum: object
    items: tuple
    seed: dict                         # {kind: context | nearest | none, units: [...]}
    coverage: list
    gated: bool = False                # True once the precedent gate (S2) has passed it; until then discovery only
    trace: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PrecedentAbstention:
    code: str
    public_reason: str
    coverage: list
    trace: dict = field(default_factory=dict)
    nearest: tuple = ()                # PrecedentItems shown APART from any answer, as leads (never as authority)

    def __post_init__(self):
        if self.code not in ABSTENTION_CODES:
            raise ValueError(f"{self.code!r} is not a precedent abstention code")


def seed_from(law) -> dict:
    """The law join's seed from a statute retrieval's result (GroundingContext | Abstention | None)."""
    from nizam.retrieval.gate import GroundingContext
    if isinstance(law, GroundingContext):
        return dict(seed_units=[i.unit_id for i in law.items], seed_kind="context")
    nearest = getattr(law, "nearest", None) or ()
    if nearest:
        return dict(seed_units=[i.unit_id for i in nearest], seed_kind="nearest")
    return dict(seed_units=[], seed_kind="none")


def context_for(question: str, *, as_of: date, forum=None, seed_units: list[str] | None = None,
                seed_kind: str = "none", k: int = 10, repo: JudgmentRead | None = None,
                encoder=None, law_join: bool = False, gate: bool = True,
                cal: dict | None = None) -> PrecedentContext | PrecedentAbstention:
    """`law_join=False` (the default, D-173): the seed units mark which of the answer's sections each judgment cites
    and the version it read, but do not change which judgments are found. Fed to the search as a generator or a vote,
    the law join lowered precedent dev v2 in every form measured (evals/results/precedent-lawjoin-dev-*.json), so it is
    off unless a later measurement turns it on.

    `gate=True` (the default, S2, D-174): the forum veto, then the precedent gate (nizam.domain.precedent.gate) for the
    profile the search ran in. A passed context is `gated=True` and may be cited; otherwise a PrecedentAbstention with
    the nearest judgments apart. `gate=False` returns the ungated context (discovery, and the gate's own features);
    the forum veto applies either way."""
    if type(as_of) is not date:
        raise ValueError("as_of is mandatory (INV-5) and is a date")
    own = repo is None
    repo = repo or JudgmentRead()
    if own:
        repo.open()
    try:
        from nizam.domain.precedent import gate as PG
        seed = list(dict.fromkeys(seed_units or []))
        with repo.transaction() as conn:
            veto = PG.forum_veto(conn, question)
        if veto:
            return PrecedentAbstention("COURT_NOT_HELD", f"The library holds no decisions of the {veto['forum']}, so "
                                       "none can be shown as its view.", [], dict(veto=veto))
        # over-fetch: verified adverse judgments are removed below, and k must still be met where it can be
        r = search(question, as_of=as_of, forum=forum, k=k * 2, repo=repo, encoder=encoder,
                   context_provisions=(seed or None) if law_join else None)
        trace = dict(search=r.trace, mode=r.mode, seed_kind=seed_kind, seed_units=len(seed), law_join=law_join)
        if r.coverage_gap:
            return PrecedentAbstention("COURT_NOT_HELD", f"No judgment of the {r.coverage_gap['name']} is in the "
                                       "library, so none can be shown as its view.", r.coverage, trace)
        jids = [h.judgment_id for h in r.hits]
        adverse = repo.adverse_status(jids, as_of)
        notes = repo.version_notes(jids, seed, as_of) if seed else {j: {} for j in jids}
        items, excluded = [], []
        for h in r.hits:
            a = adverse.get(h.judgment_id) or {"verified": [], "awaiting_review": []}
            if a["verified"]:
                excluded.append(dict(judgment_id=h.judgment_id, because=a["verified"]))
                continue
            items.append(PrecedentItem(
                judgment_id=h.judgment_id, paragraph_id=h.paragraph_id, citation=h.citation, court=h.court,
                decided_on=h.decided_on, decided_no_later_than=h.decided_no_later_than, text=h.text,
                score=h.score, generators=tuple(h.generators), authority=h.authority,
                interprets=dict(notes.get(h.judgment_id) or {}), awaiting_review=tuple(a["awaiting_review"]),
                case_key=h.case_key, names_withheld=bool((h.privacy or {}).get("names_withheld"))))
            if len(items) >= k:
                break
        trace.update(excluded_adverse=excluded,
                     law_found=sum(1 for i in items if "law" in i.generators),
                     only_law=sum(1 for i in items if i.generators and set(i.generators) <= {"law", "binding"}))
        if not items:
            return PrecedentAbstention("NO_PRECEDENT_FOUND", PUBLIC["NO_PRECEDENT_FOUND"], r.coverage, trace)
        profile = r.trace.get("dense_space") or "lexical"                # the space the dense generator read
        trace.update(profile=profile, features=PG.features(items))
        if gate:
            d = PG.decide(trace["features"], profile, cal)
            trace["gate"] = d
            if d["decision"] != "pass":
                return PrecedentAbstention(d["code"], PUBLIC[d["code"]], r.coverage, trace,
                                           nearest=tuple(items[:PG.PRESENTED]))
        return PrecedentContext(question=question, as_of=as_of, forum=forum, items=tuple(items),
                                seed=dict(kind=seed_kind, units=seed), coverage=r.coverage, trace=trace,
                                gated=bool(gate))
    finally:
        if own:
            repo.close()
