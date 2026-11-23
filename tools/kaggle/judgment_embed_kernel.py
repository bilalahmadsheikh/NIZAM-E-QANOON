# Kaggle GPU kernel: judgment chunks in the CPU generation's space (D-132). Pushed by `tools/kaggle/kg.sh jembedpush`.
#
# Reads chunks.jsonl(.gz) ({"id", "t"}: the passage exactly as nizam.storage.chunking.passage_text builds it) written by
# `nizam.workers.judgment_chunk --export`, and embeds every passage with generation 1's model as the statute chunks
# were embedded (D-098, tools/kaggle/embed_kernel.py): BAAI/bge-m3 at the pinned commit, sentence-transformers, its
# own pooling (CLS), 512 tokens, fp16 (fp32 if fp16 overflows), normalised, length-sorted batches. Output: the sign of
# each of the first 1,024 dimensions packed with numpy.packbits (128 bytes per chunk, first dimension first), in the
# input's id order: /kaggle/working/out/{bits.npy, ids.npy, meta.json}, run.log.
import gzip
import glob
import json
import os
import subprocess
import sys
import time

HUB, REV, MAXLEN = "BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", 512
T0 = time.time()
OUT = "/kaggle/working/out"
os.makedirs(OUT, exist_ok=True)
LOG = open("/kaggle/working/run.log", "a", buffering=1)


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    LOG.write(line + "\n")


subprocess.run([sys.executable, "-m", "pip", "install", "-q", "sentence-transformers>=3,<4"], check=False)
import numpy as np  # noqa: E402
import torch  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

CHUNKS = sorted(glob.glob("/kaggle/input/**/chunks.jsonl*", recursive=True))[0]
ids, texts = [], []
with (gzip.open if CHUNKS.endswith(".gz") else open)(CHUNKS, "rt", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        ids.append(r["id"]); texts.append(r["t"])
log(f"{len(texts)} chunks from {CHUNKS}; gpu {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'}")
order = np.argsort([len(t) for t in texts])
dtype = torch.float16
m = SentenceTransformer(HUB, device="cuda", revision=REV, model_kwargs={"torch_dtype": dtype})
m.max_seq_length = MAXLEN
probe = m.encode([texts[j] for j in order[-64:]], batch_size=16, normalize_embeddings=True)
if not np.isfinite(probe).all():
    log("fp16 produced non-finite values; using fp32")
    del m; torch.cuda.empty_cache()
    dtype = torch.float32
    m = SentenceTransformer(HUB, device="cuda", revision=REV, model_kwargs={"torch_dtype": dtype})
    m.max_seq_length = MAXLEN
emb = np.zeros((len(texts), 1024), dtype=np.float16)
B = 128
t = time.time()
for i in range(0, len(order), B * 64):
    idx = order[i:i + B * 64]
    e = m.encode([texts[j] for j in idx], batch_size=B, normalize_embeddings=True, convert_to_numpy=True,
                 show_progress_bar=False)
    emb[idx] = e[:, :1024].astype(np.float16)
    done = i + len(idx)
    log(f"{done}/{len(texts)} ({done / (time.time() - t):.0f}/s)")
bits = np.packbits(emb > 0, axis=1)
np.save(f"{OUT}/bits.npy", bits)
np.save(f"{OUT}/ids.npy", np.asarray(ids, dtype=np.int64))
json.dump({"model": HUB, "revision": REV, "max_tokens": MAXLEN, "dtype": str(dtype), "chunks": len(ids),
           "seconds": round(time.time() - t), "pooling": [type(x).__name__ for x in m._modules.values()]},
          open(f"{OUT}/meta.json", "w"))
log(f"done: {len(ids)} chunks in {time.time() - T0:.0f}s")
