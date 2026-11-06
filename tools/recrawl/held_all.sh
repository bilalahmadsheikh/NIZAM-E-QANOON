#!/bin/bash
# held_all.sh [MIN_DOC MAX_DOC] : every held canonical instrument: doc|quality|s7|gaps|title
cd /mnt/e/Nizam_e_Qanoon
./nz psql -tA -F '|' <<SQL
WITH h AS (
 SELECT i.id, i.document_id d, left(i.short_title,60) t,
  (SELECT q.overall_outcome FROM v_document_quality_status q WHERE q.document_id=i.document_id) qs,
  (SELECT count(*) FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=i.document_id) s7,
  (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id) gaps
 FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL
  AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
  AND i.document_id BETWEEN ${1:-0} AND ${2:-99999})
SELECT d, qs, s7, gaps, t FROM h ORDER BY (qs<>'passed'), s7+gaps, d;
SQL
