-- Source-verified split of Punjab document 4440.
--
-- The official PDF is an editorial package, not one 214-section notification.
-- Its printed contents page labels two notifications (A) and (B).  Page 3
-- prints A's own NOTIFICATION formula and sections 2--5, followed by a
-- departmental signature.  Page 4 starts a second NOTIFICATION formula with
-- the same administrative number/date but different regulated workers,
-- sections 2--7, its own signature, and an explicit SCHEDULE on page 6.
-- Numbered industry/job rows in that schedule are not notification sections.
--
-- Immutable source anchors reviewed in rendered pages 1, 3, 4 and 6 on
-- 2026-09-12.  This file appends evidence only; materialisation is a separate,
-- dry-run-gated operation.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id,i.source_observation_id,i.document_id
    FROM instrument i
   WHERE i.document_id=4440
     AND i.is_active
     AND i.duplicate_of IS NULL
), proposed(start_block_id,detected_title,source_page,support_ids) AS (
  VALUES
    (795714::bigint,
     'NOTIFICATION REGARDING MINIMUM WAGES FOR UNSKILLED FOR ALL CATEGORIES OF WORKERS EMPLOYED IN 51 INDUSTRIES IN THE PUNJAB',
     3,
     ARRAY[795655,795656,795714,795717,795718,795724,795733,795734]::bigint[]),
    (795735::bigint,
     'Notification for minimum rates of wages for skilled and semi-skilled workers employed in 51 industries in Punjab',
     4,
     ARRAY[795659,795660,795735,795736,795737,795741,795754,795807,795808,795809]::bigint[])
), source_rows AS (
  SELECT a.*,p.start_block_id,p.detected_title,p.source_page,
         (SELECT jsonb_agg(jsonb_build_object(
                    'block_id',b.id,
                    'page',b.page_no,
                    'sha256',encode(digest(b.text,'sha256'),'hex'),
                    'preview',left(regexp_replace(b.text,E'[\n\r]+',' ','g'),240))
                  ORDER BY b.reading_order)
            FROM text_block b
           WHERE b.document_id=a.document_id
             AND b.id=ANY(p.support_ids)) AS supporting_blocks
    FROM active_instrument a CROSS JOIN proposed p
)
INSERT INTO segmentation_boundary_candidate
  (instrument_id,source_observation_id,document_id,start_block_id,source_page,
   detected_title,detected_kind,detected_year,detected_number,confidence,
   method,evidence)
SELECT id,source_observation_id,document_id,start_block_id,source_page,
       detected_title,'notification',2013,'SO(D-II)MW/2011(P-II)',1.0,
       'nizam.source_verified_minimum_wages_package/1',
       jsonb_build_object(
         'reviewed_pages',jsonb_build_array(1,3,4,6),
         'source_facts',jsonb_build_array(
           'contents_explicitly_lists_A_and_B',
           'each_expression_has_independent_notification_formula',
           'each_expression_has_independent_operating_sections_and_signature',
           'B_explicitly_appends_a_schedule'),
         'supporting_blocks',supporting_blocks)
  FROM source_rows
 WHERE jsonb_array_length(supporting_blocks)=
       CASE source_page WHEN 3 THEN 8 ELSE 10 END
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication
  (candidate_id,resolution,review_basis,method,rationale,evidence,decided_by)
SELECT c.id,'confirmed_split','source_verified',
       'nizam.source_verified_minimum_wages_package/1',
       'Rendered official pages 1, 3, 4 and 6 prove two separately operative notifications. The second notification has an explicit schedule; its numbered industries and occupations are schedule rows, not top-level notification sections.',
       jsonb_build_object(
         'reviewed_pages',jsonb_build_array(1,3,4,6),
         'reviewed_on','2026-09-12',
         'source_sha256',i.source_sha256,
         'decision','materialize_as_two_disjoint_expressions'),
       'codex.source-review/1'
  FROM segmentation_boundary_candidate c
  JOIN instrument i ON i.id=c.instrument_id
 WHERE c.document_id=4440
   AND c.method='nizam.source_verified_minimum_wages_package/1'
   AND i.is_active
   AND i.duplicate_of IS NULL
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id)
ORDER BY c.source_page;

COMMIT;
