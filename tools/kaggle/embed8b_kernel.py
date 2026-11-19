# Kaggle GPU kernel: Qwen3-Embedding-8B over the whole corpus, in shards (D-099). Pushed by `tools/kaggle/kg.sh e8push`.
#
# The corpus (chunks.jsonl from dataset nizam-embed-v1, the same input generation 1 was embedded from) is cut into
# NSHARD fixed shards by chunk order. A run embeds the shards it is given, one after another, and writes each one as
# soon as it is complete:
#   out/shard_NN.npy        float16 [rows, 4096], unit length, in chunk order -- the FULL vector, so every storage
#                           form (Matryoshka prefix, sign bits, halfvec) is derived later without a GPU
#   out/shard_NN.json       rows, first/last chunk id, seconds, tokens, non-finite rows, library versions
#   out/dev_q.npy           the golden DEV questions in the model's query form, float32 [cases, 4096]
#   out/probe_gG.npy        256 fixed chunks embedded on GPU G -- compared across GPUs, runs and accounts locally, so a
#                           drift between sessions (a library upgrade, a different card) cannot pass silently
#   out/run.json            the pinned revision, versions, throughput
# A run stops before a shard it cannot finish inside HOURS (measured rate), so shards are whole or absent.
#
# Memory: the weights are ~15.1 GB in fp16 and a T4 has ~14.6 GiB usable. The token-embedding table (151,665 x 4,096,
# ~1.2 GB) stays in CPU memory and is looked up there; the 36 decoder layers and the final norm live on the GPU. With two
# T4s each holds a whole copy and they embed different batches at once (data parallel), not halves of one model.
#
# SMOKE = 1 proves the kernel instead of embedding the corpus:
#   (a) this file's tokenisation/padding/pooling against sentence-transformers' own encode, on Qwen3-Embedding-0.6B
#       (same family, same tokenizer conventions, small enough for one GPU) -- cosine must be >= 0.999;
#   (b) fp16 on the T4 (it has no bf16) against bf16 on the CPU, on the 8B itself, for a few passages and questions;
#   (c) throughput on a uniform sample of 3,000 chunks, both GPUs, and the projected corpus time;
#   (d) the dev questions and probes, as a full run writes them.
import gc
import gzip
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time

HOURS = __HOURS__
SMOKE = __SMOKE__
SHARDS = "__SHARDS__"          # e.g. "0-11" or "3,7,9"
REV = "__REV__"                # the pinned commit; empty only in the smoke run, which records the hub head
NSHARD = int("__NSHARD__" or 24)      # 24 for the corpus; 1 for a top-up of a replay's new chunks (embed_topup.py)
HUB = "Qwen/Qwen3-Embedding-8B"
SMALL = "Qwen/Qwen3-Embedding-0.6B"
TASK = "Given a question about Pakistani law, retrieve the statutory provisions that answer it"
QT = "Instruct: " + TASK + "\nQuery:{q}"    # the model card's form (no space after "Query:"), as generation 1's Qwen run
MAXLEN = 512                   # the chunker's budget; generation 1 embedded at 512 too
DIMS = 4096
# padded tokens per forward pass; halved automatically on OOM. 8,192 ran out of memory in the second smoke run
# (12.95 GiB of weights leave ~1.4 GiB per T4 for activations).
TOKBUDGET = int("__TOKBUDGET__" or 4096)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")    # before torch is imported
T0 = time.time()
OUT = "/kaggle/working/out"
os.makedirs(OUT, exist_ok=True)
LOG = open("/kaggle/working/run.log", "a", buffering=1)


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    LOG.write(line + "\n")


# exact versions: every run and both accounts must embed with the same code (the probes check that it did)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers==4.51.3", "accelerate==1.6.0",
                "sentence-transformers==4.1.0"], check=False)
import numpy as np  # noqa: E402
import torch  # noqa: E402
import transformers  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

NGPU = torch.cuda.device_count()
VERSIONS = {"torch": torch.__version__, "transformers": transformers.__version__, "cuda": torch.version.cuda,
            "gpus": [torch.cuda.get_device_name(g) for g in range(NGPU)]}
log(f"versions {VERSIONS}")
if NGPU == 0:
    raise SystemExit("no GPU attached")
if not REV:
    if not SMOKE:
        raise SystemExit("a full run needs the revision the smoke run pinned (KG_REV)")
    from huggingface_hub import HfApi
    REV = HfApi().model_info(HUB).sha
log(f"{HUB}@{REV}")

