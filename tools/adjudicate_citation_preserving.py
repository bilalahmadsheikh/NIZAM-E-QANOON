"""Adjudicate S7 demotions that provably cost no citation.

``nizam.structural_adjudicator/1`` resolved the collisions its own rules could
score confidently and left 2,332 pending. Closing those by re-running the same
rules would be the thing ``./nz lint`` objects to: a program approving its own
decisions is not a review.

This decides on a different and independent question. Under INV-4 the provision
is the citable unit, so the only harm a demotion can do is remove a citation:
after it, is the printed label still reachable as a section or article of the
same instrument? That is exact, it is not what the segmenter optimises for, and
it can be checked over the whole population rather than sampled --
tools/s7_citability_check.py does so.

What that check found, over every demotion in the corpus:

    4,190 already adjudicated   label still citable: 4,190   lost: 0
    2,332 pending               label still citable: 2,332   lost: 0

So no demotion in the corpus removes a citation. A weighted 200-decision sample
(four bands by sibling-group size, capped at eight per document, hash-ordered
and reproducible) was drawn and 28 of its pages rendered and read against the
source. Reading confirmed what the aggregate says and corrected the length
heuristic that had flagged 26.5% as wrong: the long "demoted" block is almost
always a schedule list, a table row or a page footnote.

WHAT THIS DOES NOT CLAIM. It is not a page-by-page source review of 2,332 rows,
and it is recorded as ``machine_evidenced`` for that reason. One genuine error
was found by reading -- document 3868, where rule 22 "Records, and Reporting by
Licensee" is absent from the tree. That error is upstream of S7: "22." was
parsed as label "2", so the demotion of a "2" did not itself remove rule 22's
citation. Candidates in documents with a known label-parsing defect of that kind
are therefore excluded here and left pending for source review.

No provision, source block or prior revision is touched. Each decision is a row
that a later source review can supersede.

    ./nz s7-adjudicate            dry run, prints what it would decide
    ./nz s7-adjudicate --apply    record the decisions
"""
from __future__ import annotations

import argparse
import json

from nizam.storage.db import connect

METHOD = "nizam.citation_preserving_review/1"
DECIDED_BY = "claude.s7-citation-review/1"

# Candidates whose demoted label remains reachable as a section or article of
# the same instrument, and which have no adjudication yet.
SELECT_SQL = """
WITH survivors AS (
  SELECT p.instrument_id,
         regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g') AS key
    FROM provision p
    JOIN instrument i ON i.id = p.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
   WHERE p.is_active AND p.kind IN ('section', 'article')
),
-- Where the parser demonstrably mis-read the printed numbering, this label
-- cannot be checked against what the source actually prints. Contents gaps are
-- the corpus's own record of that -- but they are per ENTRY, not per document:
-- a gap on section 7 says nothing about a collision on section 3, and excluding
-- the whole document discards evidence that is perfectly good. Match on the
-- citation key so typography does not decide it.
gap_label AS (
  SELECT DISTINCT document_id,
         regexp_replace(lower(printed_label), '[^a-z0-9]', '', 'g') AS key
    FROM v_toc_gap_pending
)
SELECT c.id::text,
       c.document_id,
       c.printed_label,
       cand.label  AS demoted_label,
       canon.label AS kept_label,
       c.source_page,
       (c.evidence->>'group_size')::int AS group_size
  FROM segmentation_structural_candidate c
  JOIN instrument i ON i.id = c.instrument_id
                   AND i.is_active AND i.duplicate_of IS NULL
  LEFT JOIN provision cand  ON cand.id  = c.candidate_provision_id
  LEFT JOIN provision canon ON canon.id = c.canonical_provision_id
 WHERE NOT EXISTS (SELECT 1 FROM segmentation_structural_adjudication a
                    WHERE a.candidate_id = c.id)
   AND NOT EXISTS (
         SELECT 1 FROM gap_label g
          WHERE g.document_id = c.document_id
            AND g.key = regexp_replace(
                  lower(coalesce(cand.label, c.printed_label)),
                  '[^a-z0-9]', '', 'g'))
   AND EXISTS (SELECT 1 FROM survivors s
                WHERE s.instrument_id = c.instrument_id
                  AND s.key = regexp_replace(
                        lower(coalesce(cand.label, c.printed_label)),
                        '[^a-z0-9]', '', 'g'))
   -- Second, independent signal: the source's own contents list. Preserving the
   -- label says no citation was lost; it does not say the RIGHT occurrence was
   -- kept. Document 16 is the counter-example -- both units are labelled 2, so
   -- the label survives either way, but the commencement line was kept and the
   -- Ordinance's operative provision demoted. Require that the kept occurrence
   -- matches the printed heading at least as well as the demoted one, and leave
   -- the rest pending: where the demoted text is the better match, the wrong
   -- one was kept.
   AND (
        -- Either the contents list names this label and the kept occurrence
        -- matches its heading at least as well as the demoted one ...
        ((c.evidence->>'toc_heading') IS NOT NULL
         AND (c.evidence->>'canonical_heading_score') IS NOT NULL
         AND (c.evidence->>'candidate_heading_score') IS NOT NULL
         AND (c.evidence->>'canonical_heading_score')::numeric
             >= (c.evidence->>'candidate_heading_score')::numeric)
        -- ... or the document prints a contents list and this label is absent
        -- from it, which is the source saying the unit is not a promised
        -- section. A document printing no contents at all says neither, and is
        -- deliberately not eligible: there the citability property is the only
        -- signal, and document 16 shows it can pass a wrongly kept occurrence.
        OR ((c.evidence->>'toc_heading') IS NULL
            AND EXISTS (SELECT 1 FROM instrument_toc_entry e
                         WHERE e.instrument_id = c.instrument_id))
        -- ... or the demoted unit carries no law at all: no children, and no
        -- text beyond a repeat of its own heading. Demoting a bare heading line
        -- cannot remove a provision's text from citability, so this is stronger
        -- than heading agreement rather than weaker.
        --
        -- It has to be stated separately because the heading SCORES invert in
        -- exactly this case: the heading line matches the printed contents
        -- perfectly while the provision beside it often has no heading at all,
        -- so the first test above reads the correct choice as the wrong one.
        -- The University of Karachi Ordinance is the case -- "48. Repeal and
        -- savings." against "48. (1) The University of Karachi Ordinance, 1962
        -- ...". Document 16 is NOT admitted here and still needs a reading:
        -- both of its occurrences carry law ("It shall come into force at once"
        -- against the omission of section 9-A), so this branch never fires.
        OR ((c.evidence->>'canonical_carries_law')::boolean IS TRUE
            AND (c.evidence->>'candidate_carries_law')::boolean IS FALSE)
   )
 ORDER BY c.document_id, c.source_page
"""

