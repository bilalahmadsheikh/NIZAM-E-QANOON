"""Did an S7 demotion actually remove a citation, or only a duplicate?

The length heuristic in ``s7_audit_sample.py`` asks which block looks more like
a provision. It over-calls badly: rendering showed a long "demoted" block is
usually a schedule list, a table row or a page footnote. This asks a different
question, and one the database can answer exactly.

Under INV-4 the provision is the citable unit, so the harm a demotion can do is
precise: after it, is the printed label still reachable as a section of that
instrument? Where a sibling with the same label remains a section, the demotion
removed a duplicate and cost nothing. Where no section carries the label any
more, the citation is gone -- that is the case a person must read against the
source.

The check is exact, not heuristic, so it can run over every decision rather
than a sample. It writes nothing.

    ./nz s7-citability                    every adjudicated decision
    ./nz s7-citability --sample FILE.json only the drawn sample
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nizam.storage.db import connect

SQL = """
WITH decided AS (
  SELECT c.id, a.id AS adjudication_id, c.instrument_id, c.document_id,
         c.printed_label, c.source_page, c.canonical_source_page,
         cand.label AS demoted_label, canon.label AS kept_label,
         (c.evidence->>'group_size')::int AS group_size
    FROM segmentation_structural_candidate c
    LEFT JOIN segmentation_structural_adjudication a ON a.candidate_id = c.id
    JOIN instrument i ON i.id = c.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
    LEFT JOIN provision cand  ON cand.id  = c.candidate_provision_id
    LEFT JOIN provision canon ON canon.id = c.canonical_provision_id
   WHERE (%(pending)s AND a.id IS NULL)
      OR (NOT %(pending)s AND a.resolution = 'accept_non_citable')
),
-- Compare on the citation key, not the raw string: "22" and "22." cite the
-- same provision, and a label that survives in another typography is not lost.
survivors AS (
  SELECT p.instrument_id,
         regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g') AS key
    FROM provision p
    JOIN instrument i ON i.id = p.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
   WHERE p.is_active AND p.kind IN ('section', 'article')
)
SELECT coalesce(d.adjudication_id::text, d.id::text), d.document_id, d.printed_label, d.demoted_label,
       d.kept_label, d.source_page, d.group_size,
       EXISTS (SELECT 1 FROM survivors s
                WHERE s.instrument_id = d.instrument_id
                  AND s.key = regexp_replace(lower(coalesce(d.demoted_label,
                                                            d.printed_label)),
                                             '[^a-z0-9]', '', 'g')) AS still_citable
  FROM decided d
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", help="restrict to adjudication ids in this JSON")
    ap.add_argument("--pending", action="store_true",
                    help="check candidates that have no adjudication yet")
    ap.add_argument("--ids-out",
                    help="write the candidate ids that keep their citation")
    ap.add_argument("--show", type=int, default=25)
    a = ap.parse_args()

    keep: set[str] | None = None
    if a.sample:
        rows = json.loads(Path(a.sample).read_text(encoding="utf-8"))
        keep = {str(r["adjudication_id"]) for r in rows}

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL, {"pending": a.pending})
        rows = [dict(zip(("adjudication_id", "document_id", "printed_label",
                          "demoted_label", "kept_label", "source_page",
                          "group_size", "still_citable"), r))
                for r in cur.fetchall()]

    if keep is not None:
        rows = [r for r in rows if r["adjudication_id"] in keep]

    lost = [r for r in rows if not r["still_citable"]]
    scope = ("the drawn sample" if keep is not None
             else ("every pending candidate" if a.pending else "every decision"))
    print(f"S7 citability check over {scope}: {len(rows)} demotions")
    print(f"  label still reachable as a section : {len(rows) - len(lost)}"
          f"  ({(len(rows) - len(lost)) / max(len(rows), 1):.1%})")
    print(f"  label NO LONGER a section          : {len(lost)}"
          f"  ({len(lost) / max(len(rows), 1):.1%})  <- read these against source")

    by_doc: dict[int, int] = {}
    for r in lost:
        by_doc[r["document_id"]] = by_doc.get(r["document_id"], 0) + 1
    print(f"\n  concentrated in {len(by_doc)} document(s); worst:")
    for document_id, n in sorted(by_doc.items(), key=lambda kv: -kv[1])[:a.show]:
        pages = sorted({r["source_page"] for r in lost
                        if r["document_id"] == document_id})[:6]
        print(f"    doc {document_id:<6} {n:>4} lost label(s)   pages {pages}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
