-- Lead, 20 Oct 2026 (S8; owner: "fix these errors without decreasing release count"). The same-blob TWIN observations
-- of plan documents 3392 (2233, 2507; canonical 2224) and 1970 (2846; canonical 2415) hold the canonical's readings
-- (the recorder writes every reading onto each observation of one file) but were never rebuilt, so their patches stand
-- unapplied (audit S8). A twin is rebuilt from its canonical's plan (tools/materialize_multi_instrument.py,
-- twin_observation_problem), and the plan route needs each observation's own confirmed_split boundaries. These are the
-- canonical observation's reviewed decisions copied onto the twin: the same file (one sha256, one document, the same
-- block ids), the same start blocks, titles and evidence, citing the canonical candidate and its owner decision.
-- Idempotent: a twin that already holds a candidate at a block gets nothing new there.
\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE twin(twin_obs bigint, canonical_obs bigint, document_id bigint) ON COMMIT DROP;
INSERT INTO twin VALUES (2233, 2224, 3392), (2507, 2224, 3392), (2846, 2415, 1970);

DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT t.*, (SELECT count(*) FROM instrument i WHERE i.source_observation_id=t.twin_obs AND i.is_active
                                                         AND i.duplicate_of IS NULL) AS canon_n,
                         (SELECT count(*) FROM source_observation a, source_observation b
                           WHERE a.id=t.twin_obs AND b.id=t.canonical_obs AND a.sha256=b.sha256) AS same_blob
               FROM twin t LOOP
        IF r.canon_n <> 0 OR r.same_blob <> 1 THEN
            RAISE EXCEPTION 'observation % is not a recorded-duplicate same-blob twin of %', r.twin_obs, r.canonical_obs;
        END IF;
    END LOOP;
END $$;

INSERT INTO segmentation_boundary_candidate (
    instrument_id, source_observation_id, document_id, start_block_id, source_page,
    detected_title, detected_kind, detected_year, detected_number, confidence, method, evidence)
SELECT ti.id, t.twin_obs, t.document_id, c.start_block_id, c.source_page,
       c.detected_title, c.detected_kind, c.detected_year, c.detected_number, c.confidence, c.method,
       c.evidence || jsonb_build_object('twin_of_candidate_id', c.id::text,
                                        'twin_of_observation_id', t.canonical_obs,
                                        'twin_basis', 'same file: one sha256 and one document; the canonical '
                                                      'observation''s reviewed boundary copied onto its twin (S8)')
  FROM twin t
  JOIN segmentation_boundary_candidate c ON c.source_observation_id = t.canonical_obs
  JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id AND a.resolution = 'confirmed_split'
  JOIN LATERAL (SELECT i.id FROM instrument i WHERE i.source_observation_id = t.twin_obs AND i.is_active
                 ORDER BY i.expression_ordinal LIMIT 1) ti ON true
 WHERE NOT EXISTS (SELECT 1 FROM segmentation_boundary_candidate x
                    WHERE x.source_observation_id = t.twin_obs AND x.start_block_id = c.start_block_id);

INSERT INTO segmentation_boundary_adjudication (candidate_id, resolution, review_basis, method, rationale, evidence,
                                                decided_by)
SELECT n.id, a.resolution, a.review_basis, a.method,
       a.rationale || ' [Twin of observation ' || (n.evidence->>'twin_of_observation_id') || '''s reviewed boundary: '
                   || 'the same file and block.]',
       a.evidence || jsonb_build_object('twin_of_candidate_id', n.evidence->>'twin_of_candidate_id'),
       'claude.twin-boundary-copy/1'
  FROM segmentation_boundary_candidate n
  JOIN v_boundary_adjudication_latest a ON a.candidate_id::text = n.evidence->>'twin_of_candidate_id'
 WHERE n.source_observation_id IN (SELECT twin_obs FROM twin)
   AND NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication x WHERE x.candidate_id = n.id);

COMMIT;

SELECT c.source_observation_id, c.start_block_id, a.resolution
  FROM segmentation_boundary_candidate c LEFT JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id
 WHERE c.source_observation_id IN (2233, 2507, 2846) ORDER BY 1, 2;
