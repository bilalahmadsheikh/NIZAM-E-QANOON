-- Official page 14 prints items (i) and (ii) indented beneath the Section 10
-- proviso, not as direct children of Section 10. This review is anchored to
-- source observation 1077 and immutable blocks 28225-28227. The identity
-- parser-input patch carries only the exact parent corrections; source text
-- remains unchanged. The separate exact-digest classifier keeps the printed
-- footer continuation at block 28230 out of operative item (ii).
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM source_observation
                  WHERE id=1077 AND sha256=
                    'bded145ccc938edd811eaac5a043daa17aebd5b329859c9bec25d06fbf4e0580')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=28225
                    AND document_id=671 AND page_no=14
                    AND text LIKE '5[Provided that%')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=28226
                    AND document_id=671 AND page_no=14
                    AND text LIKE '(i)%Only one vehicle%')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=28227
                    AND document_id=671 AND page_no=14
                    AND text LIKE '(ii)%The Chairman%')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=28230
                    AND document_id=671 AND page_no=14
                    AND encode(digest(btrim(regexp_replace(
                        text,'[[:space:]]+',' ','g')),'sha256'),'hex')=
                        '9e3842cbc40e950ca2c982e388468456226d04e1e34b5a369e7806131bea832f')
  THEN RAISE EXCEPTION 'doc 671 source no longer matches reviewed page';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,
     evidence,review_state,created_by)
VALUES
    (1077,14,'5[Provided that','5[Provided that','5[Provided that',
     jsonb_build_object(
       'document_id',671,'source_block_id',28225,
       'identity_text_patch',true,
       'defect','two operative romanette items attach to section instead of printed proviso',
       'structural_overrides',jsonb_build_object(
         'source_reparent_blocks',jsonb_build_array(
           jsonb_build_object('source_block_id',28226,'parent_block_id',28225,'kind','clause'),
           jsonb_build_object('source_block_id',28227,'parent_block_id',28225,'kind','clause'))),
       'source_sha256','bded145ccc938edd811eaac5a043daa17aebd5b329859c9bec25d06fbf4e0580',
       'source_page_image','.artifacts/structural-parser-fix-2026-09-23/source-pages/doc671-14.png',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.source-layout-review/1')
ON CONFLICT (source_observation_id,page_no,match_text,before_text) DO NOTHING;

COMMIT;
