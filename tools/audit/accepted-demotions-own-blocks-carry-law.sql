-- Accepted demotions whose OWN text carries law, past their opening block.
--
-- `accept_non_citable` retypes the demoted "section" to a clause under the same
-- parent, keeping its whole subtree. Nothing is deleted, but if the demoted node
-- was carrying law, that law is left addressed under the wrong node and a
-- citation rendered from the record names the wrong provision.
--
-- The stop-sign check written on 17 Sep reads the demoted node's DESCENDANTS:
-- any descendant matching `shall|means|may not|is hereby|are hereby` refuses the
-- accept. That check has a blind spot, found on 18 Sep by the reader working
-- shard defects-36: document 4497's candidate 344983a9 reports zero stop-word
-- descendants, yet the block the node itself OWNS (890143) carries rule 6's
-- proviso and its sub-rule (2). A node with no children at all can still hold
-- several blocks of operative text.
--
-- So ask the same question of the node's own blocks, past the first. The first
-- block is the opener -- the label, the heading, the fee cell or footnote line
-- that wrongly opened the unit -- and it is the one block that legitimately
-- belongs to a non-citable unit. Everything after it is text the unit absorbed.
--
-- Assert the rule, report the number: this reads every accept on record rather
-- than a list of ids, so it keeps answering after new decisions are made.

\pset pager off

\echo '-- 1. how many accepts are on record, and how many this check questions'
WITH accepted AS (
  SELECT c.id, c.document_id, c.printed_label, c.candidate_provision_id
  FROM v_structural_adjudication_latest a
  JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
  WHERE a.resolution = 'accept_non_citable'),
own_law AS (
  SELECT ac.id,
         count(*) FILTER (WHERE tb.text ~* '\y(shall|means|may not|is hereby|are hereby)\y')
           AS operative_blocks
  FROM accepted ac
  JOIN provision_block pb ON pb.provision_id = ac.candidate_provision_id
  JOIN block_assignment_set bas
    ON bas.id = pb.assignment_set_id AND bas.is_active
  JOIN text_block tb ON tb.id = pb.block_id
  WHERE pb.block_id <> (
          SELECT pb2.block_id FROM provision_block pb2
          JOIN block_assignment_set b2
            ON b2.id = pb2.assignment_set_id AND b2.is_active
          JOIN text_block t2 ON t2.id = pb2.block_id
          WHERE pb2.provision_id = ac.candidate_provision_id
          ORDER BY t2.page_no, t2.reading_order LIMIT 1)
  GROUP BY ac.id)
SELECT (SELECT count(*) FROM accepted) AS accepts_on_record,
       count(*) FILTER (WHERE operative_blocks > 0) AS questioned,
       sum(operative_blocks) FILTER (WHERE operative_blocks > 0) AS operative_blocks
FROM own_law;

\echo '-- 2. the rows to re-read, worst first'
WITH accepted AS (
  SELECT c.id, c.document_id, c.printed_label, c.candidate_provision_id
  FROM v_structural_adjudication_latest a
  JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
  WHERE a.resolution = 'accept_non_citable')
SELECT ac.id, ac.document_id, ac.printed_label,
       count(*) FILTER (WHERE tb.text ~* '\y(shall|means|may not|is hereby|are hereby)\y')
         AS operative_blocks,
       sum(length(tb.text)) FILTER (WHERE tb.text ~* '\y(shall|means|may not|is hereby|are hereby)\y')
         AS operative_chars,
       max(left(regexp_replace(tb.text, '\s+', ' ', 'g'), 110))
         FILTER (WHERE tb.text ~* '\y(shall|means|may not|is hereby|are hereby)\y')
         AS sample
FROM accepted ac
JOIN provision_block pb ON pb.provision_id = ac.candidate_provision_id
JOIN block_assignment_set bas
  ON bas.id = pb.assignment_set_id AND bas.is_active
JOIN text_block tb ON tb.id = pb.block_id
WHERE pb.block_id <> (
        SELECT pb2.block_id FROM provision_block pb2
        JOIN block_assignment_set b2
          ON b2.id = pb2.assignment_set_id AND b2.is_active
        JOIN text_block t2 ON t2.id = pb2.block_id
        WHERE pb2.provision_id = ac.candidate_provision_id
        ORDER BY t2.page_no, t2.reading_order LIMIT 1)
GROUP BY ac.id, ac.document_id, ac.printed_label
HAVING count(*) FILTER (WHERE tb.text ~* '\y(shall|means|may not|is hereby|are hereby)\y') > 0
ORDER BY operative_chars DESC;
