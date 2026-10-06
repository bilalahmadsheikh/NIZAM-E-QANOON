-- The official page 2 prints section 1 with its number in a separate column
-- before subsection (1). The immutable text layer collapses that separation
-- to one space, which the general parser correctly refuses as ambiguous.
-- Change only that space to a line break in derived parser input. The source
-- text, total character count, PDF, and already-released trees stay unchanged.
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM text_block
       WHERE id=69838 AND document_id=1287 AND page_no=2
         AND text LIKE '1 (1) This Act may be called%'
  ) THEN
    RAISE EXCEPTION 'doc 1287 source opener no longer matches reviewed page';
  END IF;
END $$;

INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,
     evidence,review_state,created_by)
VALUES
    (3568,2,'This Act may be called the Sindh Higher Education',
     '1 (1) This Act may be called',
     '1' || chr(10) || '(1) This Act may be called',
     jsonb_build_object(
       'document_id',1287,'source_block_id',69838,
       'defect','source text layer collapses separate printed section-number column to one space',
       'source_sha256','81b9bd2839f8fcc9a9b8cc8dd5d64614224071da5f26b0eef681ec2026aa06a7',
       'render_artifact','.scratch/review-next-opening/1287-page2.png',
       'render_sha256','2b942cdcc6aa06fb57f3e9b59f7a8d1ca42dd4a21d842732cf3d1e82c0eec0f8',
       'source_page_pdf','.artifacts/second-parser/release-all-post-T2-repeal-2026-09-23/input/1287-page2.pdf',
       'source_page_pdf_sha256','da46d970c27702296b894988505d0b28740904cda80d99b62f7635f3c9da949a',
       'reviewer_type','assistant','assistant_page_review',true),
     'source_verified','codex.source-layout-review/1')
ON CONFLICT (source_observation_id,page_no,match_text,before_text) DO NOTHING;

COMMIT;
