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
assert LOSS in ("listwise", "listwise+bce", "bce"), LOSS
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
        for g in chunk:
            cands = [random.choice(g["pos"])] + g["neg"]
            spans.append((len(pairs), len(cands)))
            pairs += [(g["q"], p) for p in cands]
        with torch.autocast("cuda", dtype=torch.float16, enabled=dev.type == "cuda"):
            s = batch_scores(model, pairs).float()
        lw = torch.stack([torch.nn.functional.cross_entropy(s[a:a + n].unsqueeze(0),
                                                            torch.zeros(1, dtype=torch.long, device=dev))
                          for a, n in spans]).mean()
        lab = torch.cat([torch.tensor([1.0] + [0.0] * (n - 1), device=dev) for _, n in spans])
        bce = torch.nn.functional.binary_cross_entropy_with_logits(s, lab)
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
model.load_state_dict(best_state)
model = model.float().cpu().eval()


class Scorer(torch.nn.Module):
    def __init__(self, m):
        super().__init__(); self.m = m

    def forward(self, input_ids, attention_mask):
        return self.m(input_ids=input_ids, attention_mask=attention_mask).logits[:, -1]


scorer = Scorer(model).eval()
vp = [(g["q"], p) for g in val[:64] for p in [g["pos"][0]] + g["neg"]]
enc = [tok(q, p, truncation="only_second", max_length=MAX_LEN)["input_ids"] for q, p in vp]


def feeds(idx):
    n = max(len(enc[i]) for i in idx)
    ids = np.full((len(idx), n), PAD, dtype=np.int64)
    mask = np.zeros((len(idx), n), dtype=np.int64)
    for r, i in enumerate(idx):
        ids[r, :len(enc[i])], mask[r, :len(enc[i])] = enc[i], 1
    return ids, mask


ids, mask = feeds([0, 1])
fp32 = f"{OUT}/fp32/model.onnx"
os.makedirs(f"{OUT}/fp32", exist_ok=True)
torch.onnx.export(scorer, (torch.from_numpy(ids), torch.from_numpy(mask)), fp32,
                  input_names=["input_ids", "attention_mask"], output_names=["score"],
                  dynamic_axes={"input_ids": {0: "b", 1: "t"}, "attention_mask": {0: "b", 1: "t"}, "score": {0: "b"}},
                  opset_version=17, dynamo=False)
quantize_dynamic(fp32, f"{OUT}/model.onnx", weight_type=QuantType.QInt8, per_channel=True,
                 use_external_data_format=False)
with torch.inference_mode():
    ref = np.concatenate([scorer(*[torch.from_numpy(x) for x in feeds(list(range(i, min(i + 16, len(enc)))))]).numpy()
                          for i in range(0, len(enc), 16)])
so = ort.SessionOptions(); so.intra_op_num_threads = 4
sess = ort.InferenceSession(f"{OUT}/model.onnx", so, providers=["CPUExecutionProvider"])
q8_parts = []
for i in range(0, len(enc), 16):
    ids_i, mask_i = feeds(list(range(i, min(i + 16, len(enc)))))
    q8_parts.append(np.asarray(sess.run(None, {"input_ids": ids_i, "attention_mask": mask_i})[0]).reshape(-1))
q8 = np.concatenate(q8_parts)
check = {"pairs": len(enc), "fp32_corr": float(np.corrcoef(q8, ref)[0, 1]),
         "fp32_abs_diff_mean": float(np.abs(q8 - ref).mean()), "fp32_abs_diff_max": float(np.abs(q8 - ref).max())}
print("int8 per_channel vs fp32", check, flush=True)
tok.save_pretrained(f"{OUT}/tok")
os.replace(f"{OUT}/tok/tokenizer.json", f"{OUT}/tokenizer.json")
json.dump({"model": HUB + f"+nizam-judgment-citations-v2-{LOSS}", "revision": REV, "kind": "cls", "max_tokens": MAX_LEN,
           "instruction": "", "variant": "fine-tuned (tools/kaggle/rerank_train_kernel.py, D-171), int8 dynamic, "
                                         "per channel"}, open(f"{OUT}/reranker.json", "w"), indent=1)
json.dump({"curve": curve, "loss": LOSS, "best_val_criterion": best, "train": len(train), "val": len(val), "epochs": EPOCHS, "lr": LR,
           "groups_per_step": GROUPS_PER_STEP, "seed": SEED, "int8_check": check, "exported": True,
           "int8_mb": round(os.path.getsize(f"{OUT}/model.onnx") / 1e6)}, open(f"{OUT}/train.json", "w"), indent=1)
import shutil  # noqa: E402
shutil.rmtree(f"{OUT}/fp32"); shutil.rmtree(f"{OUT}/tok", ignore_errors=True)
print("done", flush=True)
