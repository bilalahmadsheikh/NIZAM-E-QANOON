-- Document 1800, page 2: recover the printed section 1 opener.
--
-- The official rendering visibly prints "1. Short title, extent and
-- commencement." The immutable PDF text layer emits lowercase "l." instead,
-- so the parser never opens section 1 and the printed contents row remains
-- unlinked. Surya independently read the glyph as digit 1. This patch changes
-- only the derived parser input; text_block and the source PDF stay immutable.

BEGIN;

-- Retire the first review record if it used the visually correct but
-- whitespace-inexact locator. The row remains audit-visible and never applied.
UPDATE segmentation_curation_patch
   SET retired_at=now()
 WHERE source_observation_id=1824
   AND page_no=2
   AND before_text=E'l.\nShort title'
   AND created_by='codex.second-parser-source-review/1'
   AND retired_at IS NULL;

INSERT INTO segmentation_curation_patch
    (source_observation_id, page_no, match_text, before_text, after_text,
     evidence, review_state, created_by)
SELECT
    1824, 2, 'This Act may be called the Khyber',
    E'l.  \nShort title', E'1.  \nShort title',
    jsonb_build_object(
      'defect', 'digit 1 present as lowercase L in the source text layer',
      'document_id', 1800,
      'source_block_id', 119315,
      'second_parser', 'surya-2',
      'second_parser_reading',
        '1. Short title, extent and commencement.---(1) This Act may be called ...',
      'render_artifact',
        '.artifacts/second-parser/current-pages/review/batch-002/1800-page2.png',
      'render_sha256',
        'eb2f3152028432d8c333c08cd8669b36a39bdf5fbcf369b1f7e815a30d918391',
      'reviewer_type', 'assistant',
      'assistant_page_review', true),
    'source_verified', 'codex.second-parser-source-review/1'
WHERE NOT EXISTS (
    SELECT 1 FROM segmentation_curation_patch
     WHERE source_observation_id=1824
       AND page_no=2
       AND match_text='This Act may be called the Khyber'
       AND before_text=E'l.  \nShort title'
       AND retired_at IS NULL
);

COMMIT;
