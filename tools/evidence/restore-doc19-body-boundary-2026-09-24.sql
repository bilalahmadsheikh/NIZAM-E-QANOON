-- Document 19 official PDF p.1 is CONTENTS; p.2 opens the enacted Act at
-- block 299. The page-2 "Preamble." and "Short title." are marginal labels,
-- not operative words. The original text_block rows remain immutable.
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM source_observation
                  WHERE id=1065 AND sha256=
                    '0038a42da1bf1fbceb5892791d8ea35c0bef6877aac3e38c63e062b08d21311f')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=299 AND document_id=19
                    AND page_no=2 AND text LIKE '1THE PAKISTAN PENAL CODE%')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=304 AND document_id=19
                    AND page_no=2 AND text LIKE E'Preamble.\nWHEREAS%')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=305 AND document_id=19
                    AND page_no=2 AND text LIKE E'Short title.\n1.\nThis Act%')
     OR NOT EXISTS (SELECT 1 FROM text_block WHERE id=309 AND document_id=19
                    AND page_no=2 AND btrim(text,E' \n\r\t')='______')
  THEN RAISE EXCEPTION 'doc 19 source no longer matches reviewed pages';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,
     evidence,review_state,created_by)
VALUES
    (1065,2,E'Preamble.\nWHEREAS it is necessary to amend',
     E'Preamble.\nWHEREAS','WHEREAS',
     jsonb_build_object(
       'document_id',19,'source_block_id',304,
       'defect','printed marginal label joined to enacted preamble',
       'source_sha256','0038a42da1bf1fbceb5892791d8ea35c0bef6877aac3e38c63e062b08d21311f',
       'source_page_image','.artifacts/released-source-audit-2026-09-24/page-doc19-2.png',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.source-layout-review/1'),
    (1065,2,E'Short title.\n1.\nThis Act may be called',
     E'Short title.\n1.','1.',
     jsonb_build_object(
       'document_id',19,'source_block_id',305,
       'defect','page-2 enacted boundary was swallowed by page-1 contents; marginal heading attached to section opener',
       'structural_overrides',jsonb_build_object('source_body_start_block',299),
       'source_sha256','0038a42da1bf1fbceb5892791d8ea35c0bef6877aac3e38c63e062b08d21311f',
       'source_page_image','.artifacts/released-source-audit-2026-09-24/page-doc19-2.png',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.source-layout-review/1')
ON CONFLICT (source_observation_id,page_no,match_text,before_text) DO NOTHING;

COMMIT;
