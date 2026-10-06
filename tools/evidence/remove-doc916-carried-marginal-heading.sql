-- Document 916, page 2: remove a carried marginal heading fragment from the
-- next source block's parser input.
--
-- The official page places "Amendment of section 2 of Sindh Act No.XVIII of
-- 2016." in the right margin beside section 2. The immutable text layer
-- prepends that heading to the block which then opens section 3, so its final
-- line "2016." is parsed as a false duplicate clause 2. Remove only this
-- repeated layout fragment from derived parser input; the source block and PDF
-- stay unchanged.

BEGIN;

INSERT INTO segmentation_curation_patch
    (source_observation_id, page_no, match_text, before_text, after_text,
     evidence, review_state, created_by)
SELECT
    3650, 2, 'section 2 of Sindh ',
    E'Amendment \nof \nsection 2 of Sindh \nAct No.XVIII of \n2016. \n ',
    ' ',
    jsonb_build_object(
      'defect', 'section 2 marginal heading carried into the block that opens section 3',
      'document_id', 916,
      'source_block_id', 42669,
      'source_reading',
        'The right-margin Amendment of section 2 heading belongs beside section 2; section 3 begins below it with its own Amendment of Schedule heading.',
      'render_artifact',
        '.artifacts/second-parser/current-pages/review/batch-002/916-page2.png',
      'render_sha256',
        '82b7012c72a1b5d06ffb147aa49e62717da608fe3af766e85ee7ffea7a9ed80a',
      'reviewer_type', 'assistant',
      'assistant_page_review', true),
    'source_verified', 'codex.second-parser-source-review/1'
WHERE NOT EXISTS (
    SELECT 1 FROM segmentation_curation_patch
     WHERE source_observation_id=3650
       AND page_no=2
       AND before_text=E'Amendment \nof \nsection 2 of Sindh \nAct No.XVIII of \n2016. \n '
       AND retired_at IS NULL
);

COMMIT;
