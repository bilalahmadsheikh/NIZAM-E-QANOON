"""The GPU host's inference service (D-178): the 8B question encoder and the 8B reranker behind the two HTTP
protocols the clients already speak and verify (nizam.inference.remote.RemoteEncoder, nizam.inference.reranker.
RemoteReranker). Built on the stack the numbers were measured with (transformers + bitsandbytes, D-099, D-101, D-165),
so the served vectors and scores are the measured ones.

    NIZAM_GPU_SERVICE_ENCODER_DIR=/srv/models/encoder-gpu-nf4 NIZAM_GPU_SERVICE_RERANKER_DIR=/srv/models/reranker-gpu \
      python -m nizam.inference.gpu_service --host 0.0.0.0 --port 8090

Endpoints:
  POST /v1/embeddings  {"model", "input": [text, ...]} -> {"data": [{"index", "embedding": [...]}], "model"}
                       OpenAI form. The text arrives with the query template already applied by the client; the
                       service embeds it as the corpus run did: left-padded, truncated at the bundle's max_tokens,
                       last-token pooling, L2-normalised.
  POST /rerank         {"query", "texts": [...], "raw_scores", "truncate"} -> [{"index", "score"}], best first.
                       TEI form. For a Qwen3 reranker each text is the model card's user turn, which the client
                       builds (qwen_document); the service adds the fixed system prefix and assistant suffix and
                       returns logit("yes") - logit("no") at the last position, as the bake-off did (D-101).
  GET  /health         the loaded models, revisions, precision and device: what the clients' checks will verify.

Precision (encoder.json "precision"): "fp16" or "nf4" (4-bit NF4, fp16 compute, double quantisation: D-165's exact
configuration, which the GPU host serves under D-169). An nf4 host's bundle must carry nf4-made reference vectors:
the client's same-space check (cosine >= 0.99 against the bundle) then proves the host runs that encoder.
Nothing here decides relevance or answers anything; a request it cannot serve is an HTTP error, which the clients
treat as "dense unavailable" or "reranker unavailable" (docs/04 §9.2).
"""
from __future__ import annotations

import argparse
import json
import os
import threading
from pathlib import Path

QWEN_PREFIX = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the "
               "Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
QWEN_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
EMBED_BATCH = 8
RERANK_TOKENS_PER_BATCH = 16_000


class EncoderBackend:
    """Qwen3-Embedding-8B (or any last-token embedder) at the bundle's model, revision and precision"""

    def __init__(self, directory: Path):
        import torch
        from transformers import AutoModel, AutoTokenizer
        cfg = json.loads((Path(directory) / "encoder.json").read_text(encoding="utf-8"))
        if cfg.get("pooling") != "lasttoken":
            raise ValueError(f"this service serves last-token pooling only, not {cfg.get('pooling')!r}")
        self.cfg, self.torch = cfg, torch
        self.precision = cfg.get("precision", "fp16")
        self.max_tokens = int(cfg["max_tokens"])
        self.tok = AutoTokenizer.from_pretrained(cfg["model"], revision=cfg["revision"], padding_side="left")
        kwargs = dict(revision=cfg["revision"], torch_dtype=torch.float16, attn_implementation="sdpa")
        if self.precision == "nf4":
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True)
        elif self.precision != "fp16":
            raise ValueError(f"unknown encoder precision {self.precision!r} (fp16 | nf4)")
        self.model = AutoModel.from_pretrained(cfg["model"], device_map={"": int(os.environ.get(
            "NIZAM_GPU_SERVICE_ENCODER_DEVICE", "0"))}, **kwargs).eval()

    def embed(self, texts: list[str]) -> list[list[float]]:
        torch = self.torch
        out = []
        with torch.inference_mode():
            for i in range(0, len(texts), EMBED_BATCH):
                t = self.tok(texts[i:i + EMBED_BATCH], truncation=True, max_length=self.max_tokens, padding=True,
                             return_tensors="pt").to(self.model.device)
                h = self.model(**t).last_hidden_state[:, -1, :].float()
                out += torch.nn.functional.normalize(h, dim=-1).cpu().tolist()
        return out

    def info(self) -> dict:
        return {k: self.cfg.get(k) for k in ("model", "revision", "pooling", "max_tokens", "dims")} | {
            "precision": self.precision, "device": str(self.model.device)}


