#!/bin/bash
# held.sh : blocked canonical instruments by blocking reason
cd /mnt/e/Nizam_e_Qanoon && ./nz psql -tA -F ' | ' <<'SQL'
WITH h AS (
 SELECT i.id, i.document_id d,
  (SELECT q.overall_outcome FROM v_document_quality_status q WHERE q.document_id=i.document_id) qs,
  (SELECT count(*) FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=i.document_id) s7,
  (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id) gaps
 FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL
  AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id))
SELECT 'held', count(*), count(*) FILTER (WHERE qs<>'passed'), count(*) FILTER (WHERE s7>0), count(*) FILTER (WHERE gaps>0),
       count(*) FILTER (WHERE qs='passed' AND s7=0 AND gaps=0), sum(s7), sum(gaps) FROM h;
SELECT 'released', count(*) FROM v_release_instrument;
SQL
