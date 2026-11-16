"""Derive instrument metadata columns from the standing metadata assertions (migration 0070).

The record is about sources; these columns live on instrument rows that every replay regenerates. This re-derives
them, both ways, as tools/apply_statutory_repeals.py does for status:

  * display_title, text_language, enacted_on, commenced_on -- set to the standing value; an active instrument that
    carries a value no standing assertion supports goes back to NULL (the segmenter never writes these);
  * status (0082) -- 'in_force' where a standing status assertion says so (tools/record_status.py) and the
    instrument is 'unknown' with no repealing link; an 'in_force' no assertion stands behind, or one a repeal now
    links, goes back to 'unknown'. 'repealed' is never touched here (tools/apply_statutory_repeals.py);
  * number -- FILL-ONLY: written where the segmenter left it NULL. A segmenter number that disagrees with a standing
    assertion is reported, not overwritten. A number this tool wrote goes back to NULL when its assertion is
    withdrawn and nothing stands behind it. ONE EXCEPTION: an assertion with basis printed_number_corrects_stored
    (tools/record_instrument_numbers.py --correct-stored, 12 Nov 2026: the segmenter had stored a number cited in the
    body, e.g. 1707 'LXXI' for the Service Tribunals Act, which prints 'ACT NO. LXX OF 1973') overwrites the stored
    number; the replay writes the segmenter's value back and this step corrects it again.

Run after every replay (tools/post_replay_sequence.sh step 2b4); safe to run again.

    python tools/apply_instrument_metadata.py            # report
    python tools/apply_instrument_metadata.py --apply    # write
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# column -> SQL cast applied to the text value
BOTH_WAYS = {
    "display_title": "text",
    "text_language": "text",
    "enacted_on": "date",
    "commenced_on": "date",
}


def set_sql(field: str, cast: str) -> str:
    return f"""
UPDATE instrument i SET {field} = c.value::{cast}
  FROM v_instrument_metadata_current c
 WHERE c.field = '{field}' AND i.id = c.instrument_id
   AND i.{field} IS DISTINCT FROM c.value::{cast}"""


def unset_sql(field: str) -> str:
    return f"""
UPDATE instrument i SET {field} = NULL
 WHERE i.is_active AND i.{field} IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                    WHERE c.field = '{field}' AND c.instrument_id = i.id)"""


NUMBER_FILL = """
UPDATE instrument i SET number = c.value
  FROM v_instrument_metadata_current c
 WHERE c.field = 'number' AND i.id = c.instrument_id AND i.number IS NULL"""

# A number written by this tool whose assertion is now withdrawn: the latest row for the key is a withdrawal and the
# instrument still carries the last asserted value.
NUMBER_UNSET = """
WITH latest AS (
    SELECT DISTINCT ON (source_observation_id, expression_ordinal) *
      FROM instrument_metadata_assertion WHERE field = 'number'
     ORDER BY source_observation_id, expression_ordinal, recorded_at DESC, id DESC),
last_value AS (
    SELECT DISTINCT ON (source_observation_id, expression_ordinal) source_observation_id, expression_ordinal, value
      FROM instrument_metadata_assertion WHERE field = 'number' AND assertion = 'asserted'
     ORDER BY source_observation_id, expression_ordinal, recorded_at DESC, id DESC)
UPDATE instrument i SET number = NULL
  FROM latest l JOIN last_value v USING (source_observation_id, expression_ordinal)
 WHERE l.assertion = 'withdrawn' AND i.is_active
   AND i.source_observation_id = l.source_observation_id AND i.expression_ordinal = l.expression_ordinal
   AND i.number = v.value"""

NUMBER_CORRECT = """
UPDATE instrument i SET number = c.value
  FROM v_instrument_metadata_current c
 WHERE c.field = 'number' AND i.id = c.instrument_id AND c.basis = 'printed_number_corrects_stored'
   AND i.number IS DISTINCT FROM c.value"""

# status (0082): 'in_force' from a standing assertion, both ways -- never over a 'repealed' status or a standing
# repeal's repealed_by_id (tools/apply_statutory_repeals.py owns those; it runs first, post-replay step 2b3)
STATUS_SET = """
UPDATE instrument i SET status = 'in_force'
  FROM v_instrument_metadata_current c
 WHERE c.field = 'status' AND c.value = 'in_force' AND i.id = c.instrument_id
   AND i.status = 'unknown' AND i.repealed_by_id IS NULL"""
STATUS_UNSET = """
UPDATE instrument i SET status = 'unknown'
 WHERE i.is_active AND i.status = 'in_force'
   AND (i.repealed_by_id IS NOT NULL
        OR NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                        WHERE c.field = 'status' AND c.value = 'in_force' AND c.instrument_id = i.id))"""

NUMBER_CONFLICTS = """
SELECT i.id, i.document_id, i.number, c.value
  FROM v_instrument_metadata_current c JOIN instrument i ON i.id = c.instrument_id
 WHERE c.field = 'number' AND i.number IS NOT NULL AND i.number <> c.value
 ORDER BY i.document_id"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('instrument_metadata_assertion')")
        if cur.fetchone()[0] is None:
            print("migration 0070 is not applied; no instrument metadata to derive")
            return 0
        changed = {}
        for field, cast in BOTH_WAYS.items():
            cur.execute(set_sql(field, cast)); s = cur.rowcount
            cur.execute(unset_sql(field)); u = cur.rowcount
            changed[field] = (s, u)
        cur.execute(NUMBER_FILL); nf = cur.rowcount
        cur.execute(NUMBER_UNSET); nu = cur.rowcount
        cur.execute(NUMBER_CORRECT); nc = cur.rowcount
        changed["number"] = (nf + nc, nu)
        cur.execute(STATUS_UNSET); su = cur.rowcount
        cur.execute(STATUS_SET); ss = cur.rowcount
        changed["status"] = (ss, su)
        cur.execute(NUMBER_CONFLICTS)
        conflicts = cur.fetchall()
        cur.execute("SELECT field, count(*) FROM v_instrument_metadata_current GROUP BY 1 ORDER BY 1")
        standing = dict(cur.fetchall())
        for field, (s, u) in changed.items():
            print(f"{field:14} standing {standing.get(field, 0):6}  set {s:6}  cleared {u:6}")
        print(f"number conflicts (segmenter value kept): {len(conflicts)}")
        for row in conflicts[:20]:
            print(f"  doc {row[1]}: instrument has {row[2]!r}, assertion says {row[3]!r}")
        if args.apply:
            conn.commit()
            print("applied")
        else:
            conn.rollback()
            print("dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
