# Kaggle kernel: fine-tune the CPU profile's reranker (mMiniLM, D-101) on the courts' citations of the statutes, then
# export it as the int8 ONNX graph nizam.inference.reranker serves (D-171). Pushed by
# `tools/kaggle/kg.sh rrtrainpush NAME DATASET`; the dataset is tools/rerank_train_pairs.py's groups.jsonl.
#
#   1. load cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 at the pinned revision (the one served since D-101);
#   2. train listwise: per group, softmax cross-entropy of the positive against the slate's hard negatives (one
#      positive drawn per epoch when a sentence cites two units); AdamW, linear warmup, fp16 autocast on the T4;
#   3. every EVAL_EVERY steps, the held-out judgments' groups (split "val", never the golden set): MRR and accuracy@1
#      of the positive among its group; the best checkpoint is kept (and the untrained model's figure is reported);
#   4. export the best checkpoint exactly as tools/kaggle/rerank_export_kernel.py exports the base model (one logit per
#      pair; input_ids, attention_mask; dynamic batch and sequence), quantize int8 dynamic PER CHANNEL (D-101's variant),
#      and check the int8 graph against fp32 torch on val pairs;
#   5. write /kaggle/working/reranker/: model.onnx, tokenizer.json, reranker.json, train.json (the curve, the counts).
# The decision is NOT made here: the local served path on the golden dev split decides (evals/lexical_benchmark.py).
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
EPOCHS, LR, GROUPS_PER_STEP, WARMUP, EVAL_EVERY, SEED = 2, 2e-5, 8, 0.1, 150, 20261127
SMOKE = "__SMOKE__" == "1"
# D-171 follow-up: "listwise" (softmax over each group, D-171), "listwise+bce" (plus a per-pair yes/no, so a score
# means the same across questions -- what the gate reads), "bce" (the per-pair loss alone)
LOSS = "__LOSS__" if not "__LOSS__".startswith("__") else "listwise"
# weight interpolation (WiSE-FT style): base + alpha * (fine-tuned - base) for each alpha, each exported beside the
# fine-tuned model, with a per-layer report of what the fine-tune changed. "" = none
MERGE = [float(x) for x in "__MERGE__".split(",") if x] if not "__MERGE__".startswith("__") else []
# "distill" (D-175): learn Qwen3-Reranker-8B's scores on each group (g["teacher"]): listwise KL to its softmax plus
# MSE to its logits, so the student inherits the teacher's order AND its cross-question scale; no hard labels
assert LOSS in ("listwise", "listwise+bce", "bce", "distill"), LOSS
MSE_W = 0.5
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)

src = sorted(glob.glob("/kaggle/input/**/groups.jsonl", recursive=True))[0]
groups = [json.loads(line) for line in open(src, encoding="utf-8")]
train = [g for g in groups if g["split"] == "train"]
val = [g for g in groups if g["split"] == "val"]
if SMOKE:
    train, val = train[:64], val[:32]
print(f"{len(train)} train groups, {len(val)} val groups from {src}", flush=True)

dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tok = AutoTokenizer.from_pretrained(HUB, revision=REV)
model = AutoModelForSequenceClassification.from_pretrained(HUB, revision=REV, torch_dtype=torch.float32).to(dev)
PAD = tok.pad_token_id
base_sd = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}       # the served weights


def group_of(name: str) -> str:
    """embeddings | layer.NN.attention | layer.NN.ffn | layer.NN.norm | pooler | classifier | other"""
    import re as _re
    m = _re.search(r"layer\.(\d+)\.", name)
    if m:
        part = ("norm" if "LayerNorm" in name else
                "attention" if ".attention." in name else "ffn")
        return f"layer.{int(m.group(1)):02d}.{part}"
    for g in ("embeddings", "pooler", "classifier"):
        if g in name:
            return g
    return "other"


arch = {"config": {k: getattr(model.config, k, None) for k in ("model_type", "num_hidden_layers", "hidden_size",
                                                               "num_attention_heads", "intermediate_size",
                                                               "vocab_size", "max_position_embeddings")},
        "params_total": sum(v.numel() for v in base_sd.values() if v.dtype.is_floating_point), "groups": {}}
for k, v in base_sd.items():
    if v.dtype.is_floating_point:
        g = group_of(k)
        g = g.split(".")[0] + "." + g.split(".")[-1] if g.startswith("layer.") else g
        arch["groups"][g] = arch["groups"].get(g, 0) + v.numel()
print("architecture", json.dumps(arch), flush=True)


def batch_scores(m, q_and_p: list[tuple[str, str]]) -> torch.Tensor:
    t = tok([q for q, _ in q_and_p], [p for _, p in q_and_p], truncation="only_second", max_length=MAX_LEN,
            padding=True, return_tensors="pt").to(dev)
    return m(**t).logits[:, -1]


