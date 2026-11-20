"""gate_fit.py [--features evals/results/gate-features-dev-<date>.json] : fit the sufficiency gate on DEV under the rule
fixed before any score existed (evals/results/gate-rule-2026-11-20.json; D-102) and write the calibration serving
reads (nizam/retrieval/gate_calibration.json) plus the dev report (evals/results/gate-fit-dev-<date>.json).

Per mode (cpu, gpu, unreranked):
  1. rows = the dev cases scored in that mode (a case with no candidate is not scored: it abstains);
  2. for each candidate feature set F1-F3: leave-one-family-out logistic regression (standardised features, L2
     lambda 1.0 on the weights, Newton) -> out-of-fold probabilities -> log loss; choose the lowest, a set within
     0.005 with fewer features winning;
  3. tau = the smallest out-of-fold probability at which answered precision (sufficient among p >= tau) reaches the
     target (0.95) with at least 5 passing; if under 10% of sufficient cases pass, the target is 0.90; if still
     under 10%, the mode ships no calibration (it abstains);
  4. refit on all dev rows with the chosen set; that model and tau are served.
Nothing here reads the test split.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RULE = json.loads((ROOT / "evals/results/gate-rule-2026-11-20.json").read_text(encoding="utf-8"))
ADDENDUM = json.loads((ROOT / "evals/results/gate-rule-addendum-agree-2026-11-20.json").read_text(encoding="utf-8"))
SETS = {**RULE["candidate_feature_sets"], **ADDENDUM["candidate_feature_sets_added"]}
LAMBDA = 1.0
TARGETS = (0.95, 0.90)
MIN_PASS = 5
MIN_COVERAGE = 0.10
TIE = 0.005
VERSION = "gate-v2-2026-11-20"     # v1: D-102 (120 dev cases); v2: D-106 (305 dev cases, aliases, D-103 corpus)


def fit(X: np.ndarray, y: np.ndarray, lam: float = LAMBDA, iters: int = 100):
    """ridge logistic regression by Newton: returns (mean, scale, coef, intercept) with X standardised inside"""
    mu = X.mean(0)
    sd = X.std(0)
    sd[sd == 0] = 1.0
    Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    w = np.zeros(Z.shape[1])
    pen = np.full(Z.shape[1], lam)
    pen[0] = 0.0                                       # the intercept is not penalised
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))
        g = Z.T @ (p - y) + pen * w
        H = (Z * (p * (1 - p))[:, None]).T @ Z + np.diag(pen) + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-10:
            break
    return mu, sd, w[1:], float(w[0])


def predict(X, mu, sd, coef, b):
    return 1 / (1 + np.exp(-np.clip(((X - mu) / sd) @ coef + b, -30, 30)))


def oof(X, y, groups):
    out = np.zeros(len(y))
    for g in sorted(set(groups)):
        te = np.array([x == g for x in groups])
        if te.all() or len(set(y[~te])) < 2:
            out[te] = y[~te].mean() if (~te).any() else 0.5
            continue
        out[te] = predict(X[te], *fit(X[~te], y[~te]))
    return out


def log_loss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def ece(p, y, bins=10):
    e = 0.0
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        m = (p >= lo) & ((p < hi) if i < bins - 1 else (p <= hi))
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(e)


def choose_tau(p, y, target):
    """smallest p* with precision(p >= p*) >= target and at least MIN_PASS passing; None if none"""
    best = None
    for t in sorted(set(np.round(p, 9)), reverse=True):
        m = p >= t
        if m.sum() >= MIN_PASS and y[m].mean() >= target:
            best = float(t)
    return best


def risk_coverage(p, y):
    order = np.argsort(-p)
    pts = []
    for n in range(1, len(p) + 1):
        sel = order[:n]
        pts.append({"passed": n, "tau": round(float(p[order[n - 1]]), 4), "precision": round(float(y[sel].mean()), 4)})
    return pts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path,
                    default=Path(sorted(glob.glob(str(ROOT / "evals/results/gate-features-dev-*.json")))[-1]))
    ap.add_argument("--calibration", type=Path, default=ROOT / "nizam/retrieval/gate_calibration.json")
    ap.add_argument("--report", type=Path, default=ROOT / f"evals/results/gate-fit-dev-{date.today().isoformat()}.json")
    a = ap.parse_args()
    data = json.loads(a.features.read_text(encoding="utf-8"))
    if data["split"] != "dev":
        sys.exit("the gate is fitted on dev only")
    cases = data["cases"]
    modes_out, report = {}, {"rule": "evals/results/gate-rule-2026-11-20.json", "features_file": str(a.features.name),
                             "provisional": data["provisional"], "modes": {}}
    for mode in ("cpu", "gpu", "unreranked"):
        rows = [(cid, c, c["modes"][mode]) for cid, c in sorted(cases.items())
                if mode in c.get("modes", {}) and not c["modes"][mode].get("pending")]
        if not rows:
            report["modes"][mode] = {"status": "no rows"}
            continue
        pending = sum(1 for c in cases.values() if c.get("modes", {}).get(mode, {}).get("pending"))
        if pending:
            report["modes"][mode] = {"status": f"{pending} cases pending -- not fitted"}
            continue
        scored = [(cid, c, m) for cid, c, m in rows if m["features"]["top"] is not None]
        y = np.array([m["sufficient"] for _, _, m in scored], dtype=float)
        groups = [c["family"] for _, c, _ in scored]
        rep = {"cases": len(rows), "scored": len(scored), "unscored_abstain": len(rows) - len(scored),
               "sufficient": int(y.sum()), "sufficient_share": round(float(y.mean()), 4), "sets": {}}
        best = None
        for name, feats in SETS.items():
            X = np.array([[m["features"][f] for f in feats] for _, _, m in scored], dtype=float)
            p = oof(X, y, groups)
            ll = log_loss(p, y)
            rep["sets"][name] = {"features": feats, "oof_log_loss": round(ll, 4), "oof_ece": round(ece(p, y), 4)}
            if best is None or ll < best[1] - TIE or (abs(ll - best[1]) <= TIE and len(feats) < len(SETS[best[0]])):
                best = (name, ll, p, X)
        name, ll, p, X = best
        rep["chosen"] = name
        tau, target = None, None
        for t in TARGETS:
            cand = choose_tau(p, y, t)
            cov = float(((p >= cand) & (y == 1)).sum() / max(y.sum(), 1)) if cand is not None else 0.0
            rep[f"tau_at_{t}"] = {"tau": cand, "coverage_of_sufficient": round(cov, 4)}
            if cand is not None and cov >= MIN_COVERAGE:
                tau, target = cand, t
                break
        rep["risk_coverage_oof"] = risk_coverage(p, y)
        if tau is None:
            rep["status"] = "no calibration ships: no threshold met the target with 10% coverage"
            report["modes"][mode] = rep
            continue
        passed = p >= tau
        rep.update(status="calibrated", target_precision=target, tau=round(tau, 6),
                   oof_answered_precision=round(float(y[passed].mean()), 4), oof_passed=int(passed.sum()),
                   oof_coverage_of_sufficient=round(float((passed & (y == 1)).sum() / y.sum()), 4),
                   oof_wrong_answers=int((passed & (y == 0)).sum()))
        mu, sd, coef, b = fit(X, y)
        ident = {m["reranker"] for _, _, m in scored} if mode != "unreranked" else None
        gens = {m["dense_generation"] for _, _, m in scored}
        if (ident is not None and len(ident) != 1) or len(gens) != 1:
            sys.exit(f"{mode}: rows from more than one reranker/space: {ident} {gens}")
        cal = {"features": SETS[name], "mean": [round(float(x), 8) for x in mu],
               "scale": [round(float(x), 8) for x in sd], "coef": [round(float(x), 8) for x in coef],
               "intercept": round(b, 8), "tau": round(tau, 6), "target_precision": target,
               "dense_generation": gens.pop(), "fitted_on": f"dev, split-v1, {len(scored)} scored cases",
               "oof_answered_precision": rep["oof_answered_precision"],
               "oof_coverage_of_sufficient": rep["oof_coverage_of_sufficient"]}
        if ident is not None:
            cal["reranker"] = ident.pop()
        modes_out[mode] = cal
        report["modes"][mode] = rep
        print(f"{mode}: {name} ll={ll:.4f} tau={tau:.4f} target={target} "
              f"oof precision={rep['oof_answered_precision']} coverage={rep['oof_coverage_of_sufficient']} "
              f"passed={rep['oof_passed']}/{len(scored)} (sufficient {int(y.sum())})")
    calib = {"version": VERSION, "rule": "evals/results/gate-rule-2026-11-20.json",
             "addenda": ["evals/results/gate-rule-addendum-agree-2026-11-20.json",
                         "evals/results/gate-rule-addendum-scope-2026-11-20.json"],
             "provisional": "fitted on draft golden sets 1-10 (D-095, D-104); refit when the reviewed split exists",
             "bundle": data["bundle"], "modes": modes_out}
    a.calibration.write_text(json.dumps(calib, indent=1) + "\n", encoding="utf-8")
    a.report.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"wrote {a.calibration} and {a.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
