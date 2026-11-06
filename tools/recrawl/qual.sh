#!/bin/bash
# qual.sh : held documents failing quality -- outcomes per check, latest verify_ocr detail, s7/gaps
cd /mnt/e/Nizam_e_Qanoon
./nz psql -tA -F '|' <<'SQL'
WITH h AS (SELECT DISTINCT i.document_id d FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL
             AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id))
SELECT q.document_id, q.lane, q.character_outcome, q.ocr_outcome, q.order_outcome, q.text_quality_outcome,
       (SELECT count(*) FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=q.document_id),
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.document_id=q.document_id),
       (SELECT left(v.detail::text, 160) FROM extraction_verification v WHERE v.document_id=q.document_id ORDER BY v.verified_at DESC LIMIT 1)
  FROM v_document_quality_status q JOIN h ON h.d=q.document_id WHERE q.overall_outcome <> 'passed' ORDER BY 7+8, 1;
SQL
