-- A cross-reference number that wraps to the start of a line opens a phantom.
--
-- Found on 18 Sep by the reader working shard defects-35, confirmed four times
-- in the Punjab Prisons Rules 1978 with the render showing the wrap each time
-- (rules 584 p208, 611 p221, 1249 p481, 73 p479). The source prints
--
--     ... the fact shall be notified to all officers who have been addressed under rule
--     611. (ii) A recaptured prisoner shall ...
--
-- and every opener the segmenter has sees a line beginning "611." -- a number
-- followed by text. The unit it opens is a phantom, and it swallows whatever is
-- printed after it: the 1249 phantom took an operative sentence of rule 1250.
--
-- The tell is the cross-reference word left dangling at the end of the previous
-- LINE, inside the same PyMuPDF block -- which is where `subdivide()` cuts.
-- Real openers are preceded by a full stop, a heading, or nothing at all.
--
-- This counts the shape; it does not decide the rows. An instrument may
-- legitimately end a line with "...under rule" and then genuinely begin its
-- rule 611. Read each against the rendered page before acting.
--
-- STATUS, 18 Sep 2026: this file counts the SHAPE well (158 blocks in 122
-- documents) but does not yet reproduce the reader's evidence. Section 2, which
-- tries to link the wrap to a live section that actually opened at that number,
-- returns 2 rows -- and one of them, document 4379's section 341, reads like a
-- genuine section. Of the reader's four confirmed cases in document 4474, only
-- rule 611 on page 221 is matched by section 1's pattern at all. So the wrap is
-- being printed in more shapes than this regex sees -- across a block boundary,
-- or with the cross-reference word further back than the previous line -- and
-- the linkage in section 2 is too strict besides. Treat section 1 as a lower
-- bound on the shape and the reader's four cases as the ground truth; do not
-- quote section 2 as a corpus count until this matches them.
--
-- Assert the rule, report the number.

\pset pager off

\echo '-- 1. the shape: a cross-reference word at a line end, a number opening the next line'
SELECT count(*) AS blocks, count(DISTINCT document_id) AS documents
FROM text_block
WHERE text ~* '\y(rule|section|regulation|paragraph|para|clause|article)[ \t]*\n[ \t]*[0-9]{1,4}[.)][ \t]';

\echo '-- 2. the sharp form: a live section actually opened at that wrapped number'
WITH act AS (SELECT id, document_id FROM block_assignment_set WHERE is_active),
wrapped AS (
  SELECT tb.id AS block_id, tb.document_id, tb.page_no,
         (regexp_match(tb.text,
            '\y(?:rule|section|regulation|paragraph|para|clause|article)[ \t]*\n[ \t]*([0-9]{1,4})[.)][ \t]',
            'i'))[1] AS num
  FROM text_block tb
  WHERE tb.text ~* '\y(rule|section|regulation|paragraph|para|clause|article)[ \t]*\n[ \t]*[0-9]{1,4}[.)][ \t]')
SELECT count(*) AS phantom_candidates,
       count(DISTINCT w.document_id) AS documents
FROM wrapped w
JOIN act a ON a.document_id = w.document_id
JOIN provision_block pb ON pb.assignment_set_id = a.id AND pb.block_id = w.block_id
JOIN provision pr ON pr.id = pb.provision_id AND pr.kind = 'section' AND pr.is_active
WHERE btrim(pr.label) = w.num;

\echo '-- 3. the rows to read, by document'
WITH act AS (SELECT id, document_id FROM block_assignment_set WHERE is_active),
wrapped AS (
  SELECT tb.id AS block_id, tb.document_id, tb.page_no,
         (regexp_match(tb.text,
            '\y(?:rule|section|regulation|paragraph|para|clause|article)[ \t]*\n[ \t]*([0-9]{1,4})[.)][ \t]',
            'i'))[1] AS num
  FROM text_block tb
  WHERE tb.text ~* '\y(rule|section|regulation|paragraph|para|clause|article)[ \t]*\n[ \t]*[0-9]{1,4}[.)][ \t]')
SELECT w.document_id, w.page_no, pr.label,
       left(regexp_replace(tb.text, '\s+', ' ', 'g'), 120) AS snippet
FROM wrapped w
JOIN act a ON a.document_id = w.document_id
JOIN provision_block pb ON pb.assignment_set_id = a.id AND pb.block_id = w.block_id
JOIN provision pr ON pr.id = pb.provision_id AND pr.kind = 'section' AND pr.is_active
JOIN text_block tb ON tb.id = w.block_id
WHERE btrim(pr.label) = w.num
ORDER BY w.document_id, w.page_no
LIMIT 40;
