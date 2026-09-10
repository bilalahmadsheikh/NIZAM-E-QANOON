-- Keep a durable, queryable chain of custody when superseded derived revisions
-- move out of the hot serving database into a restore-tested archive dump.
BEGIN;

CREATE TABLE revision_archive_batch (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    archive_file         text NOT NULL,
    archive_sha256       char(64) NOT NULL CHECK (archive_sha256 ~ '^[0-9a-f]{64}$'),
    database_size_before bigint NOT NULL,
    selected_at          timestamptz NOT NULL DEFAULT now(),
    pruned_at            timestamptz,
    detail               jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE document_revision_archive_manifest (
    batch_id             uuid NOT NULL REFERENCES revision_archive_batch(id) ON DELETE RESTRICT,
    archived_document_id bigint NOT NULL,
    retained_document_id bigint NOT NULL,
    sha256               char(64) NOT NULL REFERENCES blob(sha256) ON DELETE RESTRICT,
    decision             text NOT NULL,
    reason               text NOT NULL,
    archived_record      jsonb NOT NULL,
    archived_verification jsonb,
    retained_verification jsonb,
    PRIMARY KEY (batch_id, archived_document_id)
);
CREATE INDEX document_revision_archive_sha
    ON document_revision_archive_manifest(sha256);

-- OCR candidates are evidence and survive document-revision pruning.  When a
-- candidate is re-homed to the retained revision, this non-FK value preserves
-- the exact document id under which it was originally produced; the archive
-- manifest and dump retain that original row.
ALTER TABLE page_ocr_candidate
    ADD COLUMN origin_document_id bigint;

COMMENT ON TABLE revision_archive_batch IS
    'Restore-tested archive dumps used before pruning superseded derived revisions.';
COMMENT ON TABLE document_revision_archive_manifest IS
    'Chain of custody from each pruned document revision to the retained revision and its source-verification decision.';
COMMENT ON COLUMN page_ocr_candidate.origin_document_id IS
    'Original document revision id when this candidate was re-homed during archival; intentionally not a FK because that hot row was archived.';

COMMIT;
