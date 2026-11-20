"""A reranker that replays scores computed on the GPU (D-101) -- evaluation only, never serving.

The bake-off scores every (question, passage) pair of a split on Kaggle (tools/kaggle/rerank_kernel.py, by pid of
evals/rerank_slates.py's pairs.jsonl). To measure the SERVED path (nizam.retrieval.rerank.ranked: passages read again
from L2, cited units pinned, the trace) with a model this host cannot run, those scores are replayed by (question,
passage) text. A pair it does not hold raises ValueError -- the passage read now differs from the one scored, so the
benchmark refuses to report it rather than score something else. Same interface as nizam.inference.reranker.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from nizam.inference.reranker import RerankerInfo


def _key(q: str, p: str) -> tuple[str, str]:
    return " ".join((q or "").split()), p


class PrecomputedReranker:
    def __init__(self, info: RerankerInfo, pairs_jsonl: Path, scores_npy: Path):
        scores = np.load(scores_npy)
        self.info = info
        self._by: dict = {}
        for line in open(pairs_jsonl, encoding="utf-8"):
            row = json.loads(line)
            self._by[_key(row["q"], row["p"])] = float(scores[row["pid"]])
        if len(self._by) > len(scores):
            raise ValueError(f"{len(self._by)} pairs but {len(scores)} scores")

    def score(self, question: str, passages: list[str]) -> list[float]:
        out = []
        for p in passages:
            try:
                out.append(self._by[_key(question, p)])
            except KeyError:
                raise ValueError(f"no precomputed score for this passage of {question[:50]!r}: "
                                 f"{p[:60]!r}") from None
        return out
