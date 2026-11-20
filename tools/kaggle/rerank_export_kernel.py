# Kaggle kernel: export the CPU profile's chosen reranker as an int8 ONNX graph, and prove it (D-101).
# Pushed by `tools/kaggle/kg.sh rrexportpush NAME DATASET SLUG`. The dataset is the bake-off's pairs.jsonl.
#
#   1. load the model in fp32 at the pinned revision (the same registry as tools/kaggle/rerank_kernel.py);
#   2. wrap it so the graph outputs ONE SCORE PER PAIR whatever the family -- the sequence-classification logit, or a
#      Qwen3 reranker's logit(yes) - logit(no) at the last token, multiplying only its two vocabulary rows -- and
#      torch.onnx.export it (input_ids, attention_mask -> score), dynamic batch and sequence;
#   3. onnxruntime.quantization.quantize_dynamic to int8, per tensor and per channel (D-098 kept per channel);
#   4. score EVERY bake-off pair with each int8 variant on the Kaggle CPU, exactly as nizam.inference.reranker feeds
#      it (the same tokenisation and padding), plus fp32 torch on the first 256 pairs (how far the GPU's fp16 bake-off
#      scores sit from full precision). evals/rerank_eval.py then applies the rule: int8 ships if its dev NDCG@10 is
#      within 1 point of the bake-off's;
#   5. write both int8 variants (<variant>.onnx), tokenizer.json, reranker.json, scores-int8-<variant>.npy,
#      validation.json to /kaggle/working/reranker/; the rule picks the variant locally and installs it as model.onnx.
import glob
import json
import os
import subprocess
import sys
import time

SLUG = "__SLUG__"
OUT = "/kaggle/working/reranker"
os.makedirs(OUT, exist_ok=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers==4.51.3", "onnx", "onnxruntime",
                "onnxscript"], check=False)
import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
import torch  # noqa: E402
from onnxruntime.quantization import QuantType, quantize_dynamic  # noqa: E402
from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

