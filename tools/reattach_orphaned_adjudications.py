"""Re-attach source-verified adjudications the replay orphaned.

WHY THIS EXISTS. A replay retires every structural candidate and creates fresh
ones, so an adjudication's `candidate_id` no longer resolves. Measured on
19 Sep 2026 after replaying 63 documents to land one contents fix: **all 838
`accept_non_citable` decisions in those documents were orphaned** and 142 of
their collisions came back pending. Over all 430 pre-replay corrective decisions,
242 candidates were retired and the same collision came back for 118 of them.

The readings themselves are not invalidated by a replay. They describe a PRINTED
PAGE, and the page has not changed -- each carries `observed` quoting the page,
the render path and its SHA-256. What breaks is only the pointer.

WHAT IT KEYS ON. `(document_id, source_block_id)`. The block id is stable across
re-segmentation; the candidate id is not. Keying on the printed label instead is
weaker: it matches more rows but cannot tell two collisions on one label apart,
and it silently follows a label that the replay moved to a different node.

WHAT IT REFUSES. A reading is re-attached only where exactly ONE unadjudicated
candidate now stands on that document and block. Where several do, the mapping is
ambiguous and the row is left for a reader -- the tool prints those rather than
guessing. Readings whose block carries no candidate at all are reported as
resolved: the replay removed the collision, so there is nothing to re-attach and
the work is not lost but finished.

HOW IT IS SAFE. It emits a readings file for `adjudicate_s7_from_source.py`,
which re-runs every guard against the CURRENT tree -- including the stub guard
that refuses an `accept_non_citable` whose demoted node still holds law. So a
decision that was right before the replay and is wrong after it is refused rather
than re-stamped. Nothing here writes to the database; apply the file yourself.

    ./nz reattach                      # write the readings file, report counts
    ./nz reattach --out FILE.json      # choose the path

Then, having read the counts:

    ./nz s7-source --readings FILE.json           # dry run, re-checks every guard
    ./nz s7-source --readings FILE.json --apply

Run this after every replay, together with
`tools/resolve_exact_instrument_duplicates.py --apply`, which the replay also
leaves undone: its fresh-insert path never sets `duplicate_of`, so duplicate
groups accumulate silently and carry queue rows of their own.
"""
from __future__ import annotations

import argparse
import json
import os

from nizam.storage.db import connect

RESOLVED_NOTE = (
    " [RE-ATTACHED after a replay: matched on document_id + source_block_id,"
    " which is stable across re-segmentation where candidate_id is not."
    " The printed page this observation describes has not changed.]"
)

ORPHANS = """
WITH orphan AS (
  SELECT DISTINCT ON (c.document_id, c.source_block_id)
         a.resolution, a.evidence, c.document_id, c.source_block_id,
         btrim(c.printed_label) AS label, a.decided_at
    FROM segmentation_structural_adjudication a
    JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
   WHERE a.review_basis = 'source_verified'
     AND a.evidence ? 'observed'
     AND length(a.evidence->>'observed') >= 40
     AND NOT EXISTS (SELECT 1 FROM v_active_structural_candidate v
                      WHERE v.id = a.candidate_id)
   ORDER BY c.document_id, c.source_block_id, a.decided_at DESC),
newcand AS (
  SELECT v.id, v.document_id, v.source_block_id, btrim(v.printed_label) AS label,
         count(*) OVER (PARTITION BY v.document_id, v.source_block_id) AS n
    FROM v_active_structural_candidate v
   WHERE NOT EXISTS (SELECT 1 FROM v_structural_adjudication_latest l
                      WHERE l.candidate_id = v.id))
SELECT o.document_id, o.source_block_id, o.label, o.resolution,
       o.evidence->>'observed'        AS observed,
       o.evidence->>'render_artifact' AS render,
       o.evidence->>'render_sha256'   AS render_sha256,
       nc.id                          AS new_candidate_id,
       nc.label                       AS new_label,
       coalesce(nc.n, 0)              AS candidates_on_that_block
  FROM orphan o
  LEFT JOIN newcand nc
         ON nc.document_id = o.document_id
        AND nc.source_block_id = o.source_block_id
 ORDER BY o.document_id, o.label
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=".artifacts/s7-source/reattach.json")
    args = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(ORPHANS)
        rows = cur.fetchall()
        cols = [d.name for d in cur.description]
    orphans = [dict(zip(cols, r)) for r in rows]

    # The LEFT JOIN yields one row per candidate standing on the block, so an
    # ambiguous block arrives two or three times. Count blocks, not join rows --
    # reporting the join count would overstate the reader's queue.
    readings, resolved = [], []
    ambiguous_by_block: dict = {}
    for row in orphans:
        if row["candidates_on_that_block"] == 0:
            resolved.append(row)
        elif row["candidates_on_that_block"] > 1:
            ambiguous_by_block.setdefault(
                (row["document_id"], row["source_block_id"]), row)
        else:
            readings.append({
                "candidate_id": str(row["new_candidate_id"]),
                "document_id": row["document_id"],
                "printed_label": row["new_label"],
                "resolution": row["resolution"],
                "observed": (row["observed"] or "") + RESOLVED_NOTE,
                "render": row["render"] or "",
                "render_sha256": row["render_sha256"] or "",
            })

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(readings, fh, indent=1, ensure_ascii=False)

    by_resolution: dict[str, int] = {}
    for r in readings:
        by_resolution[r["resolution"]] = by_resolution.get(r["resolution"], 0) + 1

    print(f"orphaned source-verified readings : {len(orphans)}")
    print(f"  re-attachable (one candidate)   : {len(readings)}  -> {args.out}")
    for name, n in sorted(by_resolution.items(), key=lambda kv: -kv[1]):
        print(f"      {name:<20} {n}")
    print(f"  resolved by the replay          : {len(resolved)}"
          "   (collision gone; nothing to re-attach)")
    ambiguous = list(ambiguous_by_block.values())
    print(f"  ambiguous, left for a reader     : {len(ambiguous)} block(s)")
    for row in ambiguous[:20]:
        print(f"      doc {row['document_id']:<6} label {row['label']:<8} "
              f"block {row['source_block_id']}  "
              f"{row['candidates_on_that_block']} candidates")
    if readings:
        print("\nnext: ./nz s7-source --readings "
              f"{args.out}   (dry run re-checks every guard), then --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
