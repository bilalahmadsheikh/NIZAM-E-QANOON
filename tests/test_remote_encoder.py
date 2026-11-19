"""nizam.inference.remote (D-099): the GPU encoder client refuses a service that is not the corpus run's space."""
from __future__ import annotations

import json

import numpy as np
import pytest

from nizam.inference.remote import RemoteEncoder

DIMS = 64


def _bundle(tmp_path, template="Instruct: t\nQuery:{q}"):
    rng = np.random.default_rng(1)
    ref = rng.standard_normal((4, DIMS)).astype(np.float32)
    qs = ["what is bail", "khula kya hai", "طلاق", "rent increase"]
    (tmp_path / "encoder.json").write_text(json.dumps({
        "model": "Qwen/Qwen3-Embedding-8B", "revision": "abc", "pooling": "lasttoken", "query_template": template,
        "max_tokens": 512, "dims": DIMS}), encoding="utf-8")
    np.save(tmp_path / "reference_q.npy", ref)
    (tmp_path / "reference_questions.json").write_text(json.dumps(qs, ensure_ascii=False), encoding="utf-8")
    return ref, qs


def _server(table, seen=None, scale=3.0):
    """a fake /v1/embeddings: the vector for each prefixed text from `table` (unnormalised, as servers may send)"""
    def post(payload):
        text = payload["input"][0]
        if seen is not None:
            seen.append(payload)
        return {"data": [{"embedding": (table[text] * scale).tolist()}]}
    return post


def test_matching_service_is_accepted_and_applies_the_template(tmp_path):
    ref, qs = _bundle(tmp_path)
    table = {f"Instruct: t\nQuery:{q}": r for q, r in zip(qs, ref)}
    seen = []
    enc = RemoteEncoder(tmp_path, url="http://gpu:8000/", post=_server(table, seen))
    v = enc.embed("  what   is bail ")                         # whitespace folded before the template
    assert np.isclose(np.linalg.norm(v), 1.0)
    assert np.allclose(v, ref[0] / np.linalg.norm(ref[0]), atol=1e-6)
    assert seen[-1]["input"] == ["Instruct: t\nQuery:what is bail"]
    assert seen[-1]["model"] == "Qwen/Qwen3-Embedding-8B"
    assert len(enc.bits("what is bail", 16)) == 16
    assert enc.bits("what is bail", 16) == "".join("1" if x > 0 else "0" for x in ref[0][:16])


def test_a_service_from_another_space_is_refused(tmp_path):
    ref, qs = _bundle(tmp_path)
    rng = np.random.default_rng(9)
    table = {f"Instruct: t\nQuery:{q}": rng.standard_normal(DIMS) for q in qs}    # another model's vectors
    with pytest.raises(ValueError, match="does not reproduce"):
        RemoteEncoder(tmp_path, url="http://gpu", post=_server(table))


def test_wrong_width_and_missing_url(tmp_path, monkeypatch):
    ref, qs = _bundle(tmp_path)
    short = {f"Instruct: t\nQuery:{q}": r[:10] for q, r in zip(qs, ref)}
    with pytest.raises(ValueError, match="dimensions"):
        RemoteEncoder(tmp_path, url="http://gpu", post=_server(short))
    monkeypatch.delenv("NIZAM_GPU_ENCODER_URL", raising=False)
    with pytest.raises(OSError, match="NIZAM_GPU_ENCODER_URL"):
        RemoteEncoder(tmp_path)


def test_network_failure_is_oserror(tmp_path):
    _bundle(tmp_path)
    with pytest.raises(OSError):                      # nothing listens on port 9 of localhost
        RemoteEncoder(tmp_path, url="http://127.0.0.1:9", timeout=0.5)
