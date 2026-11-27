# Kaggle GPU kernel: a per-layer weight-merge search for the CPU reranker (D-177). Pushed by
# `tools/kaggle/kg.sh rrmergepush NAME DATASET`; the dataset is tools/rerank_train_pairs.py's groups.jsonl.
#
#   1. the served model (mmarco-mMiniLMv2-L12 at its pinned revision) and two fine-tunes retrained with the D-171
#      recipe and seed: "listwise" (best ranking) and "listwise+bce" (best gate among the fine-tunes);
#   2. a merged model is base + sum_k a[k][g] * (ft_k - base), one coefficient a per fine-tune k and per part g
#      (embeddings, each of the 12 layers, the head): 28 knobs in [0, 1.2];
#   3. the objective is the held-out judgments' (mean of MRR and cross-question AUC: the gate needs comparable
#      scores), on HALF A of the val groups only; random search, then hill-climbing around the best;
#   4. the 10 best on half A are re-scored on half B (never searched); the 3 best on half B are exported as the
#      served int8 graph (one logit per pair; per channel), with their coefficients.
# The decision is NOT made here: law dev through the served CPU path and gate decides (local), test once after.
import glob
import json
import math
import os
import random
import subprocess
import sys
import time

OUT = "/kaggle/working/reranker"
os.makedirs(OUT, exist_ok=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers==4.51.3", "onnx", "onnxruntime",
                "onnxscript"], check=False)
import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
import torch  # noqa: E402
from onnxruntime.quantization import QuantType, quantize_dynamic  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup  # noqa

HUB, REV, MAX_LEN = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "1427fd652930e4ba29e8149678df786c240d8825", 512
EPOCHS, LR, GPS, WARMUP, SEED = 2, 2e-5, 8, 0.1, 20261127
RANDOM_TRIALS, CLIMB_TRIALS, SIGMA, AMAX = 60, 90, 0.15, 1.2
SMOKE = "__SMOKE__" == "1"
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
t_all = time.time()

src = sorted(glob.glob("/kaggle/input/**/groups.jsonl", recursive=True))[0]
groups = [json.loads(line) for line in open(src, encoding="utf-8")]
train = [g for g in groups if g["split"] == "train"]
val = [g for g in groups if g["split"] == "val"]
rng = random.Random(SEED)
rng.shuffle(val)
val_a, val_b = val[:len(val) // 2], val[len(val) // 2:]
if SMOKE:
    train, val_a, val_b = train[:48], val_a[:16], val_b[:16]
    RANDOM_TRIALS, CLIMB_TRIALS = 3, 3
print(f"{len(train)} train, val A {len(val_a)}, val B {len(val_b)}", flush=True)

dev = torch.device("cuda")
tok = AutoTokenizer.from_pretrained(HUB, revision=REV)
model = AutoModelForSequenceClassification.from_pretrained(HUB, revision=REV, torch_dtype=torch.float32).to(dev)
PAD = tok.pad_token_id
base_sd = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}


def scores(pairs):
    t = tok([q for q, _ in pairs], [p for _, p in pairs], truncation="only_second", max_length=MAX_LEN,
            padding=True, return_tensors="pt").to(dev)
    return model(**t).logits[:, -1]


@torch.inference_mode()
def evaluate(vs) -> dict:
    model.eval()
    rr, pos_s, neg_s = [], [], []
    for g in vs:
        cands = [g["pos"][0]] + g["neg"]
        with torch.autocast("cuda", dtype=torch.float16):
            s = scores([(g["q"], p) for p in cands]).float().cpu().numpy()
        rr.append(1.0 / (1 + int((s[1:] > s[0]).sum())))
        pos_s.append(float(s[0])); neg_s += [float(x) for x in s[1:]]
    allv = np.array(pos_s + neg_s); lab = np.array([1] * len(pos_s) + [0] * len(neg_s))
    o = allv.argsort(); r = np.empty(len(allv)); r[o] = np.arange(1, len(allv) + 1)
    auc = (r[lab == 1].sum() - len(pos_s) * (len(pos_s) + 1) / 2) / max(len(pos_s) * len(neg_s), 1)
    m, a = float(np.mean(rr)), float(auc)
    return {"mrr": round(m, 4), "global_auc": round(a, 4), "objective": round((m + a) / 2, 5)}


