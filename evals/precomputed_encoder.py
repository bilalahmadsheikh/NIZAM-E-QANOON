"""A query encoder that replays question vectors computed on the GPU (D-099) -- evaluation only, never serving.

The GPU generation's encoder runs on the GPU host (nizam.inference.remote); this machine has none. To measure the
SERVED path (nizam.retrieval.candidates: fusion, gate, latency) with generation 2 here, the golden questions are
encoded on Kaggle by the corpus run itself (dev_q.npy, dev.json order) and replayed by text. A question it does not
hold raises ValueError -- the retriever then reports the dense generator unavailable, which the benchmark refuses to
score as hybrid. It has the same interface as the live encoders: .info, .embed(q), .bits(q[, width]).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from nizam.inference.encoder import EncoderInfo, to_bits


def _key(q: str) -> str:
    return " ".join((q or "").split())


class PrecomputedEncoder:
    def __init__(self, info: EncoderInfo, questions: list[str], vectors: np.ndarray):
        if len(questions) != len(vectors) or vectors.shape[1] != info.dims:
            raise ValueError(f"{len(questions)} questions, vectors {vectors.shape}, dims {info.dims}")
        v = vectors.astype(np.float32)
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        self.info = info
        self._by = {_key(q): row for q, row in zip(questions, v)}

    @classmethod
    def from_bundle(cls, d: Path, vectors: str = "reference_q.npy", questions: str = "reference_questions.json"):
        """a directory laid out like the GPU encoder's bundle (tools/load_embeddings_gpu.py): encoder.json, the
        question vectors and their texts -- the dev bundle itself, or the test questions encoded after the freeze"""
        d = Path(d)
        cfg = json.loads((d / "encoder.json").read_text(encoding="utf-8"))
        info = EncoderInfo(cfg["model"], cfg["revision"], cfg["pooling"], cfg["query_template"],
                           int(cfg["max_tokens"]), int(cfg["dims"]))
        return cls(info, json.loads((d / questions).read_text(encoding="utf-8")), np.load(d / vectors))

    def embed(self, question: str):
        try:
            return self._by[_key(question)]
        except KeyError:
            raise ValueError(f"no precomputed vector for {question[:60]!r}") from None

    def bits(self, question: str, width: int | None = None) -> str:
        v = self.embed(question)
        return to_bits(v[: width or len(v)])
