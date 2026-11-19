"""Hybrid candidates (D-098, D-099; docs/04 §4, §5, R1): the fused lexical units and the dense units, fused by RRF
across generators.

    from nizam.retrieval.candidates import candidates
    r = candidates("Can my husband marry again without my permission?", Filters(as_of=date.today()), k=50)

The two generators run side by side (docs/04 §4: parallel candidate generators). The dense job -- encode the question
with the shared inference worker, then nizam.retrieval.lexical.dense_units on its own connection -- starts first, on a
worker thread; the lexical generator runs meanwhile on the request's thread, and fusion waits for the dense job only
when the lexical windows are done. The encoders and the database driver release the GIL, so the overlap is real
(measured, D-098). The question is encoded in its natural form, not frame-stripped. Everything after the generators
-- citations first, RRF k = 60 across generators, the INV-5 gate on the top units -- is nizam.retrieval.lexical's core.

Two embedding generations can be active at once, one per encoder device (D-099):
  gpu  Qwen3-Embedding-8B; the question is encoded by the GPU host's service (nizam.inference.remote)
  cpu  bge-m3; int8 ONNX in this process (nizam.inference.encoder) -- any host, no GPU
The profile is NIZAM_DENSE_PROFILE = gpu | cpu | auto (default auto: gpu when NIZAM_GPU_ENCODER_URL is set). The
encoder decides which space is searched (unit_search.generation_for), so the two are never mixed.

Degradation (docs/04 §9.2), each MARKED, never passed off as the better path:
  * the gpu profile cannot encode (service down, wrong model, its generation not loaded) -> the cpu generation's
    dense units, `degraded = "dense_cpu"`, reason in the trace;
  * no dense generator at all -> the lexical fusion, `degraded = "lexical_only"`.
Only DenseUnavailable (and an encoder failing to load) degrades; any other error is an error. The gate's threshold
does not move for it.

`dense=False` gives the lexical fusion alone. `encoder=` injects an encoder (evaluation replays GPU-made question
vectors through evals/precomputed_encoder.py); an injected encoder never falls back.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

from nizam.retrieval.lexical import DenseUnavailable, LexicalResult, dense_units, effective_filters, lexical_candidates
from nizam.retrieval.query import QuerySpec, parse
from nizam.storage.lexical import Filters

log = logging.getLogger(__name__)
# dense jobs of concurrent requests; each holds one database connection while it runs (~0.3 s)
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nizam-dense")


def candidates(question, filters: Filters, k: int = 50, dense: bool = True, connect_fn=None,
               encoder=None) -> LexicalResult:
    spec = question if isinstance(question, QuerySpec) else parse(question)
    if not dense:
        return lexical_candidates(spec, filters, k, connect_fn)
    return _with_dense(spec, filters, k, connect_fn, lexical=True, encoder=encoder)


def dense_only(question, filters: Filters, k: int = 50, connect_fn=None, encoder=None) -> LexicalResult:
    """the dense generator alone, collapsed to units and through the same INV-5 gate: the ablation row docs/10 asks
    for (BM25 only -> dense only -> hybrid). Not a serving path."""
    spec = question if isinstance(question, QuerySpec) else parse(question)
    return _with_dense(spec, filters, k, connect_fn, lexical=False, encoder=encoder)


def profile() -> str:
    p = os.environ.get("NIZAM_DENSE_PROFILE", "auto").strip().lower()
    if p == "auto":
        return "gpu" if os.environ.get("NIZAM_GPU_ENCODER_URL") else "cpu"
    if p not in ("gpu", "cpu"):
        raise ValueError(f"NIZAM_DENSE_PROFILE must be gpu, cpu or auto, not {p!r}")
    return p


def _load_encoder(device: str = "cpu"):
    try:
        if device == "gpu":
            from nizam.inference.remote import remote_encoder
            return remote_encoder()          # validated against the corpus run's question vectors on first use
        from nizam.inference.encoder import encoder
        return encoder()                     # loaded once per process; files missing -> OSError, bad json -> ValueError
    except (OSError, ImportError, ValueError) as exc:
        raise DenseUnavailable(f"{device} encoder: {type(exc).__name__}: {exc}") from exc


def _run_dense(text: str, filters: Filters, enc, connect_fn):
    t = time.perf_counter()
    try:
        qvec = enc.embed(text)
    except (OSError, ValueError, ImportError) as exc:
        raise DenseUnavailable(f"{type(exc).__name__}: {exc}") from exc
    encode_ms = round((time.perf_counter() - t) * 1000)
    units, tr = dense_units(qvec, filters, enc.info, connect_fn)
    return units, tr | {"encode": encode_ms, "encoder": {"model": enc.info.model, "revision": enc.info.revision}}


def _dense_job(text: str, filters: Filters, enc, connect_fn, fallback=None):
    """the dense generator; `fallback` (a loader of the cpu encoder) runs if the gpu one cannot"""
    try:
        return _run_dense(text, filters, enc, connect_fn)
    except DenseUnavailable as exc:
        if fallback is None:
            raise
        log.warning("gpu dense generator unavailable, using the cpu generation: %s", exc)
        units, tr = _run_dense(text, filters, fallback(), connect_fn)
        return units, tr | {"fell_back": f"{enc.info.model}: {exc}"}


def _with_dense(spec: QuerySpec, filters: Filters, k: int, connect_fn, lexical: bool, encoder=None) -> LexicalResult:
    fell_back = None
    try:
        if encoder is not None:
            enc, fallback = encoder, None
        elif profile() == "gpu":
            try:
                enc, fallback = _load_encoder("gpu"), (lambda: _load_encoder("cpu"))
            except DenseUnavailable as exc:
                log.warning("gpu encoder unavailable, using the cpu generation: %s", exc)
                fell_back, enc, fallback = str(exc), _load_encoder("cpu"), None
        else:
            enc, fallback = _load_encoder("cpu"), None
        job = _POOL.submit(_dense_job, spec.text, effective_filters(spec, filters), enc, connect_fn, fallback)
        r = lexical_candidates(spec, filters, k, connect_fn, dense_job=job, lexical=lexical)
    except DenseUnavailable as exc:                    # no model files / no runtime / not the active space
        if not lexical:
            raise                                      # the dense-only ablation has nothing to fall back to
        log.warning("dense generator unavailable, serving lexical_only: %s", exc)
        r = lexical_candidates(spec, filters, k, connect_fn)
        r.degraded = "lexical_only"
        r.trace["degraded"] = {"mode": "lexical_only", "reason": f"{type(exc).__name__}: {exc}"}
        return r
    stage = r.trace["dense_stage_ms"]
    r.trace["encode_ms"] = stage["encode"]
    r.trace["encoder"] = stage.pop("encoder")
    fell_back = fell_back or r.trace.pop("dense_fell_back", None)
    if fell_back:
        r.degraded = "dense_cpu"
        r.trace["degraded"] = {"mode": "dense_cpu", "reason": fell_back}
    return r
