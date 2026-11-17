-- 18 Nov 2026, DECISION-LOG D-071. Restore the boundary candidates (and their adjudication chains) that ACTIVE
-- expression manifests cite but that the retired-revision prune deleted with the instrument they were keyed to.
--
-- Found: post-replay step 2 refused 19 reviewed multi-expression documents ("need a recorded confirmed_split
-- boundary candidate at their first span start"). 315 candidate ids are cited by active manifests; 228 were gone
-- from segmentation_boundary_candidate: 226 deleted by the 11 Nov prune (batch f97cfaf2), 2 by the 9 Sep prune.
-- The prune had copied every one, with its adjudications, into instrument_revision_archive_manifest.archived_record
-- ->'boundary_candidates' before deleting it, and the 11 Nov archive dump holds the same rows (sha256 37c93bd6...).
--
-- Each row comes back as it was archived -- same id, same evidence, same adjudications with their ids, rationale and
-- decided_at -- except instrument_id, which named the pruned revision and is NULL (migration 0106). Nothing is
-- re-decided here; the rows are the original decisions. Only candidates an active manifest cites are restored.
-- Idempotent: a candidate or adjudication already present is skipped.
\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE lost ON COMMIT DROP AS
WITH cited AS (
  SELECT DISTINCT (m.evidence->>'candidate_id')::uuid AS id
    FROM instrument_expression_manifest m
   WHERE m.is_active AND m.evidence->>'candidate_id' IS NOT NULL),
archived AS (
  SELECT DISTINCT ON ((e->>'id')::uuid) (e->>'id')::uuid AS id, e AS row, b.id AS batch_id, b.selected_at
    FROM instrument_revision_archive_manifest m
    JOIN revision_archive_batch b ON b.id = m.batch_id
   CROSS JOIN LATERAL jsonb_array_elements(m.archived_record->'boundary_candidates') e
   ORDER BY (e->>'id')::uuid, b.selected_at DESC)
SELECT a.* FROM cited c JOIN archived a ON a.id = c.id
 WHERE NOT EXISTS (SELECT 1 FROM segmentation_boundary_candidate x WHERE x.id = c.id);

INSERT INTO segmentation_boundary_candidate
SELECT (r).id, NULL::uuid, (r).source_observation_id, (r).document_id, (r).start_block_id, (r).source_page,
       (r).detected_title, (r).detected_kind, (r).detected_year, (r).detected_number, (r).confidence, (r).method,
       (r).evidence, (r).created_at
  FROM (SELECT jsonb_populate_record(NULL::segmentation_boundary_candidate, l.row - 'adjudications') AS r FROM lost l) s;

INSERT INTO segmentation_boundary_adjudication
SELECT (a).*
  FROM (SELECT jsonb_populate_record(NULL::segmentation_boundary_adjudication, j) AS a
          FROM lost l CROSS JOIN LATERAL jsonb_array_elements(l.row->'adjudications') j) s
 WHERE NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication x WHERE x.id = (a).id)
 ORDER BY (a).decided_at, (a).id;

-- Report, then prove: every candidate an active manifest cites is held again.
SELECT (SELECT count(*) FROM lost) AS restored_candidates,
       (SELECT count(*) FROM lost l, jsonb_array_elements(l.row->'adjudications')) AS restored_adjudications,
       (SELECT count(DISTINCT (l.row->>'document_id')) FROM lost l) AS documents;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM instrument_expression_manifest m
              WHERE m.is_active AND m.evidence->>'candidate_id' IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM segmentation_boundary_candidate c
                                 WHERE c.id = (m.evidence->>'candidate_id')::uuid)) THEN
    RAISE EXCEPTION 'an active expression manifest still cites a missing boundary candidate';
  END IF;
END $$;
COMMIT;
