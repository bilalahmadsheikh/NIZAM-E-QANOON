"""Refresh the serving snapshots operative_provision reads: mv_instrument_serving (migration 0094, per law) and then
mv_provision_text_known_from (migration 0096, per provision; it reads the first).

Run after anything that changes what is released or how a law is classed: a replay (tools/post_replay_sequence.sh
runs it last), tools/record_status.py, tools/apply_instrument_metadata.py, record_statutory_repeals.py /
apply_statutory_repeals.py, record_territorial_extent.py, record_territorial_repeals.py,
record_consolidated_twins.py, record_delegation.py, an amendment-reference run. Audit A16 fails while either is stale.

    python tools/refresh_serving.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    from nizam.storage.db import connect
    t = time.time()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_instrument_serving")
        conn.commit()
        cur.execute("SELECT to_regclass('mv_provision_text_known_from')")
        if cur.fetchone()[0]:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_provision_text_known_from")
            conn.commit()
        cur.execute("SELECT count(*), count(*) FILTER (WHERE currency = 'current') FROM mv_instrument_serving")
        n, current = cur.fetchone()
    print(f"mv_instrument_serving refreshed: {n} laws ({current} current) in {time.time() - t:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
