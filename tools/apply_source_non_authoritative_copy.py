"""Point a non-authoritative file's instrument at the authoritative document's (migration 0065).

``source_non_authoritative_copy`` records the durable fact: this landed file is
not authoritative text -- an unofficial translation, or a Bill whose enacted
text is held -- and names the authoritative document. ``instrument.duplicate_of``
is the flag that acts on it, and it lives on an instrument row that
re-segmentation replaces, so -- exactly as tools/apply_source_same_text_copy.py
does for 0062 -- the flag is derived and re-applied after every replay
(post_replay_sequence.sh step 2b2). The decisions are 0062's, imported, not
copied: each active expression links to the authoritative document's active,
non-duplicate instrument of the same expression ordinal; a released file, or
one already pointing elsewhere, is skipped; a record that would link only some
ordinals writes nothing. Nothing is deleted.

    python tools/apply_source_non_authoritative_copy.py            # show what it would do
    python tools/apply_source_non_authoritative_copy.py --apply    # do it
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.apply_source_same_text_copy import ADVANCE, FIRST_LINK, plan  # noqa: E402

LINKS = """
SELECT s.id, s.document_id, s.authoritative_document_id, t.expression_ordinal,
       t.id::text, t.duplicate_of::text,
       (SELECT a.document_id FROM instrument a WHERE a.id = t.duplicate_of),
       (SELECT c.id::text FROM instrument c
         WHERE c.document_id = s.authoritative_document_id AND c.is_active
           AND c.duplicate_of IS NULL
           AND c.expression_ordinal = t.expression_ordinal
         ORDER BY c.created_at DESC, c.id LIMIT 1),
       EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id = t.id)
  FROM source_non_authoritative_copy s
  JOIN instrument t ON t.source_observation_id = s.source_observation_id
                   AND t.document_id = s.document_id AND t.is_active
 ORDER BY s.document_id, t.expression_ordinal
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the duplicate_of flags (default: report only)")
    args = ap.parse_args()

    from nizam.storage.db import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('source_non_authoritative_copy')")
        if cur.fetchone()[0] is None:
            print("migration 0065 is not applied; no non-authoritative files to link")
            return 0
        cur.execute(LINKS)
        decisions, partial = plan(cur.fetchall())
        counts = {"set": 0, "done": 0, "skip": 0, "missing": 0}
        for d in decisions:
            counts[d["action"]] += 1
            print(f"doc {d['copy_document']} E{d['ordinal']} -> doc "
                  f"{d['canonical_document']}: {d['action']} -- {d['reason']}")
        if partial:
            print(f"\nREFUSED: records {partial} would link only part of the file "
                  "(the authoritative document lacks some of its expression "
                  "ordinals); nothing written")
            return 1
        if args.apply:
            for d in decisions:
                if d["action"] != "set":
                    continue
                if d["already"] is None:
                    cur.execute(FIRST_LINK, (d["canonical"], d["copy"]))
                else:
                    cur.execute(ADVANCE, (d["canonical"], d["copy"], d["already"]))
                if cur.rowcount != 1:
                    conn.rollback()
                    print(f"\nREFUSED: non-authoritative record {d['record']}: expected "
                          f"to flag instrument {d['copy']}, flagged {cur.rowcount} "
                          "(released or changed since it was read); nothing written")
                    return 1
    print(f"\n{len(decisions)} non-authoritative expressions: {counts['set']} "
          f"{'applied' if args.apply else 'to apply'}, {counts['done']} already "
          f"applied, {counts['skip']} skipped, {counts['missing']} without an "
          "authoritative counterpart")
    if counts["set"] and not args.apply:
        print("run again with --apply to write them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
