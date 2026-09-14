"""Blocked documents today's parser would make worse, and by what.

`find_stale_trees` reports how many documents replaying would cost but not why,
so its "costs" set has sat at 77-80 all session as an opaque number. It is the
most interesting set in the corpus: every entry is a document where a parser
that has been fixed eighteen times still loses to a tree built by an older one.
Each is either a defect worth finding or a stored tree that was never right.

This joins a whole-corpus fingerprint against the stored trees and prints the
difference per document, ordered by how much is lost, so the set can be read
instead of counted.

    ./nz parser-worse .fp_fn_on.tsv
    ./nz parser-worse .fp_fn_on.tsv --show 30

Reads only.
"""
from __future__ import annotations

import argparse
import csv

from nizam.storage.db import connect

STORED = """
SELECT i.document_id,
       (SELECT count(*) FROM provision p WHERE p.instrument_id = i.id
          AND p.is_active AND p.kind IN ('section','article')),
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id = i.id),
       (SELECT count(*) FROM v_structural_adjudication_pending s
         WHERE s.instrument_id = i.id),
       (i.id IN (SELECT id FROM v_release_instrument)),
       left(coalesce(i.short_title, ''), 38)
  FROM instrument i
 WHERE i.is_active AND i.duplicate_of IS NULL
   AND (EXISTS (SELECT 1 FROM v_toc_gap_pending g WHERE g.instrument_id = i.id)
     OR EXISTS (SELECT 1 FROM v_structural_adjudication_pending s
                 WHERE s.instrument_id = i.id))
   -- A document already split into several expressions cannot be compared
   -- against a WHOLE-DOCUMENT fingerprint: the parser run covers all of them at
   -- once, so one expression's tree always looks smaller. Document 3949 read as
   -- "30 sections -> 16, 0 gaps -> 61" that way and was written up as an
   -- unsplit compendium; it already has three active instruments. The same
   -- omission has now been made three times in this repo -- find_stale_trees
   -- and released_but_understructured both carry the fix.
   AND (SELECT count(*) FROM instrument o
         WHERE o.document_id = i.document_id
           AND o.is_active AND o.duplicate_of IS NULL) = 1
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fingerprint")
    ap.add_argument("--show", type=int, default=20)
    a = ap.parse_args()

    now: dict[int, dict] = {}
    for row in csv.DictReader(open(a.fingerprint, encoding="utf-8"),
                              delimiter="\t"):
        doc = row.get("document")
        if not doc or not doc.isdigit():
            continue
        if not str(row.get("sections", "")).lstrip("-").isdigit():
            continue
        now[int(doc)] = {k: int(row[k]) for k in
                         ("sections", "provisions", "missing_toc", "demoted",
                          "unlinked", "stranded")}

    with connect() as conn, conn.cursor() as cur:
        cur.execute(STORED)
        stored = {r[0]: {"sections": r[1], "gaps": r[2], "s7": r[3],
                         "released": r[4], "title": r[5]}
                  for r in cur.fetchall()}

    worse = []
    for doc, was in stored.items():
        has = now.get(doc)
        if has is None:
            continue
        # the gate counts unlinked contents rows; fail closed on either arm
        now_gaps = max(has["unlinked"], max(has["missing_toc"], 0))
        lost_sections = was["sections"] - has["sections"]
        gained_gaps = now_gaps - was["gaps"]
        if gained_gaps > 0 or lost_sections > 0:
            worse.append((lost_sections, gained_gaps, doc, was, has))

    worse.sort(reverse=True)
    print(f"blocked documents compared        : {len(stored)}")
    print(f"today's parser would make worse   : {len(worse)}")
    print(f"  sections it would lose in total : "
          f"{sum(max(0, w[0]) for w in worse)}")
    print(f"  gaps it would add in total      : "
          f"{sum(max(0, w[1]) for w in worse)}\n")
    print(f"{'doc':>6} {'sections':>16} {'gaps':>14}  title")
    for lost, gained, doc, was, has in worse[:a.show]:
        print(f"{doc:>6} {was['sections']:>7} -> {has['sections']:<6} "
              f"{was['gaps']:>5} -> {max(has['unlinked'], max(has['missing_toc'],0)):<6}"
              f"  {was['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
