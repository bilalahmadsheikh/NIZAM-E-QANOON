"""invalidation_review_load.py SHEET.csv [--apply] : append a lawyer's decisions on judicial invalidation candidates
(D-161; 0146).

The sheet is the one `python -m nizam.workers.invalidation_candidates --sheet DIR` writes. Each row whose `decision`
is filled is appended to judicial_invalidation_review -- evidence, never changed or removed. A decision names its
reviewer. A `lawyer_verified` row must also give what the review establishes:
  provision_id   the provision struck down (the candidate's, or the right one: a reviewer may correct it)
  extent         whole (the unit stops being served) | words (part of its text: say which in extent_note)
  effective_on   the day it takes effect, read from the decision (Art. 203D(2)(b)); for an FSC decision, after the
                 appeal period or the appeal (203D(2) proviso) -- appeal_state: none | time_running | pending | decided
Then: `python -m nizam.workers.invalidation_candidates --apply` (statuses follow) and `python tools/refresh_serving.py`
(the serving snapshot): only then does operative_provision change, and only for verified, whole-unit rows.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
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
    problems = []
    for r in rows:
        d = r["decision"].strip()
        if d not in DECISIONS or not (r.get("reviewer") or "").strip():
            problems.append(f"{r['review_key'][:12]}: decision {d!r} / reviewer missing")
        elif d == "lawyer_verified":
            if not r.get("provision_id") or r.get("extent") not in ("whole", "words"):
                problems.append(f"{r['review_key'][:12]}: verified needs provision_id and extent whole|words")
            try:
                dt.date.fromisoformat((r.get("effective_on") or "").strip())
            except ValueError:
                problems.append(f"{r['review_key'][:12]}: verified needs effective_on as YYYY-MM-DD")
    if problems:
        sys.exit("refused:\n  " + "\n  ".join(problems[:20]))
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT review_key FROM judicial_invalidation_candidate")
        known = {k for (k,) in cur.fetchall()}
        unknown = [r["review_key"] for r in rows if r["review_key"] not in known]
        if unknown:
            sys.exit(f"{len(unknown)} review keys name no current candidate: {unknown[:3]}")
        for r in rows:
            v = r["decision"].strip() == "lawyer_verified"
            cur.execute("""INSERT INTO judicial_invalidation_review (review_key, decision, provision_id, extent,
                               extent_note, effective_on, appeal_state, reviewer, note)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (r["review_key"], r["decision"].strip(), r.get("provision_id") or None if v else None,
                         r.get("extent") or None if v else None, r.get("extent_note") or None,
                         r.get("effective_on") or None if v else None, r.get("appeal_state") or None,
                         r["reviewer"].strip(), (r.get("note") or "").strip() or None))
        print(f"{len(rows)} reviews {'appended' if a.apply else 'would be appended (dry run)'}")
        conn.commit() if a.apply else conn.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
