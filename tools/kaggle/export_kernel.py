# Kaggle kernel: export the chosen embedding model as an int8 ONNX query encoder, and prove it (D-098).
# Pushed by `tools/kaggle/kg.sh exportpush NAME VERSION SLUG HUB POOLING`. The bake-off kernel's output (bits.npy, the
# corpus in binary) is attached as a kernel source, so int8 query bits are scored against the very vectors loaded.
#
#   1. load the model in fp32 (the reference) with sentence-transformers; read its pooling from the model's own config;
#   2. torch.onnx.export of the transformer (input_ids, attention_mask -> last hidden state), dynamic batch/sequence,
#      external data for weights over 2 GB; onnxruntime.quantization.quantize_dynamic -> int8 weights;
#   3. validate on the golden DEV questions: cosine(fp32, int8) of the pooled query vectors, the share of SIGN BITS
#      that agree (the stored form is binary), and dev recall@10/@50 with int8 query bits vs fp32 query bits against
#      the bake-off's corpus bits -- the same scoring as the bake-off;
#   4. write model.onnx (int8), tokenizer.json, encoder.json, validation.json to /kaggle/working/encoder/.
import json
import os
import subprocess
import sys
import time

SLUG, HUB, POOLING, REV = "__SLUG__", "__HUB__", "__POOLING__", "__REVISION__"
QTEMPLATE = json.loads('__QTEMPLATE__')
OUT = "/kaggle/working/encoder"
os.makedirs(OUT, exist_ok=True)
LOG = open("/kaggle/working/run.log", "a", buffering=1)


def log(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True); LOG.write(line + "\n")


subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "sentence-transformers>=3.4", "transformers>=4.51",
                "onnx", "onnxruntime", "onnxscript"], check=False)
import gzip  # noqa: E402
import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
import torch  # noqa: E402
from onnxruntime.quantization import QuantType, quantize_dynamic  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

import glob  # noqa: E402
# attached datasets and kernel outputs are nested below /kaggle/input: find them recursively
src = os.path.dirname(sorted(glob.glob("/kaggle/input/**/dev.json", recursive=True))[0])
bits_dir = os.path.dirname(os.path.dirname(os.path.dirname(
    sorted(glob.glob(f"/kaggle/input/**/out/{SLUG}/bits.npy", recursive=True))[0])))
revision = REV   # the commit the bake-off embedded the corpus with: tokenizer, weights and encoder.json all name it
log(f"{HUB}@{revision}; inputs {src}, corpus bits {bits_dir}")

ref = SentenceTransformer(HUB, device="cpu", revision=revision)
pool_mode = POOLING
tok = AutoTokenizer.from_pretrained(HUB, revision=revision)
model = AutoModel.from_pretrained(HUB, revision=revision, torch_dtype=torch.float32).eval()
model.config.use_cache = False


class Hidden(torch.nn.Module):
    def __init__(self, m):
        super().__init__(); self.m = m

    def forward(self, input_ids, attention_mask):
        return self.m(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state


ex = tok(["a short probe sentence"], return_tensors="pt")
fp32 = f"{OUT}/fp32/model.onnx"
os.makedirs(f"{OUT}/fp32", exist_ok=True)
torch.onnx.export(Hidden(model), (ex["input_ids"], ex["attention_mask"]), fp32,
                  input_names=["input_ids", "attention_mask"], output_names=["last_hidden_state"],
                  dynamic_axes={"input_ids": {0: "b", 1: "t"}, "attention_mask": {0: "b", 1: "t"},
                                "last_hidden_state": {0: "b", 1: "t"}},
                  opset_version=17, dynamo=False)
log("exported fp32")
# two int8 variants: one scale per weight tensor, or one per output channel (finer, usually closer to fp32); both are
# validated below and the one whose query bits score better on dev is kept
VARIANTS = {"per_tensor": False, "per_channel": True}
for name, pc in VARIANTS.items():
    quantize_dynamic(fp32, f"{OUT}/{name}.onnx", weight_type=QuantType.QInt8, per_channel=pc,
                     use_external_data_format=False)
    log(f"quantized int8 {name}: {os.path.getsize(f'{OUT}/{name}.onnx') / 1e6:.0f} MB")
tok.save_pretrained(f"{OUT}/tok")
os.replace(f"{OUT}/tok/tokenizer.json", f"{OUT}/tokenizer.json")
sess = None
names = set()


def onnx_embed(text):
    e = tok([text], return_tensors="np", truncation=True, max_length=512)
    feeds = {"input_ids": e["input_ids"].astype(np.int64), "attention_mask": e["attention_mask"].astype(np.int64)}
    h = sess.run(None, {k: v for k, v in feeds.items() if k in names})[0][0]
    m = e["attention_mask"][0]
    if pool_mode == "cls":
        v = h[0]
    elif pool_mode == "mean":
        v = (h * m[:, None]).sum(0) / m.sum()
    else:
        v = h[int(m.sum()) - 1]
    v = v[:1024].astype(np.float32)
    return v / np.linalg.norm(v)


dev = json.load(open(f"{src}/dev.json", encoding="utf-8"))
qs = [QTEMPLATE.format(q=c["q"]) for c in dev]
ref_v = ref.encode(qs, normalize_embeddings=True, convert_to_numpy=True)[:, :1024]
so = ort.SessionOptions(); so.intra_op_num_threads = 2      # as the host runs it (NIZAM_ENCODER_THREADS)
measured = {}
for name in VARIANTS:
    sess = ort.InferenceSession(f"{OUT}/{name}.onnx", so, providers=["CPUExecutionProvider"])
    names = {i.name for i in sess.get_inputs()}
    t = time.time()
    v8 = np.stack([onnx_embed(q) for q in qs])
    ms = (time.time() - t) / len(qs) * 1000
    c = (ref_v * v8).sum(1); b = ((ref_v > 0) == (v8 > 0)).mean(1)
    measured[name] = {"vectors": v8, "cpu_ms": ms, "cos": c, "bits": b}
    log(f"{name}: cosine fp32~int8 mean {c.mean():.4f} min {c.min():.4f}; sign bits agree mean {b.mean():.4f} "
        f"min {b.min():.4f}; {ms:.0f} ms/query on 2 Kaggle CPU threads")

# dev recall with int8 query bits vs fp32 query bits, against the corpus bits (bake-off scoring)
units, juris = [], []
CHUNKS = sorted(glob.glob("/kaggle/input/**/chunks.jsonl*", recursive=True))[0]   # Kaggle decompresses .gz uploads
with (gzip.open if CHUNKS.endswith(".gz") else open)(CHUNKS, "rt", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line); units.append(r["u"]); juris.append(r["j"])
units = np.asarray(units); jn = sorted(set(juris)); jidx = np.asarray([jn.index(j) for j in juris], dtype=np.int8)
cbits = np.load(f"{bits_dir}/out/{SLUG}/bits.npy")
if len(cbits) < len(units):        # a smoke run embedded the first chunks only, in file order: score over those
    log(f"corpus bits cover {len(cbits)} of {len(units)} chunks (smoke run): recall is over that prefix")
    units, jidx = units[:len(cbits)], jidx[:len(cbits)]
POP = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint16)


