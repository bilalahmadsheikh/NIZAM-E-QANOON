-- The contents-region overrun lever.
--
-- The segmenter marks the front-matter contents list with role='contents' and
-- attaches those blocks to no provision -- correct, because a contents entry is
-- apparatus, not law. The failure is where that region does not stop: the role
-- keeps being applied after the printed list has ended, so the opening pages of
-- the BODY are filed as contents and attached to nothing.
--
-- Nothing is lost -- the text is in text_block, in the PDF's own words -- but it
-- is attached to no provision, so it cannot be cited. That is an INV-4 failure
-- (provisions are the citable unit) and it is invisible to the contents-gap
-- queue, which only asks whether a promised entry resolved.
--
-- A contents ENTRY is a short line: a label, a heading, a page number. Body text
-- is long and carries operative verbs. Section 3 uses that to separate them.
--
-- Assert the rule, report the number: this file re-derives every figure quoted
-- in .artifacts/catalogue/PATTERNS.md, it does not encode them.
--
-- Note on provision_block: it is append-only and keeps retired assignment sets.
-- Every query here joins block_assignment_set on is_active. Omitting that filter
-- multiplies every count by the number of times the document was re-segmented.

\pset pager off

\echo '-- 1. blocks filed as contents and attached to no provision (active sets only)'
WITH act AS (SELECT id, document_id FROM block_assignment_set WHERE is_active)
SELECT count(*) AS blocks,
       count(DISTINCT a.document_id) AS documents,
       sum(pb.chars) AS chars
FROM provision_block pb
JOIN act a ON a.id = pb.assignment_set_id
WHERE pb.role = 'contents' AND pb.provision_id IS NULL;

\echo '-- 2. the contents ROLE outlasting the printed contents LIST'
WITH act AS (SELECT id, document_id, instrument_id FROM block_assignment_set WHERE is_active),
role_end AS (
  SELECT a.instrument_id, a.document_id, max(tb.page_no) AS role_last_page
  FROM provision_block pb
  JOIN act a ON a.id = pb.assignment_set_id
  JOIN text_block tb ON tb.id = pb.block_id
  WHERE pb.role = 'contents' AND pb.provision_id IS NULL
  GROUP BY a.instrument_id, a.document_id),
list_end AS (
  SELECT instrument_id, max(source_page) AS list_last_page
  FROM v_toc GROUP BY instrument_id)
SELECT count(*) AS instruments,
       count(*) FILTER (WHERE r.role_last_page > l.list_last_page) AS role_outlasts_list,
       max(r.role_last_page - l.list_last_page) AS worst_overrun_pages
FROM role_end r JOIN list_end l ON l.instrument_id = r.instrument_id;

\echo '-- 3. the sharp form: operative law parked in the contents region'
-- A contents entry is a short line. A block over 200 characters that carries an
-- operative verb is body text, not a contents entry, and it is attached to no
-- provision -- law in the database that no citation can reach.
WITH act AS (SELECT id, document_id FROM block_assignment_set WHERE is_active)
SELECT count(*) AS blocks,
       count(DISTINCT a.document_id) AS documents,
       sum(pb.chars) AS chars
FROM provision_block pb
JOIN act a ON a.id = pb.assignment_set_id
JOIN text_block tb ON tb.id = pb.block_id
WHERE pb.role = 'contents' AND pb.provision_id IS NULL
  AND length(tb.text) > 200
  AND tb.text ~ '\y(shall|means|may not|is hereby|are hereby|shall be deemed)\y';

\echo '-- 4. the documents holding the most of it'
WITH act AS (SELECT id, document_id FROM block_assignment_set WHERE is_active)
SELECT a.document_id,
       count(*) AS stranded_blocks,
       sum(pb.chars) AS stranded_chars,
       min(tb.page_no) AS from_page,
       max(tb.page_no) AS to_page
FROM provision_block pb
JOIN act a ON a.id = pb.assignment_set_id
JOIN text_block tb ON tb.id = pb.block_id
WHERE pb.role = 'contents' AND pb.provision_id IS NULL
  AND length(tb.text) > 200
  AND tb.text ~ '\y(shall|means|may not|is hereby|are hereby|shall be deemed)\y'
GROUP BY a.document_id
ORDER BY stranded_chars DESC
LIMIT 20;

\echo '-- 5. the directly-releasable subset: a pending gap whose label opens such a block'
WITH act AS (SELECT id, document_id FROM block_assignment_set WHERE is_active),
stray AS (
  SELECT a.document_id,
         btrim((regexp_match(tb.text, '^[ \t]*\[?([0-9]{1,3}[A-Z]?)[.)][ \t]'))[1]) AS num
  FROM provision_block pb
  JOIN act a ON a.id = pb.assignment_set_id
  JOIN text_block tb ON tb.id = pb.block_id
  WHERE pb.role = 'contents' AND pb.provision_id IS NULL
    AND length(tb.text) > 80
    AND tb.text ~ '^[ \t]*\[?[0-9]{1,3}[A-Z]?[.)][ \t]')
SELECT count(DISTINCT g.toc_entry_id) AS gaps,
       count(DISTINCT g.document_id) AS instruments,
       (SELECT count(DISTINCT toc_entry_id) FROM v_toc_gap_pending) AS pending_gaps_total,
       round(100.0 * count(DISTINCT g.toc_entry_id)
             / nullif((SELECT count(DISTINCT toc_entry_id) FROM v_toc_gap_pending), 0), 1) AS pct
FROM v_toc_gap_pending g
JOIN stray s ON s.document_id = g.document_id
            AND s.num = btrim(g.printed_label);
