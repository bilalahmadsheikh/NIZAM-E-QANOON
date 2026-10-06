-- The official Islamabad Capital Territory Child Protection Act prints its
-- CONTENTS on pages 1-2 and starts the operative Act on page 3. The parser
-- currently carries the contents region into that body page. An exact source-
-- verified boundary at the page-3 title restores the already-printed section 1.
-- The same body block's subsection (1) is read as (l) by the text layer; the
-- character-preserving correction is the durable carrier for this boundary.
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM text_block
       WHERE id=131636 AND document_id=1887 AND page_no=3
         AND text LIKE 'THE ISLAMABAD CAPITAL TERRITORY CHILD PROTECTION ACT, 2018%'
  ) OR NOT EXISTS (
      SELECT 1 FROM text_block
       WHERE id=131641 AND document_id=1887 AND page_no=3
         AND text LIKE '1. Short title, extent and commencement.%'
         AND text LIKE '%(l) This Act may be called%'
  ) OR NOT EXISTS (
      SELECT 1 FROM text_block
       WHERE id=131600 AND document_id=1887 AND page_no=1
         AND text LIKE 'CONTENTS%'
  ) THEN
    RAISE EXCEPTION 'doc 1887 source boundary no longer matches reviewed pages';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,
     evidence,review_state,created_by)
VALUES
    (888,3,'This Act may be called the Islamabad Capital',
     '(l) This Act may be called',
     '(1) This Act may be called',
     jsonb_build_object(
       'document_id',1887,'source_block_id',131641,
       'defect','contents boundary swallows operative page 3; subsection 1 glyph read as l',
       'structural_overrides',jsonb_build_object('source_body_start_block',131636),
       'source_sha256','fb730b87f5691d147fbf7a0651f28b51b671bd117d14b50992a089e2c14a5891',
       'render_artifact','.scratch/review-probe-opening/1887-page3.png',
       'render_sha256','82f30bb9818ee6c254f4093f538332151b04ad87752887f75eff8b18dcd96168',
       'source_page_pdf','.artifacts/second-parser/release-all-post-T2-repeal-2026-09-23/input/1887-page3.pdf',
       'source_page_pdf_sha256','13bb0fd73782577620c34dfc6cf93dc5deb92472def3740ded58830270b4fb43',
       'rejected_alternative','Never promote page-1 contents entry block 131603 into body law',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.source-layout-review/1')
ON CONFLICT (source_observation_id,page_no,match_text,before_text) DO NOTHING;

COMMIT;
