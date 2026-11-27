"""precedent_gate.py: the precedent gate (S2, D-174) under the rule fixed before any score existed
(evals/results/precedent-gate-rule-2026-11-27.json).

    python evals/precedent_gate.py features --split dev --profile cpu --out F
    python evals/precedent_gate.py features --split dev --profile gpu --gpu-vectors BUNDLE --out F
    python evals/precedent_gate.py fit --features F_cpu F_gpu        # DEV only -> nizam/domain/precedent/gate_calibration.json
    python evals/precedent_gate.py eval --features F [--calibration C] --out R   # a frozen gate on a split (test: ONCE)

features: per case, the served path (nizam.domain.precedent.context_for, law join off, gate OFF) at the case's as_of
and forum; the forum veto's finding; the gate's features (nizam.domain.precedent.gate.features); the label
(sufficient: a necessary gold judgment among the first PRESENTED judgments).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

RULE = json.loads((ROOT / "evals/results/precedent-gate-rule-2026-11-27.json").read_text(encoding="utf-8"))
TARGETS, MIN_PASS, MIN_COVERAGE, TIE = (0.90, 0.80), 5, 0.10, 0.005
VERSION = "precedent-gate-v1-2026-11-27"


def features_cmd(split_name: str, profile: str, gpu_vectors: Path | None, out: Path) -> int:
    import precedent_eval as PE
    from nizam.domain.precedent import PrecedentAbstention, context_for
    from nizam.domain.precedent import gate as PG
    from nizam.storage.authority import Subordinate
    from nizam.storage.judgment_read import JudgmentRead
    split = json.loads(PE.SPLIT.read_text(encoding="utf-8"))
    chosen = [c for c in PE.cases() if split_name == "all" or c["familyId"] in split[split_name]]
    if profile == "gpu":
        from precomputed_encoder import PrecomputedEncoder
        enc = PrecomputedEncoder.from_bundle(gpu_vectors, vectors="q.npy", questions="questions.json")
    else:
        from nizam.inference.encoder import encoder
        enc = encoder()
    repo = JudgmentRead()
    repo.open()
    try:
        docs = {u["judgmentDocumentId"] for c in chosen for u in c["precedentGold"]["necessaryJudgments"]}
        with repo.transaction() as conn:
            to_j = PE._doc_to_judgment(conn, docs)
        rows, t0 = {}, time.time()
        for c in chosen:
            as_of = date.fromisoformat(c["scope"]["asOf"])
            forum = Subordinate(c["scope"]["territory"]) if c["scope"].get("forum") else None
            r = context_for(c["question"]["text"], as_of=as_of, forum=forum, k=10, repo=repo, encoder=enc,
                            gate=False)
            gold = {to_j[u["judgmentDocumentId"]] for u in c["precedentGold"]["necessaryJudgments"]
                    if u["judgmentDocumentId"] in to_j}
            row = dict(family=c["familyId"], stratum=c["stratum"], expected=c["expectedOutcome"])
            if isinstance(r, PrecedentAbstention):
                row.update(abstained=r.code, veto=r.trace.get("veto"), features=None, sufficient=False)
            else:
                head = [i.judgment_id for i in r.items[:PG.PRESENTED]]
                row.update(abstained=None, veto=None, features=r.trace["features"], profile=r.trace["profile"],
                           sufficient=bool(c["expectedOutcome"] != "abstain" and gold & set(head)),
                           gold_rank=next((n for n, j in enumerate(head, 1) if j in gold), None))
            rows[c["caseId"]] = row
            print(f"  {c['caseId']}: {row.get('abstained') or row['features']} sufficient={row['sufficient']} "
                  f"({time.time() - t0:.0f}s)", flush=True)
    finally:
        repo.close()
    out.write_text(json.dumps(dict(split=split_name, profile=profile, built=date.today().isoformat(),
                                   rule=RULE["rule"], cases=rows), indent=1), encoding="utf-8")
    print(f"{len(rows)} cases -> {out}")
    return 0


def fit_cmd(paths: list[Path], cal_out: Path, report_out: Path) -> int:
    import gate_fit as GF
    profiles, report = {}, {"rule": "evals/results/precedent-gate-rule-2026-11-27.json", "profiles": {}}
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data["split"] != "dev":
            sys.exit("the precedent gate is fitted on dev only")
        prof = data["profile"]
        scored = [(cid, r) for cid, r in sorted(data["cases"].items()) if r["features"] is not None]
        y = np.array([r["sufficient"] for _, r in scored], dtype=float)
        groups = [r["family"] for _, r in scored]
        rep = {"cases": len(data["cases"]), "scored": len(scored), "vetoed_or_empty": len(data["cases"]) - len(scored),
               "sufficient": int(y.sum()), "sets": {}}
        best = None
        for name, feats in RULE["candidate_feature_sets"].items():
            X = np.array([[r["features"][f] for f in feats] for _, r in scored], dtype=float)
            pr = GF.oof(X, y, groups)
            ll = GF.log_loss(pr, y)
            rep["sets"][name] = {"features": feats, "oof_log_loss": round(ll, 4), "oof_ece": round(GF.ece(pr, y), 4)}
            if best is None or ll < best[1] - TIE or (abs(ll - best[1]) <= TIE and len(feats) < len(
                    RULE["candidate_feature_sets"][best[0]])):
                best = (name, ll, pr, X)
        name, ll, pr, X = best
        rep["chosen"] = name
        tau, target = None, None
        for t in TARGETS:
            cand = GF.choose_tau(pr, y, t)
            cov = float(((pr >= cand) & (y == 1)).sum() / max(y.sum(), 1)) if cand is not None else 0.0
            rep[f"tau_at_{t}"] = {"tau": cand, "coverage_of_sufficient": round(cov, 4)}
            if cand is not None and cov >= MIN_COVERAGE:
                tau, target = cand, t
                break
        rep["risk_coverage_oof"] = GF.risk_coverage(pr, y)
        if tau is None:
            rep["status"] = "no calibration ships: no threshold met the target with 10% coverage"
            report["profiles"][prof] = rep
            print(f"{prof}: no calibration ({name}, ll={ll:.4f})")
            continue
        passed = pr >= tau
        rep.update(status="calibrated", target_precision=target, tau=round(tau, 6),
                   oof_answered_precision=round(float(y[passed].mean()), 4), oof_passed=int(passed.sum()),
                   oof_coverage_of_sufficient=round(float((passed & (y == 1)).sum() / y.sum()), 4))
        mu, sd, coef, b = GF.fit(X, y)
        profiles[prof] = {"features": RULE["candidate_feature_sets"][name],
                          "mean": [round(float(x), 8) for x in mu], "scale": [round(float(x), 8) for x in sd],
                          "coef": [round(float(x), 8) for x in coef], "intercept": round(b, 8),
                          "tau": round(tau, 6), "target_precision": target,
                          "fitted_on": f"dev, split-precedent-v1 (D-168), {len(scored)} scored cases",
                          "oof_answered_precision": rep["oof_answered_precision"],
                          "oof_coverage_of_sufficient": rep["oof_coverage_of_sufficient"]}
        report["profiles"][prof] = rep
        print(f"{prof}: {name} ll={ll:.4f} tau={tau:.4f} target={target} oof precision="
              f"{rep['oof_answered_precision']} coverage={rep['oof_coverage_of_sufficient']} passed="
              f"{rep['oof_passed']}/{len(scored)} (sufficient {int(y.sum())})")
    cal = {"version": VERSION, "rule": report["rule"], "presented": 5,
           "provisional": "fitted on the draft precedent stratum (D-133, D-168); refit when reviewed",
           "profiles": profiles}
    cal_out.write_text(json.dumps(cal, indent=1) + "\n", encoding="utf-8")
    report_out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"wrote {cal_out} and {report_out}")
    return 0


def _wilson(k: int, n: int):
    if not n:
        return None
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(c - h, 4), round(c + h, 4)]


def eval_cmd(path: Path, cal_path: Path | None, out: Path) -> int:
    from nizam.domain.precedent import gate as PG
    data = json.loads(path.read_text(encoding="utf-8"))
    cal = PG.calibration(cal_path) if cal_path else PG.calibration()
    rows = data["cases"]
    dec = {}
    for cid, r in rows.items():
        if r["features"] is None:
            dec[cid] = "abstain"
        else:
            dec[cid] = PG.decide(r["features"], r["profile"], cal)["decision"]
    passed = [c for c in rows if dec[c] == "pass"]
    ok = [c for c in passed if rows[c]["sufficient"]]
    suff = [c for c in rows if rows[c]["sufficient"]]
    unans = [c for c in rows if rows[c]["expected"] == "abstain"]
    res = dict(split=data["split"], profile=data["profile"], calibration=cal.get("version"), cases=len(rows),
               passed=len(passed), answered_precision=dict(k=len(ok), n=len(passed),
                                                          rate=round(len(ok) / len(passed), 4) if passed else None,
                                                          wilson95=_wilson(len(ok), len(passed))),
               coverage_of_sufficient=dict(k=len(ok), n=len(suff), rate=round(len(ok) / len(suff), 4) if suff else None),
               unanswerable_declined=dict(k=sum(1 for c in unans if dec[c] == "abstain"), n=len(unans)),
               wrong_answers=sorted(set(passed) - set(ok)),
               note="label under-counts sufficiency (gold is incomplete): precision is a lower bound")
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("features")
    f.add_argument("--split", choices=["dev", "test"], required=True)
    f.add_argument("--profile", choices=["cpu", "gpu"], required=True)
    f.add_argument("--gpu-vectors", type=Path)
    f.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("fit")
    t.add_argument("--features", type=Path, nargs="+", required=True)
    t.add_argument("--calibration", type=Path, default=ROOT / "nizam/domain/precedent/gate_calibration.json")
    t.add_argument("--report", type=Path, default=ROOT / f"evals/results/precedent-gate-fit-dev-{date.today()}.json")
    e = sub.add_parser("eval")
    e.add_argument("--features", type=Path, required=True)
    e.add_argument("--calibration", type=Path)
    e.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "features":
        if a.profile == "gpu" and not a.gpu_vectors:
            sys.exit("--gpu-vectors is needed for the gpu profile")
        return features_cmd(a.split, a.profile, a.gpu_vectors, a.out)
    if a.cmd == "fit":
        return fit_cmd(a.features, a.calibration, a.report)
    return eval_cmd(a.features, a.calibration, a.out)


if __name__ == "__main__":
    raise SystemExit(main())
