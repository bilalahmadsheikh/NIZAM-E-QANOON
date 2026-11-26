# Kaggle GPU kernel: score (question, passage) pairs with cross-encoder rerankers, for the reranker bake-off (D-101).
# Pushed by `tools/kaggle/kg.sh rrpush NAME DATASET MODELS` (MODELS: comma-separated slugs below). The dataset holds
# pairs.jsonl ({"pid", "q", "p"}; evals/rerank_slates.py) -- questions and statutory passages only, no gold.
#
# Every model is pinned to the revision the pre-registered rule names (evals/results/rerank-rule-2026-11-20.json):
#   seq-cls models  AutoModelForSequenceClassification(question, passage) -> the relevance logit
#   Qwen3 rerankers the model card's yes/no form: system prefix, "<Instruct>: ...\n<Query>: ...\n<Document>: ...",
#                   assistant suffix; score = logit(yes) - logit(no) at the last token (monotone in P(yes)). Only the
#                   two vocabulary rows are multiplied, never the full 151k-row head.
# Output: out/scores-<slug>.npy (float32, by pid), out/latency-<slug>.json (one question's 50 passages as one batch,
# after warm-up), out/run.json (versions, seconds per model). SMOKE=1 scores the first 64 pairs only.
import glob
import json
import os
import subprocess
import sys
import time

MODELS = "__MODELS__".split(",")
SMOKE = int("__SMOKE__" or 0)
OUT = "/kaggle/working/out"
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers==4.51.3", "accelerate==1.6.0"], check=False)
import numpy as np  # noqa: E402
import torch  # noqa: E402
import transformers  # noqa: E402
from transformers import (AutoModelForCausalLM, AutoModelForSequenceClassification,  # noqa: E402
                          AutoTokenizer)

REG = {
    "mminilm": ("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "1427fd652930e4ba29e8149678df786c240d8825", 512, "cls"),
    "gte-ml": ("Alibaba-NLP/gte-multilingual-reranker-base", "8215cf04918ba6f7b6a62bb44238ce2953d8831c", 1024, "cls"),
    "bge-v2-m3": ("BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", 1024, "cls"),
    "qwen3-0.6b": ("Qwen/Qwen3-Reranker-0.6B", "e61197ed45024b0ed8a2d74b80b4d909f1255473", 1024, "qwen"),
    "qwen3-4b": ("Qwen/Qwen3-Reranker-4B", "22e683669bc0f0bd69640a1354a6d0aebcfeede5", 1024, "qwen"),
    "qwen3-8b": ("Qwen/Qwen3-Reranker-8B", "77d193c791ed757ca307ee72715aa132723da912", 1024, "qwen"),
}
# gte-multilingual's modelling code lives in another repo its config points to (trust_remote_code), so its revision
# is recorded at run time: the bake-off row must say which code scored it
REMOTE_CODE = {"gte-ml": "Alibaba-NLP/new-impl"}
# the statutes' instruction (D-101, as measured); a precedent run passes its own (KG_TASK, D-167)
TASK = "__TASK__" if not "__TASK__".startswith("__") else \
    "Given a question about Pakistani law, retrieve the statutory provisions that answer it"
Q_PREFIX = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the "
            "Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
Q_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
TOKENS_PER_BATCH = 16384

src = sorted(glob.glob("/kaggle/input/**/pairs.jsonl", recursive=True))[0]
pairs = [json.loads(line) for line in open(src, encoding="utf-8")]
assert [p["pid"] for p in pairs] == list(range(len(pairs))), "pids must be 0..n-1 in order"
if SMOKE:
    pairs = pairs[:64]
print(f"{len(pairs)} pairs from {src}; gpus {[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}",
      flush=True)
run = {"versions": {"torch": torch.__version__, "transformers": transformers.__version__,
                    "gpus": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]},
       "pairs": len(pairs), "models": {}}


class SeqCls:
    def __init__(self, hub, rev, max_len):
        self.tok = AutoTokenizer.from_pretrained(hub, revision=rev, trust_remote_code=True)
        self.m = AutoModelForSequenceClassification.from_pretrained(
            hub, revision=rev, torch_dtype=torch.float16, trust_remote_code=True).to("cuda:0").eval()
        self.max_len = max_len

    def lengths(self, batch):
        return [len(self.tok(p["q"], p["p"], truncation="only_second", max_length=self.max_len)["input_ids"])
                for p in batch]

    @torch.inference_mode()
    def score(self, batch):
        x = self.tok([p["q"] for p in batch], [p["p"] for p in batch], truncation="only_second",
                     max_length=self.max_len, padding=True, return_tensors="pt").to("cuda:0")
        logits = self.m(**x).logits.float()
        return (logits[:, 0] if logits.shape[1] == 1 else logits[:, -1]).cpu().numpy()


