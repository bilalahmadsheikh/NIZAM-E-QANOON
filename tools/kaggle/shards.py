"""Reading the full-vector shard runs of tools/kaggle/embed8b_kernel.py (D-099) -- one verification for every reader
(evals/shard_dense_eval.py, tools/load_embeddings_gpu.py), so the evaluator and the loader cannot accept different
inputs.

    runs = verified_runs(ds_ids, ["/mnt/e/nizam-data/embed/out-e8a", ".../out-e8b"])
    runs.shards[s]       -> path of shard_NN.npy (float16 [rows, 4096], chunk order)
    runs.bounds          -> row bounds of the NSHARD shards in the export's order
    runs.meta            -> run.json of the first run (model, revision, query template, ...)
    runs.dev_q           -> the dev questions' float vectors (dev.json order), identical across runs

Refuses (SystemExit, naming the shard) unless: every run embedded one revision; each shard's rows, first/last chunk id
and id hash are the export's; no shard has a non-finite row; the dev questions and the 256 probe chunks agree across
runs and GPUs (cosine >= 0.999).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

AGREE = 0.999


def unit(v):
    n = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(n == 0, 1, n)


def load_ds(ds: Path):
    """(chunk ids, unit indexes, jurisdiction indexes, jurisdiction names) of an embed_inputs.py export, in its order"""
    ids, units, juris = [], [], []
    path = Path(ds) / "chunks.jsonl.gz"
    with (gzip.open(path, "rt", encoding="utf-8") if path.exists()
          else open(Path(ds) / "chunks.jsonl", encoding="utf-8")) as f:
        for line in f:
            ids.append(int(line[7:line.index(",")]))              # {"id": N, ...
            i = line.index('"u": ')
            j = line.index('"j": "', i)
            units.append(int(line[i + 5:line.index(",", i)]))
            juris.append(line[j + 6:line.index('"', j + 6)])
    jnames = sorted(set(juris))
    jmap = {n: k for k, n in enumerate(jnames)}
    return (np.asarray(ids, dtype=np.int64), np.asarray(units, dtype=np.int64),
            np.asarray([jmap[j] for j in juris], dtype=np.int8), jnames)


@dataclass
class Runs:
    meta: dict
    bounds: list
    nshard: int
    shards: dict
    missing: list
    dev_q: np.ndarray
    agreement: dict


def verified_runs(ids: np.ndarray, run_dirs) -> Runs:
    runs = [Path(r) / "out" if (Path(r) / "out").exists() else Path(r) for r in run_dirs]
    metas = [json.loads((r / "run.json").read_text(encoding="utf-8")) for r in runs if (r / "run.json").exists()]
    if not metas:
        sys.exit("no run.json in the given runs")
    revs = {m["revision"] for m in metas}
    if len(revs) != 1:
        sys.exit(f"runs embedded different revisions: {revs}")
    bounds, nshard = metas[0]["bounds"], metas[0]["nshard"]
    if bounds[-1] != len(ids):
        sys.exit(f"runs embedded {bounds[-1]} chunks, the export holds {len(ids)}")
    qs = [np.load(r / "dev_q.npy") for r in runs if (r / "dev_q.npy").exists()]
    probes = [np.load(p) for r in runs for p in sorted(r.glob("probe_g*.npy"))]
    q_agree = min(float((unit(q) * unit(qs[0])).sum(1).min()) for q in qs) if qs else None
    p_agree = min(float((unit(p) * unit(probes[0])).sum(1).min()) for p in probes) if probes else None
    if (q_agree is not None and q_agree < AGREE) or (p_agree is not None and p_agree < AGREE):
        sys.exit(f"runs disagree (dev questions {q_agree}, probes {p_agree}): not one embedding space")
    shards = {}
    for r in runs:
        for f in sorted(r.glob("shard_*.npy")):
            s = int(f.stem.split("_")[1])
            meta = json.loads(f.with_suffix(".json").read_text(encoding="utf-8"))
            lo, hi = bounds[s], bounds[s + 1]
            if (meta["rows"], meta["first_id"], meta["last_id"]) != (hi - lo, int(ids[lo]), int(ids[hi - 1])) or \
                    meta["ids_sha"] != hashlib.sha256(ids[lo:hi].tobytes()).hexdigest():
                sys.exit(f"shard {s} ({f}) does not hold the export's chunks {lo}..{hi}")
            if meta["nonfinite_rows"]:
                sys.exit(f"shard {s}: {len(meta['nonfinite_rows'])} non-finite rows")
            if meta["revision"] not in revs:
                sys.exit(f"shard {s}: revision {meta['revision']}")
            if s in shards:
                sys.exit(f"shard {s} is in two runs ({shards[s]}, {f})")
            shards[s] = f
    missing = sorted(set(range(nshard)) - set(shards))
    return Runs(metas[0], bounds, nshard, shards, missing, unit(qs[0].astype(np.float32)) if qs else None,
                {"dev_questions_cos_min": q_agree, "probes_cos_min": p_agree, "runs": len(runs),
                 "probe_sets": len(probes)})
