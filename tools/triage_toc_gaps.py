"""Split the contents-gap queue by what the corpus can already prove.

Reading pages is the only way to settle a genuine absence, but most of the queue
is not a genuine absence, and the database can say so without anyone looking.
Three source pages made the categories obvious:

  * document 775 prints "27. Repeal." exactly as its contents promises. The
    section is in the tree under label 27; only the LINK from the contents row
    is missing. No law is absent.
  * documents 1014 and 1021 print the promised heading on a DIFFERENT number --
    the contents lists "8. Power to make rules." and the body numbers it 7.
    The section is in the tree and citable; the contents page is numbered one
    ahead of the body. No law is absent.
  * what remains has neither the label nor the heading anywhere in the tree,
    and only reading the page can say whether it was omitted or missed.

So: match each gap against the instrument's own provisions, first by citation
label, then by printed heading. What survives both is the set that actually
needs a render.

Reads only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nizam.storage.db import connect

SQL = """
WITH gap AS (
  SELECT g.toc_entry_id, g.document_id, g.instrument_id, g.printed_label,
         g.printed_heading,
         regexp_replace(lower(g.printed_label), '[^a-z0-9]', '', 'g') AS label_key,
         regexp_replace(lower(coalesce(g.printed_heading, '')),
                        '[^a-z0-9]', '', 'g') AS heading_key
    FROM v_toc_gap_pending g
),
prov AS (
  SELECT p.instrument_id, p.id, p.label, p.kind::text AS kind, p.heading,
         regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g') AS label_key,
         regexp_replace(lower(coalesce(p.heading, '')),
                        '[^a-z0-9]', '', 'g') AS heading_key
    FROM provision p
    JOIN instrument i ON i.id = p.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
   WHERE p.is_active
)
SELECT gap.toc_entry_id, gap.document_id, gap.printed_label, gap.printed_heading,
       (SELECT count(*) FROM prov
         WHERE prov.instrument_id = gap.instrument_id
           AND prov.label_key = gap.label_key
           AND prov.kind IN ('section','article')) AS same_label_sections,
       (SELECT count(*) FROM prov
         WHERE prov.instrument_id = gap.instrument_id
           AND prov.label_key = gap.label_key) AS same_label_any,
       (SELECT count(*) FROM prov
         WHERE prov.instrument_id = gap.instrument_id
           AND gap.heading_key <> ''
           AND prov.heading_key = gap.heading_key) AS same_heading,
       (SELECT string_agg(DISTINCT prov.label, ',') FROM prov
         WHERE prov.instrument_id = gap.instrument_id
           AND gap.heading_key <> ''
           AND prov.heading_key = gap.heading_key) AS heading_labels
  FROM gap
"""


def bucket(row: dict) -> str:
    if row["same_label_sections"]:
        return "a. label already a section -- contents row simply not linked"
    if row["same_heading"] == 1:
        return "b. heading on one other provision -- contents numbered differently"
    if row["same_heading"] > 1:
        return "c. heading on several provisions -- ambiguous, needs a page"
    if row["same_label_any"]:
        return "d. label exists but not as a section -- demoted, needs a page"
    return "e. neither label nor heading in the tree -- needs a page"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out", help="write the classified rows here")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        keys = ("toc_entry_id", "document_id", "printed_label", "printed_heading",
                "same_label_sections", "same_label_any", "same_heading",
                "heading_labels")
        rows = [dict(zip(keys, r)) for r in cur.fetchall()]

    counts: dict[str, int] = {}
    docs: dict[str, set] = {}
    for row in rows:
        row["bucket"] = bucket(row)
        counts[row["bucket"]] = counts.get(row["bucket"], 0) + 1
        docs.setdefault(row["bucket"], set()).add(row["document_id"])

    print(f"pending contents gaps: {len(rows)}\n")
    for name in sorted(counts):
        print(f"  {name}")
        print(f"      {counts[name]:>5} gaps in {len(docs[name]):>4} documents")

    needs_page = sum(v for k, v in counts.items() if k[0] in "cde")
    print(f"\n  resolvable from the corpus itself : {len(rows) - needs_page}")
    print(f"  genuinely needs a source page     : {needs_page}")

    if a.json_out:
        Path(a.json_out).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
        print(f"\n  wrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
