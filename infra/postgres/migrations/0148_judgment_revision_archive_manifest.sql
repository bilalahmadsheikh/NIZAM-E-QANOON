-- 0148  The chain of custody for retired judgment reads removed from the serving database (DECISION-LOG D-183, under
--       D-024: archived, a restore of the archive proved, and only then removed; revisions any evidence names are
--       kept). The statute side has had instrument_revision_archive_manifest since 0023; a judgment re-read by a
--       later parser (D-128..D-157) left its earlier judgment, opinions and paragraphs behind, retired.
--
--  * one row per removed judgment revision: which archive batch holds it, its own record, the active judgment read
--    from the same file that succeeds it, and how many derived rows went with it.
--  * the judgment's document (judgment_document) and its page blocks (judgment_block) are extraction evidence and
--    are never removed by this prune (owner, 27 Nov 2026: text blocks of replaced reads are kept).

BEGIN;

CREATE TABLE IF NOT EXISTS judgment_revision_archive_manifest (
  batch_id              uuid   NOT NULL REFERENCES revision_archive_batch(id) ON DELETE RESTRICT,
  archived_judgment_id  uuid   NOT NULL,
  archived_decided_on   date,
  document_id           bigint NOT NULL REFERENCES judgment_document(id) ON DELETE RESTRICT,
  retained_judgment_id  uuid   NOT NULL,         -- the active judgment read from the same file (sha256)
  reason                text   NOT NULL,
  archived_record       jsonb  NOT NULL,         -- the judgment row as it was
  derived_counts        jsonb  NOT NULL,         -- {"opinions", "paragraphs", "lineage"} removed with it
  PRIMARY KEY (batch_id, archived_judgment_id)
);
CREATE INDEX IF NOT EXISTS judgment_revision_archive_document ON judgment_revision_archive_manifest(document_id);

COMMENT ON TABLE judgment_revision_archive_manifest IS
  'Query-visible chain of custody for retired judgment reads removed only after a restore-tested archive (D-183).';

COMMIT;
