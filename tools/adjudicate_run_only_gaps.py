"""Close contents gaps that were never contents entries.

``v_toc_gap_pending`` has two arms. One is real: an ``instrument_toc_entry``
whose ``provision_id`` is NULL -- a printed contents row whose section was not
resolved. The other is legacy: a label sitting in the latest segmentation run's
``detail->'missing'`` with no entry row behind it at all.

Six instruments carry 64 of the second kind, and in them the arithmetic does not
hold. Document 3584 prints a one-row contents list, the run matched that row,
and the run ALSO reports 14 labels missing -- "2" through "14" plus "1.2.3.1".
Every one of those is an active section of the instrument. Document 3962 is the
same shape at 37, document 3765 at 10. Where every contents entry is matched,
``missing`` must be empty; these runs overreport it.

No law is absent, so no disposition is owed. What is owed is the record that the
label resolves to a real, citable section -- which is what ``found_elsewhere``
plus ``found_provision_id`` says, and it is the resolution the schema built the
NULL-``toc_entry_id`` path for: migration 0043's guard admits a run-only gap
"only when the latest immutable run names the label and no unresolved entry row
exists for it".

The check is exact and is applied per row, not per document:

  * the citation key of the printed label matches exactly ONE active section or
    article of that instrument -- more than one and the row is left pending,
  * that provision is not already the target of some other contents entry,
  * the label really is in the latest run's missing list (the trigger enforces
    this independently).

Rows failing any of those stay pending. Nothing is deleted; each decision is a
row a later source reading can supersede.

The upstream defect -- the segmenter counting labels as missing that were never
promised -- is NOT repaired here. It needs a parser change and a replay. This
records the current state honestly in the meantime.

    ./nz toc-run-only            dry run
    ./nz toc-run-only --apply    record the decisions
"""
from __future__ import annotations

import argparse
import json

from nizam.storage.db import connect

DECIDED_BY = "claude.toc-run-only-gap/1"

SELECT_SQL = """
WITH run_only AS (
  SELECT g.instrument_id, g.document_id, g.printed_label,
         regexp_replace(lower(g.printed_label), '[^a-z0-9]', '', 'g') AS key
    FROM v_toc_gap_pending g
   WHERE g.toc_entry_id IS NULL
), matched AS (
  SELECT r.instrument_id, r.document_id, r.printed_label, r.key,
         p.id AS provision_id, p.label AS body_label, p.kind::text AS kind,
         p.first_page,
         (SELECT count(*) FROM provision p2
           WHERE p2.instrument_id = r.instrument_id AND p2.is_active
             AND p2.kind IN ('section','article')
             AND regexp_replace(lower(p2.label), '[^a-z0-9]', '', 'g') = r.key
         ) AS same_key_sections,
         EXISTS (SELECT 1 FROM instrument_toc_entry e
                  WHERE e.instrument_id = r.instrument_id
                    AND e.provision_id = p.id) AS already_an_entry_target
    FROM run_only r
    JOIN provision p ON p.instrument_id = r.instrument_id AND p.is_active
                    AND p.kind IN ('section','article')
                    AND regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g') = r.key
)
SELECT m.instrument_id::text, m.document_id, m.printed_label,
       m.provision_id::text, m.body_label, m.kind, m.first_page,
       m.same_key_sections, m.already_an_entry_target,
       (SELECT count(*) FROM instrument_toc_entry e
         WHERE e.instrument_id = m.instrument_id) AS toc_entry_rows,
       (SELECT count(*) FROM instrument_toc_entry e
         WHERE e.instrument_id = m.instrument_id
           AND e.provision_id IS NULL) AS unresolved_entry_rows
  FROM matched m
 ORDER BY m.document_id, m.printed_label
"""

RATIONALE = (
    "This label is not a printed contents row. It reached the gap queue through "
    "the legacy run-only arm of v_toc_gap_pending: the latest segmentation run "
    "lists it in detail->'missing' while the instrument's own contents entries "
    "are all matched, so the run overreported what the source promised. The "
    "label resolves to exactly one active {kind} of this instrument, label "
    "{body_label}, which is citable now -- recorded here as the provision the "
    "gap names. No section is absent from the source and none is fabricated: "
    "what is wrong is the arithmetic in the run record, and repairing that needs "
    "a segmenter change and a replay. Supersede this if a source reading "
    "disagrees."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="record the decisions")
    ap.add_argument("--show", type=int, default=12)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SELECT_SQL)
        keys = ("instrument_id", "document_id", "printed_label", "provision_id",
                "body_label", "kind", "first_page", "same_key_sections",
                "already_an_entry_target", "toc_entry_rows",
                "unresolved_entry_rows")
        rows = [dict(zip(keys, r)) for r in cur.fetchall()]

        eligible, held = [], []
        for row in rows:
            if (row["same_key_sections"] == 1
                    and not row["already_an_entry_target"]
                    and row["first_page"]):
                eligible.append(row)
            else:
                held.append(row)

        cur.execute(
            "SELECT count(*) FROM v_toc_gap_pending WHERE toc_entry_id IS NULL")
        total = cur.fetchone()[0]
        print(f"run-only gaps pending            : {total}")
        print(f"  label resolves to one section  : {len(eligible)}")
        print(f"  ambiguous or already linked    : {len(held)}")
        print(f"  no section carries the label   : {total - len(rows)}")
        for row in eligible[:a.show]:
            print(f"    doc {row['document_id']:<6} "
                  f"label {str(row['printed_label']):<9} "
                  f"-> {row['kind']} {row['body_label']} p{row['first_page']}  "
                  f"(contents rows {row['toc_entry_rows']}, "
                  f"unresolved {row['unresolved_entry_rows']})")
        for row in held[:a.show]:
            why = ("several sections share the label"
                   if row["same_key_sections"] > 1
                   else "the section already answers another contents row"
                   if row["already_an_entry_target"] else "no first page")
            print(f"    HELD doc {row['document_id']:<6} label "
                  f"{str(row['printed_label']):<9} {why}")

        if not a.apply:
            print("\ndry run -- pass --apply to record these decisions")
            return 0

        written = 0
        for row in eligible:
            evidence = {
                "found_provision_id": row["provision_id"],
                "body_label": row["body_label"],
                "body_kind": row["kind"],
                "gap_arm": "legacy run-only (no instrument_toc_entry row)",
                "instrument_contents_rows": row["toc_entry_rows"],
                "instrument_unresolved_contents_rows":
                    row["unresolved_entry_rows"],
                "check": "citation key matches exactly one active section or "
                         "article of this instrument, and that provision "
                         "answers no other contents row",
                "tool": "tools/adjudicate_run_only_gaps.py",
                "upstream_defect": "segmentation_run.detail->'missing' lists "
                                   "labels that were never contents entries; "
                                   "needs a segmenter fix and a replay",
                "reviewer_type": "assistant",
                "human_page_review": False,
            }
            cur.execute("""
                INSERT INTO toc_gap_adjudication
                    (instrument_id, document_id, toc_entry_id, printed_label,
                     resolution, source_page, evidence, rationale, decided_by)
                VALUES (%s, %s, NULL, %s, 'found_elsewhere', %s, %s, %s, %s)
            """, (row["instrument_id"], row["document_id"], row["printed_label"],
                  row["first_page"], json.dumps(evidence),
                  RATIONALE.format(kind=row["kind"],
                                   body_label=row["body_label"]),
                  DECIDED_BY))
            written += 1
        conn.commit()
        print(f"\nrecorded {written} decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
