-- Three mixed-mode pages contain only a cover title.  Their high-confidence
-- OCR yield is necessarily below the ordinary body-page minimum.  Preserve the
-- exception as page- and blob-specific source evidence; never as a global
-- threshold waiver.

BEGIN;

INSERT INTO extraction_assertion
       (sha256,page_no,kind,evidence,detail,asserted_by)
SELECT v.sha256,v.page_no,'source_content_confirmed',v.evidence,
       jsonb_build_object('method','direct-render-review',
                          'render_dpi',140,
                          'purpose','ocr-sparse-page',
                          'visible_text',v.visible_text),
       'codex-direct-visual-review'
  FROM (VALUES
    ('c419b70d1c3b4c8150eda76ad06b05a11d9a86dcbf397be2694a3d4addbd5fd6'::char(64),
     9,
     'Rendered page 9 is a sparse Pakistan Code end cover; its only visible text is THE PAKISTAN CODE, exactly matching the three-word OCR candidate.',
     'THE PAKISTAN CODE'),
    ('360de0007cd3a94a153bbdc2dd2bcdc75c17e8373bbd3823c976fdef3cdf188f'::char(64),
     15,
     'Rendered page 15 is a sparse Pakistan Code end cover; its only visible text is THE PAKISTAN CODE, exactly matching the three-word OCR candidate.',
     'THE PAKISTAN CODE'),
    ('5a299db51da08d8400b626c992eff5c07eaeffbe583d3d2471e029eebb27f32d'::char(64),
     1,
     'Rendered page 1 is a sparse cover whose visible title and year are completely represented by the selected ten-word OCR candidate.',
     'RULES OF PROCEDURE OF THE PROVINCIAL ASSEMBLY OF SINDH 2013')
  ) AS v(sha256,page_no,evidence,visible_text)
 WHERE NOT EXISTS (
       SELECT 1 FROM extraction_assertion a
        WHERE a.sha256=v.sha256 AND a.page_no=v.page_no
          AND a.kind='source_content_confirmed' AND a.is_active
          AND a.detail->>'purpose'='ocr-sparse-page'
 );

COMMIT;
