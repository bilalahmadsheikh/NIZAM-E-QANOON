-- Source-verified, character-count-preserving parser-input corrections.
-- Both current expressions are blocked only by a TOC promise for section 1.
-- The official page 2 of each source visibly prints an operative section 1;
-- the immutable text layer respectively drops its label and reads 1 as l.
-- This does not alter text_block, the PDF, or any already-released document.
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM text_block
       WHERE id=361161 AND document_id=3366 AND page_no=2
         AND text LIKE '%' || ' ' || chr(10) || 'Short title, extent and commencement.' || '%'
         AND text LIKE '%This Act may be cited as the%'
  ) THEN
    RAISE EXCEPTION 'doc 3366 source block no longer matches reviewed page';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM text_block
       WHERE id=643514 AND document_id=4256 AND page_no=2
         AND text LIKE '%' || 'l. ' || chr(10) || 'Short title, extent and commencement.' || '%'
         AND text LIKE '%It is hereby enacted as follows:%'
  ) THEN
    RAISE EXCEPTION 'doc 4256 source block no longer matches reviewed page';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,
     evidence,review_state,created_by)
VALUES
    (2943,2,'This Act may be cited as the',
     ' ' || chr(10) || 'Short title, extent and commencement.',
     '1.Short title, extent and commencement.',
     jsonb_build_object(
       'document_id',3366,'source_block_id',361161,
       'defect','printed section 1 label absent from source text layer',
       'source_sha256','4ce4dbff7e4a0a1d188ad5eea1a7643c5accd5530ab5d89714fbf4c55b9af173',
       'render_artifact','.scratch/review-3366-4256/3366-page2.png',
       'render_sha256','0fdf0ee471425b0ca69b6d91f3c176868c42df60902f13875274b8ebe48ca550',
       'source_page_pdf','.artifacts/second-parser/release-all-post-T2-repeal-2026-09-23/input/3366-page2.pdf',
       'source_page_pdf_sha256','b8e653dadbdc01e86740eeccb8807db2a095d7ccb378d8ba7a6e55086b7059ea',
       'second_parser_reading','1. Short title, extent and commencement',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.second-parser-opening-review/1'),
    (1870,2,'It is hereby enacted as follows:',
     'l. ' || chr(10) || 'Short title, extent and commencement.',
     '1. ' || chr(10) || 'Short title, extent and commencement.',
     jsonb_build_object(
       'document_id',4256,'source_block_id',643514,
       'defect','printed section 1 digit appears as lowercase l in source text layer',
       'source_sha256','5ff04daf60e1c973e752509fd281e6c89de9fabf711401021cd878d55ec8d448',
       'render_artifact','.scratch/review-3366-4256/4256-page2.png',
       'render_sha256','9f0c515e1f68d518926477f9f905c11b436f51a3e51574f408a003cb469dc1fa',
       'source_page_pdf','.artifacts/second-parser/release-all-post-T2-repeal-2026-09-23/input/4256-page2.pdf',
       'source_page_pdf_sha256','3451db00b4b99acd0ba03130fbe655ca3637b2263a15fc8c7848bb188142d1f8',
       'second_parser_reading','1. Short title, extent and commencement',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.second-parser-opening-review/1')
ON CONFLICT (source_observation_id,page_no,match_text,before_text) DO NOTHING;

COMMIT;
