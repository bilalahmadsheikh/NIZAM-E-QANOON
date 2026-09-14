"""What replaying a given list of documents would cost the gate.

`find_stale_trees` answers this for the blocked queue, and its payoff test is
"fewer unlinked contents rows". Both choices are right for the queue it serves
and wrong for the stub citations: a document holding a stub is usually
*released*, so it is never compared, and a stub moves no contents row, so the
payoff test could not see it even if it were.

`would_replay_fix_stubs` names 51 documents whose stubs today's parser already
gets right. Before replaying any of them the other half of the question has to
be answered -- what does the replay cost? -- against the measures the release
gate does count. That is this.

It reads a whole-corpus fingerprint rather than re-segmenting, so it is cheap
and uses exactly the numbers the ON/OFF discipline already produced.

    ./nz replay-cost .stub_replay_fix.txt .fp_in2_on.tsv
    ./nz replay-cost .stub_replay_fix.txt .fp_in2_on.tsv --out .safe_replay.txt

A document split into several expressions is HELD, never compared: the
fingerprint covers the whole PDF at once, so one expression's stored tree
always looks smaller. That omission has been made four times in this repo.

Reads only, and replays nothing.
"""
from __future__ import annotations

import argparse
import csv
import pathlib

from nizam.storage.db import connect

STORED = """
SELECT i.document_id,
       (SELECT count(*) FROM provision p WHERE p.instrument_id = i.id
          AND p.is_active AND p.kind::text IN ('section','article')),
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id = i.id),
       (SELECT count(*) FROM v_structural_adjudication_pending s
         WHERE s.instrument_id = i.id),
       (i.id IN (SELECT id FROM v_release_instrument)),
       left(coalesce(i.short_title, ''), 38),
       (SELECT count(*) FROM instrument o
         WHERE o.document_id = i.document_id
           AND o.is_active AND o.duplicate_of IS NULL)
  FROM instrument i
 WHERE i.is_active AND i.duplicate_of IS NULL
   AND i.document_id = ANY(%s)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("documents", help="file of document ids, one per line")
    ap.add_argument("fingerprint", help="whole-corpus fingerprint TSV")
    ap.add_argument("--out", help="write the safe replay list here")
    ap.add_argument("--show", type=int, default=25)
    a = ap.parse_args()

    ids = [int(x) for x in
           pathlib.Path(a.documents).read_text(encoding="utf-8").split()
           if x.isdigit()]

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
                          "unlinked")}

    with connect() as conn, conn.cursor() as cur:
        cur.execute(STORED, (ids,))
        stored = {r[0]: {"sections": r[1], "gaps": r[2], "s7": r[3],
                         "released": r[4], "title": r[5], "expressions": r[6]}
                  for r in cur.fetchall()}

    safe, costly, held, missing = [], [], [], []
    for doc in ids:
        was = stored.get(doc)
        has = now.get(doc)
        if was is None or has is None:
            missing.append(doc)
            continue
        if was["expressions"] != 1:
            held.append((doc, was))
            continue
        # fail closed on either arm, exactly as the gate counts it
        gaps_now = max(has["unlinked"], max(has["missing_toc"], 0))
        lost = was["sections"] - has["sections"]
        gained = gaps_now - was["gaps"]
        row = (doc, lost, gained, was, has)
        (costly if (lost > 0 or gained > 0) else safe).append(row)

    print(f"documents asked about      : {len(ids)}")
    print(f"  safe to replay           : {len(safe)}  "
          f"({sum(1 for r in safe if r[3]['released'])} released)")
    print(f"  replaying costs the gate : {len(costly)}  "
          f"({sum(1 for r in costly if r[3]['released'])} released)")
    print(f"  HELD, several expressions: {len(held)}")
    print(f"  not in the fingerprint   : {len(missing)}")

    if costly:
        costly.sort(key=lambda r: (-r[1], -r[2]))
        print(f"\ncosts -- do not batch these\n"
              f"{'doc':>6} {'sections':>16} {'gaps':>13}  rel  title")
        for doc, lost, gained, was, has in costly[:a.show]:
            print(f"{doc:>6} {was['sections']:>7} -> {has['sections']:<6} "
                  f"{was['gaps']:>5} -> "
                  f"{max(has['unlinked'], max(has['missing_toc'], 0)):<5}  "
                  f"{'y' if was['released'] else '.':^3}  {was['title']}")

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            for doc, *_ in sorted(safe):
                fh.write(f"{doc}\n")
        print(f"\nwrote {a.out}: {len(safe)} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
