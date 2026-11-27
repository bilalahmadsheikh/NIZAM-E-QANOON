"""The cross-encoder reranker (D-101; docs/04 §5.1, §9): the shared inference worker's second job. It scores (question,
passage) pairs; nizam.retrieval.rerank orders the gated candidates by those scores. A score is a relevance logit only
(docs/04 §5.1): authority, validity and publication are decided by the INV-5 gate and the database, never by it.

Two runtimes, one per encoder device, as for the query encoder (D-099):

  cpu  OnnxReranker: an int8 ONNX export made on Kaggle (tools/kaggle/rerank_export_kernel.py) and validated there
       against the full-precision model. Only onnxruntime, tokenizers and numpy -- no torch. The graph outputs one
       score per pair whatever the model family:
         kind "cls"   a sequence-classification head: the relevance logit; the pair is tokenised (question, passage)
                      with the model's own post-processor, passage truncated first
         kind "qwen"  a Qwen3 reranker exported with its two vocabulary rows: logit(yes) - logit(no) at the last
                      token; the pair is the model card's yes/no prompt (system prefix, "<Instruct>: ...\\n<Query>:
                      ...\\n<Document>: ...", assistant suffix), left-padded
       Directory NIZAM_RERANKER_DIR (default <CORPUS_ROOT>/models/reranker): model.onnx, tokenizer.json, reranker.json
       {"model", "revision", "kind", "max_tokens", "instruction"?}.
  gpu  RemoteReranker: the pinned model served on the GPU host (TEI POST {url}/rerank or vLLM POST {url}/v1/rerank).
       NIZAM_GPU_RERANKER_URL; NIZAM_GPU_RERANKER_DIR (default <CORPUS_ROOT>/models/reranker-gpu) holds reranker.json
       and reference.json -- pairs the bake-off scored on Kaggle with their scores. On first use the service must rank
       those pairs as the bake-off did (Spearman >= 0.98 per question, every question): another model, revision or
       prompt template fails that and is refused (ValueError), so a server whose formatting differs can never rerank
       silently wrong.

Failures follow the encoder's convention: missing files or a bad configuration raise OSError/ValueError at load; the
service down raises OSError. nizam.retrieval treats both as "reranker unavailable" (docs/04 §9.2), never as an order.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path

_LOCK = threading.Lock()
_CACHE: dict = {}
REFERENCE_SPEARMAN = 0.98
QWEN_PREFIX = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the "
               "Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
QWEN_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


@dataclass(frozen=True)
class RerankerInfo:
    model: str
    revision: str
    kind: str                 # "cls" | "qwen"
    max_tokens: int
    instruction: str = ""
    device: str = "cpu"       # where it runs: "cpu" (in process) | "gpu" (the GPU host's service)
    precision: str = "fp16"   # the GPU host's weights: "fp16" (D-101) | "nf4" (D-182); part of the gate's key


def reranker_key(model: str, revision: str, precision: str | None = "fp16") -> str:
    """the gate calibration's key for a reranker: model@revision, and @precision when it is not fp16 (D-182: a
    4-bit reranker's scores are calibrated on their own, so an fp16 calibration never gates them, nor the reverse)"""
    return f"{model}@{revision}" + ("" if (precision or "fp16") == "fp16" else f"@{precision}")


def _root() -> Path:
    return Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data")) / "models"


def _info(d: Path, device: str) -> RerankerInfo:
    cfg = json.loads((d / "reranker.json").read_text(encoding="utf-8"))
    info = RerankerInfo(cfg["model"], cfg["revision"], cfg["kind"], int(cfg["max_tokens"]),
                        cfg.get("instruction") or "", device, cfg.get("precision", "fp16"))
    if info.precision not in ("fp16", "nf4"):
        raise ValueError(f"unknown reranker precision {info.precision!r} (fp16 | nf4)")
    if info.kind not in ("cls", "qwen"):
        raise ValueError(f"unknown reranker kind {info.kind!r}")
    if info.kind == "qwen" and not info.instruction:
        raise ValueError("a qwen reranker needs its instruction (the bake-off's)")
    return info


