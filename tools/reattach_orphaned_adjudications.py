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

WHAT IT REFUSES. A reading is re-attached where exactly ONE unadjudicated
candidate now stands on that document and block. Where several do, it is
re-attached only if exactly one has the same printed label, source anchors,
candidate evidence, provision metadata, and candidate/canonical source-block
footprints as the retired candidate. Otherwise it is left for a reader. This
does not infer which of several different labels on one block is law. Readings
whose block carries no candidate at all are reported as resolved: the replay
removed the collision, so there is nothing to re-attach.

WHAT IT DOES NOT TOUCH: the observation. `observed` is the READER'S
description of the page, and until 21 Sep 2026 this tool appended its own
provenance to it -- 199 characters of prose per carry, compounding. Document
1154, block 56861, label '2' ran 861 -> 1060 -> 1259 -> 1458 characters across
three replays around one 861-character kernel; corpus-wide 1,439 decisions
carry 407,500 characters of boilerplate, 12.6% of all S7 observation text, and
anything reading note length as a quality signal was reading provenance.
The provenance is now structured, in `evidence.reattachment` --
`from_adjudication_id`, `origin`, `generation`, `basis` -- and the observation
carried forward is the reader's own words, with any note an earlier run
appended taken back off. Nothing already written is rewritten; the rows are
append-only and keep the notes they were made with.

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

import re

from nizam.storage.db import connect

REATTACH_BASIS = (
    "matched on (document_id, source_block_id), which is stable across "
    "re-segmentation where candidate_id is not; the printed page this "
    "observation describes has not changed"
)

# Notes this tool appended to `observed` before 21 Sep 2026, when it carried
# its provenance as prose. Every carry appended another 199 characters, so a
# decision that survived three replays reached 1,458 characters around an
# 861-character kernel -- document 1154, block 56861, label '2' is the
# specimen. Measured 21 Sep 2026: 1,439 decisions carry such a note (1,104 in
# the wording below, 335 in an earlier "after the 18 Sep replay" variant), and
# 407,500 of the 1,710,330 characters they hold -- 23.8% of those notes, 12.6%
# of all S7 observation text -- are boilerplate. The pattern matches both
# wordings, and any future one, by shape rather than by text.
#
# `observed` is the READER'S description of the page. `s7_audit_record.py` and
# the source-review tooling read it as exactly that, and anything measuring its
# length as a quality signal was measuring provenance instead. So the
# provenance now goes in `evidence.reattachment` as structured fields, and this
# pattern recovers the reader's words from a note an earlier run inflated.
#
# Nothing is rewritten: the append-only rows keep the notes they were written
# with. This strips at EMIT time, so the next carry forward of an old decision
# restores its kernel instead of compounding it.
_REATTACH_NOTE = re.compile(r"\s*\[RE-ATTACHED[^\]]*\]")


def reader_words(observed: str | None) -> str:
    """The observation with every machine-appended re-attachment note removed."""
    return _REATTACH_NOTE.sub("", observed or "").strip()

ORPHANS = """
WITH orphan AS (
  SELECT DISTINCT ON (c.document_id, c.source_block_id)
         a.id AS adjudication_id, a.resolution, a.evidence,
         c.id AS old_candidate_id,
         c.document_id, c.source_block_id,
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
       o.adjudication_id,
       o.evidence->>'observed'        AS observed,
       o.evidence->'reattachment'     AS prior_reattachment,
       o.evidence->>'render_artifact' AS render,
       o.evidence->>'render_sha256'   AS render_sha256,
       o.evidence->'structural_overrides' AS structural_overrides,
       o.old_candidate_id,
       nc.id                          AS new_candidate_id,
       nc.label                       AS new_label,
       coalesce(nc.n, 0)              AS candidates_on_that_block
  FROM orphan o
  LEFT JOIN newcand nc
         ON nc.document_id = o.document_id
        AND nc.source_block_id = o.source_block_id
 ORDER BY o.document_id, o.label
"""

# UUIDs change on replay. These fields describe the *source-backed candidate*,
# not its generated identity. In particular, the two payload arrays compare
# every source block (and assigned character count) beneath the old and new
# candidate and canonical provisions. A matching label alone is insufficient
# when a single PDF block printed several numbered units.
FINGERPRINTS = """
SELECT c.id::text, c.document_id, c.source_block_id,
       btrim(c.printed_label), c.source_page,
       c.canonical_source_block_id, c.canonical_source_page,
       c.original_kind::text, c.proposed_resolution, c.decision_kind,
       c.evidence,
       cp.kind::text, cp.label, cp.heading, cp.marginal_note,
       kp.kind::text, kp.label, kp.heading, kp.marginal_note,
       (SELECT coalesce(jsonb_agg(jsonb_build_array(pb.block_id, pb.chars,
                                                     pb.role::text)
                                  ORDER BY pb.block_id), '[]'::jsonb)
          FROM provision root
          JOIN provision p ON p.instrument_id = root.instrument_id
                          AND p.path <@ root.path
          JOIN provision_block pb ON pb.provision_id = p.id
         WHERE root.id = c.candidate_provision_id),
       (SELECT coalesce(jsonb_agg(jsonb_build_array(pb.block_id, pb.chars,
                                                     pb.role::text)
                                  ORDER BY pb.block_id), '[]'::jsonb)
          FROM provision root
          JOIN provision p ON p.instrument_id = root.instrument_id
                          AND p.path <@ root.path
          JOIN provision_block pb ON pb.provision_id = p.id
         WHERE root.id = c.canonical_provision_id)
  FROM segmentation_structural_candidate c
  JOIN provision cp ON cp.id = c.candidate_provision_id
  JOIN provision kp ON kp.id = c.canonical_provision_id
 WHERE c.id = ANY(%s::uuid[])
"""


