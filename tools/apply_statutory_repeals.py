"""Derive instrument.status / repealed_on / repealed_by_id from the standing statutory repeals (migration 0066).

The record is about sources; these fields live on instrument rows that every replay regenerates (status 'unknown').
This re-derives them, both ways:

  * a standing repeal WITH a printed date: status 'repealed', repealed_on, repealed_by_id (ck_repeal, 0004, requires
    the date for 'repealed');
  * a standing repeal without one: repealed_by_id only; status stays 'unknown' (the repeal is certain, its date is
    not established);
  * an instrument carrying a repeal this record no longer stands behind returns to 'unknown', no repealing link.

No other status is touched. Run after every replay (tools/post_replay_sequence.sh step 2b3); safe to run again.

    python tools/apply_statutory_repeals.py            # report
    python tools/apply_statutory_repeals.py --apply    # write
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# One standing repeal per instrument: the earliest-recorded one when several Acts repeal it.
TARGET = """
SELECT DISTINCT ON (repealed_instrument_id) repealed_instrument_id, repealing_instrument_id, repealed_on
  FROM v_statutory_repeal_current ORDER BY repealed_instrument_id, recorded_at, id
"""
SET = f"""
WITH t AS ({TARGET})
UPDATE instrument i
   SET status = CASE WHEN t.repealed_on IS NULL THEN 'unknown'::lifecycle_state ELSE 'repealed' END,
       repealed_on = t.repealed_on, repealed_by_id = t.repealing_instrument_id
  FROM t
 WHERE i.id = t.repealed_instrument_id
   AND (i.status IS DISTINCT FROM CASE WHEN t.repealed_on IS NULL THEN 'unknown'::lifecycle_state ELSE 'repealed' END
        OR i.repealed_on IS DISTINCT FROM t.repealed_on
        OR i.repealed_by_id IS DISTINCT FROM t.repealing_instrument_id)
"""
UNSET = """
UPDATE instrument i SET status = 'unknown', repealed_on = NULL, repealed_by_id = NULL
 WHERE i.is_active AND (i.status = 'repealed' OR i.repealed_by_id IS NOT NULL)
   AND NOT EXISTS (SELECT 1 FROM v_statutory_repeal_current c WHERE c.repealed_instrument_id = i.id)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('statutory_repeal')")
        if cur.fetchone()[0] is None:
            print("migration 0066 is not applied; no statutory repeals to derive")
            return 0
        cur.execute(SET); set_n = cur.rowcount
        cur.execute(UNSET); unset_n = cur.rowcount
        cur.execute(f"SELECT count(*), count(repealed_on) FROM ({TARGET}) t")
        standing, dated = cur.fetchone()
        if not args.apply:
            conn.rollback()
    print(f"{standing} instruments repealed by a held Act ({dated} with a printed date -> status 'repealed'; "
          f"{standing - dated} undated -> repealed_by only): {set_n} {'updated' if args.apply else 'to update'}, "
          f"{unset_n} {'cleared' if args.apply else 'to clear'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
