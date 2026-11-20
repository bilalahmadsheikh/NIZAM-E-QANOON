"""The cross-encoder stage (nizam.retrieval.rerank, D-101) and the GPU reranker client (nizam.inference.reranker):
cited units are never moved, the rest follow the score with ties in fused order, every score lands in the trace, and
each way a reranker can fail is MARKED -- the GPU falling back to the CPU, or the fused order served unreranked --
never passed off as reranked (docs/04 §9.2). The GPU client refuses a service that does not rank the bake-off's
reference pairs as the pinned model did."""
import json
from contextlib import contextmanager
from datetime import date

import pytest

import nizam.retrieval.rerank as R
from nizam.inference.reranker import RemoteReranker, RerankerInfo, spearman
from nizam.retrieval.lexical import LexicalResult, UnitCandidate
from nizam.retrieval.query import parse
from nizam.storage.lexical import Filters

INFO = RerankerInfo("m/x", "abc123", "cls", 512, "", "cpu")


def _result(cited=(), n=5):
    c = [UnitCandidate(f"u{i}", f"v{i}", "i", 1.0 / i, i, {}, f"u{i}" in cited) for i in range(1, n + 1)]
    return LexicalResult(c, parse("Can my landlord evict me?"), Filters(as_of=date(2026, 11, 20)), False, {})


ASKED = []


@pytest.fixture(autouse=True)
def passages(monkeypatch):
    ASKED.clear()

    class S:
        def unit_passages(self, cands, max_chars):
            ASKED.append((len(cands), max_chars))
            return {u: f"passage of {u}" for u, _v in cands}

    @contextmanager
    def session(filters, **kw):
        yield S()
    monkeypatch.setattr(R.unit_search, "session", session)


class Fixed:
    info = INFO

    def __init__(self, scores):
        self.scores = scores

    def score(self, q, passages):
        assert all(p.startswith("passage of ") for p in passages)
        return [self.scores[p.split()[-1]] for p in passages]


def test_the_rest_follow_the_score_and_cited_units_stay_first():
    r = R.rerank(_result(cited={"u4"}), reranker=Fixed({"u1": 0.1, "u2": 3.0, "u3": 3.0, "u4": -9.0, "u5": 2.0}))
    assert [c.unit_id for c in r.candidates] == ["u4", "u2", "u3", "u5", "u1"]   # u2/u3 tie: fused order
    assert [c.rank for c in r.candidates] == [1, 2, 3, 4, 5]
    assert r.candidates[0].rerank_score == -9.0 and r.degraded is None
    t = r.trace["rerank"]
    assert t["model"] == "m/x" and t["revision"] == "abc123" and set(t["scores"]) == {f"u{i}" for i in range(1, 6)}


def test_the_cpu_scores_only_its_depth_and_deeper_units_keep_the_fused_order():
    chars, depth = R.RERANK_INPUT["cpu"]
    n = depth + 3
    r = R.rerank(_result(cited={"u2"}, n=n), reranker=Fixed({f"u{i}": float(i) for i in range(1, n + 1)}))
    assert ASKED == [(depth, chars)]                      # only the head's passages are read, at the device's length
    ids = [c.unit_id for c in r.candidates]
    head = ["u2"] + [f"u{i}" for i in range(depth, 0, -1) if i != 2]
    assert ids == head + [f"u{i}" for i in range(depth + 1, n + 1)]
    assert [c.rank for c in r.candidates] == list(range(1, n + 1))
    assert all(c.rerank_score is None for c in r.candidates[depth:])
    t = r.trace["rerank"]
    assert (t["passage_chars"], t["depth"], t["scored"]) == (chars, depth, depth) and len(t["scores"]) == depth


def test_the_gpu_reads_the_bake_offs_length_and_depth():
    gpu = RerankerInfo("Qwen/Qwen3-Reranker-8B", "77d1", "qwen", 1024, "", "gpu")

    class G(Fixed):
        info = gpu
    R.rerank(_result(n=5), reranker=G({f"u{i}": float(i) for i in range(1, 6)}))
    assert ASKED == [(5, R.RERANK_INPUT["gpu"][0])] and R.RERANK_INPUT["gpu"] == (1600, 50)


def test_no_reranker_serves_the_fused_order_marked(monkeypatch):
    monkeypatch.setenv("NIZAM_RERANK_PROFILE", "cpu")
    monkeypatch.setattr(R, "_load", lambda d: (_ for _ in ()).throw(R.RerankUnavailable("no files")))
    r = R.rerank(_result())
    assert [c.unit_id for c in r.candidates] == ["u1", "u2", "u3", "u4", "u5"]
    assert r.degraded == "unreranked" and "rerank" not in r.trace
    assert all(c.rerank_score is None for c in r.candidates)