def fine_tune(loss_kind: str) -> dict:
    model.load_state_dict(base_sd)
    model.train()
    steps = math.ceil(len(train) / GPS) * EPOCHS
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(opt, int(steps * WARMUP), steps)
    scaler = torch.amp.GradScaler("cuda")
    r = random.Random(SEED)
    torch.manual_seed(SEED)
    for _ in range(EPOCHS):
        tr = train[:]
        r.shuffle(tr)
        for b in range(0, len(tr), GPS):
            pairs, spans = [], []
            for g in tr[b:b + GPS]:
                cands = [r.choice(g["pos"])] + g["neg"]
                spans.append((len(pairs), len(cands)))
                pairs += [(g["q"], p) for p in cands]
            with torch.autocast("cuda", dtype=torch.float16):
                s = scores(pairs).float()
            lw = torch.stack([torch.nn.functional.cross_entropy(s[a:a + n].unsqueeze(0),
                                                                torch.zeros(1, dtype=torch.long, device=dev))
                              for a, n in spans]).mean()
            if loss_kind == "listwise+bce":
                lab = torch.cat([torch.tensor([1.0] + [0.0] * (n - 1), device=dev) for _, n in spans])
                lw = lw + torch.nn.functional.binary_cross_entropy_with_logits(s, lab)
            opt.zero_grad(set_to_none=True)
            scaler.scale(lw).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt); scaler.update(); sched.step()
    return {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}


def part_of(name: str) -> int:
    """0 embeddings, 1..12 layers 0..11, 13 head (pooler, classifier, anything else)"""
    import re
    m = re.search(r"layer\.(\d+)\.", name)
    if m:
        return 1 + int(m.group(1))
    return 0 if "embeddings" in name else 13


FTS = ["listwise", "listwise+bce"]
deltas = []
for kind in FTS:
    t0 = time.time()
    sd = fine_tune(kind)
    deltas.append({k: (sd[k].float() - base_sd[k].float()) for k in base_sd if base_sd[k].dtype.is_floating_point})
    print(f"fine-tuned {kind} in {time.time() - t0:.0f}s", flush=True)
PARTS = 14
part = {k: part_of(k) for k in base_sd}


def build(a: np.ndarray) -> dict:
    """a: shape (len(FTS), PARTS)"""
    sd = {}
    for k, b in base_sd.items():
        if not b.dtype.is_floating_point:
            sd[k] = b
            continue
        v = b.float().clone()
        for i in range(len(FTS)):
            c = float(a[i, part[k]])
            if c:
                v += c * deltas[i][k]
        sd[k] = v.to(b.dtype)
    return sd


trials = []


def trial(a: np.ndarray, label: str) -> dict:
    model.load_state_dict(build(a))
    e = evaluate(val_a)
    rec = {"label": label, "a": np.round(a, 4).tolist(), **{f"A_{k}": v for k, v in e.items()}}
    trials.append(rec)
    return rec


base_a = np.zeros((len(FTS), PARTS))
starts = {"base": base_a, "listwise": np.vstack([np.ones(PARTS), np.zeros(PARTS)]),
          "listwise+bce": np.vstack([np.zeros(PARTS), np.ones(PARTS)]), "half-half": np.full((len(FTS), PARTS), 0.5)}
for name, a in starts.items():
    print("start", trial(a, name), flush=True)
for i in range(RANDOM_TRIALS):
    a = np.clip(np.random.uniform(0, 1, (len(FTS), PARTS)) * np.random.choice([0.0, 1.0], (len(FTS), 1)) * AMAX,
                0, AMAX) if i % 3 == 0 else np.random.uniform(0, AMAX, (len(FTS), PARTS))
    trial(a, f"random{i}")
best = max(trials, key=lambda t: t["A_objective"])
cur, cur_obj = np.array(best["a"]), best["A_objective"]
for i in range(CLIMB_TRIALS):
    a = np.clip(cur + np.random.normal(0, SIGMA, cur.shape), 0, AMAX)
    rec = trial(a, f"climb{i}")
    if rec["A_objective"] > cur_obj:
        cur, cur_obj = a, rec["A_objective"]
        print("climb improved", round(cur_obj, 5), flush=True)
print(f"{len(trials)} trials on val A in {time.time() - t_all:.0f}s", flush=True)

