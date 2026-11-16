"""Write a completed review into a golden set (docs/10 §5 stages A2 and A4).

Inputs: the draft set, both annotators' filled sheets, and the adjudicated disagreements sheet. Output: a NEW file
<set>.reviewed.jsonl (the draft is never edited). For every unit and outcome:
  * both annotators agree            -> their value;
  * they disagree                    -> the adjudicator's value (refused if the adjudicator left it blank);
grades of 0 move a unit to hardNegatives; a unit both mark 'remove' is dropped. Each case's review block records the
annotators, the adjudicator, the per-case agreement and the adjudication reasons. Missing provisions an annotator
named are listed in review.missingProposed for the data engineer to resolve (stage A3) -- they are never guessed.

    python evals/golden/apply_review.py SET.jsonl SHEET_A.csv SHEET_B.csv DISAGREEMENTS.csv \
           --annotator-a "name" --annotator-b "name" --adjudicator "name"
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read(p: Path) -> dict:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return {(r["case_id"], r["row_type"], r.get("provision_id", "")): r for r in csv.DictReader(f)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("golden", type=Path); ap.add_argument("sheet_a", type=Path); ap.add_argument("sheet_b", type=Path)
    ap.add_argument("disagreements", type=Path)
    ap.add_argument("--annotator-a", required=True); ap.add_argument("--annotator-b", required=True)
    ap.add_argument("--adjudicator", required=True)
    a = ap.parse_args()
    A, B = read(a.sheet_a), read(a.sheet_b)
    with a.disagreements.open(encoding="utf-8-sig", newline="") as f:
        adj = {(r["case_id"], r["item"], r["provision_id"]): r for r in csv.DictReader(f)}
    problems, out = [], []
    for line in a.golden.open(encoding="utf-8"):
        c = json.loads(line)
        cid, agree, total, reasons = c["caseId"], 0, 0, []

        def settle(item, key, col):
            nonlocal agree, total
            ra, rb = A.get(key), B.get(key)
            va = (ra or {}).get(col, "").strip().lower(); vb = (rb or {}).get(col, "").strip().lower()
            if not va or not vb:
                problems.append(f"{cid} {item} {key[2]}: not filled by both annotators"); return None
            total += 1
            if va == vb:
                agree += 1; return va
            d = adj.get((cid, item, key[2]))
            if not d or not d["adjudicated_value"].strip():
                problems.append(f"{cid} {item} {key[2]}: disagreement not adjudicated"); return None
            reasons.append(f"{item} {key[2] or ''}: A={va} B={vb} -> {d['adjudicated_value']} ({d['adjudicator_reason']})")
            return d["adjudicated_value"].strip().lower()

        oc = settle("outcome", (cid, "outcome", ""), "your_outcome")
        if oc:
            c["expectedOutcome"] = oc
        units = []
        for key in ("necessaryUnits", "relevantUnits", "hardNegatives"):
            for u in c["retrievalGold"][key]:
                g = settle("grade", (cid, "unit", u["provisionId"]), "your_grade")
                if g == "remove":
                    continue
                if g is not None:
                    u["grade"] = int(g)
                units.append(u)
        c["retrievalGold"] = {
            "necessaryUnits": [u for u in units if u["grade"] == 3],
            "relevantUnits": [u for u in units if u["grade"] in (1, 2)],
            "hardNegatives": [u for u in units if u["grade"] == 0]}
        missing = [r["your_missing_law_and_section"] for r in (A.get((cid, "missing", "")), B.get((cid, "missing", "")))
                   if r and r["your_missing_law_and_section"].strip()]
        c["review"] = {"annotatorA": a.annotator_a, "annotatorB": a.annotator_b, "adjudicator": a.adjudicator,
                       "agreement": round(agree / total, 3) if total else None, "reasons": reasons,
                       "missingProposed": missing, "status": "reviewed (A1, A2); A3 for missingProposed; A4 split"}
        c["datasetVersion"] = c["datasetVersion"].replace("-draft", "")
        out.append(c)
    if problems:
        print("NOT WRITTEN -- fix these first:"); [print("  ", p) for p in problems]
        return 1
    dst = a.golden.with_name(a.golden.name.replace(".draft", "").replace(".jsonl", ".reviewed.jsonl"))
    with dst.open("w", encoding="utf-8") as f:
        for c in out:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(out)} reviewed cases -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
