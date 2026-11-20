"""rerank_bundle.py --slug SLUG --pairs PAIRS --scores NPY --out DIR [--api tei|vllm] : the reference bundle a GPU-host
reranker service is validated against (nizam.inference.reranker.RemoteReranker, D-101).

Writes DIR/reranker.json (model, full revision, kind, max tokens, the bake-off's instruction, the server API) and
DIR/reference.json: GROUPS questions of the bake-off, each with PER passages spread across its score range and the
scores the pinned model gave them on Kaggle. A service must rank every group as the bake-off did (Spearman >= 0.98),
so a different model, revision or prompt template is refused before it reranks anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RULE = json.loads((ROOT / "evals/results/rerank-rule-2026-11-20.json").read_text(encoding="utf-8"))
SLUGS = {"mminilm": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "gte-ml": "Alibaba-NLP/gte-multilingual-reranker-base",
         "bge-v2-m3": "BAAI/bge-reranker-v2-m3", "qwen3-0.6b": "Qwen/Qwen3-Reranker-0.6B",
         "qwen3-4b": "Qwen/Qwen3-Reranker-4B", "qwen3-8b": "Qwen/Qwen3-Reranker-8B"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, choices=sorted(SLUGS))
    ap.add_argument("--pairs", required=True, type=Path)
    ap.add_argument("--scores", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--api", default="tei", choices=("tei", "vllm"))
    ap.add_argument("--groups", type=int, default=6)
    ap.add_argument("--per", type=int, default=12)
    a = ap.parse_args()
    hub = SLUGS[a.slug]
    meta = RULE["models"][hub]
    rev = RULE["full_revisions"][hub].split()[0]
    scores = np.load(a.scores)
    by_q: dict[str, list[tuple[float, str]]] = {}
    for line in open(a.pairs, encoding="utf-8"):
        r = json.loads(line)
        by_q.setdefault(r["q"], []).append((float(scores[r["pid"]]), r["p"]))
    if len(scores) != sum(len(v) for v in by_q.values()):
        sys.exit("scores and pairs differ in length")
    groups = []
    for q in sorted(by_q, key=lambda q: (len(q), q))[:: max(1, len(by_q) // a.groups)][: a.groups]:
        ranked = sorted(by_q[q], key=lambda x: -x[0])
        pick = [ranked[round(i * (len(ranked) - 1) / (a.per - 1))] for i in range(a.per)]   # spread over the range
        groups.append({"question": q, "passages": [p for _s, p in pick], "scores": [s for s, _p in pick]})
    a.out.mkdir(parents=True, exist_ok=True)
    kind = "qwen" if meta["kind"].startswith("yes-no") else "cls"
    (a.out / "reranker.json").write_text(json.dumps({
        "model": hub, "revision": rev, "kind": kind, "max_tokens": meta["max_tokens"],
        "instruction": RULE["qwen_instruction"] if kind == "qwen" else "", "api": a.api}, indent=1), encoding="utf-8")
    (a.out / "reference.json").write_text(json.dumps({"source": str(a.scores), "groups": groups}, ensure_ascii=False,
                                                     indent=0), encoding="utf-8")
    print(f"{hub}@{rev[:12]} ({kind}): {len(groups)} reference groups of {a.per} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
