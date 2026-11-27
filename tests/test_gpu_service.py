"""The GPU inference service's HTTP contract (D-178), checked through the REAL clients (RemoteEncoder,
RemoteReranker) against fake backends: the clients' own same-space checks must pass for a faithful service and refuse
a wrong one. The 8B models themselves are proved on a GPU (tools/kaggle/gpu_service_kernel.py), not here."""
from __future__ import annotations

import json

import numpy as np
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from nizam.inference.gpu_service import create_app  # noqa: E402
from nizam.inference.remote import RemoteEncoder  # noqa: E402
from nizam.inference.reranker import RemoteReranker, qwen_document  # noqa: E402

TEMPLATE = "Instruct: Given a question about Pakistani law, retrieve the statutory provisions that answer it\nQuery:{q}"
QUESTIONS = ["Can my landlord evict me?", "Is theft bailable?", "How do I register a company?"]


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


class FakeEncoder:
    """returns, for a templated reference question, its reference vector (a faithful service); else noise"""

    def __init__(self, ref: dict, wrong: bool = False):
        self.ref, self.wrong = ref, wrong
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        rng = np.random.default_rng(0)
        return [(_unit(rng.normal(size=16)) if self.wrong or t not in self.ref else self.ref[t]).tolist() for t in texts]

    def info(self):
        return {"model": "fake/Qwen3-Embedding-8B", "revision": "r", "precision": "nf4", "dims": 16}


class FakeReranker:
    def __init__(self, scores: dict, reverse: bool = False, precision: str = "fp16"):
        self.scores, self.reverse, self.precision = scores, reverse, precision

    def score(self, texts):
        return [(-1 if self.reverse else 1) * self.scores.get(t, 0.0) for t in texts]

    def info(self):
        return {"model": "fake/Qwen3-Reranker-8B", "revision": "r", "kind": "qwen", "precision": self.precision}


@pytest.fixture()
def encoder_bundle(tmp_path):
    rng = np.random.default_rng(42)
    ref = np.stack([_unit(rng.normal(size=16)) for _ in QUESTIONS])
    (tmp_path / "encoder.json").write_text(json.dumps({
        "model": "fake/Qwen3-Embedding-8B", "revision": "r", "pooling": "lasttoken", "query_template": TEMPLATE,
        "max_tokens": 512, "dims": 16, "precision": "nf4"}), encoding="utf-8")
    np.save(tmp_path / "reference_q.npy", ref)
    (tmp_path / "reference_questions.json").write_text(json.dumps(QUESTIONS), encoding="utf-8")
    by_text = {TEMPLATE.format(q=q): ref[i] for i, q in enumerate(QUESTIONS)}
    return tmp_path, by_text


def _post_to(client, path=None):
    def post(*args):
        p, payload = (path, args[0]) if path else args
        r = client.post(p, json=payload)
        if r.status_code != 200:
            raise OSError(f"HTTP {r.status_code}: {r.text}")
        return r.json()
    return post


def test_a_faithful_encoder_service_passes_the_clients_same_space_check(encoder_bundle):
    d, by_text = encoder_bundle
    fake = FakeEncoder(by_text)
    client = TestClient(create_app(encoder=fake))
    enc = RemoteEncoder(directory=d, url="http://svc", post=_post_to(client, "/v1/embeddings"))
    v = enc.embed(QUESTIONS[1])
    assert v.shape == (16,) and abs(float(np.linalg.norm(v)) - 1) < 1e-5
    assert fake.calls[0] == [TEMPLATE.format(q=QUESTIONS[0])]        # the client applies the template, not the service
    assert len(enc.bits(QUESTIONS[0])) == 16


def test_a_service_running_another_model_is_refused(encoder_bundle):
    d, by_text = encoder_bundle
    client = TestClient(create_app(encoder=FakeEncoder(by_text, wrong=True)))
    with pytest.raises(ValueError, match="does not reproduce"):
        RemoteEncoder(directory=d, url="http://svc", post=_post_to(client, "/v1/embeddings"))


def test_rerank_returns_every_index_best_first_and_the_client_maps_them_back(tmp_path):
    info = {"model": "Qwen/Qwen3-Reranker-8B", "revision": "r", "kind": "qwen", "max_tokens": 1024,
            "instruction": "Given a question about Pakistani law, retrieve the statutory provisions that answer it",
            "api": "tei"}
    (tmp_path / "reranker.json").write_text(json.dumps(info), encoding="utf-8")
    from nizam.inference.reranker import RerankerInfo
    ri = RerankerInfo(info["model"], info["revision"], "qwen", 1024, info["instruction"], "gpu")
    q, ps = "Is theft bailable?", ["s.379 PPC theft", "s.302 PPC murder", "Schedule II CrPC bailable column"]
    truth = [2.5, -1.0, 4.0]
    (tmp_path / "reference.json").write_text(json.dumps({"source": "test", "groups": [
        {"question": q, "passages": ps, "scores": truth}]}), encoding="utf-8")
    good = {qwen_document(ri, q, p): s for p, s in zip(ps, truth)}
    client = TestClient(create_app(reranker=FakeReranker(good)))
    rr = RemoteReranker(directory=tmp_path, url="http://svc", post=_post_to(client))
    assert rr.score(q, ps) == pytest.approx(truth)                    # order restored from the indexes
    raw = client.post("/rerank", json={"query": q, "texts": list(good), "raw_scores": True}).json()
    assert [r["score"] for r in raw] == sorted((r["score"] for r in raw), reverse=True)
    bad = TestClient(create_app(reranker=FakeReranker(good, reverse=True)))
    with pytest.raises(ValueError, match="does not rank"):
        RemoteReranker(directory=tmp_path, url="http://svc", post=_post_to(bad))
    # D-182: a 4-bit service ranks like fp16, so its /health is what tells an fp16 bundle it is the wrong one
    nf4 = TestClient(create_app(reranker=FakeReranker(good, precision="nf4")))
    with pytest.raises(ValueError, match="runs nf4"):
        RemoteReranker(directory=tmp_path, url="http://svc", post=_post_to(nf4), get=lambda p: nf4.get(p).json())
    (tmp_path / "reranker.json").write_text(json.dumps({**info, "precision": "nf4"}), encoding="utf-8")
    rr = RemoteReranker(directory=tmp_path, url="http://svc", post=_post_to(nf4), get=lambda p: nf4.get(p).json())
    assert rr.info.precision == "nf4"


def test_a_missing_model_is_a_503_and_limits_hold(encoder_bundle):
    d, by_text = encoder_bundle
    client = TestClient(create_app(encoder=FakeEncoder(by_text)))
    assert client.post("/rerank", json={"query": "q", "texts": ["a"]}).status_code == 503
    assert client.post("/v1/embeddings", json={"input": []}).status_code == 422
    assert client.post("/v1/embeddings", json={"input": ["x"] * 300}).status_code == 422
    h = client.get("/health").json()
    assert h["encoder"]["precision"] == "nf4" and h["reranker"] is None
