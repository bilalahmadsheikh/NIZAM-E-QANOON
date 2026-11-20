"""The reranker bake-off's scoring (evals/rerank_eval.py, D-101): binary NDCG@10 credits each gold unit once, a
sub-provision hits its section, and a cited unit is never moved by a model's score."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from rerank_eval import case_metrics, reorder  # noqa: E402

G = ["fed.act.x.s_15"]


def test_a_sub_provision_hits_its_section_and_is_credited_once():
    m = case_metrics(["fed.act.x.s_9", "fed.act.x.s_15.ss_1", "fed.act.x.s_15.ss_2"], G)
    assert m["mrr10"] == 0.5 and m["r10"] == 1.0
    assert math.isclose(m["ndcg10"], (1 / math.log2(3)) / 1.0)          # the second hit on s_15 earns nothing


def test_a_prefix_that_is_not_a_child_does_not_hit():
    assert case_metrics(["fed.act.x.s_150"], G)["r50"] == 0.0           # s_150 is not inside s_15


def test_ideal_dcg_is_capped_at_ten():
    gold = [f"fed.act.x.s_{i}" for i in range(12)]
    m = case_metrics(gold, gold)
    assert math.isclose(m["ndcg10"], 1.0) and m["r10"] == 10 / 12 and m["r50"] == 1.0


def test_cited_units_stay_first_whatever_the_model_scores():
    slate = [{"pid": 0, "citation": True, "path": "a"}, {"pid": 1, "citation": False, "path": "b"},
             {"pid": 2, "citation": False, "path": "c"}]
    out = reorder(slate, np.array([-9.0, 1.0, 5.0], dtype=np.float32))
    assert [u["path"] for u in out] == ["a", "c", "b"]
    assert reorder(slate, None) == slate                                  # the fused row is the slate itself


def test_ties_keep_the_fused_order():
    slate = [{"pid": i, "citation": False, "path": str(i)} for i in range(3)]
    assert [u["path"] for u in reorder(slate, np.zeros(3, dtype=np.float32))] == ["0", "1", "2"]
