"""treatment_review_load.py SHEET.csv [--apply] : append a reviewer's decisions on case treatments (D-160).

The sheet is the one `python -m nizam.workers.case_treatments --sheet DIR` writes (review_key, treatment, treating,
case_treated, sentence, decision, reviewer, note). Each row whose `decision` is filled (lawyer_verified, contested,
rejected) is appended to case_treatment_review -- evidence, never changed or removed (0145's trigger). A row naming
no reviewer is refused: a decision is somebody's. Then rebuild (`case_treatments --apply`) so the statuses follow.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nizam.storage.db import connect  # noqa: E402

DECISIONS = {"lawyer_verified", "contested", "rejected"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", type=Path)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(a.sheet, encoding="utf-8")) if (r.get("decision") or "").strip()]
    bad = [r["review_key"] for r in rows if r["decision"].strip() not in DECISIONS or not (r.get("reviewer") or "").strip()]
    if bad:
        sys.exit(f"{len(bad)} rows with a decision not in {sorted(DECISIONS)} or no reviewer, e.g. {bad[:3]}")
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT review_key FROM case_treatment")
        known = {k for (k,) in cur.fetchall()}
        unknown = [r["review_key"] for r in rows if r["review_key"] not in known]
        if unknown:
            sys.exit(f"{len(unknown)} review keys name no current treatment (rebuilt since the sheet?): {unknown[:3]}")
        for r in rows:
            cur.execute("INSERT INTO case_treatment_review (review_key, decision, reviewer, note) VALUES (%s, %s, %s, %s)",
                        (r["review_key"], r["decision"].strip(), r["reviewer"].strip(), (r.get("note") or "").strip() or None))
        print(f"{len(rows)} reviews {'appended' if a.apply else 'would be appended (dry run)'}")
        conn.commit() if a.apply else conn.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