def exact_ambiguous_match(rows: list[dict], fingerprints: dict) -> dict | None:
    """Return the sole source-identical current candidate, or refuse.

    The old candidate is the same for each joined row. Both the old and new
    fingerprints must exist; a missing or duplicate match is never guessed.
    """
    old = fingerprints.get(str(rows[0]["old_candidate_id"]))
    if old is None:
        return None
    matches = [row for row in rows
               if fingerprints.get(str(row["new_candidate_id"])) == old]
    return matches[0] if len(matches) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=".artifacts/s7-source/reattach.json")
    args = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(ORPHANS)
        rows = cur.fetchall()
        cols = [d.name for d in cur.description]
        orphans = [dict(zip(cols, r)) for r in rows]
        groups: dict[tuple[int, int], list[dict]] = {}
        for row in orphans:
            groups.setdefault((row["document_id"], row["source_block_id"]),
                              []).append(row)
        multi = [rows for rows in groups.values()
                 if rows[0]["candidates_on_that_block"] > 1]
        ids = sorted({str(row["old_candidate_id"])
                      for rows in multi for row in rows}
                     | {str(row["new_candidate_id"])
                        for rows in multi for row in rows})
        fingerprints = {}
        if ids:
            cur.execute(FINGERPRINTS, (ids,))
            fingerprints = {row[0]: row[1:] for row in cur.fetchall()}

    # The LEFT JOIN yields one row per candidate standing on the block, so an
    # ambiguous block arrives two or three times. Count blocks, not join rows --
    # reporting the join count would overstate the reader's queue.
    readings, resolved = [], []
    ambiguous: list[dict] = []
    emptied: list = []
    recovered = 0
    exact = 0
    selected = []
    for rows in groups.values():
        row = rows[0]
        if row["candidates_on_that_block"] == 0:
            resolved.append(row)
        elif row["candidates_on_that_block"] > 1:
            match = exact_ambiguous_match(rows, fingerprints)
            if match is None:
                ambiguous.append(row)
            else:
                selected.append(match)
                exact += 1
        else:
            selected.append(row)

    for row in selected:
            # The reader's words, with any note an earlier run appended taken
            # back off. The provenance travels beside them, not inside them.
            observed = reader_words(row["observed"])
            if len(observed) < len(row["observed"] or ""):
                recovered += len(row["observed"]) - len(observed)
            if len(observed) < 40:
                # Only boilerplate, or nothing. `adjudicate_s7_from_source.py`
                # would refuse it downstream; refuse it here and say why.
                emptied.append(row)
                continue
            prior = row["prior_reattachment"] or {}
            reading = {
                "candidate_id": str(row["new_candidate_id"]),
                "document_id": row["document_id"],
                "printed_label": row["new_label"],
                "resolution": row["resolution"],
                "observed": observed,
                "render": row["render"] or "",
                "render_sha256": row["render_sha256"] or "",
                # Structured provenance: carried into `evidence.reattachment`
                # by the adjudication entry point, never into `observed`.
                "reattached_from": str(row["adjudication_id"]),
                "reattach_origin": prior.get("origin")
                                   or str(row["adjudication_id"]),
                "reattach_generation": int(prior.get("generation", 0)) + 1,
                "reattach_basis": REATTACH_BASIS,
            }
            if row["structural_overrides"]:
                reading["structural_overrides"] = row["structural_overrides"]
            readings.append(reading)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(readings, fh, indent=1, ensure_ascii=False)

    by_resolution: dict[str, int] = {}
    for r in readings:
        by_resolution[r["resolution"]] = by_resolution.get(r["resolution"], 0) + 1

    print(f"orphaned source-verified readings : {len(orphans)}")
    print(f"  re-attachable (one candidate)   : {len(readings)}  -> {args.out}")
    if exact:
        print(f"      exact match on multi-label block: {exact}")
    for name, n in sorted(by_resolution.items(), key=lambda kv: -kv[1]):
        print(f"      {name:<20} {n}")
    print(f"  resolved by the replay          : {len(resolved)}"
          "   (collision gone; nothing to re-attach)")
    if recovered:
        print(f"  reader's words recovered        : {recovered} characters of "
              "appended re-attachment boilerplate stripped from the notes "
              "carried forward")
    if emptied:
        print(f"  refused, nothing left to carry  : {len(emptied)}"
              "   (the note was boilerplate or under 40 characters)")
        for row in emptied[:20]:
            print(f"      doc {row['document_id']:<6} label {row['label']:<8} "
                  f"block {row['source_block_id']}")
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
