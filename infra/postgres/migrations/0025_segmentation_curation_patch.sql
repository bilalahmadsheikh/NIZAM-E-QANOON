-- Auditable, rebuild-stable corrections to the parser input.
-- Extracted text remains immutable. A patch is located by source observation,
-- physical page and a unique text fragment so it survives new extraction/block
-- ids; application fails closed when that locator is no longer unique.

BEGIN;

CREATE TABLE segmentation_curation_patch (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_observation_id bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    operation             text NOT NULL DEFAULT 'replace_once'
                              CHECK (operation = 'replace_once'),
    page_no               integer NOT NULL CHECK (page_no > 0),
    match_text            text NOT NULL CHECK (length(match_text) >= 12),
    before_text           text NOT NULL CHECK (length(before_text) > 0),
    after_text            text NOT NULL CHECK (length(after_text) > 0),
    evidence              jsonb NOT NULL,
    review_state          text NOT NULL CHECK (review_state IN
                              ('proposed','source_verified','human_verified','rejected')),
    created_by            text NOT NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),
    retired_at            timestamptz,
    CHECK (jsonb_typeof(evidence) = 'object'),
    UNIQUE (source_observation_id, page_no, match_text, before_text)
);

CREATE INDEX segmentation_patch_active_observation
    ON segmentation_curation_patch(source_observation_id, page_no)
    WHERE retired_at IS NULL AND review_state IN ('source_verified','human_verified');

COMMENT ON TABLE segmentation_curation_patch IS
    'Append-only corrections applied to a derived parser input, never to '
    'text_block. Every correction has an official-PDF page locator and evidence.';
COMMENT ON COLUMN segmentation_curation_patch.review_state IS
    'source_verified means directly checked against the official PDF page; it '
    'does not imply human publication approval.';

COMMIT;
