-- The official three-page copy prints section 3 as repealed. Record the
-- exact current contents anchor; the overlay is a separate bounded step.
BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM instrument i
    JOIN instrument_toc_entry e ON e.instrument_id=i.id
    WHERE i.source_observation_id=109 AND i.expression_ordinal=0
      AND i.is_active AND i.duplicate_of IS NULL
      AND e.id=1078458 AND e.ordinal=2
      AND e.printed_label='3'
      AND e.printed_heading='Prohibition of importation'
      AND e.source_block_id=126151 AND e.source_page=1
  ) OR EXISTS (
    SELECT 1 FROM v_toc_disposition_assertion_latest a
    WHERE a.source_observation_id=109 AND a.expression_ordinal=0
      AND a.reviewed_toc_entry_id=1078458
  ) THEN
    RAISE EXCEPTION 'doc 1846 live anchor changed or already reviewed';
  END IF;
END $$;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES (
 109,0,2,1078458,'3','Prohibition of importation','repealed',
 126151,1,
 '.artifacts/release-batches/T2/repealed/doc1846-e1078458-label3-p2.png',
 'ce7b2bc3f3d5bc546add23342b0b9d9ce9dd68062ac1cd2c9cc76b8d98db3f23',
 'Repealing Act, 1938 (I of 1938), s. 2 and Schedule',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'review_batch','T2-repeal-2026-09-23',
  'contents_render','.artifacts/release-batches/T2/repealed/doc1846-e1078458-label3-p1.png',
  'contents_sha256','25de7c2582deeb55582320db240fd6287b0ba132ad739a21b223c599991b4921',
  'body_render','.artifacts/release-batches/T2/repealed/doc1846-e1078458-label3-p2.png',
  'body_sha256','ce7b2bc3f3d5bc546add23342b0b9d9ce9dd68062ac1cd2c9cc76b8d98db3f23',
  'finding','Contents page 1 promises section 3. Body page 2 prints section 3 with a bracketed heading and explicitly says Rep. by the Repealing Act, 1938, s. 2 and Schedule; no operative section-3 text remains.'),
 'codex.source_review.T2-repeal/1');
COMMIT;
