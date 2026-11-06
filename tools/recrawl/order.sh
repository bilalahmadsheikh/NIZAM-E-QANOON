#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
./nz psql -At -F ' | ' <<'SQL'
WITH lo AS (SELECT DISTINCT ON (v.document_id) v.* FROM extraction_verification v WHERE v.verifier LIKE 'nizam.verify_order/%' ORDER BY v.document_id, v.verified_at DESC, v.id DESC),
nd AS (SELECT DISTINCT d.id, o.source_metadata->>'listing' listing FROM document d JOIN source_observation o ON o.sha256=d.sha256 WHERE d.is_active AND o.scraper_version='recrawl-2026-10-20/1')
SELECT nd.listing, count(*), round(avg((lo.detail->>'triple_order_ratio')::numeric),3) avg_ratio,
       round(min((lo.detail->>'triple_order_ratio')::numeric),3) min_ratio, string_agg(DISTINCT left(lo.problems::text,60),' || ') FILTER (WHERE true) sample
  FROM lo JOIN nd ON nd.id=lo.document_id WHERE lo.outcome='review' GROUP BY 1 ORDER BY 2 DESC LIMIT 8;
SELECT jsonb_object_keys(lo.detail) FROM (SELECT DISTINCT ON (v.document_id) v.* FROM extraction_verification v WHERE v.verifier LIKE 'nizam.verify_order/%' AND v.outcome='review' ORDER BY v.document_id, v.verified_at DESC LIMIT 1) lo;
SQL
