"""Point a same-text copy's instrument at the canonical document's (migration 0062).

``source_same_text_copy`` records the durable fact: this landed file prints the
same legal text as a canonical document, differing only in page furniture.
``instrument.duplicate_of`` is the flag that acts on it -- the release views
publish only instruments with ``duplicate_of IS NULL`` -- and it lives on an
instrument row that re-segmentation retires and replaces. So, exactly as
tools/apply_source_incompleteness.py does for migration 0054, the flag is
derived and re-applied after every replay (post_replay_sequence.sh step 2b).
Safe to run as often as you like.

Each active expression of the copy is linked to the canonical document's
active, non-duplicate instrument of the same expression ordinal. It refuses
rather than guesses: a copy already pointing elsewhere, or a copy that is
RELEASED (this route never withdraws a released tree -- that needs a lead
decision), is reported and skipped, and the first-link UPDATE re-checks the
release view itself, so a copy released between the read and the write is
never flagged. A canonical with no active instrument is skipped. A record
whose copy has SOME ordinals the canonical lacks is a partial link -- half the
copy would stay publishable -- so the run writes nothing at all and exits
non-zero. Nothing is deleted.

    python tools/apply_source_same_text_copy.py            # show what it would do
    python tools/apply_source_same_text_copy.py --apply    # do it
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LINKS = """
SELECT s.id, s.document_id, s.canonical_document_id, t.expression_ordinal,
       t.id::text, t.duplicate_of::text,
       (SELECT a.document_id FROM instrument a WHERE a.id = t.duplicate_of),
       (SELECT c.id::text FROM instrument c
         WHERE c.document_id = s.canonical_document_id AND c.is_active
           AND c.duplicate_of IS NULL
           AND c.expression_ordinal = t.expression_ordinal
         ORDER BY c.created_at DESC, c.id LIMIT 1),
       EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id = t.id)
  FROM source_same_text_copy s
  JOIN instrument t ON t.source_observation_id = s.source_observation_id
                   AND t.document_id = s.document_id AND t.is_active
 ORDER BY s.document_id, t.expression_ordinal
"""


def decide(copy: str, canonical: str | None, already: str | None,
           released: bool, already_is_canonical_document: bool = False
           ) -> tuple[str, str]:
    """Returns (action, reason): 'set', 'done', 'skip', or 'missing' when the
    canonical has no active instrument at this expression ordinal.

    A pointer at a RETIRED revision of the canonical document is advanced to
    its active instrument (the canonical was replayed after the link)."""
    if already is not None and already == canonical:
        return "done", "already pointed at the canonical copy"
    if canonical is None:
        return "missing", ("the canonical document has no active canonical "
                           "instrument at this expression; refusing to retire a "
                           "tree in favour of nothing")
    if already is not None and already_is_canonical_document:
        return "set", (f"advancing {copy} from the canonical's earlier revision "
                       f"{already} to {canonical}")
    if already is not None:
        return "skip", (f"already marked a duplicate of {already}, which is not "
                        f"the canonical {canonical}; leaving it alone")
    if released:
        return "skip", (f"{copy} is RELEASED; this route never withdraws a "
                        "released tree -- needs a lead decision")
    return "set", f"linking {copy} to {canonical}"


def plan(rows: list[tuple]) -> tuple[list[dict], list[int]]:
    """Decide every copy expression; return (decisions, partial record ids).

    A record is PARTIAL when some of its ordinals link (set or done) and
    others have no canonical counterpart: linking only those would leave the
    rest of the copy publishable."""
    decisions, by_record = [], {}
    for (record, copy_doc, canonical_doc, ordinal, copy, already,
         already_document, canonical, released) in rows:
        action, reason = decide(copy, canonical, already, released,
                                already_document == canonical_doc)
        decisions.append({"record": record, "copy_document": copy_doc,
                          "canonical_document": canonical_doc, "ordinal": ordinal,
                          "copy": copy, "canonical": canonical, "already": already,
                          "action": action, "reason": reason})
        by_record.setdefault(record, set()).add(action)
    partial = sorted(record for record, actions in by_record.items()
                     if "missing" in actions and actions & {"set", "done"})
    return decisions, partial


FIRST_LINK = """
UPDATE instrument SET duplicate_of = %s
 WHERE id = %s AND is_active AND duplicate_of IS NULL
   AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id = instrument.id)
"""
ADVANCE = """
UPDATE instrument SET duplicate_of = %s
 WHERE id = %s AND is_active AND duplicate_of = %s::uuid
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the duplicate_of flags (default: report only)")
    args = ap.parse_args()

    from nizam.storage.db import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('source_same_text_copy')")
        if cur.fetchone()[0] is None:
            print("migration 0062 is not applied; no same-text copies to link")
            return 0
        cur.execute(LINKS)
        decisions, partial = plan(cur.fetchall())
        counts = {"set": 0, "done": 0, "skip": 0, "missing": 0}
        for d in decisions:
            counts[d["action"]] += 1
            print(f"doc {d['copy_document']} E{d['ordinal']} -> doc "
                  f"{d['canonical_document']}: {d['action']} -- {d['reason']}")
        if partial:
            print(f"\nREFUSED: records {partial} would link only part of the copy "
                  "(the canonical lacks some of its expression ordinals); nothing "
                  "written")
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
                    print(f"\nREFUSED: same-text copy {d['record']}: expected to flag "
                          f"instrument {d['copy']}, flagged {cur.rowcount} (released "
                          "or changed since it was read); nothing written")
                    return 1
    print(f"\n{len(decisions)} copy expressions: {counts['set']} "
          f"{'applied' if args.apply else 'to apply'}, {counts['done']} already "
          f"applied, {counts['skip']} skipped, {counts['missing']} without a "
          "canonical counterpart")
    if counts["set"] and not args.apply:
        print("run again with --apply to write them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
