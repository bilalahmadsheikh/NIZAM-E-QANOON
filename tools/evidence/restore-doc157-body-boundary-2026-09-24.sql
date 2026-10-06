-- Source-reviewed against the official two-page PDF (SHA below). Page 1 is
-- CONTENTS; page 2 begins the enacted Act at block 5524. The text replacement
-- is intentionally identity-preserving: this record carries only the reviewed
-- body boundary, and extracted source text is never altered.
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM source_observation
     WHERE id=652 AND sha256='5a75b74a52b63abb619db9e5211c58e76b08faded04e9fe8940e3d01a1f297bd'
  ) OR NOT EXISTS (
    SELECT 1 FROM text_block
     WHERE id=5524 AND document_id=157 AND page_no=2
       AND text LIKE 'THE PRESIDENT TO HOLD ANOTHER OFFICE ACT, 2004%'
  ) OR NOT EXISTS (
    SELECT 1 FROM text_block
     WHERE id=5527 AND document_id=157 AND page_no=2
       AND text LIKE '%WHEREAS paragraph (d) of clause (1) of Article 63%'
  ) OR NOT EXISTS (
    SELECT 1 FROM text_block
     WHERE id=5529 AND document_id=157 AND page_no=2
       AND btrim(text,E' \n\r\t')='____________'
  ) THEN
    RAISE EXCEPTION 'doc 157 reviewed source identity no longer matches';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,
     evidence,review_state,created_by)
VALUES
    (652,2,'THE PRESIDENT TO HOLD ANOTHER OFFICE ACT, 2004',
     'THE PRESIDENT TO HOLD ANOTHER OFFICE ACT, 2004',
     'THE PRESIDENT TO HOLD ANOTHER OFFICE ACT, 2004',
     jsonb_build_object(
       'document_id',157,'source_block_id',5524,
       'defect','page-2 enacted title and preamble classified as page-1 contents',
       'identity_text_patch',true,
       'structural_overrides',jsonb_build_object('source_body_start_block',5524),
       'source_sha256','5a75b74a52b63abb619db9e5211c58e76b08faded04e9fe8940e3d01a1f297bd',
       'source_page_image','.artifacts/released-source-audit-2026-09-24/page-doc157-2.png',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.source-layout-review/1')
ON CONFLICT (source_observation_id,page_no,match_text,before_text) DO NOTHING;

COMMIT;
