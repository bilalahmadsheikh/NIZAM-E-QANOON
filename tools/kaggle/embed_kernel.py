# Kaggle GPU kernel: the embedding bake-off and corpus embedding (D-098). Pushed by `tools/kaggle/kg.sh embedpush`.
#
# For each candidate model, in turn:
#   1. embed every chunk of the corpus (chunks.jsonl.gz: context prefix + span text), fp16, length-sorted batches;
#   2. save the BINARY vectors (sign of each of the 1024 dimensions, packed: 128 bytes per chunk, docs/03 §3) in
#      chunk order -- the winner's file is loaded into chunk.embedding as is;
#   3. score the golden DEV questions (dev.json; test cases never leave the laptop): chunks restricted to the case's
#      jurisdictions, cosine (full precision) or Hamming (binary) top 3,000 chunks, collapsed to legal units with
#      unitScore = max + 0.15 x second best (docs/04 §5), top 50 units; recall@10, recall@50, MRR@10 against the gold
#      units, per stratum and per script, at full precision AND binary (the ADR-1d check);
#   4. record throughput and the query-side cost.
# Output: /kaggle/working/out/<model-slug>/{bits.npy, ids.npy (first model only), metrics.json}, run.log.
import gc
import gzip
import json
import os
import subprocess
import sys
import time

HOURS = __HOURS__
SMOKE = __SMOKE__          # 1: the first 20,000 chunks only -- proves the kernel end to end in minutes
T0 = time.time()
OUT = "/kaggle/working/out"
os.makedirs(OUT, exist_ok=True)
LOG = open("/kaggle/working/run.log", "a", buffering=1)


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    LOG.write(line + "\n")


subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "sentence-transformers>=3.4",
                "transformers>=4.51"], check=False)
import numpy as np  # noqa: E402
import torch  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

TASK = "Given a question about Pakistani law, retrieve the statutory provisions that answer it"
MODELS = [  # (slug, hub id, query template, max tokens)
    ("bge-m3", "BAAI/bge-m3", "{q}", 512),
    ("me5-large-instruct", "intfloat/multilingual-e5-large-instruct", "Instruct: " + TASK + "\nQuery: {q}", 512),
    ("qwen3-emb-0.6b", "Qwen/Qwen3-Embedding-0.6B", "Instruct: " + TASK + "\nQuery:{q}", 512),
]
ONLY = [x for x in "__ONLY__".split(",") if x] or None     # kg.sh KG_MODELS: a subset of the slugs, else all
# ADR-1d after reranking (D-110): KG_KEEPFLOAT=1 also saves the query vectors (q.npy) and, per dev question, the TOPW
# nearest chunks in its scope by FLOAT cosine (topf_ids.npy, topf_sims.npy) and by Hamming on the same vectors' sign
# bits (topb_ids.npy) -- what the dense window of each arm holds; KG_REV pins the commit embedded (the active
# generation's own), so the floats are that generation's space
KEEP_FLOAT = "__KEEPFLOAT__" == "1"
PIN_REV = "__REV__" or None
TOPW = 900          # the served dense window: min(1000, 300 provisions x 3 chunks), nizam.storage.unit_search


def model_pooling(hub, rev):
    from huggingface_hub import hf_hub_download
    cfg = json.load(open(hf_hub_download(hub, "1_Pooling/config.json", revision=rev), encoding="utf-8"))
    modes = {"pooling_mode_cls_token": "cls", "pooling_mode_mean_tokens": "mean", "pooling_mode_lasttoken": "lasttoken"}
    on = [name for key, name in modes.items() if cfg.get(key)]
    others = [k for k, v in cfg.items() if k.startswith("pooling_mode") and v and k not in modes]
    if len(on) != 1 or others:
        raise ValueError(f"{hub}: unsupported pooling {cfg}")
    return on[0]


for _slug, _hub, _qt, _ml in MODELS:     # fail in the first minute, not after hours of embedding
    if not ONLY or _slug in ONLY:
        log(f"{_slug}: pooling {model_pooling(_hub, None)} (hub head; the run re-reads it at the pinned commit)")