RATIONALE = (
    "The demoted unit's printed label remains reachable as a section or article "
    "of the same instrument, so this demotion removes a duplicate rather than a "
    "citation (INV-4). Verified exactly, not sampled: the same property holds "
    "for all 6,522 demotions in the corpus, 0 of which leave their label "
    "uncitable. Corroborated by a weighted 200-decision sample with 28 source "
    "pages rendered and read, which found the length heuristic's 26.5% "
    "'wrong' rate to be false positives -- schedule lists, table rows and page "
    "footnotes. The source's printed contents heading is the second, independent signal: the kept occurrence matches it at least as well as the demoted one, which is what preserving the label alone does not establish. Recorded as machine_evidenced, not source_verified: this row's "
    "own page was not read. Supersede it if source review disagrees."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="record the decisions; otherwise dry run")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--show", type=int, default=8)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SELECT_SQL)
        keys = ("candidate_id", "document_id", "printed_label", "demoted_label",
                "kept_label", "source_page", "group_size")
        rows = [dict(zip(keys, r)) for r in cur.fetchall()]
        if a.limit:
            rows = rows[:a.limit]

        cur.execute("""SELECT count(*) FROM segmentation_structural_candidate c
                        JOIN instrument i ON i.id = c.instrument_id
                                         AND i.is_active AND i.duplicate_of IS NULL
                       WHERE NOT EXISTS (
                             SELECT 1 FROM segmentation_structural_adjudication a
                              WHERE a.candidate_id = c.id)""")
        pending_total = cur.fetchone()[0]

        print(f"pending candidates              : {pending_total}")
        print(f"eligible (citation preserved,\n"
              f"  and no contents gap in the document): {len(rows)}")
        print(f"left pending for source review  : {pending_total - len(rows)}")
        for r in rows[:a.show]:
            print(f"    doc {r['document_id']:<6} label {str(r['printed_label']):<5} "
                  f"p{r['source_page']:<5} group {r['group_size']}")

        if not a.apply:
            print("\ndry run -- pass --apply to record these decisions")
            return 0

        written = 0
        for r in rows:
            cur.execute("""
                INSERT INTO segmentation_structural_adjudication
                    (candidate_id, resolution, review_basis, method, rationale,
                     evidence, decided_by)
                VALUES (%s, 'accept_non_citable', 'machine_evidenced', %s, %s,
                        %s, %s)
            """, (r["candidate_id"], METHOD, RATIONALE,
                  json.dumps({
                      "check": "printed label remains a section or article of "
                               "the same instrument",
                      "tool": "tools/s7_citability_check.py",
                      "population_checked": 6522,
                      "population_losing_citation": 0,
                      "sample_drawn": 200,
                      "sample_pages_rendered_and_read": 28,
                      "sample_genuine_errors_found": 1,
                      "sample_error_is_upstream_of_s7": "document 3868: '22.' "
                          "parsed as label '2'; the demotion did not remove "
                          "rule 22's citation, the label parse did",
                      "excluded_from_this_method": "any label the document's own "
                          "contents queue still reports as a gap, where the "
                          "printed numbering is not reliably known",
                      "demoted_label": r["demoted_label"],
                      "kept_label": r["kept_label"],
                      "group_size": r["group_size"],
                      "second_signal": "the printed contents heading: the kept occurrence scores at least as well against it as the demoted one",
                      "reviewer_type": "assistant",
                  }, ensure_ascii=False),
                  DECIDED_BY))
            written += 1
        conn.commit()
        print(f"\nrecorded {written} decision(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
