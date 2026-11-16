"""Make one blank review sheet per annotator from a golden set file (docs/10 §5 stage A1).

Each annotator gets the SAME rows and fills them alone, without seeing the other's sheet or any system output:

  * one 'outcome' row per case: is the expected outcome right (answer / conditional / abstain)?
  * one 'unit' row per proposed provision: how relevant is it to the question (grade 0-3), and is its role right
    (necessary / relevant / hard negative)?
  * one 'missing' row per case: any provision the annotator thinks is needed but not listed (write its law and
    section; the data engineer resolves it to a provision id at stage A3).

    python evals/golden/make_review_sheets.py evals/golden/golden-pk-v1-set1.draft.jsonl --annotators A B
Writes evals/golden/review/<set>-annotator-<X>.csv. Open in Excel / Google Sheets / LibreOffice; fill only the
'your_' columns; save as CSV.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

COLUMNS = ["case_id", "row_type", "stratum", "jurisdiction", "territory", "as_of", "question", "proposition",
           "proposed_outcome", "unit_role", "law", "section", "provision_id", "status_currency", "excerpt",
           "official_url", "proposed_grade",
           "your_outcome", "your_grade", "your_role", "your_missing_law_and_section", "your_notes"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("golden", type=Path)
    ap.add_argument("--annotators", nargs="+", default=["A", "B"])
    a = ap.parse_args()
    cases = [json.loads(l) for l in a.golden.open(encoding="utf-8") if l.strip()]
    rows = []
    for c in cases:
        base = dict(case_id=c["caseId"], stratum=c["stratum"], jurisdiction=c["scope"]["jurisdiction"],
                    territory=c["scope"]["territory"] or "", as_of=c["scope"]["asOf"], question=c["question"]["text"],
                    proposition=" | ".join(p["text"] for p in c["propositions"]),
                    proposed_outcome=c["expectedOutcome"])
        rows.append(dict(base, row_type="outcome"))
        for role, key in (("necessary", "necessaryUnits"), ("relevant", "relevantUnits"),
                          ("hard_negative", "hardNegatives")):
            for u in c["retrievalGold"][key]:
                rows.append(dict(base, row_type="unit", unit_role=role, law=u["instrument"], section=u["label"],
                                 provision_id=u["provisionId"],
                                 status_currency=f"{u.get('currency')}: {u.get('currencyReason')}",
                                 excerpt=u["excerpt"][:400], official_url=u["officialUrl"],
                                 proposed_grade=u["grade"]))
        rows.append(dict(base, row_type="missing"))
    out = a.golden.parent / "review"
    out.mkdir(exist_ok=True)
    stem = a.golden.name.split(".")[0]
    for who in a.annotators:
        p = out / f"{stem}-annotator-{who}.csv"
        if p.exists():
            print(f"exists, not overwritten (an annotator may be filling it): {p}")
            continue
        with p.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS); w.writeheader(); w.writerows(rows)
        print(f"{len(rows)} rows -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
