"""Close contents gaps whose section is in the tree under a different number.

Three source pages showed this shape plainly. Document 1014's contents promises
"8. Power to make rules."; the body prints that exact marginal heading on
section 7. Document 1021 promises "4. Repeal."; the body's repeal section is 3.
The section is present, citable, and correct -- the contents page is numbered
differently from the body it describes, which is a fact about the print, not a
missing law.

``toc_gap_adjudication`` already has the right word for this: ``found_elsewhere``,
which requires the provision it was found as. That is a check the database can
make, so it does not need and does not claim a page reading.

WHAT THIS DELIBERATELY WILL NOT DO. The dominant bucket -- a promised label with
neither its number nor its heading anywhere in the tree -- is ``absent_in_source``,
and migration 0042 requires ``human_page_review`` and a render for it, with the
reason written out: "A claim that the official source omits a promised section
is a human page-reading result, not a parser inference. Store both facts so a
future bulk tool cannot silently manufacture these decisions." This tool is such
a bulk tool. It records none of those.

    ./nz toc-found-elsewhere            dry run
    ./nz toc-found-elsewhere --apply    record the decisions
"""
from __future__ import annotations

import argparse
import json

from nizam.storage.db import connect

DECIDED_BY = "claude.toc-heading-review/1"
METHOD = "printed heading identifies exactly one provision in the same instrument"

SQL = """
WITH gap AS (
  SELECT g.toc_entry_id, g.document_id, g.instrument_id, g.printed_label,
         g.printed_heading, g.source_page,
         regexp_replace(lower(g.printed_label), '[^a-z0-9]', '', 'g') AS label_key,
         regexp_replace(lower(coalesce(g.printed_heading,'')),
                        '[^a-z0-9]', '', 'g') AS heading_key
    FROM v_toc_gap_pending g
),
prov AS (
  SELECT p.id, p.instrument_id, p.label, p.kind::text AS kind, p.heading,
         p.first_page,
         regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g') AS label_key,
         regexp_replace(lower(coalesce(nullif(btrim(p.heading), ''),
                                       p.marginal_note, '')),
                        '[^a-z0-9]', '', 'g') AS heading_key
    FROM provision p
    JOIN instrument i ON i.id = p.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
   WHERE p.is_active
)
SELECT gap.toc_entry_id, gap.document_id, gap.instrument_id::text,
       gap.printed_label, gap.printed_heading, gap.source_page,
       m.id::text, m.label, m.kind, m.first_page
  FROM gap
  JOIN LATERAL (
     SELECT * FROM prov
      WHERE prov.instrument_id = gap.instrument_id
        AND gap.heading_key <> ''
        AND length(gap.heading_key) >= 8
        AND prov.heading_key = gap.heading_key
  ) m ON true
 -- Exactly one provision may carry the heading, and the promised number must
 -- not itself be a section: if it is, this is a linking defect, not a
 -- differently numbered section.
 WHERE (SELECT count(*) FROM prov
         WHERE prov.instrument_id = gap.instrument_id
           AND prov.heading_key = gap.heading_key) = 1
   AND (SELECT count(*) FROM prov
         WHERE prov.instrument_id = gap.instrument_id
           AND prov.label_key = gap.label_key
           AND prov.kind IN ('section','article')) = 0
   -- The match must be a section, not a part or schedule that happens to share
   -- a heading, and it must be NEAR the promised number. A contents page
   -- numbered differently from its body is off by a few: documents 1014 and
   -- 1021 are off by one, document 3291 by five. "Definitions." matching
   -- section 59B is not an offset, it is a generic heading colliding.
   AND m.kind IN ('section','article')
   AND substring(gap.printed_label from '^[0-9]+') IS NOT NULL
   AND substring(m.label from '^[0-9]+') IS NOT NULL
   AND abs((substring(gap.printed_label from '^[0-9]+'))::int
           - (substring(m.label from '^[0-9]+'))::int) <= 10
   AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication prior
                    WHERE prior.toc_entry_id = gap.toc_entry_id
                      AND prior.resolution = 'found_elsewhere')
 ORDER BY gap.document_id, gap.printed_label
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        keys = ("toc_entry_id", "document_id", "instrument_id", "printed_label",
                "printed_heading", "source_page", "provision_id",
                "body_label", "kind", "first_page")
        rows = [dict(zip(keys, r)) for r in cur.fetchall()]

        print(f"contents gaps whose heading names one provision: {len(rows)}\n")
        for row in rows:
            print(f"  doc {row['document_id']:<6} contents "
                  f"{row['printed_label']:<6} -> body {row['body_label']:<6} "
                  f"({row['kind']}, p{row['first_page']})")
            print(f"      {(row['printed_heading'] or '')[:64]}")

        if not a.apply:
            print("\ndry run -- pass --apply to record these decisions")
            return 0

        for row in rows:
            cur.execute("""
                INSERT INTO toc_gap_adjudication
                    (instrument_id, document_id, toc_entry_id, printed_label,
                     resolution, source_page, evidence, rationale, decided_by)
                VALUES (%s, %s, %s, %s, 'found_elsewhere', %s, %s, %s, %s)
            """, (row["instrument_id"], row["document_id"], row["toc_entry_id"],
                  row["printed_label"], row["source_page"],
                  json.dumps({
                      "found_provision_id": row["provision_id"],
                      "body_label": row["body_label"],
                      "body_kind": row["kind"],
                      "body_first_page": row["first_page"],
                      "printed_heading": row["printed_heading"],
                      "method": METHOD,
                      "reviewer_type": "assistant",
                      "human_page_review": False,
                  }, ensure_ascii=False),
                  "The contents row's printed heading names exactly one "
                  "provision of this instrument, and the promised number is not "
                  "a section of it. The section is present and citable under the "
                  "body's own number; the contents page is numbered differently "
                  "from the body it describes. No page reading is claimed: the "
                  "heading match is checkable in the corpus.",
                  DECIDED_BY))
            conn.commit()
        print(f"\nrecorded {len(rows)} decision(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