def qwen_document(info: RerankerInfo, question: str, passage: str) -> str:
    """the user turn of a Qwen3 reranker's prompt: the model card's format with the pinned instruction"""
    return f"<Instruct>: {info.instruction}\n<Query>: {question}\n<Document>: {passage}"


class OnnxReranker:
    def __init__(self, directory: Path | None = None):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        d = Path(directory or os.environ.get("NIZAM_RERANKER_DIR") or _root() / "reranker")
        self.info = _info(d, "cpu")
        self._np = np
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.no_padding()
        if self.info.kind == "cls":
            self.tok.enable_truncation(self.info.max_tokens, strategy="only_second")
            # the model's own pad id: XLM-R derives position ids from it, so a foreign pad would shift nothing real
            # (real tokens come first) but is not what the model was trained with
            self._pad = next((i for i in (self.tok.token_to_id(t) for t in ("<pad>", "[PAD]")) if i is not None), 0)
        else:
            self.tok.no_truncation()
            self._pre = self.tok.encode(QWEN_PREFIX, add_special_tokens=False).ids
            self._suf = self.tok.encode(QWEN_SUFFIX, add_special_tokens=False).ids
            self._pad = self.tok.token_to_id("<|endoftext|>")
            if self._pad is None:
                raise ValueError("the qwen tokenizer has no <|endoftext|> pad token")
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("NIZAM_RERANKER_THREADS", "4"))
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(str(d / "model.onnx"), so, providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self.sess.get_inputs()}

    def _encode(self, question: str, passage: str) -> list[int]:
        if self.info.kind == "cls":
            return self.tok.encode(question, passage).ids
        body = self.tok.encode(qwen_document(self.info, question, passage), add_special_tokens=False).ids
        return self._pre + body[: self.info.max_tokens - len(self._pre) - len(self._suf)] + self._suf

    def score(self, question: str, passages: list[str], batch: int = 16) -> list[float]:
        """one relevance score per passage, in order; higher is more relevant"""
        np = self._np
        enc = [self._encode(question, p) for p in passages]
        order = sorted(range(len(enc)), key=lambda i: len(enc[i]))          # similar lengths pad least
        scores = [0.0] * len(enc)
        for s in range(0, len(order), batch):
            idx = order[s:s + batch]
            n = max(len(enc[i]) for i in idx)
            ids = np.full((len(idx), n), self._pad, dtype=np.int64)
            mask = np.zeros((len(idx), n), dtype=np.int64)
            for r, i in enumerate(idx):
                e = enc[i]
                if self.info.kind == "cls":                   # right padding, masked
                    ids[r, :len(e)], mask[r, :len(e)] = e, 1
                else:                                         # left padding: the last token is the answer slot
                    ids[r, n - len(e):], mask[r, n - len(e):] = e, 1
            feeds = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feeds["token_type_ids"] = np.zeros_like(ids)
            got = np.asarray(self.sess.run(None, feeds)[0], dtype=np.float32).reshape(len(idx), -1)[:, -1]
            if not np.isfinite(got).all():
                raise ValueError("the reranker produced a non-finite score")
            for r, i in enumerate(idx):
                scores[i] = float(got[r])
        return scores


