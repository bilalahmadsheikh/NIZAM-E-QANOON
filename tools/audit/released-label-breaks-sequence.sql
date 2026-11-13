-- Released sections whose numeric label breaks the ascending run of its neighbours (INV-1).
--
-- Found 13 Nov 2026 repairing document 7527 (Municipal Administration Ordinance, 1960): sections 100, 108, 111 and
-- 123 were released labelled 9, 8, 411 and 3 -- a dip or a spike inside a run 97 .. 101. The first-block test
-- (label-disagrees-with-first-block.sql) mixed these with correct shapes: 377 of its 400 rows were a misread digit
-- in the TEXT under a right label, a shared block, a fused footnote marker or an owner-cited label
-- (tools/audit/label_triage.py). This test reads the LABELS only: in printed order (first block's page and reading
-- order) within one instrument, a section whose number is below both neighbours or above both, while the neighbours
-- themselves ascend, is out of its run.
--
-- Not every row is a defect: an instrument that restarts numbering (a schedule's rules, a second instrument printed in
-- the same file), a two-column page read across, or a section printed out of order by the source can trip it. Read the
-- page. Assert the rule, report the number.

\pset pager off

CREATE TEMP TABLE label_run AS
SELECT r.document_id, p.instrument_id, p.id, p.label, p.path::text AS path, tb.page_no,
       (regexp_match(p.label, '^(\d{1,4})'))[1]::int AS n,
       row_number() OVER (PARTITION BY p.instrument_id ORDER BY tb.page_no, tb.reading_order, p.path) AS k
  FROM v_release_instrument r
  JOIN provision p ON p.instrument_id = r.id AND p.is_active AND p.kind = 'section'
  JOIN text_block tb ON tb.id = p.first_block
 WHERE p.label ~ '^\d{1,4}' AND p.path::text !~ '__p';   -- an owner-cited label is adjudicated

CREATE TEMP TABLE label_break AS
SELECT b.*, a.n AS prev_n, c.n AS next_n
  FROM label_run b
  JOIN label_run a ON a.instrument_id = b.instrument_id AND a.k = b.k - 1
  JOIN label_run c ON c.instrument_id = b.instrument_id AND c.k = b.k + 1
 WHERE a.n < c.n AND c.n - a.n <= 6                                   -- the neighbours ascend closely
   AND (b.n < a.n OR b.n > c.n);                                      -- this one is outside them

\echo '-- 1. how many'
SELECT count(*) AS sections, count(DISTINCT instrument_id) AS instruments FROM label_break;

\echo '-- 2. every one, for reading'
SELECT b.document_id, left(i.short_title, 40) AS title, b.prev_n || ' [' || b.label || '] ' || b.next_n AS run,
       b.page_no, b.path
  FROM label_break b JOIN instrument i ON i.id = b.instrument_id
 ORDER BY b.document_id, b.page_no;
