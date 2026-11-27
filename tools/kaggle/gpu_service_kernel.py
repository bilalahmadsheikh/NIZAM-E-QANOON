# Kaggle GPU kernel: prove the GPU inference service (D-178) end to end with the REAL clients. The dataset holds the
# repository's own nizam/inference/*.py (unchanged) and the host bundles models/encoder-gpu-nf4 (4-bit, D-169) and
# models/reranker-gpu. The service starts in this kernel (uvicorn, 127.0.0.1:8090) with both 8B models loaded; then
# RemoteEncoder and RemoteReranker are constructed against it, which runs their own reference checks (encoder: cosine
# >= 0.99 against the nf4 reference vectors; reranker: Spearman >= 0.98 against the D-101 bake-off scores), and the
# request latencies the app will see are timed (one question; 10 and 50 passages at 1,600 characters).
# Output: out/proof.json. Pushed by `kg.sh gpusvcpush NAME DATASET`.
import glob
import json
import os
import subprocess
import sys
import threading
import time

OUT = "/kaggle/working/out"
os.makedirs(OUT, exist_ok=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers==4.51.3", "accelerate==1.6.0",
                "bitsandbytes", "fastapi", "uvicorn"], check=False)
found = sorted(glob.glob("/kaggle/input/**/nizam/inference/gpu_service.py", recursive=True))
if not found:                                                 # folders uploaded as zips (kg.sh KG_DIR_MODE=zip) and kept
    import zipfile
    os.makedirs("/kaggle/working/src", exist_ok=True)
    for z in glob.glob("/kaggle/input/**/*.zip", recursive=True):
        name = os.path.splitext(os.path.basename(z))[0]
        zipfile.ZipFile(z).extractall(os.path.join("/kaggle/working/src", name))
    found = sorted(glob.glob("/kaggle/working/src/**/nizam/inference/gpu_service.py", recursive=True))
root = os.path.dirname(os.path.dirname(os.path.dirname(found[0])))   # the folder holding nizam/
sys.path.insert(0, root)
models = os.path.join(root, "models")
os.environ["NIZAM_GPU_SERVICE_ENCODER_DEVICE"] = "0"
os.environ["NIZAM_GPU_SERVICE_RERANKER_DEVICE"] = "auto"
os.environ["NIZAM_GPU_SERVICE_MAX_MEMORY"] = "0:6GiB,1:15GiB"   # encoder (~7 GiB) on card 0, the reranker mostly on 1
import numpy as np  # noqa: E402
import torch  # noqa: E402

proof = {"gpus": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}
t0 = time.time()
from nizam.inference import gpu_service as S  # noqa: E402

enc = S.EncoderBackend(os.path.join(models, "encoder-gpu-nf4"))
rr = S.RerankerBackend(os.path.join(models, "reranker-gpu"))
proof["load_seconds"] = round(time.time() - t0)
proof["vram_gib_after_load"] = [round(torch.cuda.memory_allocated(i) / 2**30, 2) for i in range(torch.cuda.device_count())]
app = S.create_app(enc, rr)
import uvicorn  # noqa: E402

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8090, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(120):
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:8090/health", timeout=2).read()
        break
    except Exception:  # noqa: BLE001
        time.sleep(1)
proof["health"] = json.loads(urllib.request.urlopen("http://127.0.0.1:8090/health").read())

from nizam.inference.remote import RemoteEncoder  # noqa: E402
from nizam.inference.reranker import RemoteReranker  # noqa: E402

try:
    renc = RemoteEncoder(directory=os.path.join(models, "encoder-gpu-nf4"), url="http://127.0.0.1:8090", timeout=60)
    ref = np.load(os.path.join(models, "encoder-gpu-nf4", "reference_q.npy"))
    qs = json.load(open(os.path.join(models, "encoder-gpu-nf4", "reference_questions.json"), encoding="utf-8"))
    cos = [float(renc.embed(q) @ (ref[i] / np.linalg.norm(ref[i]))) for i, q in enumerate(qs[:40])]
    proof["encoder_check"] = {"passed": True, "cosine_min_40": round(min(cos), 5), "cosine_mean_40": round(float(np.mean(cos)), 5)}
    times = []
    for q in qs[40:90]:
        t = time.perf_counter(); renc.embed(q); times.append((time.perf_counter() - t) * 1000)
    times.sort()
    proof["encoder_ms"] = {"p50": round(times[len(times) // 2], 1), "p95": round(times[int(len(times) * .95)], 1)}
except Exception as exc:  # noqa: BLE001
    proof["encoder_check"] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"[:500]}
try:
    rrc = RemoteReranker(directory=os.path.join(models, "reranker-gpu"), url="http://127.0.0.1:8090", timeout=600)
    proof["reranker_check"] = {"passed": True}
    refj = json.load(open(os.path.join(models, "reranker-gpu", "reference.json"), encoding="utf-8"))
    g = refj["groups"][0]
    passages = [(p * 4)[:1600] for p in g["passages"]]
    for n in (10, 50):
        docs = (passages * ((n // len(passages)) + 1))[:n]
        ts = []
        for _ in range(3):
            t = time.perf_counter(); rrc.score(g["question"], docs); ts.append((time.perf_counter() - t) * 1000)
        proof[f"rerank_{n}_ms"] = round(sorted(ts)[1], 1)
except Exception as exc:  # noqa: BLE001
    proof["reranker_check"] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"[:500]}
proof["vram_gib_peak"] = [round(torch.cuda.max_memory_allocated(i) / 2**30, 2) for i in range(torch.cuda.device_count())]
proof["total_seconds"] = round(time.time() - t0)
json.dump(proof, open(f"{OUT}/proof.json", "w"), indent=1)
print(json.dumps(proof, indent=1))
