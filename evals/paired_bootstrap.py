"""paired_bootstrap.py METRICS_JSON [ARM_A ARM_B] : paired bootstrap CI of (B - A) per metric, over the same dev cases.

Default arms: per_case_full vs per_case_binary from a bake-off run's metrics.json (tools/kaggle/embed_kernel.py) --
the same query vectors, so the pair isolates what binarising the corpus costs (ADR-1d). Cases are resampled with
replacement 10,000 times (seeded); the 95% interval is the 2.5th..97.5th percentile of the mean difference. This is
the percentile paired bootstrap (Efron & Tibshirani 1993, ch. 13); docs/10 asks for intervals on every comparison.
"""
from __future__ import annotations

import json
import sys

import numpy as np


def paired(a: list[dict], b: list[dict], key: str, n: int = 10_000, seed: int = 0) -> dict:
    ia = {r["case"]: r[key] for r in a}
    ib = {r["case"]: r[key] for r in b}
    cases = sorted(set(ia) & set(ib))
    d = np.array([ib[c] - ia[c] for c in cases], dtype=float)
    rng = np.random.default_rng(seed)
    boots = d[rng.integers(0, len(d), size=(n, len(d)))].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"n": len(d), "mean": round(float(d.mean()), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "worse": int((d < 0).sum()), "better": int((d > 0).sum())}


def main() -> int:
    m = json.load(open(sys.argv[1], encoding="utf-8"))
    arm_a, arm_b = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("per_case_full", "per_case_binary")
    out = {k: paired(m[arm_a], m[arm_b], k) for k in ("r10", "r50", "mrr10")}
    print(json.dumps({"model": m.get("model"), "b_minus_a": f"{arm_b} - {arm_a}", **out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
