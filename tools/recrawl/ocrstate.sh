#!/bin/bash
# ocrstate.sh DOC ... : per doc -- Surya pages, adjudicated accepted pages, successor doc (promoted) and its release (read-only)
cd /mnt/e/Nizam_e_Qanoon
for d in "$@"; do ./nz psql -tA -F '|' <<SQL
SELECT $d, (SELECT count(DISTINCT page_no) FROM page_ocr_candidate WHERE document_id=$d AND engine LIKE 'surya%'),
 (SELECT count(DISTINCT c.page_no) FROM page_ocr_candidate c JOIN page_ocr_adjudication a ON a.candidate_id=c.id WHERE c.document_id=$d AND a.decision='accepted'),
 (SELECT is_active FROM document WHERE id=$d),
 (SELECT string_agg(i.document_id::text||':'||(EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id))::text, ',') FROM instrument i WHERE i.is_active AND i.document_id=$d);
SQL
done
