-- The stranded-number lever.
--
-- PyMuPDF does not always isolate the left-hand number cell of a two- or
-- three-column Gazette layout: often it appends it to the paragraph block
-- above, so the section number becomes the LAST line of the previous
-- section's block and no block begins with it. Every opener the segmenter
-- has expects the number and the text it opens to be adjacent in one block,
-- so the section is never created.
--
-- Nothing is missing from the PDF -- `pdftotext -layout` prints the number in
-- its proper place -- the digits are in text_block, in the wrong block.
--
-- Assert the rule, report the number: this file re-derives the counts quoted
-- in .artifacts/catalogue/PATTERNS.md, it does not encode them.

\pset pager off

\echo '-- 1. blocks that end with a line that is nothing but a section number'
SELECT count(*) AS blocks, count(DISTINCT document_id) AS documents
FROM text_block
WHERE text ~ '(?:^|\n)[ \t]*[0-9]{1,3}[A-Z]?\.?[ \t]*\n?[ \t]*$'
  AND length(text) > 40;

\echo '-- 2. pending contents gaps sitting in documents that show the shape'
WITH lever AS (
  SELECT DISTINCT document_id
  FROM text_block
  WHERE text ~ '(?:^|\n)[ \t]*[0-9]{1,3}[A-Z]?\.?[ \t]*\n?[ \t]*$'
    AND length(text) > 40
)
SELECT count(DISTINCT g.document_id) AS documents, count(*) AS pending_gaps
FROM v_toc_gap_pending g
WHERE g.document_id IN (SELECT document_id FROM lever);

\echo '-- 3. the sharp form: the stranded number IS the label the gap names'
WITH lever AS (
  SELECT tb.document_id,
         btrim((regexp_match(tb.text,
           '(?:^|\n)[ \t]*([0-9]{1,3}[A-Z]?)\.?[ \t]*\n?[ \t]*$'))[1]) AS num
  FROM text_block tb
  WHERE tb.text ~ '(?:^|\n)[ \t]*[0-9]{1,3}[A-Z]?\.?[ \t]*\n?[ \t]*$'
    AND length(tb.text) > 40
)
SELECT g.document_id, min(g.short_title) AS instrument,
       count(DISTINCT g.toc_entry_id) AS gaps,
       string_agg(DISTINCT g.printed_label, ',' ORDER BY g.printed_label) AS labels
FROM v_toc_gap_pending g
JOIN lever l ON l.document_id = g.document_id
            AND l.num = btrim(g.printed_label)
GROUP BY g.document_id
ORDER BY gaps DESC, g.document_id;

\echo '-- 4. that sharp form as a share of everything still open'
WITH lever AS (
  SELECT tb.document_id,
         btrim((regexp_match(tb.text,
           '(?:^|\n)[ \t]*([0-9]{1,3}[A-Z]?)\.?[ \t]*\n?[ \t]*$'))[1]) AS num
  FROM text_block tb
  WHERE tb.text ~ '(?:^|\n)[ \t]*[0-9]{1,3}[A-Z]?\.?[ \t]*\n?[ \t]*$'
    AND length(tb.text) > 40
),
sharp AS (
  SELECT count(DISTINCT g.toc_entry_id) AS n
  FROM v_toc_gap_pending g
  JOIN lever l ON l.document_id = g.document_id
              AND l.num = btrim(g.printed_label)
)
SELECT (SELECT n FROM sharp) AS reachable_by_this_rule,
       (SELECT count(DISTINCT toc_entry_id) FROM v_toc_gap_pending) AS pending_gaps_total,
       round(100.0 * (SELECT n FROM sharp) / nullif((SELECT count(DISTINCT toc_entry_id) FROM v_toc_gap_pending), 0), 1) AS pct;
