#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
./nz psql <<'SQL'
\pset pager off
CREATE TEMP TABLE q AS
SELECT i.id, i.document_id, i.source_observation_id obs, o.source_id, d.lane,
       qs.overall_outcome quality, qs.character_outcome ch, qs.ocr_outcome ocr, qs.order_outcome ord, qs.text_quality_outcome txt,
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id) toc,
       (SELECT count(*) FROM v_structural_adjudication_pending s WHERE s.instrument_id=i.id) s7,
       (SELECT count(*) FROM v_boundary_adjudication_pending x WHERE x.document_id=i.document_id) bnd,
       (SELECT count(*) FROM provision p WHERE p.instrument_id=i.id AND p.is_active) provs
  FROM instrument i JOIN document d ON d.id=i.document_id AND d.is_active JOIN source_observation o ON o.id=i.source_observation_id
  JOIN v_document_quality_status qs ON qs.document_id=d.id
 WHERE i.is_active AND i.duplicate_of IS NULL AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id);
SELECT count(*) total, count(*) FILTER (WHERE quality<>'passed') quality_blocked, count(*) FILTER (WHERE quality='passed' AND (s7>0 OR toc>0 OR bnd>0)) structure_only,
       count(*) FILTER (WHERE quality='passed' AND s7=0 AND toc=0 AND bnd=0) other FROM q;
SELECT quality, ch, ocr, ord, txt, count(*) FROM q WHERE quality<>'passed' GROUP BY 1,2,3,4,5 ORDER BY 6 DESC LIMIT 12;
SELECT CASE WHEN s7>0 AND toc>0 THEN 's7+toc' WHEN s7>0 THEN 's7' WHEN toc>0 THEN 'toc' WHEN bnd>0 THEN 'boundary' ELSE 'none' END kind, count(*), sum(s7), sum(toc), percentile_cont(0.5) WITHIN GROUP (ORDER BY s7+toc) med_units
  FROM q WHERE quality='passed' GROUP BY 1 ORDER BY 2 DESC;
SELECT source_id, count(*), count(*) FILTER (WHERE quality<>'passed') qual FROM q GROUP BY 1;
SELECT CASE WHEN s7+toc=0 THEN '0' WHEN s7+toc=1 THEN '1' WHEN s7+toc<=3 THEN '2-3' WHEN s7+toc<=10 THEN '4-10' ELSE '>10' END bucket, count(*) FROM q WHERE quality='passed' GROUP BY 1 ORDER BY 1;
SQL
