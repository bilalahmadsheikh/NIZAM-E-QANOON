-- Remove only superseded derived segmentation graphs. Source observations,
-- blobs, documents, pages, text blocks, OCR candidates, assertions and all
-- extraction revisions remain untouched.
\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE prune_instrument ON COMMIT DROP AS
SELECT old.id archived_id,cur.id retained_id,old.source_observation_id
  FROM instrument old
  JOIN instrument cur ON cur.source_observation_id=old.source_observation_id
                     AND cur.is_active
                     -- One observation can materialize many expressions.  A
                     -- retired expression is succeeded only by the active
                     -- expression at the same ordinal; joining on observation
                     -- alone multiplies each archive row and can associate an
                     -- old Act with an unrelated embedded Rules expression.
                     AND cur.expression_ordinal=old.expression_ordinal
 WHERE NOT old.is_active
   -- Identity resolutions are append-only proof over two exact tree revisions.
   -- Retain either endpoint rather than rewriting or weakening that proof.
   AND NOT EXISTS (
       SELECT 1 FROM instrument_identity_resolution x
        WHERE x.duplicate_instrument_id=old.id OR x.canonical_instrument_id=old.id);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM instrument old
     WHERE NOT old.is_active
       AND NOT EXISTS (SELECT 1 FROM prune_instrument p WHERE p.archived_id=old.id)
       AND NOT EXISTS (
           SELECT 1 FROM instrument_identity_resolution x
            WHERE x.duplicate_instrument_id=old.id OR x.canonical_instrument_id=old.id)
  ) THEN
    RAISE EXCEPTION 'retired instrument without exactly selected active successor';
  END IF;
END $$;

WITH batch AS (
  SELECT id FROM revision_archive_batch
   WHERE pruned_at IS NULL AND detail->>'scope'='retired segmentation revisions only'
   ORDER BY selected_at DESC LIMIT 1
), structural_adjudications AS (
  SELECT a.candidate_id,jsonb_agg(to_jsonb(a) ORDER BY a.decided_at,a.id) rows
    FROM segmentation_structural_adjudication a
    JOIN segmentation_structural_candidate c ON c.id=a.candidate_id
    JOIN prune_instrument p ON p.archived_id=c.instrument_id
   GROUP BY a.candidate_id
), structural_evidence AS (
  SELECT c.instrument_id,
         jsonb_agg(to_jsonb(c) || jsonb_build_object(
           'adjudications',coalesce(a.rows,'[]'::jsonb)) ORDER BY c.source_page,c.id) rows
    FROM segmentation_structural_candidate c
    JOIN prune_instrument p ON p.archived_id=c.instrument_id
    LEFT JOIN structural_adjudications a ON a.candidate_id=c.id
   GROUP BY c.instrument_id
), boundary_adjudications AS (
  SELECT a.candidate_id,jsonb_agg(to_jsonb(a) ORDER BY a.decided_at,a.id) rows
    FROM segmentation_boundary_adjudication a
    JOIN segmentation_boundary_candidate c ON c.id=a.candidate_id
    JOIN prune_instrument p ON p.archived_id=c.instrument_id
   GROUP BY a.candidate_id
), boundary_evidence AS (
  SELECT c.instrument_id,
         jsonb_agg(to_jsonb(c) || jsonb_build_object(
           'adjudications',coalesce(a.rows,'[]'::jsonb)) ORDER BY c.source_page,c.id) rows
    FROM segmentation_boundary_candidate c
    JOIN prune_instrument p ON p.archived_id=c.instrument_id
    LEFT JOIN boundary_adjudications a ON a.candidate_id=c.id
   GROUP BY c.instrument_id
), provision_counts AS (
  SELECT x.instrument_id,count(*) n FROM provision x
    JOIN prune_instrument p ON p.archived_id=x.instrument_id GROUP BY x.instrument_id
), version_counts AS (
  SELECT x.instrument_id,count(*) n FROM provision_version v
    JOIN provision x ON x.id=v.provision_id
    JOIN prune_instrument p ON p.archived_id=x.instrument_id GROUP BY x.instrument_id
), block_counts AS (
  SELECT x.instrument_id,count(*) n FROM provision_block pb
    JOIN provision x ON x.id=pb.provision_id
    JOIN prune_instrument p ON p.archived_id=x.instrument_id GROUP BY x.instrument_id
), toc_counts AS (
  SELECT e.instrument_id,count(*) n FROM instrument_toc_entry e
    JOIN prune_instrument p ON p.archived_id=e.instrument_id GROUP BY e.instrument_id
), latest_run AS (
  SELECT DISTINCT ON (r.instrument_id) r.instrument_id,to_jsonb(r) row
    FROM segmentation_run r
   WHERE r.instrument_id IN (
         SELECT archived_id FROM prune_instrument
         UNION SELECT retained_id FROM prune_instrument)
   ORDER BY r.instrument_id,r.run_at DESC,r.id DESC
)
INSERT INTO instrument_revision_archive_manifest
  (batch_id,archived_instrument_id,retained_instrument_id,source_observation_id,
   reason,archived_record,archived_run,retained_run,derived_counts)
