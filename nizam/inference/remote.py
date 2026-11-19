"""The GPU generation's query encoder (D-099): Qwen3-Embedding-8B, served on the GPU host beside the answer model.

An 8B encoder cannot run on the CPU inside the latency budget (D-099), so it is not loaded into this process. The GPU
host serves the pinned model through an OpenAI-compatible embeddings endpoint (POST {url}/v1/embeddings -- vLLM and
Hugging Face TEI both expose it) and this client asks it for one vector per question. The client applies the query
template itself, so the server embeds exactly the text the corpus run's questions were embedded from.

Configuration:
  NIZAM_GPU_ENCODER_URL   the service's base URL (unset: the GPU generation is unavailable on this host)
  NIZAM_GPU_ENCODER_DIR   default <CORPUS_ROOT>/models/encoder-gpu, holding
      encoder.json            {"model", "revision", "pooling", "query_template", "max_tokens", "dims", "served_model"?}
      reference_q.npy         float32 [n, dims]: questions embedded on the GPU by the corpus run itself (Kaggle)
      reference_questions.json  their raw texts, in the same order

On first use the service must reproduce the first three reference vectors (cosine >= 0.99). A service running another
model, commit, pooling or prefix fails that and is refused (ValueError), so its vectors are never compared with the
corpus: the same rule check_generation enforces for the CPU encoder (docs/03 §3). Network failures are OSError.
Both are what nizam.retrieval treats as "dense unavailable" (docs/04 §9.2) -- never as an answer.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.request
from pathlib import Path

from nizam.inference.encoder import EncoderInfo, to_bits

_LOCK = threading.Lock()
_ENC = None
REFERENCE_COSINE = 0.99


def model_dir() -> Path:
    if os.environ.get("NIZAM_GPU_ENCODER_DIR"):
        return Path(os.environ["NIZAM_GPU_ENCODER_DIR"])
    return Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data")) / "models" / "encoder-gpu"


class RemoteEncoder:
    def __init__(self, directory: Path | None = None, url: str | None = None, timeout: float = 2.0, post=None):
        import numpy as np
        self._np = np
        d = Path(directory or model_dir())
        cfg = json.loads((d / "encoder.json").read_text(encoding="utf-8"))
        self.info = EncoderInfo(cfg["model"], cfg["revision"], cfg["pooling"], cfg["query_template"],
                                int(cfg["max_tokens"]), int(cfg["dims"]))
        self.served_model = cfg.get("served_model") or cfg["model"]
        self.url = (url or os.environ.get("NIZAM_GPU_ENCODER_URL") or "").rstrip("/")
        if not self.url:
            raise OSError("NIZAM_GPU_ENCODER_URL is not set: no GPU encoder on this host")
        self.timeout = timeout
        self._post = post or self._http_post
        ref = np.load(d / "reference_q.npy")
        qs = json.loads((d / "reference_questions.json").read_text(encoding="utf-8"))
        if len(qs) != len(ref) or ref.shape[1] != self.info.dims:
            raise ValueError(f"reference vectors {ref.shape} do not match {len(qs)} questions / {self.info.dims} dims")
        for q, want in list(zip(qs, ref))[:3]:
            got = self.embed(q)
            cos = float(got @ (want / np.linalg.norm(want)))
            if cos < REFERENCE_COSINE:
                raise ValueError(f"the GPU encoder at {self.url} does not reproduce the corpus run's question vectors "
                                 f"(cosine {cos:.4f} < {REFERENCE_COSINE}): another model, commit, pooling or prefix")

    def _http_post(self, payload: dict) -> dict:
        req = urllib.request.Request(self.url + "/v1/embeddings", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:      # URLError and timeouts are OSError
            return json.loads(resp.read().decode("utf-8"))

    def embed(self, question: str):
        """the question's unit-length float vector (dims,), in the model's query form"""
        np = self._np
        text = self.info.query_template.format(q=" ".join((question or "").split()))
        out = self._post({"model": self.served_model, "input": [text]})
        try:
            v = np.asarray(out["data"][0]["embedding"], dtype=np.float32)
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"unexpected embeddings response: {str(out)[:200]}") from exc
        if v.shape != (self.info.dims,):
            raise ValueError(f"the GPU encoder returned {v.shape[0]} dimensions, expected {self.info.dims}")
        n = float(np.linalg.norm(v))
        if not n or not np.isfinite(n):
            raise ValueError("the GPU encoder returned a zero or non-finite vector")
        return v / n

    def bits(self, question: str, width: int | None = None) -> str:
        v = self.embed(question)
        return to_bits(v[: width or len(v)])


def remote_encoder() -> RemoteEncoder:
    global _ENC
    if _ENC is None:
        with _LOCK:
            if _ENC is None:
                _ENC = RemoteEncoder()
    return _ENC