@torch.inference_mode()
def evaluate(m) -> dict:
    m.eval()
    rr, top1, pos_s, neg_s = [], 0, [], []
    for g in val:
        cands = [g["pos"][0]] + g["neg"]
        with torch.autocast("cuda", dtype=torch.float16, enabled=dev.type == "cuda"):
            s = batch_scores(m, [(g["q"], p) for p in cands]).float().cpu().numpy()
        rank = 1 + int((s[1:] > s[0]).sum())
        rr.append(1.0 / rank)
        top1 += rank == 1
        pos_s.append(float(s[0])); neg_s += [float(x) for x in s[1:]]
    m.train()
    # global AUC: a positive of ANY question above a negative of ANY question -- cross-question comparability
    allv = np.array(pos_s + neg_s); lab = np.array([1] * len(pos_s) + [0] * len(neg_s))
    order = allv.argsort(); ranks = np.empty(len(allv)); ranks[order] = np.arange(1, len(allv) + 1)
    auc = (ranks[lab == 1].sum() - len(pos_s) * (len(pos_s) + 1) / 2) / max(len(pos_s) * len(neg_s), 1)
    return {"mrr": round(float(np.mean(rr)), 4), "acc1": round(top1 / max(len(val), 1), 4),
            "global_auc": round(float(auc), 4)}


def select(e: dict) -> float:
    """the checkpoint criterion: MRR for the listwise model (D-171); with the per-pair loss, MRR and global AUC"""
    return e["mrr"] if LOSS == "listwise" else (e["mrr"] + e["global_auc"]) / 2


curve = [{"step": 0, **evaluate(model)}]
print("untrained", curve[0], flush=True)
steps_per_epoch = math.ceil(len(train) / GROUPS_PER_STEP)
total = steps_per_epoch * EPOCHS
opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
sched = get_linear_schedule_with_warmup(opt, int(total * WARMUP), total)
scaler = torch.amp.GradScaler("cuda", enabled=dev.type == "cuda")
best, best_state, step, t0 = select(curve[0]), None, 0, time.time()
model.train()
for epoch in range(EPOCHS):
    random.shuffle(train)
    for b in range(0, len(train), GROUPS_PER_STEP):
        chunk = train[b:b + GROUPS_PER_STEP]
        pairs, spans = [], []
        teach = []
        for g in chunk:
            pi = random.randrange(len(g["pos"]))
            cands = [g["pos"][pi]] + g["neg"]
            spans.append((len(pairs), len(cands)))
            pairs += [(g["q"], p) for p in cands]
            if LOSS == "distill":
                teach += [g["teacher"]["pos"][pi]] + list(g["teacher"]["neg"])
        with torch.autocast("cuda", dtype=torch.float16, enabled=dev.type == "cuda"):
            s = batch_scores(model, pairs).float()
        lw = torch.stack([torch.nn.functional.cross_entropy(s[a:a + n].unsqueeze(0),
                                                            torch.zeros(1, dtype=torch.long, device=dev))
                          for a, n in spans]).mean()
        lab = torch.cat([torch.tensor([1.0] + [0.0] * (n - 1), device=dev) for _, n in spans])
        bce = torch.nn.functional.binary_cross_entropy_with_logits(s, lab)
        if LOSS == "distill":
            t = torch.tensor(teach, device=dev, dtype=torch.float32)
            kl = torch.stack([torch.nn.functional.kl_div(torch.log_softmax(s[a:a + n], 0), torch.softmax(t[a:a + n], 0),
                                                         reduction="sum") for a, n in spans]).mean()
            loss = kl + MSE_W * torch.nn.functional.mse_loss(s, t)
        else:
            loss = lw if LOSS == "listwise" else (bce if LOSS == "bce" else lw + bce)
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt); scaler.update(); sched.step()
        step += 1
        if step % EVAL_EVERY == 0 or step == total:
            e = {"step": step, "epoch": epoch, "loss": round(float(loss), 4), **evaluate(model),
                 "seconds": round(time.time() - t0)}
            curve.append(e)
            print(e, flush=True)
            if select(e) > best:
                best = select(e)
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
if best_state is None:
    print("no checkpoint beat the untrained model on val: exporting nothing", flush=True)
    json.dump({"curve": curve, "train": len(train), "val": len(val), "exported": False},
              open(f"{OUT}/train.json", "w"), indent=1)
    sys.exit(0)
ft_sd = best_state


def weight_report() -> dict:
    """what the fine-tune changed, per group: relative change ||ft - base|| / ||base||, and the share of all change"""
    rows, tot = {}, 0.0
    for k, b in base_sd.items():
        if not b.dtype.is_floating_point:
            continue
        d = ft_sd[k].float() - b.float()
        dn, bn = float(d.norm()), float(b.float().norm())
        r = rows.setdefault(group_of(k), {"delta_sq": 0.0, "base_sq": 0.0, "params": 0})
        r["delta_sq"] += dn * dn
        r["base_sq"] += bn * bn
        r["params"] += b.numel()
        tot += dn * dn
    return {g: {"relative_change": round((r["delta_sq"] ** 0.5) / max(r["base_sq"] ** 0.5, 1e-12), 6),
                "share_of_change": round(r["delta_sq"] / max(tot, 1e-12), 4), "params": r["params"]}
            for g, r in sorted(rows.items())}


