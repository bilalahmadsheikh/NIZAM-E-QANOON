#!/bin/bash
# succ.sh DOC ... : the active successor of each OCR-promoted doc, its instrument(s), release, quality, S7, gaps (read-only)
cd /mnt/e/Nizam_e_Qanoon; L=$(echo "$@" | tr ' ' ',')
./nz psql -tA -F '|' <<SQL
SELECT d.supersedes_document_id old, d.id new, i.id inst, left(i.short_title,45),
 EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id) rel,
 (SELECT q.overall_outcome FROM v_document_quality_status q WHERE q.document_id=d.id) qs,
 (SELECT count(*) FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=d.id) s7,
 (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id) gaps,
 (SELECT count(*) FROM extraction_verification v WHERE v.document_id=d.id) ver
FROM document d LEFT JOIN instrument i ON i.document_id=d.id AND i.is_active
WHERE d.is_active AND d.supersedes_document_id IN ($L) ORDER BY 1;
SQL
