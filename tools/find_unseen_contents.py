"""Documents that print a contents list the parser did not see.

The signature is duplication. When a contents list is not recognised, its rows
are parsed as sections AND the body's real sections are parsed again, so the
instrument carries the same citation label twice -- once pointing at a heading
with no law under it, once at the provision. The Sind Civil Servants Ordinance
held 50 sections where the Act has 25.

Three marker variants were found this way and each was worth a fix:

    Sections            the bare column name, in 194 documents
    C O N T E N T       singular, in 9
    (four entries)      a list too short for the five-entry fallback

This finds the rest: instruments with no contents entries at all whose top-level
section labels repeat, and prints what their opening pages actually say. The
last column is the point -- it is the line a marker pattern would have to match.

WHAT IT DOES NOT SEPARATE, and this matters before acting on the list. Label
duplication has more than one cause, and only one of them is an unseen contents
list:

  * an unseen contents list -- the Sind Civil Servants Ordinance, 50 sections
    against 25 real ones. This is the case worth a marker fix.
  * an AMENDING act quoting the sections it inserts. The Sind Local Government
    (Fourth Amendment) Ordinance, 1987 duplicates 45 labels for that reason and
    prints no contents list at all; see docs/AMENDING-ACT-SECTIONS.md.
  * a right-margin gazette whose marginal notes sit at x0 455 and arrive AFTER
    the block they head, so headings and bodies interleave.

So the count is an upper bound on the marker-fix opportunity, not an estimate of
it. Read the opening lines before writing a pattern for any of them.

Reads only.

    ./nz unseen-contents
    ./nz unseen-contents --show 30
"""
from __future__ import annotations

import argparse
import re

from nizam.storage.db import connect

SQL = """
WITH no_contents AS (
  SELECT i.id, i.document_id
    FROM instrument i
   WHERE i.is_active AND i.duplicate_of IS NULL
     AND NOT EXISTS (SELECT 1 FROM instrument_toc_entry e
                      WHERE e.instrument_id = i.id)
), duplicated AS (
  SELECT n.id, n.document_id, count(*) AS repeated_labels
    FROM no_contents n
    JOIN provision p ON p.instrument_id = n.id AND p.is_active
                    AND p.kind IN ('section','article')
   GROUP BY n.id, n.document_id,
            regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g')
  HAVING count(*) > 1
)
SELECT d.document_id, sum(d.repeated_labels) AS duplicate_sections,
       (SELECT count(*) FROM provision p
         WHERE p.instrument_id = d.id AND p.is_active
           AND p.kind IN ('section','article')) AS sections
  FROM duplicated d
 GROUP BY d.id, d.document_id
 ORDER BY 2 DESC
"""

LINES = """
SELECT b.document_id, b.text
  FROM text_block b
 WHERE b.document_id = ANY(%s) AND b.page_no <= 3
 ORDER BY b.document_id, b.reading_order
"""

# what a recognised marker looks like today
KNOWN = re.compile(
    r"^\s*(?:c\s*o\s*n\s*t\s*e\s*n\s*t\s*s?|table\s+of\s+contents"
    r"|arrangement\s+of\s+(?:sections|rules|articles)"
    r"|sections?|rules?|articles?|regulations?|clauses?)\s*[.:]?\s*$", re.I)

# a line that could plausibly be heading a list, and is not already known
CANDIDATE = re.compile(r"^[A-Za-z][A-Za-z \-&.,']{2,44}$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=20)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        rows = cur.fetchall()
        documents = sorted({row[0] for row in rows})
        if not documents:
            print("none")
            return 0
        cur.execute(LINES, (documents,))
        opening: dict[int, list[str]] = {}
        for document_id, text in cur.fetchall():
            for line in (text or "").splitlines():
                stripped = line.strip()
                if stripped:
                    opening.setdefault(document_id, []).append(stripped)

    already, unknown = 0, []
    for document_id, duplicates, sections in rows:
        lines = opening.get(document_id, [])
        if any(KNOWN.match(line) for line in lines):
            already += 1
            continue
        headers = [line for line in lines[:14] if CANDIDATE.match(line)]
        unknown.append((duplicates, document_id, sections, headers[:3]))

    print(f"instruments with no contents entries whose section labels repeat: "
          f"{len(rows)}")
    print(f"  already print a marker the parser now knows : {already}")
    print(f"  print no known marker                       : {len(unknown)}\n")
    unknown.sort(reverse=True)
    for duplicates, document_id, sections, headers in unknown[:a.show]:
        print(f"  doc {document_id:<6} {sections:>4} sections, "
              f"{duplicates:>3} duplicated   {headers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
