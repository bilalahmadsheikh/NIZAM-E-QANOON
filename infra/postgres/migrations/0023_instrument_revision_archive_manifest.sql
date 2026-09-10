-- Chain of custody for pruning superseded *segmentation* revisions without
-- touching retired extraction/document evidence.
BEGIN;

CREATE TABLE instrument_revision_archive_manifest (
    batch_id                uuid NOT NULL REFERENCES revision_archive_batch(id) ON DELETE RESTRICT,
    archived_instrument_id  uuid NOT NULL,
    retained_instrument_id  uuid NOT NULL,
    source_observation_id   bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    reason                  text NOT NULL,
    archived_record         jsonb NOT NULL,
    archived_run            jsonb,
    retained_run            jsonb,
    derived_counts          jsonb NOT NULL,
    PRIMARY KEY (batch_id, archived_instrument_id)
);
CREATE INDEX instrument_revision_archive_observation
    ON instrument_revision_archive_manifest(source_observation_id);

COMMENT ON TABLE instrument_revision_archive_manifest IS
  'Query-visible chain of custody for superseded derived legal trees removed only after a restore-tested archive.';

COMMIT;
