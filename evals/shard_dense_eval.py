"""shard_dense_eval.py DS_DIR RUN_DIR... [--out JSON] [--allow-partial] : the dense generator of a FULL-vector shard run
(tools/kaggle/embed8b_kernel.py, D-099) on the golden DEV split, in every storage form at once.

Every arm is scored exactly as the bake-off kernel scored generation 1's candidates (tools/kaggle/embed_kernel.py):
candidates in the case's scope jurisdictions, the top 3,000 chunks collapsed to legal units by best chunk plus 0.15 x
max(second best, 0), recall against the gold units. So the table sits beside D-098's bake-off rows.

Arms (the query is always the float vector the run wrote, dev_q.npy; each arm derives its corpus form from the same
float16 shards, as a loader would):
  full<D>          cosine on the first D dimensions, renormalised (Matryoshka prefix; D = 4096 is the whole vector)
  bits<W>          Hamming on the sign of the first W dimensions (what a bit(W) column + HNSW serves)
  bits<W>>half<D>@S  the Hamming top S chunks re-ranked by float-query cosine against the halfvec(D) prefix (what a
                   bit(W) HNSW shortlist plus a halfvec(D) column serves)

Hamming is computed exactly as (W - s.q)/2 on +-1 vectors (a float matmul; integers below 2^24 are exact), the sign
of 0 counting as negative like numpy.packbits(v > 0).

Before scoring it proves the inputs: each shard's row count, first/last chunk id and id hash match DS_DIR's chunks
(the export the run embedded); no non-finite rows; one revision; the dev questions and the 256 probe chunks agree
across runs and GPUs (cosine >= 0.999). Shards are streamed one at a time (WSL here has 5 GB). TEST cases are not read.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.binary_ablation import collapse, score, summarise  # noqa: E402
from tools.kaggle.shards import load_ds, unit, verified_runs  # noqa: E402

K = 3000
PREFIXES = (4096, 2048, 1024)
WIDTHS = (4096, 2048, 1024)
RESCORE = [(1024, 1024, 1000), (1024, 1024, 3000), (2048, 1024, 1000), (2048, 1024, 3000), (4096, 1024, 1000)]


class TopK:
    """per query, the best K (primary score) rows seen so far, carrying a secondary score"""

    def __init__(self, nq, k):
        self.k = k
        self.s = [np.empty(0, np.float32) for _ in range(nq)]
        self.r = [np.empty(0, np.int64) for _ in range(nq)]
        self.x = [np.empty(0, np.float32) for _ in range(nq)]

    def add(self, qi, scores, rows, extra=None):
        s = np.concatenate([self.s[qi], scores]); r = np.concatenate([self.r[qi], rows])
        x = np.concatenate([self.x[qi], extra if extra is not None else scores])
        if len(s) > self.k:
            keep = np.argpartition(-s, self.k - 1)[:self.k]
            s, r, x = s[keep], r[keep], x[keep]
        self.s[qi], self.r[qi], self.x[qi] = s, r, x

    def ranked(self, qi, by_extra=False):
        key = self.x[qi] if by_extra else self.s[qi]
        o = np.lexsort((self.r[qi], -key))         # score desc, then row (chunk order) for ties
        return self.r[qi][o], key[o]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ds"); ap.add_argument("runs", nargs="+")
    ap.add_argument("--out"); ap.add_argument("--allow-partial", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    ids, units, jidx, jnames = load_ds(Path(a.ds))
    dev = json.loads((Path(a.ds) / "dev.json").read_text(encoding="utf-8"))
    R = verified_runs(ids, a.runs)
    metas, bounds, nshard, shard_files, missing = [R.meta], R.bounds, R.nshard, R.shards, R.missing
    q_agree, p_agree = R.agreement["dev_questions_cos_min"], R.agreement["probes_cos_min"]
    print(f"dev questions agree across runs: cosine min {q_agree:.6f}; probes across "
          f"{R.agreement['probe_sets']} GPU-runs: {p_agree:.6f}")
    q = R.dev_q
    assert q.shape == (len(dev), 4096), q.shape
    if missing and not a.allow_partial:
        sys.exit(f"shards missing: {missing} (pass --allow-partial for a progress reading; it is not a result)")
    print(f"{len(shard_files)}/{nshard} shards verified; {len(dev)} dev cases")

    scope = [np.isin(jidx, [jnames.index(j) for j in c["juris"] if j in jnames]) for c in dev]
    arms = {f"full{d}": TopK(len(dev), K) for d in PREFIXES} | {f"bits{w}": TopK(len(dev), K) for w in WIDTHS}
    arms |= {f"bits{w}>half{d}@{s}": TopK(len(dev), s) for w, d, s in RESCORE}
    qp = {d: unit(q[:, :d]) for d in PREFIXES}
    qsign = np.where(q > 0, 1.0, -1.0).astype(np.float32)
    for s in sorted(shard_files):
        ts = time.time()
        lo = bounds[s]
        X = np.load(shard_files[s]).astype(np.float32)              # (n, 4096)
        cos = {}
        for d in PREFIXES:
            cos[d] = unit(X[:, :d]) @ qp[d].T                        # (n, Q)
        half = unit(X[:, :1024].astype(np.float16).astype(np.float32)) @ qp[1024].T   # the halfvec(1024) score
        S = np.where(X > 0, 1.0, -1.0).astype(np.float32)
        del X
        sims = {}
        for w in WIDTHS:
            dot = S[:, :w] @ qsign[:, :w].T
            sims[w] = 1.0 - ((w - dot) / 2.0) / (w / 2.0)             # 1 - hamming/(W/2), as the served path scores
        del S
        for qi in range(len(dev)):
            m = scope[qi][lo:lo + len(half)]
            rows = np.nonzero(m)[0]
            if not len(rows):
                continue
            gr = rows + lo
            for d in PREFIXES:
                arms[f"full{d}"].add(qi, cos[d][rows, qi], gr)
            for w in WIDTHS:
                arms[f"bits{w}"].add(qi, sims[w][rows, qi], gr)
            for w, d, sz in RESCORE:
                arms[f"bits{w}>half{d}@{sz}"].add(qi, sims[w][rows, qi], gr, half[rows, qi])
        print(f"  shard {s}: {time.time() - ts:.0f}s", flush=True)

    results, per_case = {}, {}
    for name, tk in arms.items():
        rows_out = []
        for qi, c in enumerate(dev):
            r, sc = tk.ranked(qi, by_extra=">" in name)
            meta = {"case": c["case"], "stratum": c["stratum"], "script": c["script"]}
            rows_out.append(meta | score(c, collapse(units, r[:K], sc[:K])[:50]))
        results[name] = summarise(rows_out)
        per_case[name] = rows_out
    names = list(results)
    print(f"\n   {'slice':22} {'n':>4}  " + "  ".join(f"{n:>22}" for n in names))
    for sl in results["full4096"]:
        print(f"   {sl:22} {results['full4096'][sl]['n']:>4}  " + "  ".join(
            f"{results[n][sl]['r10']:.3f}/{results[n][sl]['r50']:.3f}".rjust(22) for n in names))
    if a.out:
        Path(a.out).write_text(json.dumps({
            "split": "dev", "cases": len(dev), "model": metas[0]["model"], "revision": metas[0]["revision"],
            "query_template": metas[0]["query_template"], "k_chunks": K, "shards": len(shard_files),
            "partial": bool(missing), "agreement": {"dev_questions_cos_min": q_agree, "probes_cos_min": p_agree},
            "results": results, "per_case": per_case, "seconds": round(time.time() - t0)}, indent=1),
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
