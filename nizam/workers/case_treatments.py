"""Case treatments (D-160; docs/PRECEDENT-MODEL.md §2.1): how each released judgment treats the cases it cites.

    uv run python -m nizam.workers.case_treatments [--apply] [--sheet DIR]

For every resolved case citation (judgment_case_reference, resolution 'resolved', of a released judgment) the
sentence holding it is read by nizam.storage.treatment; a treatment read is a row of case_treatment (0145), a
machine candidate, its review_status set from the latest review of its key (case_treatment_review). Rebuilt in one
transaction by one builder. --sheet writes the negative readings not yet reviewed, with their evidence, for a lawyer
(a CSV the review loader reads back: decision, reviewer, note per review_key).
Run after nizam.workers.judgment_links, whose citations this reads.
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
import time
from pathlib import Path

from nizam.storage.db import connect
from nizam.storage.treatment import NEGATIVE, review_key, sentence_bounds, treatment_of

BUILDER = "nizam.case_treatments/1"
# A court bound by another's decisions cannot overrule, disapprove or hold per incuriam that court's case: its words
# report the superior court's own treatment (an IHC judgment: 'PLD 2016 SC 769 ... is not good law', quoting the
# Supreme Court). Ranked by the recorded court class: apex courts above the shariat and high courts.
_RANK = {"apex": 3, "constitutional_apex": 3, "shariat": 2, "high_court": 2}


def build(cur) -> tuple[list[tuple], collections.Counter, list[dict]]:
    cur.execute("""SELECT DISTINCT ON (review_key) review_key, decision FROM case_treatment_review
                    ORDER BY review_key, reviewed_at DESC""")
    reviews = dict(cur.fetchall())
    cur.execute("SELECT code, court_class FROM court")
    rank = {code: _RANK.get(cls, 1) for code, cls in cur.fetchall()}
    cur.execute("""SELECT r.judgment_id, r.decided_on, r.paragraph_id, r.char_start, r.char_end, r.dst_case_key,
                          r.dst_judgment_id, p.text, j.court_code, j.case_no_printed
                     FROM judgment_case_reference r
                     JOIN v_release_judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
                     JOIN judgment_paragraph p ON p.id = r.paragraph_id AND p.decided_on = r.decided_on
                    WHERE r.resolution = 'resolved' AND r.dst_case_key IS NOT NULL""")
    rows, tally, sheet = [], collections.Counter(), []
    seen = set()
    for jid, day, pid, s, e, dst, dst_j, text, court, case in cur.fetchall():
        a, b = sentence_bounds(text, s, e)
        if (pid, a, dst) in seen:                       # one treatment per sentence and case treated
            continue
        sentence = text[a:b]
        t = treatment_of(sentence)
        if t is None:
            continue
        if t in NEGATIVE and rank.get(court, 1) < rank.get(dst.split("/", 1)[0], 1):
            tally["negative_by_a_court_below:skipped"] += 1     # a report of the superior court's treatment
            continue
        seen.add((pid, a, dst))
        key = review_key(sentence, dst, t)
        status = reviews.get(key, "machine_candidate")
        rows.append((jid, day, pid, s, e, a, b, dst, dst_j, t, "grammar", key, status, BUILDER))
        tally[f"treatment:{t}"] += 1
        tally[f"review:{status}"] += 1
        if t in NEGATIVE and status == "machine_candidate":
            sheet.append(dict(review_key=key, treatment=t, treating=f"{court} {case} ({day})", case_treated=dst,
                              sentence=" ".join(sentence.split()), decision="", reviewer="", note=""))
    return rows, tally, sheet


def main() -> int:
    ap = argparse.ArgumentParser(description="case treatments from the court's own words (D-160)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--sheet", type=Path, help="write the negative readings awaiting review to DIR")
    a = ap.parse_args()
    t0 = time.time()
    with connect() as conn, conn.cursor() as cur:
        rows, tally, sheet = build(cur)
        cur.execute("DELETE FROM case_treatment")
        with cur.copy("COPY case_treatment (judgment_id, decided_on, paragraph_id, cite_start, cite_end, sentence_start, "
                      "sentence_end, dst_case_key, dst_judgment_id, treatment, method, review_key, review_status, "
                      "builder) FROM STDIN") as cp:
            for r in rows:
                cp.write_row(r)
        for k, v in sorted(tally.items()):
            print(f"  {k:28} {v:7,}")
        if a.sheet:
            a.sheet.mkdir(parents=True, exist_ok=True)
            out = a.sheet / f"negative-treatments-{time.strftime('%Y-%m-%d')}.csv"
            with open(out, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(sheet[0]) if sheet else ["review_key"])
                w.writeheader()
                w.writerows(sheet)
            print(f"review sheet: {len(sheet)} negative readings -> {out}")
        if a.apply:
            conn.commit()
            print(f"applied {len(rows)} treatments in {time.time() - t0:.0f}s ({BUILDER})")
        else:
            conn.rollback()
            print("dry run: nothing written (add --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