wr = weight_report()
print("weight change by group:", json.dumps(wr)[:4000], flush=True)


class Scorer(torch.nn.Module):
    def __init__(self, m):
        super().__init__(); self.m = m

    def forward(self, input_ids, attention_mask):
        return self.m(input_ids=input_ids, attention_mask=attention_mask).logits[:, -1]


vp = [(g["q"], p) for g in val[:64] for p in [g["pos"][0]] + g["neg"]]
enc = [tok(q, p, truncation="only_second", max_length=MAX_LEN)["input_ids"] for q, p in vp]


def feeds(idx):
    n = max(len(enc[i]) for i in idx)
    ids = np.full((len(idx), n), PAD, dtype=np.int64)
    mask = np.zeros((len(idx), n), dtype=np.int64)
    for r, i in enumerate(idx):
        ids[r, :len(enc[i])], mask[r, :len(enc[i])] = enc[i], 1
    return ids, mask


def export(sd: dict, out: str, tag: str) -> dict:
    """the state dict as the served int8 graph (one logit per pair), checked against fp32 on val pairs"""
    import shutil
    os.makedirs(f"{out}/fp32", exist_ok=True)
    model.load_state_dict(sd)
    m = model.float().cpu().eval()
    scorer = Scorer(m).eval()
    ids, mask = feeds([0, 1])
    torch.onnx.export(scorer, (torch.from_numpy(ids), torch.from_numpy(mask)), f"{out}/fp32/model.onnx",
                      input_names=["input_ids", "attention_mask"], output_names=["score"],
                      dynamic_axes={"input_ids": {0: "b", 1: "t"}, "attention_mask": {0: "b", 1: "t"},
                                    "score": {0: "b"}}, opset_version=17, dynamo=False)
    quantize_dynamic(f"{out}/fp32/model.onnx", f"{out}/model.onnx", weight_type=QuantType.QInt8, per_channel=True,
                     use_external_data_format=False)
    with torch.inference_mode():
        ref = np.concatenate([scorer(*[torch.from_numpy(x) for x in feeds(list(range(i, min(i + 16, len(enc)))))])
                              .numpy() for i in range(0, len(enc), 16)])
    so = ort.SessionOptions()
    so.intra_op_num_threads = 4
    sess = ort.InferenceSession(f"{out}/model.onnx", so, providers=["CPUExecutionProvider"])
    parts = []
    for i in range(0, len(enc), 16):
        ids_i, mask_i = feeds(list(range(i, min(i + 16, len(enc)))))
        parts.append(np.asarray(sess.run(None, {"input_ids": ids_i, "attention_mask": mask_i})[0]).reshape(-1))
    q8 = np.concatenate(parts)
    check = {"pairs": len(enc), "fp32_corr": float(np.corrcoef(q8, ref)[0, 1]),
             "fp32_abs_diff_mean": float(np.abs(q8 - ref).mean())}
    tok.save_pretrained(f"{out}/tok")
    os.replace(f"{out}/tok/tokenizer.json", f"{out}/tokenizer.json")
    json.dump({"model": HUB + f"+nizam-judgment-citations-v2-{tag}", "revision": REV, "kind": "cls",
               "max_tokens": MAX_LEN, "instruction": "",
               "variant": f"fine-tuned ({tag}; tools/kaggle/rerank_train_kernel.py, D-171), int8 dynamic, per channel"},
              open(f"{out}/reranker.json", "w"), indent=1)
    shutil.rmtree(f"{out}/fp32")
    shutil.rmtree(f"{out}/tok", ignore_errors=True)
    model.to(dev)
    print(tag, "int8 vs fp32", check, flush=True)
    return check


check = export(ft_sd, OUT, LOSS)
merges = []
for a in MERGE:
    sd = {k: (b.float() + a * (ft_sd[k].float() - b.float())).to(b.dtype) if b.dtype.is_floating_point else b
          for k, b in base_sd.items()}
    model.load_state_dict(sd)
    model.to(dev)
    e = evaluate(model)
    tag = f"{LOSS}-a{a:g}"
    c = export(sd, f"{OUT}/a{a:g}", tag)
    merges.append({"alpha": a, **e, "int8_check": c})
    print("merge", merges[-1], flush=True)
json.dump({"curve": curve, "loss": LOSS, "best_val_criterion": best, "train": len(train), "val": len(val),
           "epochs": EPOCHS, "lr": LR, "groups_per_step": GROUPS_PER_STEP, "seed": SEED, "int8_check": check,
           "exported": True, "int8_mb": round(os.path.getsize(f"{OUT}/model.onnx") / 1e6),
           "architecture": arch, "weight_change": wr, "merges": merges}, open(f"{OUT}/train.json", "w"), indent=1)
print("done", flush=True)
