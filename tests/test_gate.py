"""D-102: the sufficiency gate and the retrieval port. INV-2: retrieve() returns GroundingContext | Abstention and
nothing else -- no retry at a lower threshold, no answer from an uncalibrated mode, no evidence beyond the bundle."""
from __future__ import annotations

import json
import math
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest

from nizam.retrieval import gate as G
from nizam.retrieval.lexical import LexicalResult, UnitCandidate
from nizam.retrieval.query import parse
from nizam.storage.lexical import Filters

ROOT = Path(__file__).resolve().parents[1]
SCOPED = Filters(as_of=date(2026, 11, 16), jurisdictions=("punjab", "fed"))
UNSCOPED = Filters(as_of=date(2026, 11, 16))
CPU = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1@1427fd652930e4ba29e8149678df786c240d8825"
CAL = {"version": "test-cal", "modes": {
    "cpu": {"reranker": CPU, "features": ["top", "margin"], "mean": [0.0, 1.0], "scale": [2.0, 1.0],
            "coef": [2.0, 0.5], "intercept": -1.0, "tau": 0.8, "dense_generation": 1},
}}


def cand(i, score=None, inst="I1", cited=False, fused=0.03):
    return UnitCandidate(f"u{i}", f"v{i}", inst, fused - i * 0.001, i, {}, cited, score)


def result(cands, filters=SCOPED, degraded=None, q="Can my landlord evict me?", rerank=CPU, gen=1):
    trace = {"dense_generation": gen}
    if rerank:
        model, rev = rerank.split("@")
        trace["rerank"] = {"model": model, "revision": rev}
    return LexicalResult(cands, parse(q), filters, truncated=False, trace=trace, degraded=degraded)


def strong():
    return [cand(1, 6.0), cand(2, 1.0), cand(3, 0.5, "I2")] + [cand(i, -2.0, "I3") for i in range(4, 13)]


def test_abstention_codes_are_the_documents():
    with pytest.raises(ValueError):
        G.Abstention("LOW_CONFIDENCE", "x")
    assert "INSUFFICIENT_EVIDENCE" in G.CODES and "RETRIEVAL_DEGRADED" in G.CODES


def test_features_read_the_bundle():
    f = G.features(result(strong()), "cpu")
    assert f == {"top": 6.0, "margin": 5.0, "conc": 0.4, "cited": 0, "agree": 0}      # I1 holds 2 of the first 5
    # a cited unit is pinned first by rerank; top is still the best score, conc follows the best-scored unit
    cs = [cand(1, -1.0, "IC", cited=True), cand(2, 4.0, "I1"), cand(3, 3.0, "I1")]
    f = G.features(result(cs), "cpu")
    assert f["top"] == 4.0 and f["margin"] == 1.0 and f["cited"] == 1 and f["conc"] == pytest.approx(2 / 3, abs=1e-5)
    # unreranked: the fused score of the served order
    f = G.features(result([cand(1, fused=0.05), cand(2, fused=0.03)], degraded="unreranked", rerank=None),
                   "unreranked")
    assert f["top"] == pytest.approx(0.049) and f["margin"] == pytest.approx(0.021)


def test_units_below_the_rerank_depth_do_not_count_as_scored():
    cs = [cand(1, 2.0), cand(2, 1.0)] + [cand(i, None) for i in range(3, 13)]
    f = G.features(result(cs), "cpu")
    assert f["top"] == 2.0 and f["margin"] == 1.0


def test_probability_is_the_logistic_of_the_standardised_features():
    m = CAL["modes"]["cpu"]
    z = 2.0 * (6.0 - 0.0) / 2.0 + 0.5 * (5.0 - 1.0) / 1.0 - 1.0
    assert G.probability({"top": 6.0, "margin": 5.0}, m) == pytest.approx(1 / (1 + math.exp(-z)))


def test_a_strong_result_passes_with_only_the_bundle():
    r = result(strong())
    out = G.gate(r, cal=CAL, territory_check=False)
    assert isinstance(out, G.GroundingContext)
    assert len(out.items) == G.BUNDLE and [i.unit_id for i in out.items] == [f"u{i}" for i in range(1, 11)]
    assert out.gate["decision"] == "pass" and out.gate["mode"] == "cpu" and out.confidence >= out.threshold == 0.8
    assert out.trace is r.trace and out.gate["features"]["top"] == 6.0       # INV-3: what decided is recorded


def test_a_weak_result_abstains_with_nearest_results_apart():
    r = result([cand(1, -3.0), cand(2, -3.1), cand(3, -4.0)])
    out = G.gate(r, cal=CAL, territory_check=False)
    assert isinstance(out, G.Abstention) and out.code == "INSUFFICIENT_EVIDENCE"
    assert out.confidence < out.threshold == 0.8 and out.gate["stage"] == "threshold"
    assert [n.unit_id for n in out.nearest] == ["u1", "u2", "u3"] and out.suggestions


def test_nothing_found_abstains():
    out = G.gate(result([]), cal=CAL, territory_check=False)
    assert isinstance(out, G.Abstention) and out.code == "INSUFFICIENT_EVIDENCE" and out.gate["stage"] == "empty"


def test_unreranked_without_its_calibration_is_retrieval_degraded():
    r = result(strong(), degraded="unreranked", rerank=None)
    out = G.gate(r, cal=CAL, territory_check=False)
    assert isinstance(out, G.Abstention) and out.code == "RETRIEVAL_DEGRADED"


