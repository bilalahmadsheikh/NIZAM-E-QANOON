"""The query encoder (D-098): the shared inference worker's first job (docs/01 layer rule: "plus the shared inference
worker"). It turns a question into the same 1024-dimension space the chunk embeddings live in, then into the binary
form chunk.embedding stores (the sign of each dimension, docs/03 §3).

Runs on the CPU with ONNX Runtime and an int8-quantised export of the chosen model, made on Kaggle by
tools/kaggle/export_kernel.py and validated there against the full-precision model. Locally it needs only
onnxruntime, tokenizers and numpy -- no torch -- so it loads in seconds in a few hundred megabytes.

The model directory (NIZAM_ENCODER_DIR, default <CORPUS_ROOT>/models/encoder) holds:
  model.onnx       the int8 graph (inputs input_ids, attention_mask; output the last hidden state)
  tokenizer.json   the model's own tokenizer
  encoder.json     {"model", "revision", "pooling": cls|mean|lasttoken, "query_template", "max_tokens", "dims"}
encoder.json must name the ACTIVE embedding_generation's model and revision: a query encoded by another model would
be compared with passages from a different space (docs/03 §3), so `check_generation` refuses that.

Threads are capped (NIZAM_ENCODER_THREADS, default 2) so the encoder never starves Postgres on the same host. The
session is created once, lazily, and shared; ONNX Runtime sessions are safe to call from several threads.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

_LOCK = threading.Lock()
_ENC = None


@dataclass(frozen=True)
class EncoderInfo:
    model: str
    revision: str
    pooling: str
    query_template: str
    max_tokens: int
    dims: int


def model_dir() -> Path:
    if os.environ.get("NIZAM_ENCODER_DIR"):
        return Path(os.environ["NIZAM_ENCODER_DIR"])
    return Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data")) / "models" / "encoder"


class Encoder:
    def __init__(self, directory: Path | None = None):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        d = Path(directory or model_dir())
        cfg = json.loads((d / "encoder.json").read_text(encoding="utf-8"))
        self.info = EncoderInfo(cfg["model"], cfg["revision"], cfg["pooling"], cfg["query_template"],
                                int(cfg["max_tokens"]), int(cfg["dims"]))
        if self.info.pooling not in ("cls", "mean", "lasttoken"):
            raise ValueError(f"unknown pooling {self.info.pooling!r}")
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(self.info.max_tokens)
        self.tok.no_padding()      # one sequence, unpadded: the last real token is the last token (lasttoken pooling)
        self._np = np
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("NIZAM_ENCODER_THREADS", "2"))
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(str(d / "model.onnx"), so, providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self.sess.get_inputs()}

    def embed(self, question: str):
        """the question's unit-length float vector (dims,), in the model's query form"""
        return self._vector(self.info.query_template.format(q=" ".join((question or "").split())))

    def embed_passage(self, text: str):
        """a passage's vector: no query template (the model cards: documents take no instruction); used for the
        few chunks a replay adds between GPU runs"""
        return self._vector(text or "")

    def _vector(self, text: str):
        np = self._np
        enc = self.tok.encode(text)
        ids = np.asarray([enc.ids], dtype=np.int64)
        mask = np.asarray([enc.attention_mask], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._inputs:
            feeds["token_type_ids"] = np.zeros_like(ids)
        hidden = self.sess.run(None, feeds)[0][0]             # (tokens, hidden)
        if self.info.pooling == "cls":
            v = hidden[0]
        elif self.info.pooling == "mean":
            m = mask[0][:, None].astype(hidden.dtype)
            v = (hidden * m).sum(0) / max(m.sum(), 1.0)
        else:                                               # lasttoken: the final non-padding token
            v = hidden[int(mask[0].sum()) - 1]
        v = v[: self.info.dims].astype(np.float32)
        n = float(np.linalg.norm(v))
        if not n or not np.isfinite(n):
            raise ValueError("the encoder produced a zero or non-finite vector")
        return v / n

    def bits(self, question: str) -> str:
        """the question in chunk.embedding's form: a 1024-character '0'/'1' string, sign of each dimension"""
        return to_bits(self.embed(question))

    def passage_bits(self, text: str) -> str:
        return to_bits(self.embed_passage(text))


def to_bits(v) -> str:
    """sign of each dimension, first dimension first -- the order numpy.packbits/unpackbits use in the GPU run"""
    return "".join("1" if x > 0 else "0" for x in v)


def encoder() -> Encoder:
    global _ENC
    if _ENC is None:
        with _LOCK:
            if _ENC is None:
                _ENC = Encoder()
    return _ENC


def check_generation(active: dict, info: EncoderInfo) -> None:
    """refuse a query encoder that is not the active embedding generation's model (docs/03 §3)"""
    if active is None:
        raise ValueError("no active embedding generation: chunk embeddings are not loaded")
    if (active["model"], active["revision"], active["pooling"], active["query_template"]) != \
            (info.model, info.revision, info.pooling, info.query_template):
        raise ValueError(f"the query encoder ({info.model}@{info.revision[:12]}) is not the active embedding "
                         f"generation ({active['model']}@{active['revision'][:12]}): different spaces")