top = sorted(trials, key=lambda t: -t["A_objective"])[:10]
for t in top + [t for t in trials if t["label"] in starts]:
    if "B_objective" not in t:
        model.load_state_dict(build(np.array(t["a"])))
        t.update({f"B_{k}": v for k, v in evaluate(val_b).items()})
finalists = sorted(top, key=lambda t: -t["B_objective"])[:3]


class Scorer(torch.nn.Module):
    def __init__(self, m):
        super().__init__(); self.m = m

    def forward(self, input_ids, attention_mask):
        return self.m(input_ids=input_ids, attention_mask=attention_mask).logits[:, -1]


vp = [(g["q"], p) for g in val_b[:48] for p in [g["pos"][0]] + g["neg"]]
enc = [tok(q, p, truncation="only_second", max_length=MAX_LEN)["input_ids"] for q, p in vp]


def feeds(idx):
    n = max(len(enc[i]) for i in idx)
    ids = np.full((len(idx), n), PAD, dtype=np.int64)
    mask = np.zeros((len(idx), n), dtype=np.int64)
    for r, i in enumerate(idx):
        ids[r, :len(enc[i])], mask[r, :len(enc[i])] = enc[i], 1
    return ids, mask


def export(sd, out, tag):
    import shutil
    os.makedirs(f"{out}/fp32", exist_ok=True)
    model.load_state_dict(sd)
    m = model.float().cpu().eval()
    sc = Scorer(m).eval()
    ids, mask = feeds([0, 1])
    torch.onnx.export(sc, (torch.from_numpy(ids), torch.from_numpy(mask)), f"{out}/fp32/model.onnx",
                      input_names=["input_ids", "attention_mask"], output_names=["score"],
                      dynamic_axes={"input_ids": {0: "b", 1: "t"}, "attention_mask": {0: "b", 1: "t"},
                                    "score": {0: "b"}}, opset_version=17, dynamo=False)
    quantize_dynamic(f"{out}/fp32/model.onnx", f"{out}/model.onnx", weight_type=QuantType.QInt8, per_channel=True,
                     use_external_data_format=False)
    with torch.inference_mode():
        ref = np.concatenate([sc(*[torch.from_numpy(x) for x in feeds(list(range(i, min(i + 16, len(enc)))))])
                              .numpy() for i in range(0, len(enc), 16)])
    so = ort.SessionOptions(); so.intra_op_num_threads = 4
    sess = ort.InferenceSession(f"{out}/model.onnx", so, providers=["CPUExecutionProvider"])
    q8 = np.concatenate([np.asarray(sess.run(None, dict(zip(("input_ids", "attention_mask"),
                                                            feeds(list(range(i, min(i + 16, len(enc))))))))[0])
                         .reshape(-1) for i in range(0, len(enc), 16)])
    tok.save_pretrained(f"{out}/tok")
    os.replace(f"{out}/tok/tokenizer.json", f"{out}/tokenizer.json")
    json.dump({"model": HUB + f"+nizam-merge-{tag}", "revision": REV, "kind": "cls", "max_tokens": MAX_LEN,
               "instruction": "", "variant": f"per-layer merge {tag} (tools/kaggle/rerank_merge_kernel.py, D-177), "
                                             "int8 dynamic, per channel"}, open(f"{out}/reranker.json", "w"), indent=1)
    shutil.rmtree(f"{out}/fp32"); shutil.rmtree(f"{out}/tok", ignore_errors=True)
    model.to(dev)
    return {"fp32_corr": float(np.corrcoef(q8, ref)[0, 1])}


for i, t in enumerate(finalists, 1):
    t["int8_check"] = export(build(np.array(t["a"])), f"{OUT}/m{i}", f"m{i}")
    json.dump(t, open(f"{OUT}/m{i}/merge.json", "w"), indent=1)
    print("finalist", i, {k: t[k] for k in t if k != "a"}, flush=True)
json.dump({"fine_tunes": FTS, "parts": ["embeddings"] + [f"layer.{i:02d}" for i in range(12)] + ["head"],
           "val_a": len(val_a), "val_b": len(val_b), "trials": trials, "finalists": finalists,
           "seconds": round(time.time() - t_all)}, open(f"{OUT}/search.json", "w"), indent=1)
print("done", flush=True)
