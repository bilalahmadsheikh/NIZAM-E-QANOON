"""gate_eval.py --split test [--features F] : the frozen gate (nizam/retrieval/gate_calibration.json) applied to a
split's served features, case by case exactly as nizam.retrieval.gate decides (D-102). On test this is run ONCE per
mode, after gate_fit.py wrote the calibration; nothing is changed after.

Decision per case and mode: a scope veto (time, source, place) -> abstain; no candidate -> abstain; no calibration for
the mode -> abstain; p = gate.probability(features) >= tau -> pass, else abstain.

Reported (evals/results/gate-rule-2026-11-20.json, "report"):
  answered precision   sufficient among passed (Wilson 95%)  -- the gate's promise: what passes holds the law
  coverage             passed among sufficient; passed among answerable
  wrong answers        passed while insufficient (the risk), and passed while the case expects abstention
  unanswerable stratum abstention recall and precision (docs/10: >= 0.90 precision, >= 0.85 recall) -- strict
                       (against expectedOutcome) and against the sufficiency label; the L6-owned
                       professional_review_required cases in their own row
  ECE                  10 equal-width bins over the scored cases
  by script, and vetoes apart from the classifier
PROVISIONAL: golden sets 1-10 are drafts (D-095, D-104).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.retrieval import gate as G  # noqa: E402

L6_CODES = {"professional_review_required"}


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def rate(k, n):
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None, "wilson95": wilson(k, n)}


def decide(case: dict, mode: str, cal: dict) -> dict:
    m = case["modes"].get(mode)
    if m is None or m.get("pending"):
        return {"decision": "missing"}
    if case.get("veto"):
        return {"decision": "abstain", "by": f"veto:{case['veto']['kind']}"}
    if m["features"]["top"] is None:
        return {"decision": "abstain", "by": "empty"}
    c = cal["modes"].get(mode)
    if c is None:
        return {"decision": "abstain", "by": "uncalibrated"}
    p = G.probability(m["features"], c)
    return {"decision": "pass" if p >= c["tau"] else "abstain", "by": "classifier", "p": p}


def summarise(cases: dict, mode: str, cal: dict) -> dict:
    rows = []
    for cid, c in sorted(cases.items()):
        d = decide(c, mode, cal)
        if d["decision"] == "missing":
            continue
        rows.append((cid, c, c["modes"][mode], d))
    if not rows:
        return {"status": "no rows"}
    passed = [r for r in rows if r[3]["decision"] == "pass"]
    abst = [r for r in rows if r[3]["decision"] == "abstain"]
    suff = [r for r in rows if r[2]["sufficient"]]
    answerable = [r for r in rows if r[1]["expected"] in ("answer", "conditional")]
    unans = [r for r in rows if r[1]["expected"] == "abstain"]
    unans_l3 = [r for r in unans if r[1].get("abstention_code") not in L6_CODES]
    unans_l6 = [r for r in unans if r[1].get("abstention_code") in L6_CODES]
    out = {
        "cases": len(rows),
        "passed": len(passed),
        "answered_precision": rate(sum(1 for r in passed if r[2]["sufficient"]), len(passed)),
        "coverage_of_sufficient": rate(sum(1 for r in suff if r[3]["decision"] == "pass"), len(suff)),
        "coverage_of_answerable": rate(sum(1 for r in answerable if r[3]["decision"] == "pass"), len(answerable)),
        "wrong_answers": {"passed_insufficient": sum(1 for r in passed if not r[2]["sufficient"]),
                          "passed_expected_abstain": sum(1 for r in passed if r[1]["expected"] == "abstain"),
                          "cases": [r[0] for r in passed if not r[2]["sufficient"]]},
        "unanswerable": {
            "recall_all": rate(sum(1 for r in unans if r[3]["decision"] == "abstain"), len(unans)),
            "recall_l3_scope": rate(sum(1 for r in unans_l3 if r[3]["decision"] == "abstain"), len(unans_l3)),
            "recall_l6_professional_review": rate(sum(1 for r in unans_l6 if r[3]["decision"] == "abstain"),
                                                  len(unans_l6)),
            "precision_strict": rate(sum(1 for r in abst if r[1]["expected"] == "abstain"), len(abst)),
            "precision_vs_sufficiency": rate(sum(1 for r in abst if not r[2]["sufficient"]), len(abst)),
            "missed": [r[0] for r in unans if r[3]["decision"] == "pass"],
        },
        "abstained_by": {},
        "by_script": {},
    }
    for r in abst:
        out["abstained_by"][r[3]["by"]] = out["abstained_by"].get(r[3]["by"], 0) + 1
    for sc in sorted({r[1]["script"] for r in rows}):
        sr = [r for r in rows if r[1]["script"] == sc]
        sp = [r for r in sr if r[3]["decision"] == "pass"]
        ss = [r for r in sr if r[2]["sufficient"]]
        out["by_script"][sc] = {"cases": len(sr), "passed": len(sp),
                                "answered_precision": rate(sum(1 for r in sp if r[2]["sufficient"]), len(sp)),
                                "coverage_of_sufficient": rate(sum(1 for r in ss if r[3]["decision"] == "pass"),
                                                               len(ss))}
    probs = [(r[3]["p"], r[2]["sufficient"]) for r in rows if "p" in r[3]]
    if probs:
        e = 0.0
        for i in range(10):
            lo, hi = i / 10, (i + 1) / 10
            b = [(p, y) for p, y in probs if lo <= p < hi or (i == 9 and p == 1.0)]
            if b:
                e += len(b) / len(probs) * abs(sum(p for p, _ in b) / len(b) - sum(y for _, y in b) / len(b))
        out["ece"] = round(e, 4)
    # the classifier alone, vetoes off: what the vetoes add
    alone = [(r, decide({**r[1], "veto": None}, mode, cal)) for r in rows]
    out["classifier_alone"] = {
        "unanswerable_recall": rate(sum(1 for r, d in alone if r[1]["expected"] == "abstain" and
                                        d["decision"] == "abstain"), len(unans)),
        "answered_precision": rate(sum(1 for r, d in alone if d["decision"] == "pass" and r[2]["sufficient"]),
                                   sum(1 for _, d in alone if d["decision"] == "pass"))}
    out["vetoes_on_answerable"] = [r[0] for r in answerable if r[1].get("veto")]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--features", type=Path)
    ap.add_argument("--modes", default="cpu,gpu,unreranked")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    f = a.features or Path(sorted(glob.glob(str(ROOT / f"evals/results/gate-features-{a.split}-*.json")))[-1])
    data = json.loads(f.read_text(encoding="utf-8"))
    if data["split"] != a.split:
        sys.exit(f"{f} is the {data['split']} split")
    cal = G.calibration()
    # the vetoes are recomputed from the question with the CURRENT rules (nizam.retrieval.scope), never read from the
    # features file: what is reported is what serving would do
    from nizam.retrieval.query import parse
    from nizam.storage.lexical import Filters
    for fn in sorted(glob.glob(str(ROOT / "evals/golden/golden-pk-v1-set*.draft.jsonl"))):
        for line in open(fn, encoding="utf-8"):
            d = json.loads(line)
            if d["caseId"] in data["cases"]:
                v = G.pre_veto(parse(d["question"]["text"]), Filters(as_of=date.fromisoformat(d["scope"]["asOf"])))
                data["cases"][d["caseId"]]["veto"] = v.__dict__ if v else None
    res = {"provisional": data["provisional"], "split": a.split, "calibration": cal.get("version"),
           "features_file": f.name, "note": ("dev decisions use the REFIT model (in-sample); the honest dev figures are "
                                             "the out-of-fold ones in gate-fit-dev") if a.split == "dev" else
           f"test: scored once after the calibration {cal.get('version')} was frozen (D-102, D-106)",
           "modes": {m: summarise(data["cases"], m, cal) for m in a.modes.split(",")}}
    out = a.out or ROOT / f"evals/results/gate-{a.split}-{date.today().isoformat()}.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    for m, s in res["modes"].items():
        if "answered_precision" in s:
            print(f"{m}: passed {s['passed']}/{s['cases']}  precision {s['answered_precision']['rate']} "
                  f"{s['answered_precision']['wilson95']}  coverage(suff) {s['coverage_of_sufficient']['rate']}  "
                  f"unans recall {s['unanswerable']['recall_all']['rate']} (L3 {s['unanswerable']['recall_l3_scope']['rate']})"
                  f"  abst precision strict {s['unanswerable']['precision_strict']['rate']}  ece {s.get('ece')}")
        else:
            print(m, s)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