SELECT batch.id,p.archived_id,p.retained_id,p.source_observation_id,
       'superseded segmenter output; source extraction retained unchanged',
       to_jsonb(old) || jsonb_build_object(
         'structural_candidates',coalesce(se.rows,'[]'::jsonb),
         'boundary_candidates',coalesce(be.rows,'[]'::jsonb)),
       archived_run.row,retained_run.row,
       jsonb_build_object(
         'provisions',coalesce(pc.n,0),'versions',coalesce(vc.n,0),
         'block_links',coalesce(bc.n,0),'toc_entries',coalesce(tc.n,0))
  FROM prune_instrument p
  JOIN instrument old ON old.id=p.archived_id
  CROSS JOIN batch
  LEFT JOIN structural_evidence se ON se.instrument_id=p.archived_id
  LEFT JOIN boundary_evidence be ON be.instrument_id=p.archived_id
  LEFT JOIN provision_counts pc ON pc.instrument_id=p.archived_id
  LEFT JOIN version_counts vc ON vc.instrument_id=p.archived_id
  LEFT JOIN block_counts bc ON bc.instrument_id=p.archived_id
  LEFT JOIN toc_counts tc ON tc.instrument_id=p.archived_id
  LEFT JOIN latest_run archived_run ON archived_run.instrument_id=p.archived_id
  LEFT JOIN latest_run retained_run ON retained_run.instrument_id=p.retained_id;

DO $$
BEGIN
  IF (SELECT count(*) FROM instrument_revision_archive_manifest m
       WHERE m.batch_id=(SELECT id FROM revision_archive_batch
                          WHERE pruned_at IS NULL
                            AND detail->>'scope'='retired segmentation revisions only'
                          ORDER BY selected_at DESC LIMIT 1))
     <> (SELECT count(*) FROM prune_instrument) THEN
    RAISE EXCEPTION 'archive manifest count does not equal prune selection';
  END IF;
END $$;

UPDATE instrument i SET supersedes_instrument_id=NULL
 WHERE EXISTS (SELECT 1 FROM prune_instrument p
                WHERE p.archived_id=i.supersedes_instrument_id);
UPDATE block_assignment_set s SET supersedes_set_id=NULL
 WHERE EXISTS (SELECT 1 FROM block_assignment_set old
                JOIN prune_instrument p ON p.archived_id=old.instrument_id
               WHERE old.id=s.supersedes_set_id);

-- Boundary manifests are permanent source evidence.  Retired manifests may
-- point at the retired materialization they describe, while their active
-- successor points back to that manifest.  Keep both manifests and sever only
-- the optional link to the derived tree after the tree has been archived.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM instrument_expression_manifest m
    JOIN prune_instrument p ON p.archived_id=m.materialized_instrument_id
    WHERE m.is_active
  ) THEN
    RAISE EXCEPTION 'active expression manifest points at retired prune target';
  END IF;
END $$;
UPDATE instrument_expression_manifest m SET materialized_instrument_id=NULL
 WHERE NOT m.is_active
   AND EXISTS (SELECT 1 FROM prune_instrument p
                WHERE p.archived_id=m.materialized_instrument_id);

DELETE FROM provision_block pb USING block_assignment_set s,prune_instrument p
 WHERE pb.assignment_set_id=s.id AND s.instrument_id=p.archived_id;
DELETE FROM block_assignment_set s USING prune_instrument p
 WHERE s.instrument_id=p.archived_id;
DELETE FROM instrument_source s USING prune_instrument p
 WHERE s.instrument_id=p.archived_id;
DELETE FROM instrument_status_assertion s USING prune_instrument p
 WHERE s.instrument_id=p.archived_id;
DELETE FROM segmentation_boundary_adjudication a
 USING segmentation_boundary_candidate c,prune_instrument p
 WHERE a.candidate_id=c.id AND c.instrument_id=p.archived_id;
DELETE FROM segmentation_boundary_candidate c USING prune_instrument p
 WHERE c.instrument_id=p.archived_id;
DELETE FROM segmentation_structural_adjudication a
 USING segmentation_structural_candidate c,prune_instrument p
 WHERE a.candidate_id=c.id AND c.instrument_id=p.archived_id;
DELETE FROM segmentation_structural_candidate c USING prune_instrument p
 WHERE c.instrument_id=p.archived_id;
DELETE FROM instrument_toc_entry e USING prune_instrument p
 WHERE e.instrument_id=p.archived_id;
DELETE FROM provision_version v USING provision x,prune_instrument p
 WHERE v.provision_id=x.id AND x.instrument_id=p.archived_id;
DELETE FROM provision_block pb USING provision x,prune_instrument p
 WHERE pb.provision_id=x.id AND x.instrument_id=p.archived_id;
UPDATE provision x SET parent_id=NULL,first_block=NULL
 WHERE EXISTS (SELECT 1 FROM prune_instrument p WHERE p.archived_id=x.instrument_id);
DELETE FROM provision x USING prune_instrument p
 WHERE x.instrument_id=p.archived_id;
UPDATE segmentation_run r SET instrument_id=NULL
 WHERE EXISTS (SELECT 1 FROM prune_instrument p WHERE p.archived_id=r.instrument_id);
DELETE FROM instrument i USING prune_instrument p WHERE i.id=p.archived_id;

UPDATE revision_archive_batch b
   SET pruned_at=now(),
       detail=detail || jsonb_build_object(
         'instrument_revisions_archived',(SELECT count(*) FROM prune_instrument),
         'active_documents_retained',(SELECT count(*) FROM document WHERE is_active),
         'retired_documents_retained',(SELECT count(*) FROM document WHERE NOT is_active),
         'active_instruments_retained',(SELECT count(*) FROM instrument WHERE is_active))
 WHERE b.id=(SELECT id FROM revision_archive_batch
              WHERE pruned_at IS NULL
                AND detail->>'scope'='retired segmentation revisions only'
              ORDER BY selected_at DESC LIMIT 1);

COMMIT;

SELECT (SELECT count(*) FROM instrument WHERE NOT is_active) retired_instruments,
       (SELECT count(*) FROM document WHERE NOT is_active) retired_documents,
       (SELECT count(*) FROM instrument_revision_archive_manifest) archived_instruments;