class QwenYesNo:
    def __init__(self, hub, rev, max_len):
        self.tok = AutoTokenizer.from_pretrained(hub, revision=rev, padding_side="left")
        big = "8B" in hub
        self.m = AutoModelForCausalLM.from_pretrained(
            hub, revision=rev, torch_dtype=torch.float16, attn_implementation="sdpa",
            device_map="auto" if big else {"": 0},
            max_memory={0: "13GiB", 1: "14GiB"} if big else None).eval()
        self.pre = self.tok.encode(Q_PREFIX, add_special_tokens=False)
        self.suf = self.tok.encode(Q_SUFFIX, add_special_tokens=False)
        self.max_len = max_len
        yes, no = self.tok.convert_tokens_to_ids("yes"), self.tok.convert_tokens_to_ids("no")
        w = self.m.get_output_embeddings().weight
        self.w = w[[no, yes]].detach().float()            # the two rows, on the head's device

    def _ids(self, p):
        body = self.tok.encode(f"<Instruct>: {TASK}\n<Query>: {p['q']}\n<Document>: {p['p']}",
                               add_special_tokens=False)[: self.max_len - len(self.pre) - len(self.suf)]
        return self.pre + body + self.suf

    def lengths(self, batch):
        return [len(self._ids(p)) for p in batch]

    @torch.inference_mode()
    def score(self, batch):
        ids = [self._ids(p) for p in batch]
        n = max(map(len, ids))
        pad = self.tok.pad_token_id
        input_ids = torch.tensor([[pad] * (n - len(i)) + i for i in ids])
        mask = torch.tensor([[0] * (n - len(i)) + [1] * len(i) for i in ids])
        dev = next(self.m.model.embed_tokens.parameters()).device
        h = self.m.model(input_ids=input_ids.to(dev), attention_mask=mask.to(dev)).last_hidden_state[:, -1, :]
        z = h.float().to(self.w.device) @ self.w.T          # [n, 2]: no, yes
        return (z[:, 1] - z[:, 0]).cpu().numpy()


def batches(model, items):
    lens = model.lengths(items)
    order = sorted(range(len(items)), key=lambda i: lens[i])
    cur, longest = [], 0
    for i in order:
        longest = max(longest, lens[i])
        if cur and longest * (len(cur) + 1) > TOKENS_PER_BATCH:
            yield cur
            cur, longest = [], lens[i]
        cur.append(i)
    if cur:
        yield cur


for slug in MODELS:
    hub, rev, max_len, kind = REG[slug]
    t0 = time.time()
    model = (QwenYesNo if kind == "qwen" else SeqCls)(hub, rev, max_len)
    t_load = time.time() - t0
    scores = np.full(len(pairs), np.nan, dtype=np.float32)
    t1 = time.time()
    for idx in batches(model, pairs):
        scores[idx] = model.score([pairs[i] for i in idx])
    t_score = time.time() - t1
    bad = int((~np.isfinite(scores)).sum())
    np.save(f"{OUT}/scores-{slug}.npy", scores)
    # latency (D-106): one question's passages, micro-batched by the scoring token budget -- a single 50-pair batch ran
    # out of memory on a T4 (D-101) -- timed end to end for the first 10 and for all 50 of a question. A proxy: the
    # serving GPU (TEI or vLLM, continuous batching) is faster than Kaggle's T4s
    by_q: dict = {}
    for p in pairs:
        by_q.setdefault(p["q"], []).append(p)
    groups = [g[:50] for g in by_q.values() if len(g) >= 50][:20] or [pairs[:50]]

    def timed(g):
        torch.cuda.synchronize()
        t = time.perf_counter()
        for idx in batches(model, g):
            model.score([g[i] for i in idx])
        torch.cuda.synchronize()
        return (time.perf_counter() - t) * 1000

    def pct(xs, q):
        xs = sorted(xs)
        return round(xs[min(len(xs) - 1, int(q * (len(xs) - 1) + 0.5))], 1)
    try:
        timed(groups[0])                                   # warm-up
        t50 = [timed(g) for g in groups]
        t10 = [timed(g[:10]) for g in groups]
        lat = {"n": len(groups), "p50_ms_50": pct(t50, .5), "p95_ms_50": pct(t50, .95), "p50_ms_10": pct(t10, .5),
               "p95_ms_10": pct(t10, .95), "tokens_per_batch": TOKENS_PER_BATCH,
               "note": "one question's passages micro-batched by the scoring token budget, fp16, Kaggle T4 (proxy)"}
    except torch.cuda.OutOfMemoryError as exc:             # the scores above are already saved
        lat = {"error": f"OutOfMemoryError: {str(exc)[:200]}"}
    json.dump(lat, open(f"{OUT}/latency-{slug}.json", "w"), indent=1)
    run["models"][slug] = {"hub": hub, "revision": rev, "max_tokens": max_len, "kind": kind, "load_s": round(t_load),
                           "score_s": round(t_score), "nonfinite": bad, "latency": lat}
    if slug in REMOTE_CODE:
        from huggingface_hub import HfApi
        run["models"][slug]["remote_code"] = {REMOTE_CODE[slug]: HfApi().model_info(REMOTE_CODE[slug]).sha}
    print(f"{slug}: {len(pairs)} pairs in {t_score:.0f}s (load {t_load:.0f}s), nonfinite {bad}, latency {lat}",
          flush=True)
    json.dump(run, open(f"{OUT}/run.json", "w"), indent=1)
    del model
    torch.cuda.empty_cache()
print("done")