import glob  # noqa: E402
CHUNKS = sorted(glob.glob("/kaggle/input/**/chunks.jsonl*", recursive=True))[0]
src = os.path.dirname(CHUNKS)
ids, texts = [], []
with (gzip.open if CHUNKS.endswith(".gz") else open)(CHUNKS, "rt", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        ids.append(r["id"]); texts.append(r["t"])
ids = np.asarray(ids, dtype=np.int64)
N = len(texts)
dev = json.load(open(f"{src}/dev.json", encoding="utf-8"))
log(f"{N} chunks, {len(dev)} dev cases, from {src}")
bounds = [N * s // NSHARD for s in range(NSHARD + 1)]
PROBE = np.linspace(0, N - 1, 256).astype(np.int64)        # fixed rows, the same in every run


def parse_shards(spec):
    out = []
    for part in [p for p in spec.split(",") if p]:
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    return [s for s in out if 0 <= s < NSHARD]


tok = AutoTokenizer.from_pretrained(HUB, revision=REV, padding_side="left")
probe_ids = tok(["x"]).input_ids[0]
APPENDS_EOS = probe_ids[-1] == tok.eos_token_id or probe_ids[-1] == tok.pad_token_id
log(f"tokenizer: pad {tok.pad_token!r}/{tok.pad_token_id}, eos {tok.eos_token!r}/{tok.eos_token_id}, "
    f"'x' -> {probe_ids} (appends end token: {APPENDS_EOS})")


def tokenize(strs):
    return tok(strs, truncation=True, max_length=MAXLEN, padding=False).input_ids


def batches(seqs, budget):
    """index batches, longest first (an OOM shows in the first minute), each <= budget padded tokens"""
    order = sorted(range(len(seqs)), key=lambda i: -len(seqs[i]))
    out, i = [], 0
    while i < len(order):
        L = len(seqs[order[i]])
        n = max(1, min(256, budget // max(L, 1)))
        out.append(order[i:i + n]); i += n
    return out


def pad_left(seqs, pad):
    L = max(len(s) for s in seqs)
    ids_ = torch.full((len(seqs), L), pad, dtype=torch.long)
    mask = torch.zeros((len(seqs), L), dtype=torch.long)
    for r, s in enumerate(seqs):
        ids_[r, L - len(s):] = torch.tensor(s, dtype=torch.long)
        mask[r, L - len(s):] = 1
    return ids_, mask


_CPU_EMBED = {}


def cpu_embedding(hub, rev):
    """the token-embedding table, read straight from the checkpoint into a plain CPU nn.Embedding (float16), shared
    by every worker. (accelerate keeps a module it maps to "cpu" as an offloaded meta tensor -- the first smoke run
    died copying out of it -- so the model's own embed_tokens is never called: the forward takes inputs_embeds.)"""
    if (hub, rev) not in _CPU_EMBED:
        from huggingface_hub import hf_hub_download
        from safetensors import safe_open
        idx = json.load(open(hf_hub_download(hub, "model.safetensors.index.json", revision=rev), encoding="utf-8"))
        key = next(k for k in idx["weight_map"] if k.endswith("embed_tokens.weight"))
        with safe_open(hf_hub_download(hub, idx["weight_map"][key], revision=rev), "pt") as f:
            w = f.get_tensor(key).to(torch.float16)
        _CPU_EMBED[(hub, rev)] = torch.nn.Embedding.from_pretrained(w, freeze=True)
        log(f"token table {key} {tuple(w.shape)} read to the CPU")
    return _CPU_EMBED[(hub, rev)]


class Worker:
    """one copy of a model on one GPU; the token table on the CPU (or on the GPU when it fits: the small model)"""

    def __init__(self, hub, rev, g, embed_on_cpu=True, dtype=torch.float16):
        self.g, self.dev = g, f"cuda:{g}"
        dm = ({"embed_tokens": "cpu", "layers": g, "norm": g, "rotary_emb": g} if embed_on_cpu else {"": g})
        self.model = AutoModel.from_pretrained(hub, revision=rev, torch_dtype=dtype, device_map=dm,
                                               attn_implementation="sdpa").eval()
        self.embed = cpu_embedding(hub, rev) if embed_on_cpu else self.model.embed_tokens

    @torch.inference_mode()
    def encode(self, seqs):
        ids_, mask = pad_left(seqs, tok.pad_token_id)
        x = self.embed(ids_.to(self.embed.weight.device)).to(self.dev, non_blocking=True)
        h = self.model(inputs_embeds=x, attention_mask=mask.to(self.dev)).last_hidden_state
        v = h[:, -1, :].float()                     # left padding: the last position is the last real token
        return torch.nn.functional.normalize(v, dim=-1).cpu().numpy()

    def encode_safe(self, seqs):
        """halve the batch on OOM rather than die"""
        try:
            return self.encode(seqs)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if len(seqs) == 1:
                raise
            h = len(seqs) // 2
            return np.concatenate([self.encode_safe(seqs[:h]), self.encode_safe(seqs[h:])])


def run_parallel(workers, seqs, budget, dest):
    """embed seqs into dest (float16 [len(seqs), DIMS]) on every worker at once; returns (tokens, nonfinite rows)"""
    q = queue.Queue()
    for b in batches(seqs, budget):
        q.put(b)
    stats = {"tokens": 0, "nonfinite": []}
    lock = threading.Lock()
    errors = []

    def loop(w):
        try:
            while True:
                try:
                    b = q.get_nowait()
                except queue.Empty:
                    return
                v = w.encode_safe([seqs[i] for i in b])
                bad = ~np.isfinite(v).all(axis=1)
                dest[b] = v.astype(np.float16)
                with lock:
                    stats["tokens"] += sum(len(seqs[i]) for i in b)
                    stats["nonfinite"].extend(int(b[j]) for j in np.nonzero(bad)[0])
        except BaseException as exc:          # surfaced in the main thread
            errors.append(exc)

    threads = [threading.Thread(target=loop, args=(w,)) for w in workers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise errors[0]
    return stats["tokens"], stats["nonfinite"]


run_meta = {"model": HUB, "revision": REV, "query_template": QT, "max_tokens": MAXLEN, "dims": DIMS,
            "pooling": "lasttoken", "normalised": True, "nshard": NSHARD, "bounds": bounds, "versions": VERSIONS,
            "appends_eos": bool(APPENDS_EOS), "tokbudget": TOKBUDGET}

if SMOKE:
    # (a) this pipeline == sentence-transformers' encode, on the 0.6B
    from sentence_transformers import SentenceTransformer
    sample = [texts[i] for i in np.linspace(0, N - 1, 48).astype(int)] + [QT.format(q=c["q"]) for c in dev[:16]]
    st = SentenceTransformer(SMALL, device="cuda:0", model_kwargs={"torch_dtype": torch.float32})
    st.max_seq_length = MAXLEN
    ref = st.encode(sample, batch_size=8, normalize_embeddings=True, convert_to_numpy=True)
    del st; gc.collect(); torch.cuda.empty_cache()
    tok_8b = tok
    tok = AutoTokenizer.from_pretrained(SMALL, padding_side="left")
    w = Worker(SMALL, None, 0, embed_on_cpu=False, dtype=torch.float32)
    mine = np.concatenate([w.encode(tokenize(sample[i:i + 8])) for i in range(0, len(sample), 8)])
    cos = (mine * ref).sum(1)
    run_meta["smoke_pipeline_vs_st_cos"] = {"min": float(cos.min()), "mean": float(cos.mean())}
    log(f"(a) pipeline vs sentence-transformers on {SMALL}: cosine min {cos.min():.5f} mean {cos.mean():.5f}")
    same_tok = tok("x").input_ids == tok_8b("x").input_ids
    log(f"    the 8B tokenizer treats 'x' the same as the 0.6B's: {same_tok}")
    run_meta["smoke_same_tokenizer_convention"] = bool(same_tok)
    del w; gc.collect(); torch.cuda.empty_cache()
    tok = tok_8b

    # (b) fp16 on the GPU against bf16 on the CPU, on the 8B
    few = [texts[i] for i in np.linspace(0, N - 1, 4).astype(int)] + [QT.format(q=c["q"]) for c in dev[:3]]
    few = [s[:600] for s in few]          # short: the CPU reference is slow
    t = time.time()
    cpu_model = AutoModel.from_pretrained(HUB, revision=REV, torch_dtype=torch.bfloat16, device_map={"": "cpu"},
                                          attn_implementation="sdpa").eval()
    with torch.inference_mode():
        refs = []
        for s in few:
            ii = tok([s], truncation=True, max_length=MAXLEN, return_tensors="pt")
            h = cpu_model(**ii).last_hidden_state[:, -1, :].float()
            refs.append(torch.nn.functional.normalize(h, dim=-1).numpy()[0])
    refs = np.stack(refs)
    del cpu_model; gc.collect()
    log(f"(b) bf16 CPU reference for {len(few)} texts in {time.time() - t:.0f}s")

workers = []
for g in range(NGPU):
    t = time.time()
    workers.append(Worker(HUB, REV, g))
    log(f"8B loaded on GPU {g} in {time.time() - t:.0f}s; {torch.cuda.memory_allocated(g) / 2**30:.2f} GiB allocated")

if SMOKE:
    fp16 = workers[0].encode_safe(tokenize(few))
    cos = (fp16 * refs).sum(1)
    run_meta["smoke_fp16_vs_bf16_cos"] = {"min": float(cos.min()), "mean": float(cos.mean()),
                                          "sign_agreement": float(((fp16 > 0) == (refs > 0)).mean())}
    log(f"(b) fp16 GPU vs bf16 CPU: cosine min {cos.min():.5f} mean {cos.mean():.5f}; "
        f"sign agreement {run_meta['smoke_fp16_vs_bf16_cos']['sign_agreement']:.4f}")

# the dev questions, the way every run writes them (dev only: test questions never leave the laptop before freeze)
qv = np.concatenate([workers[0].encode_safe(tokenize([QT.format(q=c["q"]) for c in dev[i:i + 16]]))
                     for i in range(0, len(dev), 16)])
np.save(f"{OUT}/dev_q.npy", qv.astype(np.float32))
for w in workers:
    pv = np.concatenate([w.encode_safe(tokenize([texts[i] for i in PROBE[j:j + 8]])) for j in range(0, len(PROBE), 8)])
    np.save(f"{OUT}/probe_g{w.g}.npy", pv.astype(np.float32))
if len(workers) > 1:
    a, b = np.load(f"{OUT}/probe_g0.npy"), np.load(f"{OUT}/probe_g1.npy")
    log(f"probes GPU 0 vs 1: cosine min {(a * b).sum(1).min():.6f}")
for g in range(NGPU):
    log(f"GPU {g} peak {torch.cuda.max_memory_allocated(g) / 2**30:.2f} GiB")

if SMOKE:
    # (c) throughput on a uniform sample, both GPUs
    rng = np.random.default_rng(0)
    rows = np.sort(rng.choice(N, 3000, replace=False))
    seqs = tokenize([texts[i] for i in rows])
    dest = np.zeros((len(seqs), DIMS), dtype=np.float16)
    for g in range(NGPU):
        torch.cuda.reset_peak_memory_stats(g)
    t = time.time()
    ntok, bad = run_parallel(workers, seqs, TOKBUDGET, dest)
    secs = time.time() - t
    lens = np.array([len(s) for s in seqs])
    run_meta["smoke_throughput"] = {"chunks": len(seqs), "seconds": round(secs, 1), "chunks_per_second":
                                    round(len(seqs) / secs, 2), "tokens_per_second": round(ntok / secs),
                                    "mean_tokens": float(lens.mean()), "p50_tokens": float(np.median(lens)),
                                    "share_at_512": float((lens >= MAXLEN).mean()), "nonfinite": len(bad),
                                    "projected_corpus_hours": round(N / (len(seqs) / secs) / 3600, 1),
                                    "peak_gib": [round(torch.cuda.max_memory_allocated(g) / 2**30, 2)
                                                 for g in range(NGPU)]}
    log(f"(c) throughput {run_meta['smoke_throughput']}")
    json.dump(run_meta, open(f"{OUT}/run.json", "w"), indent=1)
    log("smoke done")
    raise SystemExit(0)

todo = parse_shards(SHARDS)
log(f"shards to embed: {todo}")
rate = None                                     # seconds per chunk, measured on this run's first shard
done = []
for s in todo:
    if os.path.exists(f"{OUT}/shard_{s:02d}.npy"):
        continue
    a, b = bounds[s], bounds[s + 1]
    left = HOURS * 3600 - (time.time() - T0) - 900
    if rate is not None and rate * (b - a) > left:
        log(f"shard {s}: {rate * (b - a) / 3600:.2f} h needed, {left / 3600:.2f} h left -- stopping")
        break
    t = time.time()
    seqs = tokenize(texts[a:b])
    dest = np.zeros((b - a, DIMS), dtype=np.float16)
    ntok, bad = run_parallel(workers, seqs, TOKBUDGET, dest)
    secs = time.time() - t
    rate = secs / (b - a)
    np.save(f"{OUT}/shard_{s:02d}.npy", dest)
    meta = {"shard": s, "rows": b - a, "first_row": a, "first_id": int(ids[a]), "last_id": int(ids[b - 1]),
            "ids_sha": hashlib.sha256(ids[a:b].tobytes()).hexdigest(), "seconds": round(secs),
            "tokens": ntok, "nonfinite_rows": bad, "revision": REV, "versions": VERSIONS}
    json.dump(meta, open(f"{OUT}/shard_{s:02d}.json", "w"))
    done.append(s)
    log(f"shard {s}: {b - a} chunks in {secs / 3600:.2f} h ({(b - a) / secs:.1f}/s, {ntok / secs:.0f} tok/s); "
        f"{len(bad)} non-finite")
run_meta["shards_done"] = done
json.dump(run_meta, open(f"{OUT}/run.json", "w"), indent=1)
log(f"done: shards {done}")
