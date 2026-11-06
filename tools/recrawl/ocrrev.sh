#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
./nz psql -At -F ' | ' <<'SQL'
WITH lo AS (SELECT DISTINCT ON (v.document_id) v.* FROM extraction_verification v WHERE v.verifier LIKE 'nizam.verify_ocr/%' ORDER BY v.document_id, v.verified_at DESC, v.id DESC)
SELECT count(*), sum(d.page_count), round(avg((lo.detail->>'mean_confidence')::numeric),3),
       count(*) FILTER (WHERE (lo.detail->>'mean_confidence')::numeric < 0.7) lt70,
       string_agg(DISTINCT o.source_id, ',')
  FROM lo JOIN document d ON d.id=lo.document_id AND d.is_active JOIN source_observation o ON o.sha256=d.sha256
 WHERE lo.outcome='review' AND o.scraper_version='recrawl-2026-10-20/1';
WITH lo AS (SELECT DISTINCT ON (v.document_id) v.* FROM extraction_verification v WHERE v.verifier LIKE 'nizam.verify_ocr/%' ORDER BY v.document_id, v.verified_at DESC, v.id DESC)
SELECT d.id, d.page_count, lo.detail->>'mean_confidence', lo.problems::text, left(o.source_metadata->>'title',70)
  FROM lo JOIN document d ON d.id=lo.document_id AND d.is_active JOIN source_observation o ON o.sha256=d.sha256
 WHERE lo.outcome='review' AND o.scraper_version='recrawl-2026-10-20/1' ORDER BY (lo.detail->>'mean_confidence')::numeric LIMIT 8;
SQL
