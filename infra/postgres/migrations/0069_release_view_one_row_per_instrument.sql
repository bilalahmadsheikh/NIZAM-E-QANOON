-- v_release_instrument returns one row per released instrument.
--
-- Migration 0043 joined `segmentation_run` on `outcome='segmented'`. Any
-- instrument with two segmented runs therefore appeared twice, and every view
-- built on it (v_release_provision, v_release_provision_version) doubled that
-- instrument's whole tree. The held-expression release of doc 9361 e0 recorded
-- the same run twice (runs 63652 and 63716, identical counts, 10 and 11 Nov
-- 2026): 770 provisions were served as 1,540 rows. A citation resolves by
-- provision id, so a duplicate is not a wrong answer, but a retrieval layer
-- that indexes the release views would have indexed that instrument twice, and
-- every count taken from them was off by one instrument and 770 provisions.
--
-- Run rows are evidence and stay: append-only, nothing is deleted. The gate
-- asks whether a segmented run EXISTS, which is what the join always meant.
-- Exact gate equivalence is kept -- at the time of writing no active
-- instrument whose latest run is not 'segmented' has an earlier segmented one,
-- so "some segmented run" and "latest run segmented" release the same set.
--
-- Column list is unchanged (i.*), so CREATE OR REPLACE is enough and
-- v_release_provision / v_release_provision_version are not touched.

BEGIN;

CREATE OR REPLACE VIEW v_release_instrument AS
SELECT i.*
  FROM instrument i
  JOIN v_document_quality_status q ON q.document_id=i.document_id
 WHERE i.is_active
   AND i.duplicate_of IS NULL
   AND q.overall_outcome='passed'
   AND EXISTS (
       SELECT 1 FROM segmentation_run r
        WHERE r.instrument_id=i.id AND r.outcome='segmented')
   AND NOT EXISTS (
       SELECT 1 FROM v_toc_gap_pending t WHERE t.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_structural_adjudication_pending s
        WHERE s.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_boundary_adjudication_pending b
        WHERE b.instrument_id=i.id);

COMMENT ON VIEW v_release_instrument IS
  'One row per released instrument: active, not a duplicate, quality passed, at least one segmented run, no pending TOC/structural/boundary decision.';

-- The guard: a duplicate here fails the migration rather than shipping.
DO $$
DECLARE
    rows_ bigint;
    distinct_ bigint;
BEGIN
    SELECT count(*), count(DISTINCT id) INTO rows_, distinct_ FROM v_release_instrument;
    IF rows_ <> distinct_ THEN
        RAISE EXCEPTION 'v_release_instrument still repeats instruments: % rows, % distinct',
                        rows_, distinct_;
    END IF;
END $$;

COMMIT;
