# Kaggle GPU kernel: the question side of Qwen3-Embedding-8B with QUANTIZED weights (D-165 measurement): does a 4-bit
# (bitsandbytes NF4) or 8-bit (LLM.int8) encoder put questions where the fp16 encoder puts them, so the corpus vectors
# (embedded once in fp16, D-099/D-158) need not be re-embedded? Pushed by `tools/kaggle/kg.sh q4push NAME DATASET`.
#
# The dataset is a q8push dataset: questions.json (dev questions only; no gold leaves the laptop) and dev.json (the
# generation's own dev questions: their fp16 vectors are the encoder bundle's reference_q.npy, so the comparison is
# against the very vectors the corpus space was proved with). For each precision in turn, nf4 then int8, the model is
# loaded alone on GPU 0, the questions encoded exactly as query8b_kernel does (template, truncation, last token,
# normalised), the peak VRAM read, and single-question latency timed. Output (out/):
#   <p>_dev_q.npy  <p>_q.npy  (float32 [n, 4096])     <p>.json  (peak GiB, latency, library versions)
import gc
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
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers==4.51.3", "accelerate==1.6.0",
                "bitsandbytes"], check=False)
import bitsandbytes  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import transformers  # noqa: E402
from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig  # noqa: E402

if not REV:
    raise SystemExit("KG_REV is required: the corpus run's commit")
src = os.path.dirname(sorted(glob.glob("/kaggle/input/**/questions.json", recursive=True))[0])
questions = json.load(open(f"{src}/questions.json", encoding="utf-8"))
dev = json.load(open(f"{src}/dev.json", encoding="utf-8"))
tok = AutoTokenizer.from_pretrained(HUB, revision=REV, padding_side="left")
PRECISIONS = {
    "nf4": BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16,
                              bnb_4bit_use_double_quant=True),
    "int8": BitsAndBytesConfig(load_in_8bit=True),
}
summary = {}
for name, cfg in PRECISIONS.items():
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(0)
    t = time.time()
    model = AutoModel.from_pretrained(HUB, revision=REV, quantization_config=cfg, torch_dtype=torch.float16,
                                      device_map={"": 0}, attn_implementation="sdpa").eval()
    load_s = time.time() - t
    weights_gib = torch.cuda.memory_allocated(0) / 2**30

    @torch.inference_mode()
    def encode(texts):
        ids = tok([QT.format(q=" ".join(x.split())) for x in texts], truncation=True, max_length=512, padding=True,
                  return_tensors="pt").to("cuda:0")
        h = model(**ids).last_hidden_state
        return torch.nn.functional.normalize(h[:, -1, :].float(), dim=-1).cpu().numpy()

    np.save(f"{OUT}/{name}_dev_q.npy",
            np.concatenate([encode([c["q"] for c in dev[i:i + 8]]) for i in range(0, len(dev), 8)]))
    np.save(f"{OUT}/{name}_q.npy", np.concatenate([encode(questions[i:i + 8]) for i in range(0, len(questions), 8)]))
    for q in questions[:5]:
        encode([q])                                 # warm-up
    times = []
    for q in questions:
        torch.cuda.synchronize()
        s = time.perf_counter()
        encode([q])
        torch.cuda.synchronize()
        times.append((time.perf_counter() - s) * 1000)
    times.sort()
    summary[name] = {"gpu": torch.cuda.get_device_name(0), "load_seconds": round(load_s),
                     "weights_gib": round(weights_gib, 2),
                     "peak_gib": round(torch.cuda.max_memory_allocated(0) / 2**30, 2),
                     "latency_ms": {"p50": round(times[len(times) // 2], 1),
                                    "p95": round(times[int(0.95 * (len(times) - 1))], 1)},
                     "versions": {"torch": torch.__version__, "transformers": transformers.__version__,
                                  "bitsandbytes": bitsandbytes.__version__}, "revision": REV}
    json.dump(summary[name], open(f"{OUT}/{name}.json", "w"), indent=1)
    print(name, summary[name], flush=True)
    del model
    gc.collect()
json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=1)
