-- Source-reviewed parser-input correction for still-blocked document 2155.
-- The official page 3 prints the operative first section's number in a
-- separate left column, followed by subsection (1) and then section 2.
-- Its text layer drops that number. Reuse only the two leading whitespace
-- characters in the derived parser input; leave the immutable source alone.
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM text_block
       WHERE id=163351 AND document_id=2155 AND page_no=3
         AND text LIKE ' ' || chr(10) || 'Short title, extent   and ' || chr(10) || 'commencement.%'
  ) THEN
    RAISE EXCEPTION 'doc 2155 source opener no longer matches reviewed page';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,
     evidence,review_state,created_by)
VALUES
    (1555,3,'Short title, extent   and ' || chr(10) || 'commencement.',
     ' ' || chr(10) || 'Short title, extent   and ' || chr(10) || 'commencement. ' || chr(10),
     '1.Short title, extent   and ' || chr(10) || 'commencement. ' || chr(10),
     jsonb_build_object(
       'document_id',2155,'source_block_id',163351,
       'defect','operative section 1 number printed in a separate column but absent from source text layer',
       'source_sha256','3c56779ec2755c111ebb81e05826bc339b7900a68d07e09c7733cd79fe919fe9',
       'render_artifact','.scratch/review-probe-opening/2155-page3.png',
       'render_sha256','2da929354a8705570fc8d94bcf98f8ba411a1d911b9b2d748be498c7c513e30c',
       'source_page_pdf','.artifacts/second-parser/release-all-post-T2-repeal-2026-09-23/input/2155-page3.pdf',
       'source_page_pdf_sha256','21847783b3544d6fd10a06096a4c72b6c8a897111c403af74fd0c02376504097',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.source-layout-review/1')
ON CONFLICT (source_observation_id,page_no,match_text,before_text) DO NOTHING;

COMMIT;
