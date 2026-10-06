"""Point a truncated source's instrument at the complete copy of the same Act.

``source_incompleteness`` (migration 0054) records the durable fact: this
landed file is a partial copy, and this other document holds the whole statute.
That fact is about SOURCES, and it survives anything the parser does.

``instrument.duplicate_of`` is the flag that acts on it -- the release views
publish only instruments with ``duplicate_of IS NULL`` -- and that flag lives
on an instrument row, which re-segmentation retires and replaces. So the flag
is derived, not authored: after every replay it has to be re-applied from the
source-level record. That is what this does, and it is safe to run as often as
you like.

NOTHING IS DELETED. The truncated document, its pages, its text blocks and its
provision tree all stay exactly where they are -- everything in the PDF stays
in the database. The only change is which of two instruments the corpus
publishes as the Act, and the effect is to make MORE law citable, not less:
sections 6 to 19 of the Raisani Hospital Act and 3 to 29 of the Balochistan
Witness Protection Act resolve to the complete copy instead of to a gap.

It refuses rather than guesses. If the complete document has no active
instrument, or the truncated one already points somewhere else, the row is
reported and skipped.

    python tools/apply_source_incompleteness.py            # show what it would do
    python tools/apply_source_incompleteness.py --apply    # do it
"""
from __future__ import annotations

import argparse

from nizam.storage.db import connect


def decide(truncated: str | None, complete: str | None,
           already: str | None) -> tuple[str, str]:
    """What to do with one supersession, and why.

    Returns (action, reason) where action is 'set', 'skip' or 'done'.
    """
    if complete is None:
        return "skip", ("the complete document has no active instrument; "
                        "refusing to retire a tree in favour of nothing")
    if truncated is None:
        return "skip", ("the truncated document has no active instrument; "
                        "nothing to flag")
    if already == complete:
        return "done", "already pointed at the complete copy"
    if already is not None:
        return "skip", (f"already marked a duplicate of {already}, which is "
                        f"not the complete copy {complete}; leaving it alone")
    return "set", f"retiring {truncated} in favour of {complete}"


SUPERSESSIONS = """
SELECT s.id, s.document_id, s.complete_document_id,
       (SELECT i.id::text FROM instrument i
         WHERE i.document_id = s.document_id AND i.is_active
         ORDER BY i.created_at DESC, i.id LIMIT 1)                 AS truncated_instrument,
       (SELECT i.duplicate_of::text FROM instrument i
         WHERE i.document_id = s.document_id AND i.is_active
         ORDER BY i.created_at DESC, i.id LIMIT 1)                 AS already,
       (SELECT i.id::text FROM instrument i
         WHERE i.document_id = s.complete_document_id AND i.is_active
           AND i.duplicate_of IS NULL
         ORDER BY i.created_at DESC, i.id LIMIT 1)                 AS complete_instrument,
       (SELECT count(*) FROM provision p JOIN instrument i ON i.id = p.instrument_id
         WHERE i.document_id = s.document_id AND i.is_active AND p.is_active),
       (SELECT count(*) FROM provision p JOIN instrument i ON i.id = p.instrument_id
         WHERE i.document_id = s.complete_document_id AND i.is_active
           AND i.duplicate_of IS NULL AND p.is_active)
  FROM v_source_incompleteness_latest s
 WHERE s.resolution = 'superseded_by_complete_copy'
 ORDER BY s.document_id
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the duplicate_of flags (default: report only)")
    args = ap.parse_args()

    set_count = skip_count = done_count = 0
    with connect() as conn, conn.cursor() as cur:
        cur.execute(SUPERSESSIONS)
        rows = cur.fetchall()
        for (row_id, truncated_doc, complete_doc, truncated, already,
             complete, truncated_provisions, complete_provisions) in rows:
            action, reason = decide(truncated, complete, already)
            print(f"doc {truncated_doc} ({truncated_provisions} provisions) "
                  f"-> doc {complete_doc} ({complete_provisions} provisions): "
                  f"{action} -- {reason}")
            if action == "set":
                set_count += 1
                if args.apply:
                    cur.execute(
                        "UPDATE instrument SET duplicate_of = %s "
                        " WHERE id = %s AND is_active AND duplicate_of IS NULL",
                        (complete, truncated))
                    if cur.rowcount != 1:
                        raise SystemExit(
                            f"incompleteness {row_id}: expected to flag one "
                            f"instrument, flagged {cur.rowcount}")
            elif action == "done":
                done_count += 1
            else:
                skip_count += 1
        if args.apply:
            conn.commit()

    print(f"\n{len(rows)} supersessions: {set_count} "
          f"{'applied' if args.apply else 'to apply'}, {done_count} already "
          f"applied, {skip_count} skipped")
    if set_count and not args.apply:
        print("run again with --apply to write them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
