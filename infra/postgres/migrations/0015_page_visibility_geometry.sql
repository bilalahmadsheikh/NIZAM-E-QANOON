-- Preserve both the PDF media box (all source content) and crop box (the
-- publisher's visible window). Full-media extraction prevents clipped legal
-- text from disappearing, while `inside_cropbox` keeps visibility explicit.
ALTER TABLE page
    ADD COLUMN crop_box numeric(9,3)[],
    ADD COLUMN media_box numeric(9,3)[];

ALTER TABLE text_block
    ADD COLUMN inside_cropbox boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN text_block.inside_cropbox IS
    'true only when the complete block bbox lies inside the PDF crop box';
