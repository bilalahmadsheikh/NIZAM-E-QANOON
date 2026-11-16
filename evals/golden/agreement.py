"""Agreement between two filled review sheets (docs/10 §5 stage A1: 'raw agreement, categorical agreement').

    python evals/golden/agreement.py evals/golden/review/golden-pk-v1-set1-annotator-A.csv \
                                     evals/golden/review/golden-pk-v1-set1-annotator-B.csv

Reports, for grades (0-3) and for outcomes: the number of items both annotators filled, percent agreement, Cohen's
kappa (chance-corrected, unweighted: kappa = (po - pe) / (1 - pe), pe from each annotator's own marginals), and the
confusion table; then lists every disagreement for the adjudicator (stage A2). docs/10: "do not worship one
coefficient" -- low agreement means improve the guidance or keep the ambiguity, never majority-vote it away.
Before quoting a figure in the thesis, confirm the kappa definition against a cited source (nizam-evals skill).
Writes <sheet A stem>-disagreements.csv beside the sheets.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path


def read(p: Path) -> dict:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return {(r["case_id"], r["row_type"], r.get("provision_id", "")): r for r in csv.DictReader(f)}


def kappa(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan")
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")


def table(pairs, labels):
    t = Counter(pairs)
    head = "A\\B " + " ".join(f"{l:>5}" for l in labels)
    lines = [head] + [f"{a:>4} " + " ".join(f"{t[(a, b)]:>5}" for b in labels) for a in labels]
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__); return 2
    pa, pb = Path(sys.argv[1]), Path(sys.argv[2])
    A, B = read(pa), read(pb)
    disagreements = []
    for what, col, rowtype in (("grade", "your_grade", "unit"), ("outcome", "your_outcome", "outcome")):
        pairs = []
        for k, ra in A.items():
            if k[1] != rowtype or k not in B:
                continue
            a, b = ra[col].strip().lower(), B[k][col].strip().lower()
            if not a or not b:
                continue
            pairs.append((a, b))
            if a != b:
                disagreements.append(dict(case_id=k[0], item=what, provision_id=k[2], law=ra.get("law", ""),
                                          section=ra.get("section", ""), annotator_A=a, annotator_B=b,
                                          notes_A=ra["your_notes"], notes_B=B[k]["your_notes"]))
        po, k = kappa(pairs)
        labels = sorted({x for p in pairs for x in p})
        print(f"== {what}: {len(pairs)} items both filled; agreement {po:.3f}; Cohen's kappa {k:.3f}")
        if pairs:
            print(table(pairs, labels))
    out = pa.with_name(pa.stem.replace("-annotator-A", "") + "-disagreements.csv")
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "item", "provision_id", "law", "section", "annotator_A",
                                          "annotator_B", "notes_A", "notes_B", "adjudicated_value",
                                          "adjudicator_reason"])
        w.writeheader(); w.writerows(disagreements)
    print(f"{len(disagreements)} disagreements -> {out} (the adjudicator fills adjudicated_value and reason)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
