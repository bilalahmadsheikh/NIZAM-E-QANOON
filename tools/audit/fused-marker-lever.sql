-- The fused-footnote-marker shape -- and the evidence that it is NOT a lever.
--
-- Pakistani consolidations print footnote markers immediately before a section
-- number, and the extractor fuses them: "8114." for section 114, "7, 8112." for
-- section 112. The opener strips ONE leading marker, so "8114." and "2116."
-- both resolve, but a comma-separated LIST -- "7, 8112.", "1, 2115.",
-- "1, 2117." -- defeats it and the section is never created. Document 4501
-- (Code of Criminal Procedure, held twice) shows both behaviours on the same
-- two pages, and loses sections 112, 113, 115 and 117 to it.
--
-- It is worth fixing, because it is cheap and it costs the Code four sections.
-- It is NOT worth planning around: run this and see how few blocks carry the
-- shape. Assert the rule, report the number.

\pset pager off

\echo '-- 1. blocks that open with a comma-separated marker list fused to a number'
SELECT count(*) AS blocks, count(DISTINCT document_id) AS documents
FROM text_block
WHERE text ~ '^[ \t]*[0-9]{1,2}(,[ \t]*[0-9]{1,2})+[0-9]{1,4}[A-Z]?\.[ \t]';

\echo '-- 2. every one of them, so the shape can be judged by eye'
SELECT document_id, page_no, id AS block_id,
       left(regexp_replace(text, '\s+', ' ', 'g'), 90) AS opens
FROM text_block
WHERE text ~ '^[ \t]*[0-9]{1,2}(,[ \t]*[0-9]{1,2})+[0-9]{1,4}[A-Z]?\.[ \t]'
ORDER BY document_id, page_no, reading_order;

\echo '-- 3. pending contents gaps in the documents that carry the shape'
WITH lever AS (
  SELECT DISTINCT document_id
  FROM text_block
  WHERE text ~ '^[ \t]*[0-9]{1,2}(,[ \t]*[0-9]{1,2})+[0-9]{1,4}[A-Z]?\.[ \t]'
)
SELECT g.document_id, min(g.short_title) AS instrument, count(*) AS pending_gaps,
       string_agg(DISTINCT g.printed_label, ',' ORDER BY g.printed_label) AS labels
FROM v_toc_gap_pending g
WHERE g.document_id IN (SELECT document_id FROM lever)
GROUP BY g.document_id
ORDER BY pending_gaps DESC;