def test_profile_off_is_marked_unreranked(monkeypatch):
    monkeypatch.setenv("NIZAM_RERANK_PROFILE", "off")
    assert R.rerank(_result()).degraded == "unreranked"


def test_the_gpu_failing_falls_back_to_the_cpu_marked(monkeypatch):
    monkeypatch.setenv("NIZAM_RERANK_PROFILE", "gpu")

    def load(device):
        if device == "gpu":
            raise R.RerankUnavailable("gpu reranker: OSError: connection refused")
        return Fixed({f"u{i}": float(i) for i in range(1, 6)})
    monkeypatch.setattr(R, "_load", load)
    r = R.rerank(_result())
    assert [c.unit_id for c in r.candidates] == ["u5", "u4", "u3", "u2", "u1"]
    assert r.degraded == "rerank_cpu" and "connection refused" in r.trace["degraded_stages"][0]["reason"]


def test_a_service_failing_mid_request_is_unreranked_not_an_error():
    class Down:
        info = INFO

        def score(self, q, p):
            raise OSError("timed out")
    r = R.rerank(_result(), reranker=Down())
    assert r.degraded == "unreranked" and [c.unit_id for c in r.candidates][0] == "u1"


def test_an_earlier_degradation_is_kept_beside_the_new_one():
    r = _result()
    r.degraded = "lexical_only"
    R._mark(r, "unreranked", "x")
    assert r.degraded == "lexical_only+unreranked"


def test_any_other_error_is_an_error():
    class Broken:
        info = INFO

        def score(self, q, p):
            raise RuntimeError("bug")
    with pytest.raises(RuntimeError):
        R.rerank(_result(), reranker=Broken())


# --- the GPU client --------------------------------------------------------------------------------------------
def _bundle(tmp_path, scores, api="tei"):
    (tmp_path / "reranker.json").write_text(json.dumps({"model": "Qwen/Qwen3-Reranker-8B", "revision": "77d1",
                                                        "kind": "qwen", "max_tokens": 1024, "api": api,
                                                        "instruction": "Given a question about Pakistani law"}))
    (tmp_path / "reference.json").write_text(json.dumps({"groups": [
        {"question": "q1", "passages": ["a", "b", "c", "d"], "scores": scores}]}))
    return tmp_path


def test_a_service_ranking_the_reference_pairs_as_the_bake_off_did_is_accepted(tmp_path):
    seen = []

    def post(path, payload):
        seen.append((path, payload))
        order = {"a": 4.0, "b": 3.0, "c": 2.0, "d": 1.0}
        return [{"index": i, "score": order[t.rsplit(": ", 1)[-1]]} for i, t in enumerate(payload["texts"])]
    rr = RemoteReranker(_bundle(tmp_path, [9.0, 5.0, 1.0, -2.0]), url="http://gpu", post=post)
    assert seen[0][0] == "/rerank" and seen[0][1]["texts"][0].startswith("<Instruct>: Given a question about")
    assert rr.score("q", ["a", "d"]) == [4.0, 1.0]


def test_a_service_ranking_them_differently_is_refused(tmp_path):
    def post(path, payload):
        return [{"index": i, "score": float(i)} for i in range(len(payload["texts"]))]   # reversed ranking
    with pytest.raises(ValueError, match="does not rank"):
        RemoteReranker(_bundle(tmp_path, [9.0, 5.0, 1.0, -2.0]), url="http://gpu", post=post)


def test_the_vllm_response_shape_is_read(tmp_path):
    def post(path, payload):
        assert path == "/v1/rerank"
        n = len(payload["documents"])
        return {"results": [{"index": i, "relevance_score": float(n - i)} for i in range(n)]}
    rr = RemoteReranker(_bundle(tmp_path, [9.0, 5.0, 1.0, -2.0], api="vllm"), url="http://gpu", post=post)
    assert rr.score("q", ["x", "y"]) == [2.0, 1.0]


def test_no_url_is_oserror(tmp_path, monkeypatch):
    monkeypatch.delenv("NIZAM_GPU_RERANKER_URL", raising=False)
    with pytest.raises(OSError):
        RemoteReranker(_bundle(tmp_path, [1.0, 2.0, 3.0, 4.0]))


def test_spearman_handles_ties_and_constants():
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1, 1, 1], [1, 2, 3]) == 0.0