REG = {
    "mminilm": ("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "1427fd652930e4ba29e8149678df786c240d8825", 512, "cls"),
    "gte-ml": ("Alibaba-NLP/gte-multilingual-reranker-base", "8215cf04918ba6f7b6a62bb44238ce2953d8831c", 1024, "cls"),
    "bge-v2-m3": ("BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", 1024, "cls"),
    "qwen3-0.6b": ("Qwen/Qwen3-Reranker-0.6B", "e61197ed45024b0ed8a2d74b80b4d909f1255473", 1024, "qwen"),
}
TASK = "Given a question about Pakistani law, retrieve the statutory provisions that answer it"
Q_PREFIX = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the "
            "Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
Q_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
hub, rev, max_len, kind = REG[SLUG]
src = sorted(glob.glob("/kaggle/input/**/pairs.jsonl", recursive=True))[0]
pairs = [json.loads(line) for line in open(src, encoding="utf-8")]
print(f"{SLUG}: {hub}@{rev[:12]} ({kind}), {len(pairs)} pairs", flush=True)

if kind == "cls":
    tok = AutoTokenizer.from_pretrained(hub, revision=rev, trust_remote_code=True)
    model = AutoModelForSequenceClassification.from_pretrained(hub, revision=rev, torch_dtype=torch.float32,
                                                               trust_remote_code=True).eval()
    PAD = tok.pad_token_id

    class Scorer(torch.nn.Module):
        def __init__(self, m):
            super().__init__(); self.m = m

        def forward(self, input_ids, attention_mask):
            z = self.m(input_ids=input_ids, attention_mask=attention_mask).logits
            return z[:, -1]

    def encode(p):
        return tok(p["q"], p["p"], truncation="only_second", max_length=max_len)["input_ids"]
else:
    tok = AutoTokenizer.from_pretrained(hub, revision=rev, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(hub, revision=rev, torch_dtype=torch.float32,
                                                 attn_implementation="eager").eval()
    model.config.use_cache = False
    PAD = tok.pad_token_id
    PRE = tok.encode(Q_PREFIX, add_special_tokens=False)
    SUF = tok.encode(Q_SUFFIX, add_special_tokens=False)
    YES, NO = tok.convert_tokens_to_ids("yes"), tok.convert_tokens_to_ids("no")

    class Scorer(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m.model
            self.register_buffer("w", m.get_output_embeddings().weight[[NO, YES]].detach().clone())

        def forward(self, input_ids, attention_mask):
            h = self.m(input_ids=input_ids, attention_mask=attention_mask, use_cache=False).last_hidden_state[:, -1, :]
            z = h @ self.w.T
            return z[:, 1] - z[:, 0]

    def encode(p):
        body = tok.encode(f"<Instruct>: {TASK}\n<Query>: {p['q']}\n<Document>: {p['p']}",
                          add_special_tokens=False)[: max_len - len(PRE) - len(SUF)]
        return PRE + body + SUF

scorer = Scorer(model).eval()
enc = [encode(p) for p in pairs]


def feeds(idx):
    n = max(len(enc[i]) for i in idx)
    ids = np.full((len(idx), n), PAD, dtype=np.int64)
    mask = np.zeros((len(idx), n), dtype=np.int64)
    for r, i in enumerate(idx):
        e = enc[i]
        if kind == "cls":
            ids[r, :len(e)], mask[r, :len(e)] = e, 1
        else:
            ids[r, n - len(e):], mask[r, n - len(e):] = e, 1
    return ids, mask


ids, mask = feeds([0, 1])
fp32 = f"{OUT}/fp32/model.onnx"
os.makedirs(f"{OUT}/fp32", exist_ok=True)
torch.onnx.export(scorer, (torch.from_numpy(ids), torch.from_numpy(mask)), fp32,
                  input_names=["input_ids", "attention_mask"], output_names=["score"],
                  dynamic_axes={"input_ids": {0: "b", 1: "t"}, "attention_mask": {0: "b", 1: "t"}, "score": {0: "b"}},
                  opset_version=17, dynamo=False)
print("exported fp32", flush=True)
VARIANTS = {"per_tensor": False, "per_channel": True}
for name, pc in VARIANTS.items():
    quantize_dynamic(fp32, f"{OUT}/{name}.onnx", weight_type=QuantType.QInt8, per_channel=pc,
                     use_external_data_format=False)
    print(f"int8 {name}: {os.path.getsize(f'{OUT}/{name}.onnx') / 1e6:.0f} MB", flush=True)

# fp32 torch on the first 256 pairs: the full-precision reference the GPU's fp16 bake-off approximates
with torch.inference_mode():
    ref = np.concatenate([scorer(*[torch.from_numpy(x) for x in feeds(list(range(i, min(i + 16, 256))))]).numpy()
                          for i in range(0, 256, 16)])
order = sorted(range(len(enc)), key=lambda i: len(enc[i]))
so = ort.SessionOptions(); so.intra_op_num_threads = 4
measured = {}
for name in VARIANTS:
    sess = ort.InferenceSession(f"{OUT}/{name}.onnx", so, providers=["CPUExecutionProvider"])
    sc = np.zeros(len(enc), dtype=np.float32)
    t = time.time()
    for s in range(0, len(order), 16):
        idx = order[s:s + 16]
        i_, m_ = feeds(idx)
        sc[idx] = np.asarray(sess.run(None, {"input_ids": i_, "attention_mask": m_})[0], dtype=np.float32).reshape(-1)
    secs = time.time() - t
    np.save(f"{OUT}/scores-int8-{name}.npy", sc)
    d = sc[:256] - ref
    measured[name] = {"seconds_all_pairs": round(secs), "ms_per_pair": round(secs / len(enc) * 1000, 2),
                      "fp32_abs_diff_mean": float(np.abs(d).mean()), "fp32_abs_diff_max": float(np.abs(d).max()),
                      "fp32_corr": float(np.corrcoef(sc[:256], ref)[0, 1])}
    print(name, measured[name], flush=True)
# both variants are kept: the rule (dev NDCG@10 of the int8 scores, evals/rerank_eval.py) picks one locally, and
# that one is installed as model.onnx
tok.save_pretrained(f"{OUT}/tok")
os.replace(f"{OUT}/tok/tokenizer.json", f"{OUT}/tokenizer.json")
np.save(f"{OUT}/scores-fp32-first256.npy", ref.astype(np.float32))
json.dump({"model": hub, "revision": rev, "kind": kind, "max_tokens": max_len,
           "instruction": TASK if kind == "qwen" else ""}, open(f"{OUT}/reranker.json", "w"), indent=1)
json.dump({"variants": measured, "int8_mb": {n: round(os.path.getsize(f"{OUT}/{n}.onnx") / 1e6) for n in VARIANTS},
           "kaggle_cpu_threads": 4, "pairs": len(enc)}, open(f"{OUT}/validation.json", "w"), indent=1)
import shutil  # noqa: E402
shutil.rmtree(f"{OUT}/fp32"); shutil.rmtree(f"{OUT}/tok", ignore_errors=True)
print("done", flush=True)
