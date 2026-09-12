"""Released instruments whose stored tree holds fewer sections than the parser finds.

`find_stale_trees` refuses to replay a released instrument that would come back
with any pending gap or collision, because that costs release. That guard is
right as far as it goes, and it hides a real question: some of those instruments
are released only because their stored tree is too FLAT to disagree with itself.

The Sindh Public Procurement Act, 2009 is the case. Stored: 36 sections, 546
provisions, no contents list, no gaps -- released. Today's parser: 87 sections,
749 provisions, a contents list, and 19 rows it cannot resolve. The 51 sections
in between are not missing from the corpus; they sit as subsections under
"part I", so they are not citable at the number the statute prints (INV-4).
A perfect gap count, because a tree with no contents has nothing to fail.

So this reports the trade rather than taking it: what would be gained in citable
sections against what would be lost in release. It writes nothing.

    ./nz understructured
"""
from __future__ import annotations

import argparse
import csv
import sys

from nizam.storage.db import connect

STORED = """
SELECT i.document_id,
       (SELECT count(*) FROM provision p WHERE p.instrument_id = i.id
          AND p.is_active AND p.kind IN ('section','article')),
       (SELECT count(*) FROM provision p WHERE p.instrument_id = i.id
          AND p.is_active),
       (SELECT count(*) FROM provision p
          JOIN provision par ON par.id = p.parent_id AND par.is_active
         WHERE p.instrument_id = i.id AND p.is_active AND p.kind = 'subsection'
           AND par.kind::text IN ('chapter','part','division'))
  FROM instrument i
 WHERE i.id IN (SELECT id FROM v_release_instrument)
   -- A document already split into several legal expressions cannot be
   -- compared against a whole-document parse: the ordinary worker would
   -- re-merge them. Documents 4434 and 4497 read as 6 -> 356 and 10 -> 210
   -- sections that way, which is the S10 split being undone, not law found.
   AND (SELECT count(*) FROM instrument o
         WHERE o.source_observation_id = i.source_observation_id
           AND o.is_active AND o.duplicate_of IS NULL) = 1
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fingerprint", help="a fingerprint TSV from today's parser")
    ap.add_argument("--show", type=int, default=14)
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
                         ("sections", "provisions", "unlinked", "demoted")}

    with connect() as conn, conn.cursor() as cur:
        cur.execute(STORED)
        stored = {r[0]: {"sections": r[1], "provisions": r[2], "orphans": r[3]}
                  for r in cur.fetchall()}

    rows = []
    for doc, was in stored.items():
        has = now.get(doc)
        if has is None:
            continue
        gained = has["sections"] - was["sections"]
        blocked_after = has["unlinked"] > 0 or has["demoted"] > 0
        if gained > 0 and blocked_after:
            rows.append((doc, was, has, gained))

    rows.sort(key=lambda r: -r[3])
    print(f"released instruments compared     : {len(stored)}")
    print(f"  would gain sections but lose release : {len(rows)}")
    print(f"  citable sections at stake            : "
          f"{sum(r[3] for r in rows)}")
    print(f"  subsections sitting under a division : "
          f"{sum(r[1]['orphans'] for r in rows)}")
    print()
    print(f"{'doc':>6}  {'sections':>16}  {'under a division':>16}  "
          f"{'gaps after':>10}")
    for doc, was, has, gained in rows[:a.show]:
        print(f"{doc:>6}  {was['sections']:>6} -> {has['sections']:<6}  "
              f"{was['orphans']:>16}  {has['unlinked']:>10}")
    if not rows:
        print("  none -- every released instrument is at least as structured "
              "as today's parser would make it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
