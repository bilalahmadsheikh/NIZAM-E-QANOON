"""Would replaying fix the stub citations, or do they need a decision?

`find_stub_citations` shows 359 citations across 194 documents resolving to
less than half the provision: a phantom node kept the section number and the
real body, arriving later with the same label, was retyped non-citable.

The phantoms are anchored to footnotes, wrapped continuations and provisos --
the family `_section_numbers` stopped producing when the `_is_furniture` filter
landed. Those trees were built before the fix and have never been replayed, so
some unknown share of the queue needs no adjudication at all, only a replay.

Unknown is not a plan. This runs today's segmenter over each affected document
and asks what it now builds for the label in question:

  fixed        one node carries the label, it is a section, and it has text
  still split  two or more siblings carry it -- the defect survives
  now empty    the label survives only as a node with no text
  gone         today's parser builds nothing with that label

Only the `still split` rows need a decision. The rest are a replay, which is
append-only and costs nothing but time.

    ./nz replay-would-fix
    ./nz replay-would-fix --released-only --limit 40

Reads only, and replays nothing.
"""
from __future__ import annotations

import argparse
import collections

from nizam.corpus import segment as seg
from nizam.storage import legal_write
from nizam.storage.db import connect

CITABLE = ("section", "article")

# The same pairing find_stub_citations uses, narrowed to the cases where the
# citable node carries less than half of what the retyped sibling holds.
STUBS = """
WITH decided AS (
  SELECT DISTINCT c.candidate_provision_id AS pid, c.instrument_id,
         c.document_id, c.printed_label
    FROM segmentation_structural_adjudication a
    JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
   WHERE a.resolution = 'accept_non_citable'
), sized AS (
  SELECT d.*, p.path,
         (SELECT coalesce(sum(pb.chars), 0) FROM provision x
            JOIN provision_block pb ON pb.provision_id = x.id
           WHERE x.instrument_id = d.instrument_id AND x.is_active
             AND x.path <@ p.path) AS retyped_chars,
         (d.instrument_id IN (SELECT id FROM v_release_instrument)) AS released
    FROM decided d JOIN provision p ON p.id = d.pid AND p.is_active
)
SELECT s.document_id, s.printed_label, s.retyped_chars, s.released
  FROM sized s
  JOIN LATERAL (
      SELECT (SELECT coalesce(sum(pb.chars), 0) FROM provision y
                JOIN provision_block pb ON pb.provision_id = y.id
               WHERE y.instrument_id = s.instrument_id AND y.is_active
                 AND y.path <@ t.path) AS keep_chars
        FROM provision t
       WHERE t.instrument_id = s.instrument_id AND t.is_active
         AND t.kind::text IN ('section', 'article')
         AND regexp_replace(lower(t.label), '[^a-z0-9]', '', 'g')
           = regexp_replace(lower(s.printed_label), '[^a-z0-9]', '', 'g')
       ORDER BY t.ordinal LIMIT 1) k ON true
 WHERE s.retyped_chars >= 500 AND k.keep_chars < s.retyped_chars * 0.5
 ORDER BY s.document_id
"""


def norm(label: str | None) -> str:
    return "".join(ch for ch in (label or "").lower() if ch.isalnum())


def walk(node, out):
    for child in node.children:
        out.append(child)
        walk(child, out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--released-only", action="store_true")
    ap.add_argument("--limit", type=int, help="stop after this many documents")
    ap.add_argument("--show", type=int, default=20)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(STUBS)
        rows = cur.fetchall()

    wanted = collections.defaultdict(list)
    for doc, label, chars, released in rows:
        if a.released_only and not released:
            continue
        wanted[doc].append((label, chars, released))

    docs = sorted(wanted)
    if a.limit:
        docs = docs[:a.limit]

    tally = collections.Counter()
    still: list[tuple] = []
    for n, doc in enumerate(docs, 1):
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT source_observation_id FROM instrument
                            WHERE document_id=%s AND is_active
                              AND duplicate_of IS NULL LIMIT 1""", (doc,))
            row = cur.fetchone()
        if row is None:
            tally["no active instrument"] += len(wanted[doc])
            continue
        try:
            blocks = legal_write.blocks_for(doc)
            tree = seg.segment(
                blocks,
                curation_patches=legal_write.segmentation_patches_for(row[0]),
                toc_dispositions=legal_write.toc_dispositions_for(row[0]))
        except Exception as exc:                       # noqa: BLE001
            tally["segmenter error"] += len(wanted[doc])
            print(f"doc {doc}: {type(exc).__name__}: {exc}")
            continue

        nodes: list = []
        walk(tree.root, nodes)
        # `repeated_sibling_label` is about SIBLINGS. Counting every node in the
        # tree that carries the label instead reports clause (2) under thirty
        # different sections as a thirty-way split, which is how doc 855 first
        # came back as "10 nodes" for label 2. Group by parent identity.
        by_label = collections.defaultdict(list)
        for node in nodes:
            by_label[norm(node.label)].append(node)

        for label, chars, released in wanted[doc]:
            same = by_label.get(norm(label), [])
            sections = [x for x in same if x.kind in CITABLE]
            by_parent = collections.Counter(id(x.parent) for x in same)
            widest = max(by_parent.values()) if by_parent else 0
            if not same:
                tally["gone"] += 1
            elif widest > 1:
                tally["still split"] += 1
                still.append((doc, label, chars, released, widest,
                              len(sections)))
            elif sections and sections[0].text.strip():
                tally["fixed"] += 1
            else:
                tally["now empty"] += 1
        if n % 25 == 0:
            print(f"  {n}/{len(docs)} documents", flush=True)

    total = sum(tally.values())
    print(f"\nstub citations checked : {total} over {len(docs)} documents")
    for name, count in tally.most_common():
        share = 100.0 * count / total if total else 0.0
        print(f"  {name:<20} {count:>5}  {share:5.1f}%")

    if still:
        print(f"\nneed a decision, not a replay ({len(still)}):")
        print(f"{'doc':>6} {'lbl':<6} {'buried':>8} {'siblings':>9} {'sections':>9}  rel")
        still.sort(key=lambda s: -s[2])
        for doc, label, chars, released, widest, n_sec in still[:a.show]:
            print(f"{doc:>6} {str(label)[:6]:<6} {chars:>8} {widest:>6} "
                  f"{n_sec:>9}  {'y' if released else '.'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