def test_unreranked_calibration_must_match_the_dense_space():
    cal = {"version": "x", "modes": {"unreranked": {**CAL["modes"]["cpu"], "features": ["top"], "mean": [0.0],
                                                    "scale": [1.0], "coef": [100.0], "intercept": 0.0, "tau": 0.5,
                                                    "dense_generation": 1}}}
    ok = G.gate(result(strong(), degraded="unreranked", rerank=None, gen=1), cal=cal, territory_check=False)
    assert isinstance(ok, G.GroundingContext) and ok.gate["mode"] == "unreranked"
    other_space = G.gate(result(strong(), degraded="unreranked", rerank=None, gen=2), cal=cal, territory_check=False)
    lexical_only = G.gate(result(strong(), degraded="lexical_only+unreranked", rerank=None, gen=None), cal=cal,
                          territory_check=False)
    assert other_space.code == lexical_only.code == "RETRIEVAL_DEGRADED"


def test_a_reranker_with_no_calibration_of_its_own_never_borrows_one():
    r = result(strong(), rerank="BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e")
    out = G.gate(r, cal=CAL, territory_check=False)
    assert isinstance(out, G.Abstention) and out.code == "RETRIEVAL_DEGRADED"
    assert "bge-reranker" in out.gate["mode"]


@contextmanager
def fake_session(juris):
    class S:
        def instrument_jurisdictions(self, ids):
            return {i: juris.get(i) for i in ids}
    yield S()


def test_no_territory_and_two_provinces_leading_is_jurisdiction_unresolved(monkeypatch):
    juris = {"PB": "punjab", "SD": "sindh", "F": "fed"}
    monkeypatch.setattr(G.unit_search, "session", lambda f, **kw: fake_session(juris))
    cs = [cand(1, 6.0, "PB"), cand(2, 5.0, "SD"), cand(3, 1.0, "F")]
    out = G.gate(result(cs, filters=UNSCOPED), cal=CAL)
    assert isinstance(out, G.Abstention) and out.code == "JURISDICTION_UNRESOLVED"
    assert out.missing == ("territory",) and out.gate["provinces"] == ["punjab", "sindh"]
    # one province, or federal law only, or a territory given: no veto
    assert isinstance(G.gate(result([cand(1, 6.0, "PB"), cand(2, 1.0, "F")], filters=UNSCOPED), cal=CAL),
                      G.GroundingContext)
    assert isinstance(G.gate(result(cs, filters=SCOPED), cal=CAL), G.GroundingContext)
    assert isinstance(G.gate(result(cs, filters=UNSCOPED, q="My landlord in Lahore wants me out"), cal=CAL),
                      G.GroundingContext)


def test_retrieve_vetoes_before_searching(monkeypatch):
    import nizam.retrieval.rerank as R
    monkeypatch.setattr(R, "ranked", lambda *a, **k: pytest.fail("a vetoed question must not be searched"))
    out = G.retrieve("What did the Supreme Court decide in the Panama Papers case?", SCOPED, cal=CAL,
                     today=date(2026, 11, 20))
    assert isinstance(out, G.Abstention) and out.code == "CORPUS_GAP" and out.gate["stage"] == "veto:source"
    assert "judgments" in out.public_reason
    out = G.retrieve("Can my landlord evict me?", Filters(as_of=date(2027, 1, 1)), cal=CAL, today=date(2026, 11, 20))
    assert out.code == "NO_VALID_VERSION"


def test_retrieve_is_two_valued_and_never_retries(monkeypatch):
    import nizam.retrieval.rerank as R
    calls = []

    def fake_ranked(spec, filters, k, **kw):
        calls.append(spec.text)
        return result([cand(1, -3.0), cand(2, -3.5)], filters=filters, q=spec.text)
    monkeypatch.setattr(R, "ranked", fake_ranked)
    out = G.retrieve("Can my landlord evict me?", SCOPED, cal=CAL, today=date(2026, 11, 20))
    assert type(out) in (G.GroundingContext, G.Abstention)
    assert isinstance(out, G.Abstention) and len(calls) == 1          # abstained once; no second, looser search


def _any_result():
    return result(strong())


def test_agreement_counts_the_generators_that_rank_the_lead_unit_high():
    lead = UnitCandidate("u1", "v1", "I1", 0.03, 1, {"lexical": 3, "dense": 8, "citation": 1}, True, 5.0)
    other = UnitCandidate("u2", "v2", "I1", 0.02, 2, {"lexical": 1, "dense": 40}, False, 1.0)
    assert G.features(result([lead, other]), "cpu")["agree"] == 3
    weak = UnitCandidate("u1", "v1", "I1", 0.03, 1, {"lexical": 30, "dense": 8}, False, 5.0)
    assert G.features(result([weak, other]), "cpu")["agree"] == 1


def test_the_shipped_calibration_is_well_formed():
    p = ROOT / "nizam/retrieval/gate_calibration.json"
    if not p.exists():
        pytest.skip("no calibration shipped yet")
    cal = json.loads(p.read_text(encoding="utf-8"))
    rule = json.loads((ROOT / cal["rule"]).read_text(encoding="utf-8"))
    sets = list(rule["candidate_feature_sets"].values())
    for extra in cal.get("addenda", []):
        sets += list(json.loads((ROOT / extra).read_text(encoding="utf-8"))["candidate_feature_sets_added"].values())
    assert cal["bundle"] == G.BUNDLE
    for name, m in cal["modes"].items():
        assert m["features"] in sets and set(m["features"]) <= set(G.features(_any_result(), "cpu"))
        assert len(m["coef"]) == len(m["mean"]) == len(m["scale"]) == len(m["features"])
        assert 0 < m["tau"] < 1 and m["target_precision"] in (0.95, 0.90)
        assert (name == "unreranked") == ("reranker" not in m)
