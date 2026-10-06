-- Document 2033, page 2: keep the schedule's column-number legend out of
-- the citable row sequence.
--
-- The official rendering prints 1–10 as column identifiers directly beneath
-- the schedule headings. They are not schedule items. The source text layer
-- places all ten identifiers in one block immediately before row 1, causing
-- the segmenter to open a false clause 10 and suffix the real item 10.
-- This patch removes only that derived legend; source text/PDF remain intact.

BEGIN;

-- Retire the first record if it used the visually correct but
-- whitespace-inexact locator. The source text layer has a trailing space on
-- each table-cell line; that row matched zero blocks and never applied.
UPDATE segmentation_curation_patch
   SET retired_at=now()
 WHERE source_observation_id=2740
   AND page_no=2
   AND before_text=E'1.\n2.\n3.\n4.\n5.\n6.\n7.\n8.\n9.\n10.'
   AND created_by='codex.second-parser-source-review/1'
   AND retired_at IS NULL;

INSERT INTO segmentation_curation_patch
    (source_observation_id, page_no, match_text, before_text, after_text,
     evidence, review_state, created_by)
SELECT
    2740, 2, 'Initial Recruitment ',
    E'1. \n2. \n3. \n4. \n5. \n6. \n7. \n8. \n9. \n10.',
    'Column identifiers.',
    jsonb_build_object(
      'defect', 'schedule column identifiers 1-10 parsed as a citable clause 10',
      'document_id', 2033,
      'source_block_id', 150332,
      'source_reading',
        'The row numbered 1-10 is the schedule column legend; the first legal post row begins below it with 1. Manager MIS.',
      'render_artifact',
        '.artifacts/second-parser/current-pages/review/batch-002/2033-page2.png',
      'render_sha256',
        '02264fba9f33bc0d1312584a2d59319c9673ec9570ab7ca1ec72096f7c5f07d4',
      'reviewer_type', 'assistant',
      'assistant_page_review', true),
    'source_verified', 'codex.second-parser-source-review/1'
WHERE NOT EXISTS (
    SELECT 1 FROM segmentation_curation_patch
     WHERE source_observation_id=2740
       AND page_no=2
       AND before_text=E'1. \n2. \n3. \n4. \n5. \n6. \n7. \n8. \n9. \n10.'
       AND retired_at IS NULL
);

COMMIT;
