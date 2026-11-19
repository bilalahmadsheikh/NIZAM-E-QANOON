"""D-098: the embedding slice's rules that need no model -- the stored bit order, the one-space guard, the passage text
both embedders read, the loader's refusals, the chunk worker's rebuild refusal, and the hybrid core's own guard."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_bits_are_the_sign_of_each_dimension_in_packbits_order():
    from nizam.inference.encoder import to_bits
    rng = np.random.default_rng(7)
    v = rng.standard_normal(1024).astype(np.float32)
    s = to_bits(v)
    assert len(s) == 1024 and set(s) <= {"0", "1"}
    # the GPU run stores np.packbits(v > 0); unpacking it must give the same string, first dimension first
    unpacked = np.unpackbits(np.packbits(v > 0))
    assert s == "".join(map(str, unpacked))
    assert to_bits(np.zeros(4)) == "0000"            # zero is not positive: the same rule as `emb > 0`


def _info(**kw):
    from nizam.inference.encoder import EncoderInfo
    base = dict(model="BAAI/bge-m3", revision="a" * 40, pooling="cls", query_template="{q}", max_tokens=512,
                dims=1024)
    base.update(kw)
    return EncoderInfo(**base)


def test_a_query_encoder_from_another_space_is_refused():
    from nizam.inference.encoder import check_generation
    active = {"id": 1, "model": "BAAI/bge-m3", "revision": "a" * 40, "pooling": "cls", "query_template": "{q}"}
    check_generation(active, _info())                       # the same space passes
    for change in ({"model": "intfloat/multilingual-e5-large-instruct"}, {"revision": "b" * 40},
                   {"pooling": "mean"}, {"query_template": "query: {q}"}):
        with pytest.raises(ValueError, match="different spaces"):
            check_generation(active, _info(**change))
    with pytest.raises(ValueError, match="no active embedding generation"):
        check_generation(None, _info())


def test_both_embedders_read_the_same_passage_string():
    from nizam.storage.chunking import passage_text
    assert passage_text("Pakistan Penal Code · s 302", "Whoever commits qatl-i-amd") == \
        "Pakistan Penal Code · s 302\nWhoever commits qatl-i-amd"
    src = (ROOT / "tools/kaggle/embed_inputs.py").read_text(encoding="utf-8")
    assert "passage_text(prefix, text)" in src             # the GPU export uses the shared function, not a copy
    assert "passage_text(pfx, text)" in (ROOT / "nizam/workers/chunk.py").read_text(encoding="utf-8")


def _run_loader(tmp_path, ids, bits, metrics, enc):
    out = tmp_path / "run" / "out" / "m"
    out.mkdir(parents=True)
    np.save(tmp_path / "run" / "out" / "ids.npy", np.asarray(ids, dtype=np.int64))
    np.save(out / "bits.npy", np.asarray(bits, dtype=np.uint8))
    (out / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    ed = tmp_path / "enc"
    ed.mkdir()
    (ed / "encoder.json").write_text(json.dumps(enc), encoding="utf-8")
    return subprocess.run([sys.executable, str(ROOT / "tools/load_embeddings.py"), str(tmp_path / "run"), "m",
                           str(ed)], capture_output=True, text=True, cwd=ROOT)


SAME = {"model": "BAAI/bge-m3", "revision": "a" * 40, "pooling": "cls", "query_template": "{q}"}


def test_the_loader_refuses_bits_of_the_wrong_shape(tmp_path):
    r = _run_loader(tmp_path, [1, 2], np.zeros((2, 64)), SAME, {**SAME, "max_tokens": 512})
    assert r.returncode != 0 and "expected (2, 128)" in r.stderr


def test_the_loader_refuses_an_encoder_that_is_not_the_runs_model(tmp_path):
    for key, other in (("model", "Qwen/Qwen3-Embedding-0.6B"), ("revision", "b" * 40), ("pooling", "lasttoken"),
                       ("query_template", "Instruct: x\nQuery:{q}")):
        sub = tmp_path / key
        sub.mkdir()
        r = _run_loader(sub, [1, 2], np.zeros((2, 128)), SAME, {**SAME, key: other, "max_tokens": 512})
        assert r.returncode != 0 and f"encoder {key}" in r.stderr, (key, r.stderr)


def test_a_second_matching_provision_never_lowers_a_unit():
    """docs/04 §5 unitScore = max + 0.15 x second best. With scores that can be negative, adding the raw second best
    PUNISHED units with supporting evidence (19 Nov: dense scored -Hamming, dev recall@50 0.45 vs 0.71)."""
    from types import SimpleNamespace as NS

    from nizam.retrieval.lexical import _collapse

    class FakeSession:
        def units_of(self, pids):
            return {p: NS(unit_id=p.split(":")[0]) for p in pids}
    for best, second, other in ((-300.0, -305.0, -301.0), (0.41, 0.40, 0.405), (-0.2, -0.3, -0.25)):
        # unit A: two provisions, best `best`; unit B: one provision scoring a little worse than A's best
        hits = [NS(provision_id="A:1", score=best), NS(provision_id="A:2", score=second),
                NS(provision_id="B:1", score=other)]
        ranked = _collapse(FakeSession(), hits)
        assert ranked[0][0].unit_id == "A", (best, second, other, ranked)
        assert ranked[0][1] >= best                     # never below its own best provision


def test_lexical_off_needs_a_dense_list():
    from datetime import date

    from nizam.retrieval.lexical import lexical_candidates
    from nizam.storage.lexical import Filters
    with pytest.raises(ValueError, match="needs a dense generator"):
        lexical_candidates("anything", Filters(as_of=date(2026, 11, 19)), lexical=False)


def test_without_an_encoder_hybrid_degrades_marked_lexical_only(monkeypatch, tmp_path):
    """docs/04 §9.2: embedder unavailable -> the lexical path, MARKED lexical_only; never passed off as hybrid"""
    from datetime import date

    import nizam.inference.encoder as E
    from nizam.retrieval import candidates as C
    from nizam.storage.lexical import Filters
    monkeypatch.setenv("NIZAM_ENCODER_DIR", str(tmp_path / "absent"))
    monkeypatch.setattr(E, "_ENC", None)
    calls = {}

    def fake_lexical(spec, filters, k, connect_fn=None, **kw):
        from nizam.retrieval.lexical import LexicalResult
        calls["kw"] = kw
        return LexicalResult([], spec, filters, truncated=False, trace={})
    monkeypatch.setattr(C, "lexical_candidates", fake_lexical)
    r = C.candidates("Can my landlord evict me?", Filters(as_of=date(2026, 11, 19)))
    assert r.degraded == "lexical_only" and r.trace["degraded"]["mode"] == "lexical_only"
    assert "dense_job" not in calls["kw"]                  # the fallback really is the lexical fusion
    assert "encoder.json" in r.trace["degraded"]["reason"]  # the reason names what is missing
    from nizam.retrieval.lexical import DenseUnavailable
    with pytest.raises(DenseUnavailable):                  # the dense-only ablation has nothing to fall back to
        C.dense_only("Can my landlord evict me?", Filters(as_of=date(2026, 11, 19)))


def test_only_an_unavailable_embedder_degrades(monkeypatch):
    """a bug elsewhere in retrieval is an error, not a quiet lexical_only answer"""
    from concurrent.futures import Future
    from datetime import date

    from nizam.retrieval import candidates as C
    from nizam.storage.lexical import Filters
    monkeypatch.setattr(C, "_load_encoder", lambda: type("E", (), {"info": None})())

    def ok_job(*a, **kw):
        f = Future()
        f.set_result(([], {"dense_mode": "hnsw", "encode": 1}))
        return f
    monkeypatch.setattr(C._POOL, "submit", ok_job)

    def broken(*a, **kw):
        raise ValueError("a retrieval bug")
    monkeypatch.setattr(C, "lexical_candidates", broken)
    with pytest.raises(ValueError, match="a retrieval bug"):
        C.candidates("Can my landlord evict me?", Filters(as_of=date(2026, 11, 19)))
