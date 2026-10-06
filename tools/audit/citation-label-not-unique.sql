-- Does "section N of this instrument" resolve to exactly one unit?
--
-- WHY THIS EXISTS. S6 asks "no sibling sections share one citation label" and
-- groups by (instrument, PARENT, kind, label). Two units both labelled
-- "section 5" under DIFFERENT parents -- one under Chapter II, one under
-- Chapter III -- are not siblings, so S6 never compares them. But section
-- numbers in Pakistani statutes run continuously across chapters and parts:
-- "section 5 of the Act" names one provision, whichever chapter holds it. Two
-- holders make the citation ambiguous, and nothing flagged it.
--
-- Found 22 Sep 2026 while classifying the S7 collisions a replay would
-- dissolve. 97 of the first 1,029 dissolved rows were a footnote and a real
-- section BOTH holding "section N" under different parents -- the collision
-- the S7 queue used to show simply stops being a sibling collision, drops out
-- of every queue, and the instrument becomes releasable with an ambiguous
-- citation inside it. A falling S7 count would have read as success.
--
-- WHAT IS EXCLUDED, and why. Schedules, annexures, appendices and forms
-- legitimately restart their own numbering, so "rule 3 of the First Schedule"
-- and "section 3" are different citations. A unit beneath any of them is left
-- out. The path encodes ancestry (e.g. `...sch_Schedule_n74_1.cl_13`), which is
-- how "beneath a schedule" is tested.
--
-- REPORTING ONLY, AND ITS FIRST RESULT IS MOSTLY A FALSE ALARM. Read this
-- before quoting the count.
--
-- Run on 22 Sep 2026 it reported 436 shared labels in 96 RELEASED instruments.
-- The worst row -- document 3393, "section 1" held by five units under five
-- parents -- is the Quaid-e-Azam Library Membership Rules 2001, which numbers
-- EACH PART FROM 1: Part "General" rule 1, Part "Membership Fee" rule 1, Part
-- "Timings" rule 1. That is the source's own drafting scheme, parsed
-- correctly. It is not an ambiguous citation in the source; it is a citation
-- that needs its Part to be unique.
--
-- So a label-only test cannot separate the two things it catches:
--   * legitimate per-Part numbering (fine in the source -- but it means a
--     rendered citation MUST carry the Part, or "Rule 1" names five rules;
--     that is a citation-rendering requirement under INV-1, not a corpus
--     defect), and
--   * a stray duplicate, where a footnote or list cell holds "section N"
--     alongside the real section under another parent. That is the real
--     defect, and it needs the TEXT of each holder to see -- see the
--     `apparatus_alongside_real` class in `.frame_rows.py`, which found 97 such
--     rows in the first 1,029 collisions a replay would dissolve.
--
-- A useful refinement: in per-Part numbering every parent carries its own run
-- starting at 1; a stray duplicate is an isolated number under a parent whose
-- run does not otherwise exist. Until that is built, do not gate on this.
--
--     ./nz psql < tools/audit/citation-label-not-unique.sql

\pset format aligned
\set ON_ERROR_STOP on
SET work_mem = '256MB';

CREATE TEMP TABLE citable AS
SELECT p.id, p.instrument_id, i.document_id, p.parent_id, p.kind::text AS kind,
       btrim(p.label) AS label, p.first_page, p.path::text AS path,
       (r.id IS NOT NULL) AS released
  FROM provision p
  JOIN instrument i ON i.id = p.instrument_id AND i.is_active AND i.duplicate_of IS NULL
  LEFT JOIN v_release_instrument r ON r.id = i.id
 WHERE p.is_active
   AND p.kind IN ('section', 'article')
   AND btrim(p.label) <> ''
   -- outside any subtree that restarts its own numbering
   AND p.path::text !~ '\.(sch|app|ann|annex|form|frm)_';

CREATE TEMP TABLE shared AS
SELECT instrument_id, document_id, kind, label,
       count(*)                    AS holders,
       count(DISTINCT parent_id)   AS distinct_parents,
       bool_or(released)           AS released
  FROM citable
 GROUP BY instrument_id, document_id, kind, label
HAVING count(*) > 1;

\echo ''
\echo '-- labels held by more than one unit in the same citation space'
SELECT count(*)                                              AS shared_labels,
       count(DISTINCT instrument_id)                         AS instruments,
       count(*) FILTER (WHERE distinct_parents > 1)          AS across_parents_S6_cannot_see,
       count(*) FILTER (WHERE distinct_parents = 1)          AS same_parent_S6_catches,
       count(*) FILTER (WHERE released)                      AS in_released_instruments,
       count(DISTINCT instrument_id) FILTER (WHERE released) AS released_instruments
  FROM shared;

\echo ''
\echo '-- the released ones S6 cannot see, worst first -- each needs a page read'
SELECT s.document_id, s.kind, s.label, s.holders, s.distinct_parents,
       string_agg(DISTINCT coalesce(c.first_page::text,'?'), ',') AS pages
  FROM shared s
  JOIN citable c ON c.instrument_id = s.instrument_id AND c.label = s.label AND c.kind = s.kind
 WHERE s.released AND s.distinct_parents > 1
 GROUP BY s.document_id, s.kind, s.label, s.holders, s.distinct_parents
 ORDER BY s.holders DESC, s.document_id
 LIMIT 30;