class RemoteReranker:
    def __init__(self, directory: Path | None = None, url: str | None = None, timeout: float = 5.0, post=None,
                 get=None):
        d = Path(directory or os.environ.get("NIZAM_GPU_RERANKER_DIR") or _root() / "reranker-gpu")
        self.info = _info(d, "gpu")
        cfg = json.loads((d / "reranker.json").read_text(encoding="utf-8"))
        self.served_model = cfg.get("served_model") or self.info.model
        self.api = cfg.get("api", "tei")                       # "tei" (/rerank) | "vllm" (/v1/rerank)
        self.url = (url or os.environ.get("NIZAM_GPU_RERANKER_URL") or "").rstrip("/")
        if not self.url:
            raise OSError("NIZAM_GPU_RERANKER_URL is not set: no GPU reranker on this host")
        self.timeout = timeout
        self._post = post or self._http_post
        # an injected transport brings its own health (tests); the real one asks the service
        self._get = get or (self._http_get if post is None else None)
        self._check_precision()
        ref = json.loads((d / "reference.json").read_text(encoding="utf-8"))
        for g in ref["groups"]:
            got = self.score(g["question"], g["passages"])
            rho = spearman(got, g["scores"])
            if rho < REFERENCE_SPEARMAN:
                raise ValueError(f"the GPU reranker at {self.url} does not rank the bake-off's reference pairs as "
                                 f"{self.info.model}@{self.info.revision[:12]} did (Spearman {rho:.3f} < "
                                 f"{REFERENCE_SPEARMAN}): another model, revision or prompt template")

    def _check_precision(self) -> None:
        """the reference check cannot tell fp16 from nf4 (they rank alike, D-182), so the precision is asked: our GPU
        service's /health names it (D-178). A server that does not report one (TEI) is not refused for that"""
        if self._get is None:
            return
        try:
            health = self._get("/health")
        except (OSError, ValueError):
            return
        got = ((health or {}).get("reranker") or {}).get("precision") if isinstance(health, dict) else None
        if got is not None and got != self.info.precision:
            raise ValueError(f"the GPU reranker at {self.url} runs {got}, but this bundle is calibrated for "
                             f"{self.info.precision}: install the {got} bundle (models/reranker-gpu"
                             f"{'' if got == 'fp16' else '-' + got}) or serve {self.info.precision}")

    def _http_get(self, path: str):
        with urllib.request.urlopen(self.url + path, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "null")

    def _http_post(self, path: str, payload: dict):
        req = urllib.request.Request(self.url + path, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:      # URLError and timeouts are OSError
            return json.loads(resp.read().decode("utf-8"))

    def score(self, question: str, passages: list[str], instruction: str | None = None) -> list[float]:
        """`instruction`: another task's instruction for a Qwen3 reranker (judgment passages, D-176); None keeps the
        pinned one the reference check verified"""
        if self.info.kind == "qwen":       # the server is sent the card's user turn; its template adds the rest
            info = replace(self.info, instruction=instruction) if instruction else self.info
            docs = [qwen_document(info, question, p) for p in passages]
        else:
            docs = list(passages)
        try:
            if self.api == "vllm":
                out = self._post("/v1/rerank", {"model": self.served_model, "query": question, "documents": docs})
                pairs = [(r["index"], float(r["relevance_score"])) for r in out["results"]]
            else:
                out = self._post("/rerank", {"query": question, "texts": docs, "raw_scores": True, "truncate": True})
                pairs = [(r["index"], float(r["score"])) for r in out]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"unexpected rerank response: {exc}") from exc
        scores = [None] * len(passages)
        for i, s in pairs:
            scores[i] = s
        if any(s is None for s in scores):
            raise ValueError("the GPU reranker did not score every passage")
        return scores


def spearman(a: list[float], b: list[float]) -> float:
    """rank correlation of two score lists (average ranks for ties)"""
    import numpy as np

    def ranks(x):
        x = np.asarray(x, dtype=np.float64)
        order = np.argsort(x, kind="mergesort")
        r = np.empty(len(x))
        r[order] = np.arange(len(x))
        for v in np.unique(x):                       # ties share their mean rank
            m = x == v
            r[m] = r[m].mean()
        return r
    ra, rb = ranks(a), ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def reranker(device: str = "cpu"):
    """the process-wide reranker of a device, loaded once"""
    if device not in _CACHE:
        with _LOCK:
            if device not in _CACHE:
                _CACHE[device] = RemoteReranker() if device == "gpu" else OnnxReranker()
    return _CACHE[device]
