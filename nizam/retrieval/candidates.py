"""Hybrid candidates (D-098; docs/04 §4, §5, R1): the fused lexical units and the dense units, fused by RRF across
generators.

    from nizam.retrieval.candidates import candidates
    r = candidates("Can my husband marry again without my permission?", Filters(as_of=date.today()), k=50)

The two generators run side by side (docs/04 §4: parallel candidate generators). The dense job -- encode the question
with the shared inference worker's query encoder (nizam.inference.encoder: the active embedding generation's model,
int8 ONNX on the CPU), then nizam.retrieval.lexical.dense_units on its own connection -- starts first, on a worker
thread; the lexical generator runs meanwhile on the request's thread, and fusion waits for the dense job only when
the lexical windows are done. onnxruntime and the database driver release the GIL, so the overlap is real (measured,
D-098). The question is encoded in its natural form, not frame-stripped: embedding models are trained on questions as
people write them. Everything after the generators -- citations first, RRF k = 60 across generators, the INV-5 gate
on the top units -- is nizam.retrieval.lexical's core.

`dense=False` gives the lexical fusion alone (what lexical_candidates returns).

Degradation (docs/04 §9.2): if the embedder cannot run -- no encoder installed, no runtime, no active generation, or
an encoder that is not the active generation's model (check_generation) -- the result is the lexical fusion, MARKED
`degraded = "lexical_only"` with the reason in the trace (and a warning logged), never a lexical result passed off as
hybrid. Only DenseUnavailable (and the encoder failing to load) degrades; any other error is an error. The gate's
threshold does not move for it (docs/04 §9.2: "normal gate threshold remains").
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from nizam.retrieval.lexical import DenseUnavailable, LexicalResult, dense_units, effective_filters, lexical_candidates
from nizam.retrieval.query import QuerySpec, parse
from nizam.storage.lexical import Filters

log = logging.getLogger(__name__)
# dense jobs of concurrent requests; each holds one database connection while it runs (~0.3 s)
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nizam-dense")


def candidates(question, filters: Filters, k: int = 50, dense: bool = True, connect_fn=None) -> LexicalResult:
    spec = question if isinstance(question, QuerySpec) else parse(question)
    if not dense:
        return lexical_candidates(spec, filters, k, connect_fn)
    return _with_dense(spec, filters, k, connect_fn, lexical=True)


def dense_only(question, filters: Filters, k: int = 50, connect_fn=None) -> LexicalResult:
    """the dense generator alone, collapsed to units and through the same INV-5 gate: the ablation row docs/10 asks
    for (BM25 only -> dense only -> hybrid). Not a serving path."""
    spec = question if isinstance(question, QuerySpec) else parse(question)
    return _with_dense(spec, filters, k, connect_fn, lexical=False)


def _dense_job(text: str, filters: Filters, enc, connect_fn):
    t = time.perf_counter()
    try:
        bits = enc.bits(text)
    except (OSError, ValueError, ImportError) as exc:
        raise DenseUnavailable(f"{type(exc).__name__}: {exc}") from exc
    encode_ms = round((time.perf_counter() - t) * 1000)
    units, tr = dense_units(bits, filters, enc.info, connect_fn)
    return units, tr | {"encode": encode_ms}


def _load_encoder():
    try:
        from nizam.inference.encoder import encoder
        return encoder()                     # loaded once per process; files missing -> OSError, bad json -> ValueError
    except (OSError, ImportError, ValueError) as exc:
        raise DenseUnavailable(f"{type(exc).__name__}: {exc}") from exc


def _with_dense(spec: QuerySpec, filters: Filters, k: int, connect_fn, lexical: bool) -> LexicalResult:
    try:
        enc = _load_encoder()
        job = _POOL.submit(_dense_job, spec.text, effective_filters(spec, filters), enc, connect_fn)
        r = lexical_candidates(spec, filters, k, connect_fn, dense_job=job, lexical=lexical)
    except DenseUnavailable as exc:                    # no model files / no runtime / not the active space
        if not lexical:
            raise                                      # the dense-only ablation has nothing to fall back to
        log.warning("dense generator unavailable, serving lexical_only: %s", exc)
        r = lexical_candidates(spec, filters, k, connect_fn)
        r.degraded = "lexical_only"
        r.trace["degraded"] = {"mode": "lexical_only", "reason": f"{type(exc).__name__}: {exc}"}
        return r
    r.trace["encode_ms"] = r.trace["dense_stage_ms"]["encode"]
    r.trace["encoder"] = {"model": enc.info.model, "revision": enc.info.revision}
    return r
