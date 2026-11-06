#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
./nz psql -At -F ' | ' <<'SQL'
SELECT i.document_id, i.year, d.lane, d.page_count, q.overall_outcome,
       (SELECT count(*) FROM v_structural_adjudication_pending s WHERE s.instrument_id=i.id) s7,
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id) toc,
       lower(coalesce(d.pdf_metadata->>'creator','')||'/'||coalesce(d.pdf_metadata->>'producer','')) cp,
       left(i.short_title, 60)
  FROM instrument i JOIN document d ON d.id=i.document_id AND d.is_active JOIN v_document_quality_status q ON q.document_id=d.id
 WHERE i.is_active AND i.duplicate_of IS NULL AND i.year >= 2020 AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
 ORDER BY 6, 7, 2 DESC;
SQL
