#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
./nz psql -At -F ' | ' <<'SQL'
WITH blocked AS (
  SELECT DISTINCT i.document_id FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL
     AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)),
nd AS (SELECT DISTINCT d.id, d.lane, d.sha256, lower(coalesce(d.pdf_metadata->>'creator','')||' '||coalesce(d.pdf_metadata->>'producer','')) cp
         FROM document d JOIN source_observation o ON o.sha256=d.sha256
        WHERE d.is_active AND o.scraper_version='recrawl-2026-10-20/1')
SELECT CASE WHEN nd.lane='E4' THEN 'E4 (tesseract already)'
            WHEN cp ~ 'ocr|abbyy|paper capture|camscanner|scan|tesseract|omnipage|finereader|naps2|clearscan' THEN 'E2 with OCR text layer'
            ELSE 'E2 born-digital?' END cls,
       count(*) total, count(*) FILTER (WHERE nd.id IN (SELECT document_id FROM blocked)) blocked
  FROM nd GROUP BY 1 ORDER BY 1;
SELECT cp, count(*) FROM (SELECT DISTINCT d.id, lower(coalesce(d.pdf_metadata->>'creator','')||' | '||coalesce(d.pdf_metadata->>'producer','')) cp
  FROM document d JOIN source_observation o ON o.sha256=d.sha256 WHERE d.is_active AND o.scraper_version='recrawl-2026-10-20/1') x GROUP BY 1 ORDER BY 2 DESC LIMIT 12;
SQL