def recall(qbits):
    r10 = r50 = 0.0
    for c, qb in zip(dev, qbits):
        cand = np.nonzero(np.isin(jidx, [jn.index(j) for j in c["juris"] if j in jn]))[0]
        sims = -POP[np.bitwise_xor(cbits[cand], qb[None, :])].sum(1).astype(np.float32)
        k = min(3000, len(cand)); part = np.argpartition(-sims, k - 1)[:k]; part = part[np.argsort(-sims[part])]
        best = {}
        for row, s in zip(cand[part], sims[part]):
            u = int(units[row]); b = best.get(u)
            if b is None: best[u] = [s, -1e9]
            elif s > b[0]: best[u] = [s, b[0]]
            elif s > b[1]: best[u][1] = s
        ranked = [u for u, _ in sorted(best.items(), key=lambda kv: -(kv[1][0] + 0.15 * max(kv[1][1], 0)))][:50]
        gold = set(c["gold"]); tot = max(1, c["gold_total"])
        r10 += sum(1 for u in ranked[:10] if u in gold) / tot; r50 += sum(1 for u in ranked if u in gold) / tot
    return round(r10 / len(dev), 4), round(r50 / len(dev), 4)


r_ref = recall(np.packbits(ref_v > 0, axis=1))
for name, m in measured.items():
    m["recall"] = recall(np.packbits(m["vectors"] > 0, axis=1))
    log(f"dev recall@10/@50 with fp32 query bits {r_ref}, with {name} int8 query bits {m['recall']}")
# keep the variant with the better dev recall@50, then @10, then sign-bit agreement
best = max(measured, key=lambda n: (measured[n]["recall"][1], measured[n]["recall"][0], measured[n]["bits"].mean()))
os.replace(f"{OUT}/{best}.onnx", f"{OUT}/model.onnx")
for n in VARIANTS:
    if os.path.exists(f"{OUT}/{n}.onnx"):
        os.remove(f"{OUT}/{n}.onnx")
int8 = f"{OUT}/model.onnx"
cos, bit_agree, cpu_ms, r_int8 = (measured[best]["cos"], measured[best]["bits"], measured[best]["cpu_ms"],
                                  measured[best]["recall"])
log(f"kept {best}")
# the kept variant's dev query vectors, so the host can prove its encoder (tokenizers + onnxruntime, no torch)
# reproduces them: tests/test_encoder_model.py
np.save(f"{OUT}/dev_query_int8.npy", measured[best]["vectors"].astype(np.float32))
json.dump([c["q"] for c in dev], open(f"{OUT}/dev_questions.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"model": HUB, "revision": revision, "pooling": pool_mode, "query_template": QTEMPLATE,
           "max_tokens": 512, "dims": 1024}, open(f"{OUT}/encoder.json", "w"), indent=1)
json.dump({"cosine_mean": float(cos.mean()), "cosine_min": float(cos.min()),
           "sign_bits_agree_mean": float(bit_agree.mean()), "sign_bits_agree_min": float(bit_agree.min()),
           "kaggle_cpu_ms_per_query": round(cpu_ms), "dev_recall_fp32_query": r_ref, "dev_recall_int8_query": r_int8,
           "quantization": best,
           "variants": {n: {"cosine_mean": float(m["cos"].mean()), "sign_bits_agree_mean": float(m["bits"].mean()),
                            "dev_recall": m["recall"], "cpu_ms": round(m["cpu_ms"])} for n, m in measured.items()},
           "int8_mb": round(os.path.getsize(int8) / 1e6)}, open(f"{OUT}/validation.json", "w"), indent=1)
import shutil  # noqa: E402
shutil.rmtree(f"{OUT}/fp32"); shutil.rmtree(f"{OUT}/tok", ignore_errors=True)
log("done")
