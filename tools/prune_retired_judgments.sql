-- Remove only retired judgment READS (D-183, under D-024): a judgment row a later parser superseded, with its
-- opinions, paragraphs and machine-candidate lineage rows. The judgment's document, page blocks, source rows and
-- every reviewed or evidence row stay. Run after a revision_archive_batch row of scope 'retired judgment reads only'
-- names a restore-tested archive (tools/test_prune_retired.sh, tools/prune_retired_live.sh).
\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE r_judgment ON COMMIT DROP AS
SELECT j.id, j.decided_on, j.document_id, d.sha256
  FROM judgment j JOIN judgment_document d ON d.id = j.document_id
 WHERE NOT j.is_active;

-- A retired judgment that evidence names is kept whole; so is one with no active successor read from its file
-- (withdrawn, not superseded: its file is now held, a reprint or awaiting OCR).
CREATE TEMP TABLE keep_judgment ON COMMIT DROP AS
SELECT r.id FROM r_judgment r
 WHERE EXISTS (SELECT 1 FROM case_treatment x WHERE r.id IN (x.judgment_id, x.dst_judgment_id))
    OR EXISTS (SELECT 1 FROM judicial_invalidation_candidate x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_recorded_outcome x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_relation x WHERE r.id IN (x.judgment_id, x.other_judgment_id))
    OR EXISTS (SELECT 1 FROM judgment_lineage_link x WHERE r.id IN (x.upper_judgment_id, x.lower_judgment_id))
    OR EXISTS (SELECT 1 FROM judgment_lineage x WHERE x.lower_judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_lineage x WHERE x.upper_judgment_id = r.id
                                                 AND x.review_status <> 'machine_candidate')
    OR EXISTS (SELECT 1 FROM judgment_case_reference x WHERE r.id IN (x.judgment_id, x.dst_judgment_id))
    OR EXISTS (SELECT 1 FROM judgment_statute_reference x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM reporter_citation x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_case x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_case_state x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_chunk x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_display x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_sensitivity x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_subject x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_link_state x WHERE x.judgment_id = r.id)
    OR EXISTS (SELECT 1 FROM judgment_paragraph p
                WHERE p.judgment_id = r.id
                  AND (EXISTS (SELECT 1 FROM authority_rule a WHERE a.source_paragraph_id = p.id)
                    OR EXISTS (SELECT 1 FROM judicial_invalidation_candidate a WHERE a.paragraph_id = p.id)
                    OR EXISTS (SELECT 1 FROM case_treatment a WHERE a.paragraph_id = p.id)))
    OR NOT EXISTS (SELECT 1 FROM judgment a JOIN judgment_document d ON d.id = a.document_id
                    WHERE a.is_active AND d.is_active AND d.sha256 = r.sha256);

CREATE TEMP TABLE prune_judgment ON COMMIT DROP AS
SELECT r.*, (SELECT a.id FROM judgment a JOIN judgment_document d ON d.id = a.document_id
              WHERE a.is_active AND d.is_active AND d.sha256 = r.sha256
              ORDER BY a.created_at DESC, a.id LIMIT 1) AS retained_id
  FROM r_judgment r
 WHERE NOT EXISTS (SELECT 1 FROM keep_judgment k WHERE k.id = r.id);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM prune_judgment WHERE retained_id IS NULL) THEN
    RAISE EXCEPTION 'retired judgment selected without an active successor';
  END IF;
  IF EXISTS (SELECT 1 FROM prune_judgment p JOIN judgment j ON j.id = p.id WHERE j.is_active) THEN
    RAISE EXCEPTION 'an active judgment was selected';
  END IF;
  IF (SELECT count(*) FROM revision_archive_batch
       WHERE pruned_at IS NULL AND detail->>'scope' = 'retired judgment reads only') <> 1 THEN
    RAISE EXCEPTION 'expected exactly one open archive batch of scope retired judgment reads only';
  END IF;
END $$;

WITH batch AS (
  SELECT id FROM revision_archive_batch
   WHERE pruned_at IS NULL AND detail->>'scope' = 'retired judgment reads only'
), op AS (
  SELECT o.judgment_id, count(*) n FROM judgment_opinion o JOIN prune_judgment p ON p.id = o.judgment_id GROUP BY 1
), pa AS (
  SELECT x.judgment_id, count(*) n FROM judgment_paragraph x JOIN prune_judgment p ON p.id = x.judgment_id GROUP BY 1
), li AS (
  SELECT x.upper_judgment_id judgment_id, count(*) n FROM judgment_lineage x
    JOIN prune_judgment p ON p.id = x.upper_judgment_id GROUP BY 1
)
INSERT INTO judgment_revision_archive_manifest
  (batch_id, archived_judgment_id, archived_decided_on, document_id, retained_judgment_id, reason, archived_record,
   derived_counts)
SELECT b.id, p.id, p.decided_on, p.document_id, p.retained_id, 'superseded by a later read of the same file',
       to_jsonb(j), jsonb_build_object('opinions', coalesce(op.n, 0), 'paragraphs', coalesce(pa.n, 0),
                                       'lineage', coalesce(li.n, 0))
  FROM prune_judgment p CROSS JOIN batch b
  JOIN judgment j ON j.id = p.id
  LEFT JOIN op ON op.judgment_id = p.id
  LEFT JOIN pa ON pa.judgment_id = p.id
  LEFT JOIN li ON li.judgment_id = p.id;

DO $$
BEGIN
  IF (SELECT count(*) FROM judgment_revision_archive_manifest m
        JOIN revision_archive_batch b ON b.id = m.batch_id
       WHERE b.pruned_at IS NULL AND b.detail->>'scope' = 'retired judgment reads only')
     <> (SELECT count(*) FROM prune_judgment) THEN
    RAISE EXCEPTION 'archive manifest count does not equal prune selection';
  END IF;
END $$;

DELETE FROM judgment_lineage x USING prune_judgment p
 WHERE x.upper_judgment_id = p.id AND x.review_status = 'machine_candidate';
DELETE FROM judgment_paragraph x USING prune_judgment p
 WHERE x.judgment_id = p.id AND x.decided_on IS NOT DISTINCT FROM p.decided_on;
DELETE FROM judgment_paragraph x USING prune_judgment p WHERE x.judgment_id = p.id;   -- any left by a re-dated read
DELETE FROM judgment_opinion x USING prune_judgment p WHERE x.judgment_id = p.id;
DELETE FROM judgment j USING prune_judgment p WHERE j.id = p.id;

UPDATE revision_archive_batch
   SET pruned_at = now(),
       detail = detail || jsonb_build_object('judgments_archived', (SELECT count(*) FROM prune_judgment),
                                             'judgments_kept', (SELECT count(*) FROM keep_judgment))
 WHERE pruned_at IS NULL AND detail->>'scope' = 'retired judgment reads only';

SELECT (SELECT count(*) FROM prune_judgment) archived, (SELECT count(*) FROM keep_judgment) kept;
COMMIT;