import glob  # noqa: E402
# Kaggle nests attached datasets below /kaggle/input (the OCR kernel finds its inputs the same way, recursively)
# Kaggle stores an uploaded .gz decompressed (chunks.jsonl); accept either form
CHUNKS = sorted(glob.glob("/kaggle/input/**/chunks.jsonl*", recursive=True))[0]
src = os.path.dirname(CHUNKS)
log(f"inputs {src}; gpu {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'}")
ids, units, juris, texts = [], [], [], []
with (gzip.open if CHUNKS.endswith(".gz") else open)(CHUNKS, "rt", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        ids.append(r["id"]); units.append(r["u"]); juris.append(r["j"]); texts.append(r["t"])
if SMOKE:
    ids, units, juris, texts = ids[:20000], units[:20000], juris[:20000], texts[:20000]
ids = np.asarray(ids, dtype=np.int64); units = np.asarray(units, dtype=np.int64)
jnames = sorted(set(juris)); jidx = np.asarray([jnames.index(j) for j in juris], dtype=np.int8)
dev = json.load(open(f"{src}/dev.json", encoding="utf-8"))
log(f"{len(texts)} chunks, {units.max() + 1} units, {len(dev)} dev cases, jurisdictions {jnames}")
np.save(f"{OUT}/ids.npy", ids)
order = np.argsort([len(t) for t in texts])          # length-sorted batches waste less padding


def collapse(chunk_rows, scores):
    best = {}
    for row, s in zip(chunk_rows, scores):
        u = int(units[row])
        b = best.get(u)
        if b is None:
            best[u] = [s, -1e9]
        elif s > b[0]:
            best[u] = [s, b[0]]
        elif s > b[1]:
            best[u][1] = s
    ranked = sorted(best.items(), key=lambda kv: -(kv[1][0] + 0.15 * max(kv[1][1], 0)))
    return [u for u, _ in ranked]


POP = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint16)


def evaluate(qvec, cvec, binary):
    """qvec: queries (float16 [Q,1024], or packed bits [Q,128] when binary); cvec: chunks, same form"""
    rows = []
    if not binary:   # cosine on the GPU, all chunks at once per query block (unit vectors: dot product)
        E = torch.from_numpy(cvec).cuda()
        sims_all = (torch.from_numpy(qvec).cuda() @ E.T).float().cpu().numpy()
        del E; torch.cuda.empty_cache()
    for qi, (case, qv) in enumerate(zip(dev, qvec)):
        mask = np.isin(jidx, [jnames.index(j) for j in case["juris"] if j in jnames])
        cand = np.nonzero(mask)[0]
        if binary:   # Hamming distance on packed bits via a popcount table -> similarity = -distance
            sims = -POP[np.bitwise_xor(cvec[cand], qv[None, :])].sum(axis=1).astype(np.float32)
        else:
            sims = sims_all[qi, cand]
        k = min(3000, len(cand))
        part = np.argpartition(-sims, k - 1)[:k]
        part = part[np.argsort(-sims[part])]
        ranked = collapse(cand[part], sims[part])[:50]
        gold = set(case["gold"])
        hit = [r for r, u in enumerate(ranked, 1) if u in gold]
        rows.append({"case": case["case"], "stratum": case["stratum"], "script": case["script"],
                     "r10": sum(1 for u in ranked[:10] if u in gold) / max(1, case["gold_total"]),
                     "r50": sum(1 for u in ranked if u in gold) / max(1, case["gold_total"]),
                     "mrr10": 1 / hit[0] if hit and hit[0] <= 10 else 0.0})

    def agg(rs):
        return {k: round(float(np.mean([r[k] for r in rs])), 4) for k in ("r10", "r50", "mrr10")} | {"n": len(rs)}
    out = {"all": agg(rows)}
    for key in ("stratum", "script"):
        for v in sorted({r[key] for r in rows}):
            out[f"{key}:{v}"] = agg([r for r in rows if r[key] == v])
    return out, rows