class RerankerBackend:
    """Qwen3-Reranker-8B: logit(yes) - logit(no) of the card's prompt, as the D-101 bake-off scored it"""

    def __init__(self, directory: Path):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        cfg = json.loads((Path(directory) / "reranker.json").read_text(encoding="utf-8"))
        if cfg.get("kind") != "qwen":
            raise ValueError(f"this service serves Qwen3 rerankers only, not kind {cfg.get('kind')!r}")
        self.cfg, self.torch = cfg, torch
        self.max_tokens = int(cfg["max_tokens"])
        self.tok = AutoTokenizer.from_pretrained(cfg["model"], revision=cfg["revision"], padding_side="left")
        dev = os.environ.get("NIZAM_GPU_SERVICE_RERANKER_DEVICE", "auto")
        # NIZAM_GPU_SERVICE_MAX_MEMORY "0:8GiB,1:15GiB": where "auto" may place layers (two smaller cards; unset on one)
        mm = os.environ.get("NIZAM_GPU_SERVICE_MAX_MEMORY")
        max_memory = {int(k): v for k, v in (x.split(":") for x in mm.split(","))} if mm else None
        self.model = AutoModelForCausalLM.from_pretrained(
            cfg["model"], revision=cfg["revision"], torch_dtype=torch.float16, attn_implementation="sdpa",
            device_map="auto" if dev == "auto" else {"": int(dev)},
            **({"max_memory": max_memory} if max_memory and dev == "auto" else {})).eval()
        self.pre = self.tok.encode(QWEN_PREFIX, add_special_tokens=False)
        self.suf = self.tok.encode(QWEN_SUFFIX, add_special_tokens=False)
        yes, no = self.tok.convert_tokens_to_ids("yes"), self.tok.convert_tokens_to_ids("no")
        w = self.model.get_output_embeddings().weight
        self.w = w[[no, yes]].detach().float()

    def _ids(self, text: str) -> list[int]:
        body = self.tok.encode(text, add_special_tokens=False)[: self.max_tokens - len(self.pre) - len(self.suf)]
        return self.pre + body + self.suf

    def score(self, texts: list[str]) -> list[float]:
        torch = self.torch
        ids = [self._ids(t) for t in texts]
        order = sorted(range(len(ids)), key=lambda i: len(ids[i]))
        scores = [0.0] * len(ids)
        pad = self.tok.pad_token_id
        dev = next(self.model.model.embed_tokens.parameters()).device
        with torch.inference_mode():
            i = 0
            while i < len(order):
                j, longest = i, 0
                while j < len(order) and max(longest, len(ids[order[j]])) * (j - i + 1) <= RERANK_TOKENS_PER_BATCH:
                    longest = max(longest, len(ids[order[j]]))
                    j += 1
                j = max(j, i + 1)
                batch = order[i:j]
                n = max(len(ids[k]) for k in batch)
                inp = torch.tensor([[pad] * (n - len(ids[k])) + ids[k] for k in batch], device=dev)
                mask = torch.tensor([[0] * (n - len(ids[k])) + [1] * len(ids[k]) for k in batch], device=dev)
                h = self.model.model(input_ids=inp, attention_mask=mask).last_hidden_state[:, -1, :]
                z = h.float().to(self.w.device) @ self.w.T
                for k, v in zip(batch, (z[:, 1] - z[:, 0]).cpu().tolist()):
                    scores[k] = float(v)
                i = j
        return scores

    def info(self) -> dict:
        return {k: self.cfg.get(k) for k in ("model", "revision", "kind", "max_tokens")} | {
            "precision": "fp16", "device": str(next(self.model.parameters()).device)}


try:                                              # request bodies at module level: FastAPI resolves them here
    from pydantic import BaseModel

    class EmbeddingsIn(BaseModel):
        input: list[str] | str
        model: str | None = None

    class RerankIn(BaseModel):
        query: str
        texts: list[str]
        raw_scores: bool = True
        truncate: bool = True
except ImportError:                               # the service's own host always has them; a bare import still works
    EmbeddingsIn = RerankIn = None


def create_app(encoder=None, reranker=None):
    """the HTTP surface over injected backends (tests inject fakes); either may be None (that endpoint is 503)"""
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="nizam GPU inference service")
    lock = threading.Lock()                       # one GPU job at a time: the batch is the unit of parallelism

    @app.get("/health")
    def health():
        return {"status": "ok", "encoder": encoder.info() if encoder else None,
                "reranker": reranker.info() if reranker else None}

    @app.post("/v1/embeddings")
    def embeddings(body: EmbeddingsIn):
        if encoder is None:
            raise HTTPException(503, "no encoder on this service")
        texts = [body.input] if isinstance(body.input, str) else body.input
        if not texts or len(texts) > 256:
            raise HTTPException(422, "1 to 256 inputs")
        with lock:
            vecs = encoder.embed(texts)
        return {"object": "list", "model": encoder.info()["model"],
                "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vecs)]}

    @app.post("/rerank")
    def rerank(body: RerankIn):
        if reranker is None:
            raise HTTPException(503, "no reranker on this service")
        if not body.texts or len(body.texts) > 200:
            raise HTTPException(422, "1 to 200 texts")
        with lock:
            s = reranker.score(body.texts)
        return sorted(({"index": i, "score": v} for i, v in enumerate(s)), key=lambda r: -r["score"])

    return app


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8090)
    a = ap.parse_args()
    import uvicorn
    enc_dir = os.environ.get("NIZAM_GPU_SERVICE_ENCODER_DIR")
    rr_dir = os.environ.get("NIZAM_GPU_SERVICE_RERANKER_DIR")
    if not (enc_dir or rr_dir):
        raise SystemExit("set NIZAM_GPU_SERVICE_ENCODER_DIR and/or NIZAM_GPU_SERVICE_RERANKER_DIR")
    app = create_app(EncoderBackend(Path(enc_dir)) if enc_dir else None,
                     RerankerBackend(Path(rr_dir)) if rr_dir else None)
    uvicorn.run(app, host=a.host, port=a.port, workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
