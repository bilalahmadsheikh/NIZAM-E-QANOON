"""D-099: two active embedding generations -- the encoder picks the space; a GPU failure falls back to the CPU
generation MARKED dense_cpu; no dense generator at all is lexical_only; an injected encoder never falls back."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace as NS

import numpy as np
import pytest

from nizam.inference.encoder import EncoderInfo
from nizam.retrieval import candidates as C
from nizam.retrieval.lexical import DenseUnavailable, LexicalResult
from nizam.storage.lexical import Filters

F = Filters(as_of=date(2026, 11, 19))
GPU = EncoderInfo("Qwen/Qwen3-Embedding-8B", "1d8ad4ca" + "0" * 32, "lasttoken", "Instruct: t\nQuery:{q}", 512, 4096)
CPU = EncoderInfo("BAAI/bge-m3", "5617a9f6" + "0" * 32, "cls", "{q}", 512, 1024)


class Enc:
    def __init__(self, info, fail=False):
        self.info, self.fail = info, fail

    def embed(self, q):
        if self.fail:
            raise OSError("connection refused")
        return np.ones(self.info.dims, dtype=np.float32) / np.sqrt(self.info.dims)


@pytest.fixture
def wired(monkeypatch):
    """lexical core and dense_units faked: records which encoder's space the dense generator was asked for"""
    seen = {}

    def fake_dense_units(qvec, filters, info, connect_fn=None):
        seen.setdefault("spaces", []).append(info.model)
        return [], {"dense_mode": "hnsw", "dense_window": 1, "dense_units_of": 1,
                    "generation": 2 if info.model.startswith("Qwen") else 1}

    def fake_lexical(spec, filters, k, connect_fn=None, dense_job=None, lexical=True):
        trace = {}
        if dense_job is not None:
            _units, dtrace = dense_job.result()
            trace["dense_mode"] = dtrace.pop("dense_mode")
            trace["dense_generation"] = dtrace.pop("generation", None)
            if "fell_back" in dtrace:
                trace["dense_fell_back"] = dtrace.pop("fell_back")
            trace["dense_stage_ms"] = dtrace
        return LexicalResult([], spec, filters, truncated=False, trace=trace)
    monkeypatch.setattr(C, "dense_units", fake_dense_units)
    monkeypatch.setattr(C, "lexical_candidates", fake_lexical)
    return seen


def test_profile_from_environment(monkeypatch):
    monkeypatch.delenv("NIZAM_DENSE_PROFILE", raising=False)
    monkeypatch.delenv("NIZAM_GPU_ENCODER_URL", raising=False)
    assert C.profile() == "cpu"
    monkeypatch.setenv("NIZAM_GPU_ENCODER_URL", "http://gpu:8000")
    assert C.profile() == "gpu"
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "cpu")
    assert C.profile() == "cpu"
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "fastest")
    with pytest.raises(ValueError):
        C.profile()


def test_gpu_profile_searches_the_gpu_space(monkeypatch, wired):
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "gpu")
    monkeypatch.setattr(C, "_load_encoder", lambda device="cpu": Enc(GPU if device == "gpu" else CPU))
    r = C.candidates("Can my landlord evict me?", F)
    assert wired["spaces"] == ["Qwen/Qwen3-Embedding-8B"]
    assert r.degraded is None and r.trace["dense_generation"] == 2
    assert r.trace["encoder"]["model"] == "Qwen/Qwen3-Embedding-8B"


def test_gpu_failing_to_encode_falls_back_to_cpu_marked(monkeypatch, wired):
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "gpu")
    monkeypatch.setattr(C, "_load_encoder", lambda device="cpu": Enc(GPU, fail=True) if device == "gpu" else Enc(CPU))
    r = C.candidates("Can my landlord evict me?", F)
    assert wired["spaces"] == ["BAAI/bge-m3"]                       # the GPU never reached the database
    assert r.degraded == "dense_cpu" and "connection refused" in r.trace["degraded"]["reason"]
    assert r.trace["dense_generation"] == 1


def test_gpu_failing_to_load_falls_back_to_cpu_marked(monkeypatch, wired):
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "gpu")

    def load(device="cpu"):
        if device == "gpu":
            raise DenseUnavailable("gpu encoder: OSError: NIZAM_GPU_ENCODER_URL is not set")
        return Enc(CPU)
    monkeypatch.setattr(C, "_load_encoder", load)
    r = C.candidates("Can my landlord evict me?", F)
    assert r.degraded == "dense_cpu" and "NIZAM_GPU_ENCODER_URL" in r.trace["degraded"]["reason"]


def test_both_failing_is_lexical_only(monkeypatch, wired):
    monkeypatch.setenv("NIZAM_DENSE_PROFILE", "gpu")
    monkeypatch.setattr(C, "_load_encoder", lambda device="cpu": Enc(GPU if device == "gpu" else CPU, fail=True))
    r = C.candidates("Can my landlord evict me?", F)
    assert r.degraded == "lexical_only"


def test_an_injected_encoder_never_falls_back(monkeypatch, wired):
    monkeypatch.setattr(C, "_load_encoder", lambda device="cpu": pytest.fail("no loader may run"))
    r = C.candidates("q", F, encoder=Enc(GPU))
    assert r.degraded is None and wired["spaces"] == ["Qwen/Qwen3-Embedding-8B"]
    with pytest.raises(DenseUnavailable):
        C.dense_only("q", F, encoder=Enc(GPU, fail=True))


def test_generation_for_matches_the_encoders_space():
    from nizam.storage.unit_search import Session

    class Cur:
        def execute(self, *a):
            pass

        def fetchall(self):
            return [(1, CPU.model, CPU.revision, CPU.pooling, CPU.query_template, 1024, "chunk.embedding", None),
                    (2, GPU.model, GPU.revision, GPU.pooling, GPU.query_template, 2048, "chunk_embedding_gpu", 1024)]
    s = Session(Cur(), NS(jurisdictions=None, territory=None))
    assert s.generation_for(GPU)["id"] == 2 and s.generation_for(CPU)["id"] == 1
    assert s.generation_for(EncoderInfo(GPU.model, "other", GPU.pooling, GPU.query_template, 512, 4096)) is None
    assert s.generation_for(EncoderInfo(CPU.model, CPU.revision, CPU.pooling, "query: {q}", 512, 1024)) is None