for slug, hub, qtemplate, maxlen in MODELS:
    if ONLY and slug not in ONLY:
        continue
    if time.time() - T0 > HOURS * 3600 - 1800:
        log(f"time budget reached before {slug}"); break
    os.makedirs(f"{OUT}/{slug}", exist_ok=True)
    if os.path.exists(f"{OUT}/{slug}/metrics.json"):
        continue
    from huggingface_hub import HfApi  # noqa: E402
    rev = PIN_REV or HfApi().model_info(hub).sha   # the exact commit embedded; the query encoder is exported from it
    log(f"== {slug}: loading {hub}@{rev}")
    dtype = torch.float16
    m = SentenceTransformer(hub, device="cuda", revision=rev, model_kwargs={"torch_dtype": dtype})
    m.max_seq_length = maxlen
    probe = m.encode([texts[j] for j in order[-64:]], batch_size=16, normalize_embeddings=True)   # longest texts
    if not np.isfinite(probe).all():      # fp16 overflow (the T4 has no bf16): fall back to fp32, slower but sound
        log(f"{slug}: fp16 produced non-finite values; using fp32")
        del m; torch.cuda.empty_cache()
        dtype = torch.float32
        m = SentenceTransformer(hub, device="cuda", revision=rev, model_kwargs={"torch_dtype": dtype})
        m.max_seq_length = maxlen
    t = time.time()
    emb = np.zeros((len(texts), 1024), dtype=np.float16)
    B = 128
    for i in range(0, len(order), B * 64):
        idx = order[i:i + B * 64]
        e = m.encode([texts[j] for j in idx], batch_size=B, normalize_embeddings=True, convert_to_numpy=True,
                     show_progress_bar=False)
        emb[idx] = e[:, :1024].astype(np.float16)
        if (i // (B * 64)) % 20 == 0:
            done = i + len(idx)
            log(f"{slug}: {done}/{len(texts)} ({done / (time.time() - t):.0f}/s)")
    secs = time.time() - t
    bits = np.packbits(emb > 0, axis=1)                       # 128 bytes per chunk
    np.save(f"{OUT}/{slug}/bits.npy", bits)
    tq = time.time()
    qtexts = [qtemplate.format(q=c["q"]) for c in dev]
    qv = m.encode(qtexts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True)[:, :1024]
    qsecs = (time.time() - tq) / len(qtexts)
    if KEEP_FLOAT:
        np.save(f"{OUT}/{slug}/q.npy", qv.astype(np.float16))
        E = torch.from_numpy(emb).cuda()
        qb = np.packbits(qv > 0, axis=1)
        tf_ids = np.full((len(dev), TOPW), -1, dtype=np.int64)
        tf_sims = np.zeros((len(dev), TOPW), dtype=np.float32)
        tb_ids = np.full((len(dev), TOPW), -1, dtype=np.int64)
        for qi, case in enumerate(dev):
            cand = np.nonzero(np.isin(jidx, [jnames.index(j) for j in case["juris"] if j in jnames]))[0]
            k = min(TOPW, len(cand))
            s = (E[torch.from_numpy(cand).cuda()] @ torch.from_numpy(qv[qi].astype(np.float16)).cuda()).float().cpu().numpy()
            top = np.argpartition(-s, k - 1)[:k]
            top = top[np.argsort(-s[top], kind="stable")]
            tf_ids[qi, :k], tf_sims[qi, :k] = ids[cand[top]], s[top]
            h = POP[np.bitwise_xor(bits[cand], qb[qi][None, :])].sum(axis=1)
            topb = np.lexsort((ids[cand], h))[:k]          # Hamming, ties by chunk id (serving's ORDER BY)
            tb_ids[qi, :k] = ids[cand[topb]]
        del E; torch.cuda.empty_cache()
        np.save(f"{OUT}/{slug}/topf_ids.npy", tf_ids)
        np.save(f"{OUT}/{slug}/topf_sims.npy", tf_sims)
        np.save(f"{OUT}/{slug}/topb_ids.npy", tb_ids)
        log(f"{slug}: kept float and binary top-{TOPW} for {len(dev)} questions")
    full, full_rows = evaluate(qv.astype(np.float16), emb, binary=False)
    binr, bin_rows = evaluate(np.packbits(qv > 0, axis=1), bits, binary=True)
    if not np.isfinite(emb).all():
        log(f"{slug}: NON-FINITE embeddings; metrics withheld")
        json.dump({"model": hub, "error": "non-finite embeddings"}, open(f"{OUT}/{slug}/metrics.json", "w"))
        del m, emb, bits; gc.collect(); torch.cuda.empty_cache()
        continue
    # the model's own pooling, read from the file sentence-transformers itself loads (1_Pooling/config.json at the
    # pinned commit) -- independent of the library's API, which changed between versions (19 Nov: the full run
    # died on a removed method after embedding the corpus)
    pooling = model_pooling(hub, rev)
    metrics = {"model": hub, "revision": rev,
               "pooling": pooling, "query_template": qtemplate, "modules": [type(mod).__name__ for mod in m._modules.values()],
               "dims": 1024, "max_tokens": maxlen, "chunks": len(texts), "dtype": str(dtype),
               "embed_seconds": round(secs), "chunks_per_second": round(len(texts) / secs),
               "gpu_query_seconds_each": round(qsecs, 4), "full_precision": full, "binary": binr,
               "per_case_full": full_rows, "per_case_binary": bin_rows}
    json.dump(metrics, open(f"{OUT}/{slug}/metrics.json", "w"), indent=1)
    log(f"== {slug}: {secs/3600:.2f} h; full r50 {full['all']['r50']} r10 {full['all']['r10']}; "
        f"binary r50 {binr['all']['r50']} r10 {binr['all']['r10']}")
    del m, emb, bits
    gc.collect(); torch.cuda.empty_cache()
log("done")
