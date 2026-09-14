"""Which S7 collisions today's parser no longer produces at all.

S7 is a parser-repair queue: `v_structural_adjudication_pending` keeps a
candidate pending unless its resolution is `accept_non_citable`, so recording
`restore_citable`, `reparent` or `split_instrument` clears nothing. Of the
1,035 pending units `./nz s7` classes 451 as needing a parser fix rather than a
decision, and 447 more as unclear.

Most of those fixes have already landed. The trees have not been rebuilt, so
the collisions persist in the database while the segmenter that would produce
them is gone. Twenty documents were replayed on that basis earlier and 101 of
their 115 collisions simply ceased to exist.

This asks the question for the whole queue: segment each affected document with
today's parser and count the sibling groups that still share a citation label.

  clears      today's parser produces no colliding siblings -- replay is enough
  reduces     fewer than the tree holds, but not zero
  unchanged   the same count; the fix for this one has not been written
  worse       more than the tree holds -- read before replaying

`replay_cost` must still run over anything this proposes: a document can shed
its collisions and lose sections doing it.

    ./nz replay-clears-s7
    ./nz replay-clears-s7 --out .s7_clears.txt --limit 60

Reads only, and replays nothing.
"""
from __future__ import annotations

import argparse
import collections

from nizam.corpus import segment as seg
from nizam.storage import legal_write
from nizam.storage.db import connect

CITABLE = ("section", "article")

PENDING = """
SELECT s.document_id, count(*) AS pending,
       (SELECT count(*) FROM instrument i
         WHERE i.document_id = s.document_id
           AND i.is_active AND i.duplicate_of IS NULL) AS expressions,
       bool_or(s.instrument_id IN (SELECT id FROM v_release_instrument)) AS released,
       left(coalesce(max(i2.short_title), ''), 38) AS title
  FROM v_structural_adjudication_pending s
  JOIN instrument i2 ON i2.id = s.instrument_id
 GROUP BY s.document_id
 ORDER BY count(*) DESC
"""


def key(label: str | None) -> str:
    return "".join(ch for ch in (label or "").lower() if ch.isalnum())


def walk(node, out):
    for child in node.children:
        out.append((id(node), child))
        walk(child, out)


def collisions(root) -> int:
    """Sibling groups under one parent sharing a citation label."""
    pairs: list = []
    walk(root, pairs)
    groups: dict[tuple, collections.Counter] = {}
    for parent_id, child in pairs:
        if child.kind not in CITABLE:
            continue
        groups.setdefault(parent_id, collections.Counter())[key(child.label)] += 1
    return sum(1 for counter in groups.values()
               for label, n in counter.items() if label and n > 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write documents whose collisions clear")
    ap.add_argument("--limit", type=int, help="stop after this many documents")
    ap.add_argument("--show", type=int, default=20)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(PENDING)
        rows = cur.fetchall()
    if a.limit:
        rows = rows[:a.limit]

    tally = collections.Counter()
    clears: list[int] = []
    detail: list[tuple] = []
    for n, (doc, pending, expressions, released, title) in enumerate(rows, 1):
        # A document split into several expressions cannot be judged from a
        # whole-document parse: the run covers all of them at once. Held, not
        # guessed. The same omission has been made four times in this repo.
        if expressions != 1:
            tally["held: several expressions"] += 1
            continue
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT source_observation_id FROM instrument
                            WHERE document_id=%s AND is_active
                              AND duplicate_of IS NULL LIMIT 1""", (doc,))
            row = cur.fetchone()
        if row is None:
            tally["no active instrument"] += 1
            continue
        try:
            blocks = legal_write.blocks_for(doc)
            tree = seg.segment(
                blocks,
                curation_patches=legal_write.segmentation_patches_for(row[0]),
                toc_dispositions=legal_write.toc_dispositions_for(row[0]))
        except Exception as exc:                       # noqa: BLE001
            tally["segmenter error"] += 1
            print(f"doc {doc}: {type(exc).__name__}: {exc}")
            continue

        now = collisions(tree.root)
        if now == 0:
            tally["clears"] += 1
            clears.append(doc)
        elif now < pending:
            tally["reduces"] += 1
        elif now == pending:
            tally["unchanged"] += 1
        else:
            tally["worse"] += 1
        detail.append((pending - now, doc, pending, now, released, title))
        if n % 25 == 0:
            print(f"  {n}/{len(rows)} documents", flush=True)

    total = sum(tally.values())
    print(f"\ndocuments with pending S7 : {total}")
    for name, count in tally.most_common():
        print(f"  {name:<26} {count:>5}")

    detail.sort(reverse=True)
    print(f"\n{'doc':>6} {'stored':>7} {'today':>6} {'gain':>5}  rel  title")
    for gain, doc, pending, now, released, title in detail[:a.show]:
        print(f"{doc:>6} {pending:>7} {now:>6} {gain:>+5}  "
              f"{'y' if released else '.':^3}  {title}")

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            for doc in sorted(clears):
                fh.write(f"{doc}\n")
        print(f"\nwrote {a.out}: {len(clears)} documents whose collisions clear")
        print("run ./nz replay-cost over it before replaying anything")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
