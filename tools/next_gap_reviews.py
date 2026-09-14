"""The next rendered contents gaps awaiting a page reading.

`review_toc_gaps.py` renders the pages where a promised section should be and
writes a manifest. This picks the next batch that is still pending and not yet
adjudicated, and prints exactly what a reader needs: what the contents promises,
which pages were rendered, and what the tree holds either side of the gap.

Reading one of these answers one question:

  * the section IS printed there -> the parser missed it. That is a
    parser_defect: it stays pending, because only a corrected parse resolves it.
  * the section is NOT there     -> the promise outlived the section, and the
    decision needs a basis saying who looked (migration 0050).

Reads only; it decides nothing.

    ./nz next-reviews --limit 12
"""
from __future__ import annotations

import argparse
import json
import pathlib

from nizam.storage.db import connect

MANIFEST = pathlib.Path(".artifacts/toc-gap-review/manifest.json")

PENDING = """
SELECT g.toc_entry_id, g.document_id, g.instrument_id::text, g.printed_label,
       coalesce(g.printed_heading, ''), g.source_page
  FROM v_toc_gap_pending g
 WHERE g.toc_entry_id = ANY(%s)
   AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication a
                    WHERE a.toc_entry_id = g.toc_entry_id)
"""

NEIGHBOURS = """
SELECT p.label, p.kind::text, p.first_page,
       left(regexp_replace(coalesce(pv.text_en, ''), '\\s+', ' ', 'g'), 70)
  FROM provision p
  LEFT JOIN provision_version pv ON pv.provision_id = p.id
 WHERE p.instrument_id = %s AND p.is_active
   AND p.kind IN ('section','article')
 ORDER BY p.ordinal
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--document", type=int, help="only this document")
    a = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_entry = {item["toc_entry_id"]: item for item in manifest}

    with connect() as conn, conn.cursor() as cur:
        cur.execute(PENDING, (list(by_entry),))
        rows = cur.fetchall()
        if a.document:
            rows = [r for r in rows if r[1] == a.document]
        rows.sort(key=lambda r: (r[1], r[0]))
        print(f"rendered gaps still pending and unadjudicated: {len(rows)}\n")
        for entry_id, document, instrument, label, heading, page in rows[:a.limit]:
            item = by_entry[entry_id]
            cur.execute(NEIGHBOURS, (instrument,))
            held = cur.fetchall()
            labels = [row[0] for row in held]
            print(f"doc {document}  entry {entry_id}  promises {label!r}: "
                  f"{heading[:58]!r}")
            print(f"  contents page {page} · instrument {instrument[:8]} · "
                  f"{item.get('short_title', '')[:46]}")
            print(f"  tree holds {len(labels)} sections: "
                  f"{', '.join(str(x) for x in labels[:14])}"
                  f"{' ...' if len(labels) > 14 else ''}")
            for render in item.get("renders", []):
                print(f"  render p{render['page']}: {render['file']}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
