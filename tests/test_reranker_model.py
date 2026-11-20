"""D-101: the installed CPU reranker, read through the served path, ranks as the full-precision model does.

The export (tools/kaggle/rerank_export_kernel.py) saved fp32 torch scores for the bake-off's first 256 dev pairs
(scores-fp32-first256.npy); the install put those pairs beside the model (reference_pairs.jsonl: question and passage,
no gold). Here the HOST's path -- the `tokenizers` library reading tokenizer.json, pair truncation, the model's pad id,
onnxruntime on the CPU -- scores them one question at a time, as rerank() does. The int8 graph quantises activations
per batch, so a score depends on its batch-mates (0.17 mean absolute difference between batch 16 and batch 1,
measured 20 Nov): an exact match is not the test. Agreement with fp32 is -- the kernel measured correlation 0.9946 for
this variant, and a tokenisation or padding error drops it far below. Skips when no reranker is installed.
"""
import json
import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def installed():
    from nizam.inference.reranker import OnnxReranker, _root
    d = Path(os.environ.get("NIZAM_RERANKER_DIR") or _root() / "reranker")
    if not (d / "model.onnx").exists() or not (d / "reference_pairs.jsonl").exists():
        pytest.skip(f"no validated reranker installed at {d}")
    return OnnxReranker(d), d


def test_the_host_ranks_the_reference_pairs_as_full_precision_does(installed):
    rr, d = installed
    pairs = [json.loads(x) for x in open(d / "reference_pairs.jsonl", encoding="utf-8")]
    ref = np.load(d / "scores-fp32-first256.npy")
    by_q: dict[str, list[dict]] = {}
    for p in pairs:
        by_q.setdefault(p["q"], []).append(p)
    got = np.zeros(len(ref), dtype=np.float32)
    for q, ps in by_q.items():
        for p, s in zip(ps, rr.score(q, [p["p"] for p in ps])):
            got[p["pid"]] = s
    corr = float(np.corrcoef(got, ref)[0, 1])
    assert corr > 0.98, f"correlation with fp32 {corr:.4f}"
    assert float(np.abs(got - ref).mean()) < 0.4


def test_the_installed_reranker_is_the_pinned_cpu_model(installed):
    rr, _ = installed
    rule = json.loads((ROOT / "evals/results/rerank-rule-2026-11-20.json").read_text(encoding="utf-8"))
    assert rr.info.model == "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    assert rr.info.revision == rule["full_revisions"][rr.info.model]
    assert rr.info.kind == "cls" and rr.info.device == "cpu"
