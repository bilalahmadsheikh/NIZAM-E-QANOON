-- Two detector-v1 proposals found real internal enactment sequences but chose a
-- citation inside the preamble as start/title. Preserve those proposals,
-- adjudicate the selected anchors as references, and append source-verified
-- candidates at the printed titles. No source or tree row changes.
\set ON_ERROR_STOP on
BEGIN;

WITH wrong AS (
  SELECT c.id,c.document_id,c.start_block_id
    FROM segmentation_boundary_candidate c
   WHERE c.method='nizam.multi_instrument_detector/1'
     AND (c.document_id,c.start_block_id) IN ((3423,374816),(4434,793360))
)
INSERT INTO segmentation_boundary_adjudication
  (candidate_id,resolution,review_basis,method,rationale,evidence,decided_by)
SELECT id,'embedded_reference','source_verified','boundary-anchor-review/1',
       'The surrounding sequence is a real internal instrument, but this selected block is a reference in its covering letter or preamble rather than the printed boundary title.',
       jsonb_build_object('document_id',document_id,'rejected_start_block_id',start_block_id,
                          'reviewed_against','ordered source text blocks'),
       'boundary-anchor-review/1'
  FROM wrong
 WHERE NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication a
                    WHERE a.candidate_id=wrong.id);

WITH corrected(document_id,start_block_id,title,support_ids) AS (
  VALUES
    (3423::bigint,374815::bigint,
     'THE PUNJAB EMPLOYEES EFFICIENCY, DISCIPLINE AND ACCOUNTABILITY (AMENDMENT) ACT, 2014',
     ARRAY[374815,374817,374818,374819]::bigint[]),
    (4434::bigint,793353::bigint,
     'The Constitution (Eighteenth Amendment) Act, 2010',
     ARRAY[793353,793358,793361,793362]::bigint[])
), source_rows AS (
  SELECT c.*,i.id instrument_id,i.source_observation_id,b.page_no,
         (SELECT jsonb_agg(jsonb_build_object(
                    'block_id',t.id,'page',t.page_no,
                    'preview',left(regexp_replace(t.text,E'[\\n\\r]+',' ','g'),240))
                  ORDER BY t.reading_order)
            FROM text_block t WHERE t.id=ANY(c.support_ids)) support
    FROM corrected c
    JOIN instrument i ON i.document_id=c.document_id
                     AND i.is_active AND i.duplicate_of IS NULL
    JOIN text_block b ON b.id=c.start_block_id AND b.document_id=c.document_id
)
INSERT INTO segmentation_boundary_candidate
  (instrument_id,source_observation_id,document_id,start_block_id,source_page,
   detected_title,detected_kind,detected_year,confidence,method,evidence)
SELECT instrument_id,source_observation_id,document_id,start_block_id,page_no,
       title,'act',CASE document_id WHEN 3423 THEN 2014 ELSE 2010 END,
       1.0,'boundary-anchor-review/1',
       jsonb_build_object(
         'rules',jsonb_build_array('printed_title','enactment_formula',
                                   'section_one_self_names_instrument',
                                   'substantive_material_precedes_marker'),
         'supporting_blocks',support,
         'correction','supersedes a detector-v1 reference anchor by adjudication')
  FROM source_rows
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

COMMIT;
