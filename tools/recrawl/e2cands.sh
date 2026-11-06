#!/bin/bash
# e2cands.sh : held E2 documents with no active curation patch, by text-layer legal rate (latest verify_text_quality)
cd /mnt/e/Nizam_e_Qanoon
./nz psql -tA -F '|' <<'SQL'
WITH h AS (SELECT DISTINCT i.document_id d FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL
             AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id))
SELECT d.id, d.page_count,
       (SELECT (v.detail->>'legal_rate')::numeric(5,3) FROM extraction_verification v WHERE v.document_id=d.id AND v.verifier LIKE 'nizam.verify_text_quality/%' ORDER BY v.verified_at DESC LIMIT 1) lr,
       (SELECT count(*) FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=d.id) s7,
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.document_id=d.id) gaps
  FROM document d JOIN h ON h.d=d.id
 WHERE d.is_active AND d.lane='E2'
   AND NOT EXISTS (SELECT 1 FROM segmentation_curation_patch c JOIN instrument i ON i.source_observation_id=c.source_observation_id
                    WHERE i.document_id=d.id AND c.retired_at IS NULL)
 ORDER BY 3 NULLS LAST;
SQL
