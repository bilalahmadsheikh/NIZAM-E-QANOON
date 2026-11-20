"""The cross-encoder stage (D-101; docs/04 §5.1, §9): the gated candidates, reordered by relevance to the question.

    from nizam.retrieval.rerank import ranked
    r = ranked("Can my landlord evict me for not paying rent?", Filters(as_of=date.today()), k=50)
    r.candidates -> UnitCandidate(..., rank = reranked position, rerank_score = the model's logit)

What it does, after nizam.retrieval.candidates has produced k gated units:
  1. reads each unit's passage from L2 (Session.unit_passages: the unit's prefix and its OPERATIVE words at the
     request's as_of and territory -- INV-5 holds for what the model reads, not only for what is returned);
  2. scores (question, passage) with the shared inference worker's reranker (nizam.inference.reranker) -- the first
     `depth` units, passages cut at `chars`, both per device (RERANK_INPUT); deeper units keep their fused order;
  3. keeps the units the citation fast path resolved first, in their order (a cited section is the user's own
     identifier, docs/04 §2.2), and orders the rest by score, ties in fused order;
  4. records model, revision, device, every unit's score and the stage times in the trace (INV-3, docs/04 §9.3).

Profiles follow the dense ones (D-099): NIZAM_RERANK_PROFILE = gpu | cpu | auto | off (default auto: gpu when
NIZAM_GPU_RERANKER_URL is set, else cpu). The slate each profile reranks is the bake-off's choice (SLATE_WINDOWS).

Degradation (docs/04 §9.2), each MARKED in `degraded` and the trace, never passed off as the better path:
  * the gpu reranker cannot load or answer -> the cpu reranker, "rerank_cpu";
  * no reranker at all (or profile off) -> the fused order, "unreranked". docs/04: the gate then needs its own
    degraded-mode calibration, and abstains until that has shipped -- the gate reads this mark.
Only a reranker failing to load or answer (OSError, ValueError, ImportError) degrades; any other error is an error.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import replace

from nizam.retrieval.candidates import candidates, profile as dense_profile
from nizam.retrieval.lexical import LexicalResult
from nizam.retrieval.query import QuerySpec, parse
from nizam.storage import unit_search
from nizam.storage.lexical import Filters

log = logging.getLogger(__name__)

# which slate each profile reranks (evals/results/rerank-rule-2026-11-20.json, rule 5): True = the hybrid (citations,
# RRF of the BM25 windows and dense); False = citations then dense, no BM25 windows. Set from the dev bake-off, D-101.
SLATE_WINDOWS = {"gpu": False, "cpu": True}

# what each reranker device reads: passage characters (unit_passages' max_chars) and depth (how many of the fused
# slate's first units are scored; the rest keep their fused order below them). gpu: the bake-off's 1,600 x 50
# (Qwen3-Reranker-8B). cpu: the latency addendum's choice (evals/results/rerank-rule-addendum-cpu-2026-11-20.json;
# int8 mMiniLM at 800 x 10, dev p50 589 ms on the 6-core build host, where 1,600 x 50 took 5 s), D-101.
RERANK_INPUT = {"gpu": (1600, 50), "cpu": (800, 10)}


class RerankUnavailable(Exception):
    """no reranker can score: its files, runtime or service are missing, or it is not the pinned model"""


def rerank_profile() -> str:
    p = os.environ.get("NIZAM_RERANK_PROFILE", "auto").strip().lower()
    if p == "auto":
        return "gpu" if os.environ.get("NIZAM_GPU_RERANKER_URL") else "cpu"
    if p not in ("gpu", "cpu", "off"):
        raise ValueError(f"NIZAM_RERANK_PROFILE must be gpu, cpu, auto or off, not {p!r}")
    return p


def _load(device: str):
    try:
        from nizam.inference.reranker import reranker
        return reranker(device)
    except (OSError, ImportError, ValueError) as exc:
        raise RerankUnavailable(f"{device} reranker: {type(exc).__name__}: {exc}") from exc


def _mark(r: LexicalResult, mode: str, reason: str) -> None:
    r.degraded = f"{r.degraded}+{mode}" if r.degraded else mode
    r.trace.setdefault("degraded_stages", []).append({"mode": mode, "reason": reason})


def rerank(r: LexicalResult, reranker=None, connect_fn=None) -> LexicalResult:
    """`r` reordered by the reranker (injected, or the profile's), marked if it could not run"""
    if not r.candidates:
        return r
    t0 = time.perf_counter()
    rr, fell_back = reranker, None
    if rr is None:
        prof = rerank_profile()
        if prof == "off":
            _mark(r, "unreranked", "NIZAM_RERANK_PROFILE=off")
            return r
        try:
            rr = _load(prof)
        except RerankUnavailable as exc:
            if prof != "gpu":
                _mark(r, "unreranked", str(exc))
                return r
            fell_back = str(exc)
            try:
                rr = _load("cpu")
            except RerankUnavailable as exc2:
                _mark(r, "unreranked", f"{exc}; {exc2}")
                return r
    info = rr.info
    chars, depth = RERANK_INPUT[info.device]
    head, tail = r.candidates[:depth], r.candidates[depth:]
    kwargs = {"connect_fn": connect_fn} if connect_fn else {}
    with unit_search.session(r.filters, **kwargs) as s:
        texts = s.unit_passages([(c.unit_id, c.version_id) for c in head], max_chars=chars)
    t1 = time.perf_counter()
    try:
        scores = rr.score(r.spec.text, [texts[c.unit_id] for c in head])
    except (OSError, ValueError) as exc:                  # the service went away mid-request, or answered nonsense
        _mark(r, "unreranked", f"{type(exc).__name__}: {exc}")
        return r
    t2 = time.perf_counter()
    scored = [replace(c, rerank_score=round(float(s), 6)) for c, s in zip(head, scores)]
    cited = [c for c in scored if c.via_citation]
    rest = sorted((c for c in scored if not c.via_citation), key=lambda c: (-c.rerank_score, c.rank))
    # units below the depth were not scored: they keep their fused order, after every scored unit, rerank_score None
    r.candidates = [replace(c, rank=i) for i, c in enumerate(cited + rest + tail, 1)]
    r.trace["rerank"] = {"model": info.model, "revision": info.revision, "kind": info.kind, "device": info.device,
                         "passage_chars": chars, "depth": depth, "scored": len(head),
                         "passages_ms": round((t1 - t0) * 1000), "score_ms": round((t2 - t1) * 1000),
                         "scores": {c.unit_id: c.rerank_score for c in scored}}
    if fell_back:
        _mark(r, "rerank_cpu", fell_back)
    return r


def ranked(question, filters: Filters, k: int = 50, connect_fn=None, encoder=None, reranker=None,
           windows: bool | None = None) -> LexicalResult:
    """L3's candidates, reranked: the slate the profile's bake-off chose (SLATE_WINDOWS), then the cross-encoder.
    `encoder` / `reranker` inject replayed GPU outputs for evaluation (evals/precomputed_encoder.py,
    evals/precomputed_reranker.py); `windows` overrides the slate (the bake-off measures both)."""
    spec = question if isinstance(question, QuerySpec) else parse(question)
    if windows is None:
        windows = SLATE_WINDOWS["gpu" if (encoder is not None or dense_profile() == "gpu") else "cpu"]
    r = candidates(spec, filters, k, connect_fn=connect_fn, encoder=encoder, windows=windows)
    if r.degraded == "dense_cpu" and windows != SLATE_WINDOWS["cpu"]:
        # the gpu space could not be searched and bge-m3's was: rebuild the slate the CPU profile chose, still marked
        reason = r.trace.get("degraded")
        r = candidates(spec, filters, k, connect_fn=connect_fn, windows=SLATE_WINDOWS["cpu"])
        r.degraded, r.trace["degraded"] = "dense_cpu", reason
    return rerank(r, reranker=reranker, connect_fn=connect_fn)
