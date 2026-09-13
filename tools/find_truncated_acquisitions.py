"""Documents whose PDF stops before the statute does.

A contents gap has two innocent explanations, and a third that no parser fix
reaches. Either the parser missed a section the page prints, or the source
genuinely omits it -- but sometimes the acquired FILE is a partial copy of a
complete statute, and the promised sections are absent from the copy rather than
from the law.

The Nawab Shaheed Ghous Bakhsh Raisani Memorial Hospital Act, 2012 is the worked
example. The Balochistan Code holds it as three pages that stop during section
5, while its own contents lists sixteen. No re-parse recovers section 6; the
nine-page official Gazette does, and ``recover_acquisition.py --alternate-for``
landed it.

Recording those gaps as ``absent_in_source`` would assert something false about
the statute -- that the legislature never enacted the section -- on evidence
that only shows the file is short. So they are held out, and this finds them.

THREE TESTS, EACH ADDED BECAUSE THE ONE BEFORE IT WAS NOT ENOUGH.

1. The contents promises a highest label the tree never reaches, and the last
   provision sits on the document's last page. Alone this flags healthy
   documents: a complete Act also ends its last section on its last page.

2. Every gap sits ABOVE the highest label the tree holds. Truncation loses a
   contiguous tail; a parser defect scatters.

3. The last real line does not end a sentence. The Registration Act, 1908 passes
   both tests above and is whole -- it ends "THE SCHEDULE.-[REPEAL OF
   ENACTMENTS.] Rep. by the Repealing Act, 1938", then "Page 35 of 35". Its
   three gaps are absent_in_source. The Raisani Act ends "The administration and
   management of the affairs of the": no terminal punctuation, mid-clause, no
   schedule, no footer. That is what a short file looks like.

WHAT IT STILL CANNOT DO. Test 3 is confounded and the output must be read, not
trusted. A statute that ends in a FORM, a printer's imprint, a schedule table or
a footnote also has no terminal punctuation on its last line, and those are
complete documents:

    1043  "Signature of the dealer / importer / manufacturer"
    4522  "Printed at the Sindh Government Press 7-05-2..."
    4344  "RGN Dated:18-03-2026"
    3387  "8 Salt 24 Poultry food 9 Potatoes 25 Surgical gloves"

So this narrows the contents-gap queue from ~1,240 rows to a few dozen worth
looking at; it does not decide which are short copies. Only an independent
official copy settles that, which is the point -- the answer to a truncated
acquisition is another acquisition, not another parse.

Reads only. It writes nothing and adjudicates nothing.

    ./nz truncated
"""
from __future__ import annotations

import argparse

from nizam.storage.db import connect

SQL = r"""
WITH live AS (
  SELECT i.id, i.document_id, i.short_title, d.page_count
    FROM instrument i
    JOIN document d ON d.id = i.document_id AND d.is_active
   WHERE i.is_active AND i.duplicate_of IS NULL
), promised AS (
  SELECT e.instrument_id,
         max((regexp_match(e.printed_label, '^(\d{1,4})'))[1]::int) AS top_promised,
         count(*) AS entries
    FROM instrument_toc_entry e
   WHERE e.printed_label ~ '^\d{1,4}'
   GROUP BY e.instrument_id
), held AS (
  SELECT p.instrument_id,
         max((regexp_match(p.label, '^(\d{1,4})'))[1]::int) AS top_held,
         max(p.last_page) AS last_provision_page,
         count(*) FILTER (WHERE p.kind IN ('section','article')) AS sections
    FROM provision p
   WHERE p.is_active AND p.label ~ '^\d{1,4}'
   GROUP BY p.instrument_id
)
SELECT l.document_id, l.page_count, pr.top_promised, h.top_held,
       h.sections, pr.entries,
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id = l.id) AS gaps,
       left(fin.tail, 54) AS last_line,
       left(coalesce(l.short_title, ''), 34) AS title
  FROM live l
  JOIN promised pr ON pr.instrument_id = l.id
  JOIN held h ON h.instrument_id = l.id
  -- The last real line of the file. Page footers and bare running numbers are
  -- skipped: they say nothing about whether the text stopped.
  JOIN LATERAL (
    SELECT btrim(regexp_replace(b.text, '\s+', ' ', 'g')) AS tail
      FROM text_block b
     WHERE b.document_id = l.document_id
       AND b.page_no = (SELECT max(page_no) FROM text_block x
                         WHERE x.document_id = l.document_id)
       AND length(btrim(b.text)) >= 25
       AND btrim(b.text) !~* '^(page\s+\d+\s+of\s+\d+|\d+)\s*$'
     ORDER BY b.reading_order DESC
     LIMIT 1) fin ON true
 WHERE pr.top_promised > h.top_held
   -- A trailing year read as a section label ("An Act to amend ..., 1972.")
   -- inflates top_promised into the thousands and drowns the real cases: the
   -- first run reported 2000, 1987 and 1499 as promised sections. A contents
   -- list cannot promise a number far beyond the rows it prints, so bound it by
   -- the list's own length; 30 is slack for suffixed labels such as 53-A.
   AND pr.top_promised <= pr.entries + 30
   -- (1) the tree runs out ON the last page
   AND h.last_provision_page >= l.page_count
   -- (2) and every gap is in the tail, not scattered through the body
   AND NOT EXISTS (
         SELECT 1 FROM v_toc_gap_pending g
          WHERE g.instrument_id = l.id
            AND g.printed_label ~ '^\d{1,4}'
            AND (regexp_match(g.printed_label, '^(\d{1,4})'))[1]::int <= h.top_held)
   -- (3) and the file stops mid-sentence. ASCII terminators only: a curly quote
   -- written into this file through a shell heredoc arrived as a replacement
   -- character and silently matched nothing.
   AND fin.tail !~ '[.;:!?)\]"]$'
   AND (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id = l.id) > 0
 ORDER BY (pr.top_promised - h.top_held) DESC
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=25)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL)
        rows = cur.fetchall()

    total_gaps = sum(r[6] for r in rows)
    print(f"documents that stop mid-sentence below what their contents "
          f"promises: {len(rows)}")
    print(f"contents gaps sitting in them: {total_gaps}")
    print("\ncandidates for a complete official copy, NOT for "
          "absent_in_source:\n")
    print(f"{'doc':>6} {'pages':>6} {'promised':>9} {'held':>6} {'gaps':>5}  "
          f"{'last line of the file':<54}  title")
    for (doc, pages, top_promised, top_held, _sections, _entries,
         gaps, last_line, title) in rows[:a.show]:
        print(f"{doc:>6} {pages:>6} {top_promised:>9} {top_held:>6} "
              f"{gaps:>5}  {(last_line or ''):<54}  {title}")
    if len(rows) > a.show:
        print(f"  ... and {len(rows) - a.show} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
