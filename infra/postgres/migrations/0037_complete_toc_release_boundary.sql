-- A printed contents list is source evidence that named provisions exist.
-- An instrument with promised-but-unresolved entries must not become
-- application-visible merely because its repeated-label candidates reached
-- zero. Keep the full active tree for review; narrow only the release view.

BEGIN;

DROP VIEW v_release_provision_version;
DROP VIEW v_release_provision;
DROP VIEW v_release_instrument;

CREATE VIEW v_release_instrument AS
SELECT i.*
  FROM instrument i
  JOIN v_document_quality_status q ON q.document_id=i.document_id
  JOIN segmentation_run r ON r.instrument_id=i.id
 WHERE i.is_active
   AND i.duplicate_of IS NULL
   AND q.overall_outcome='passed'
   AND r.outcome='segmented'
   AND (NOT r.toc_found OR coalesce(r.toc_missing,0)=0)
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

COMMENT ON VIEW v_release_instrument IS
  'Fail-closed quality, exact-identity, S7 and printed-contents-completeness boundary.';

COMMIT;
