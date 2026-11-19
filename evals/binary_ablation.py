"""binary_ablation.py DS_DIR QUERY_DIR RUN_DIR/SLUG... : ADR-1d's binary-vs-full-precision ablation, on the DEV split.

Three arms per model, each scored exactly as the bake-off kernel scored (tools/kaggle/embed_kernel.py: candidates in
the case's scope jurisdictions, the top 3,000 chunks collapsed to legal units by best chunk plus 0.15 x the second
best, recall against the gold units):

  full      the float query against float chunk vectors -- read from the run's metrics.json (the GPU kept no float
            corpus vector; docs/03 stores none)
  binary    the query's sign bits against the chunk sign bits, Hamming -- recomputed HERE from bits.npy and checked
            against the run's own binary numbers (a mismatch means this script does not score what the kernel scored)
  rescore@W the Hamming top W chunks re-scored by the FLOAT query against each chunk's +-1 bits (asymmetric scoring:
            q . (2b - 1) / sqrt(1024), the cosine between the query and the sign vector), then collapsed. This is what
            serving can do with the bits it stores and the query it encodes -- no float corpus vector anywhere.

QUERY_DIR holds q-<slug>.npy from tools/kaggle/query_kernel.py (the dev questions in dev.json order). Writes the
table to stdout and, with --out, a JSON record. TEST cases are not read (they are not in dev.json).
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np

POP = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint16)


def load_chunks(ds: Path):
    units, juris = [], []
    path = ds / "chunks.jsonl.gz"
    with (gzip.open(path, "rt", encoding="utf-8") if path.exists() else open(ds / "chunks.jsonl", encoding="utf-8")) as f:
        for line in f:
            # only the two fields needed; the text is skipped without building it into a Python object per line
            i = line.index('"u": ')
            j = line.index('"j": "', i)
            units.append(int(line[i + 5:line.index(",", i)]))
            juris.append(line[j + 6:line.index('"', j + 6)])
    jnames = sorted(set(juris))
    jmap = {n: k for k, n in enumerate(jnames)}
    return np.asarray(units, dtype=np.int64), np.asarray([jmap[j] for j in juris], dtype=np.int8), jnames


def collapse(units, rows, scores):
    best: dict[int, list[float]] = {}
    for row, s in zip(rows, scores):
        u = int(units[row])
        b = best.get(u)
        if b is None:
            best[u] = [s, -1e9]
        elif s > b[0]:
            best[u] = [s, b[0]]
        elif s > b[1]:
            best[u][1] = s
    return [u for u, _ in sorted(best.items(), key=lambda kv: -(kv[1][0] + 0.15 * max(kv[1][1], 0)))]


def score(case, ranked):
    gold = set(case["gold"])
    hit = [r for r, u in enumerate(ranked, 1) if u in gold]
    return {"r10": sum(1 for u in ranked[:10] if u in gold) / max(1, case["gold_total"]),
            "r50": sum(1 for u in ranked[:50] if u in gold) / max(1, case["gold_total"]),
            "mrr10": 1 / hit[0] if hit and hit[0] <= 10 else 0.0}


def agg(rows):
    return {k: round(float(np.mean([r[k] for r in rows])), 4) for k in ("r10", "r50", "mrr10")} | {"n": len(rows)}


def summarise(rows):
    out = {"all": agg(rows)}
    for key in ("stratum", "script"):
        for v in sorted({r[key] for r in rows}):
            out[f"{key}:{v}"] = agg([r for r in rows if r[key] == v])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("queries")
    ap.add_argument("runs", nargs="+", help="RUN_DIR/SLUG")
    ap.add_argument("--widths", default="300,1000,3000")
    ap.add_argument("--out")
    a = ap.parse_args()
    ds, qd = Path(a.ds), Path(a.queries)
    units, jidx, jnames = load_chunks(ds)
    dev = json.loads((ds / "dev.json").read_text(encoding="utf-8"))
    widths = [int(w) for w in a.widths.split(",")]
    signs = np.array([-1.0, 1.0], dtype=np.float32)
    record = {}
    for spec in a.runs:
        run, slug = spec.rsplit("/", 1)
        m = json.loads((Path(run) / "out" / slug / "metrics.json").read_text(encoding="utf-8"))
        bits = np.load(Path(run) / "out" / slug / "bits.npy", mmap_mode="r")
        assert bits.shape == (len(units), 128), (bits.shape, len(units))
        qv = np.load(qd / f"q-{slug}.npy")
        assert qv.shape == (len(dev), 1024)
        qbits = np.packbits(qv > 0, axis=1)
        arms: dict[str, list] = {"binary": []} | {f"rescore@{w}": [] for w in widths}
        for c, q, qb in zip(dev, qv, qbits):
            cand = np.nonzero(np.isin(jidx, [jnames.index(j) for j in c["juris"] if j in jnames]))[0]
            cb = np.asarray(bits[cand])
            ham = -POP[np.bitwise_xor(cb, qb[None, :])].sum(axis=1).astype(np.float32)
            k = min(3000, len(cand))
            part = np.argpartition(-ham, k - 1)[:k]
            part = part[np.argsort(-ham[part], kind="stable")]
            meta = {"case": c["case"], "stratum": c["stratum"], "script": c["script"]}
            arms["binary"].append(meta | score(c, collapse(units, cand[part], ham[part])[:50]))
            order = np.argsort(-ham, kind="stable")
            for w in widths:
                top = order[:min(w, len(cand))]
                pm = signs[np.unpackbits(cb[top], axis=1)]                # +-1, first dimension first
                s = (pm @ q) / 32.0                                     # cosine of q with the sign vector
                o = np.argsort(-s, kind="stable")
                arms[f"rescore@{w}"].append(meta | score(c, collapse(units, cand[top[o]], s[o])[:50]))
        res = {"full": m["full_precision"], "binary_kernel": m["binary"]} | {k: summarise(v) for k, v in arms.items()}
        drift = abs(res["binary"]["all"]["r50"] - m["binary"]["all"]["r50"])
        print(f"\n== {slug}  (binary recomputed vs kernel: r50 {res['binary']['all']['r50']} vs "
              f"{m['binary']['all']['r50']}{'  MISMATCH' if drift > 0.01 else ''})")
        names = ["full", "binary"] + [f"rescore@{w}" for w in widths]
        print(f"   {'slice':22} {'n':>4}  " + "  ".join(f"{n:>17}" for n in names))
        for sl in res["full"]:
            print(f"   {sl:22} {res['full'][sl]['n']:>4}  " + "  ".join(
                f"{res[n][sl]['r10']:.3f}/{res[n][sl]['r50']:.3f}".rjust(17) for n in names if sl in res[n]))
        record[slug] = res | {"model": m["model"], "revision": m["revision"]}
    if a.out:
        Path(a.out).write_text(json.dumps({"split": "dev", "cases": len(dev), "models": record}, indent=1),
                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
