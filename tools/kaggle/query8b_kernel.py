# Kaggle GPU kernel: encode questions with Qwen3-Embedding-8B exactly as the corpus run did (D-099), and time it.
# Pushed by `tools/kaggle/kg.sh q8push NAME DATASET`. The dataset holds questions.json (a list of texts -- the golden
# TEST questions, once, after the configuration is frozen; no gold leaves the laptop) and dev.json (re-encoded: they
# must reproduce the corpus run's dev vectors, the proof that this is the same space).
#
# Output: out/q.npy (float32 [n, 4096], questions.json order), out/dev_q.npy, out/latency.json -- one question at a
# time, batch 1, after warm-up: what a GPU host's encoder spends per request (the T4 is a slow card; a serving GPU
# is faster).
import glob
import json
import os
import subprocess
import sys
import time

REV = "__REV__"
HUB = "Qwen/Qwen3-Embedding-8B"
TASK = "Given a question about Pakistani law, retrieve the statutory provisions that answer it"
QT = "Instruct: " + TASK + "\nQuery:{q}"
OUT = "/kaggle/working/out"
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers==4.51.3", "accelerate==1.6.0"], check=False)
import numpy as np  # noqa: E402
import torch  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402
from safetensors import safe_open  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

if not REV:
    raise SystemExit("KG_REV is required: the corpus run's commit")
src = os.path.dirname(sorted(glob.glob("/kaggle/input/**/questions.json", recursive=True))[0])
questions = json.load(open(f"{src}/questions.json", encoding="utf-8"))
dev = json.load(open(f"{src}/dev.json", encoding="utf-8"))
tok = AutoTokenizer.from_pretrained(HUB, revision=REV, padding_side="left")
idx = json.load(open(hf_hub_download(HUB, "model.safetensors.index.json", revision=REV), encoding="utf-8"))
key = next(k for k in idx["weight_map"] if k.endswith("embed_tokens.weight"))
with safe_open(hf_hub_download(HUB, idx["weight_map"][key], revision=REV), "pt") as f:
    embed = torch.nn.Embedding.from_pretrained(f.get_tensor(key).to(torch.float16), freeze=True)
model = AutoModel.from_pretrained(HUB, revision=REV, torch_dtype=torch.float16,
                                  device_map={"embed_tokens": "cpu", "layers": 0, "norm": 0, "rotary_emb": 0},
                                  attn_implementation="sdpa").eval()


@torch.inference_mode()
def encode(texts):
    ids = tok([QT.format(q=" ".join(t.split())) for t in texts], truncation=True, max_length=512, padding=True,
              return_tensors="pt")
    x = embed(ids.input_ids).to("cuda:0")
    h = model(inputs_embeds=x, attention_mask=ids.attention_mask.to("cuda:0")).last_hidden_state
    return torch.nn.functional.normalize(h[:, -1, :].float(), dim=-1).cpu().numpy()


np.save(f"{OUT}/dev_q.npy", np.concatenate([encode([c["q"] for c in dev[i:i + 8]]) for i in range(0, len(dev), 8)]))
np.save(f"{OUT}/q.npy", np.concatenate([encode(questions[i:i + 8]) for i in range(0, len(questions), 8)]))
for q in questions[:5]:
    encode([q])                                     # warm-up
times = []
for q in questions:
    torch.cuda.synchronize()
    t = time.perf_counter()
    encode([q])
    torch.cuda.synchronize()
    times.append((time.perf_counter() - t) * 1000)
times.sort()
lat = {"gpu": torch.cuda.get_device_name(0), "n": len(times), "p50_ms": round(times[len(times) // 2], 1),
       "p95_ms": round(times[int(0.95 * (len(times) - 1))], 1), "max_ms": round(times[-1], 1),
       "note": "batch 1, fp16, token table looked up on the CPU; includes tokenisation and the copy back"}
json.dump(lat, open(f"{OUT}/latency.json", "w"), indent=1)
print(lat)
