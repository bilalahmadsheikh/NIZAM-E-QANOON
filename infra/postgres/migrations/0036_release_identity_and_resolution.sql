-- Make the legal release boundary exact about two different questions:
--   1. a corrective S7 decision is not complete until a corrected tree exists;
--   2. byte-identical source observations may preserve distinct provenance but
--      must not publish an identical legal expression twice.

BEGIN;

CREATE TABLE instrument_identity_resolution (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    duplicate_instrument_id  uuid NOT NULL REFERENCES instrument(id) ON DELETE RESTRICT,
    canonical_instrument_id  uuid NOT NULL REFERENCES instrument(id) ON DELETE RESTRICT,
    source_sha256            char(64) NOT NULL REFERENCES blob(sha256) ON DELETE RESTRICT,
    tree_sha256              char(64) NOT NULL,
    method                   text NOT NULL,
    evidence                 jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    resolved_by              text NOT NULL,
    resolved_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (duplicate_instrument_id),
    CHECK (duplicate_instrument_id<>canonical_instrument_id),
    CHECK (tree_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE INDEX instrument_identity_canonical
    ON instrument_identity_resolution(canonical_instrument_id);

COMMENT ON TABLE instrument_identity_resolution IS
  'Append-only proof that two instrument revisions have identical relative structure and text; source observations remain distinct.';

DROP VIEW v_release_provision_version;
DROP VIEW v_release_provision;
DROP VIEW v_release_instrument;
DROP VIEW v_structural_adjudication_pending;
DROP VIEW v_active_structural_candidate;

CREATE VIEW v_active_structural_candidate AS
SELECT c.*
  FROM segmentation_structural_candidate c
  JOIN instrument i ON i.id=c.instrument_id
                   AND i.is_active
                   AND i.duplicate_of IS NULL;

-- Only accepting the parser's non-citable classification resolves the current
-- candidate as written. Restore/reparent/split/reject are instructions to build
-- a corrected revision, so they remain blocking until that replay supersedes
-- the candidate with a tree in which it no longer exists.
CREATE VIEW v_structural_adjudication_pending AS
SELECT c.*
  FROM v_active_structural_candidate c
  LEFT JOIN v_structural_adjudication_latest a ON a.candidate_id=c.id
 WHERE a.id IS NULL OR a.resolution<>'accept_non_citable';

CREATE VIEW v_release_instrument AS
SELECT i.*
  FROM instrument i
  JOIN v_document_quality_status q ON q.document_id=i.document_id
 WHERE i.is_active
   AND i.duplicate_of IS NULL
   AND q.overall_outcome='passed'
   AND NOT EXISTS (
       SELECT 1 FROM v_structural_adjudication_pending p
        WHERE p.instrument_id=i.id);

CREATE VIEW v_release_provision AS
SELECT p.*
  FROM provision p
  JOIN v_release_instrument i ON i.id=p.instrument_id
 WHERE p.is_active;

CREATE VIEW v_release_provision_version AS
SELECT v.*
  FROM provision_version v
  JOIN v_release_provision p ON p.id=v.provision_id;

COMMENT ON VIEW v_structural_adjudication_pending IS
  'Current non-duplicate tree candidates not yet accepted as non-citable; corrective decisions block until applied by replay.';
COMMENT ON VIEW v_release_instrument IS
  'Fail-closed quality and structure boundary, with exact-tree duplicates represented once.';

COMMIT;
