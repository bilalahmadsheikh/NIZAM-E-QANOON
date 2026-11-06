#!/bin/bash
# reocr2_list.sh OUT : held E2 documents (no released instrument) with pending S7/TOC, year < 1975, no curation patch
cd /mnt/e/Nizam_e_Qanoon
./nz psql -tA -F ' ' -c "
SELECT DISTINCT d.sha256, d.id, i.year, d.page_count,
       (SELECT count(*) FROM v_structural_adjudication_pending s WHERE s.instrument_id=i.id) +
       (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id)
  FROM document d JOIN instrument i ON i.document_id=d.id AND i.is_active AND i.duplicate_of IS NULL
 WHERE d.is_active AND d.lane='E2' AND coalesce(i.year,0) < 1975
   AND NOT EXISTS (SELECT 1 FROM instrument x JOIN v_release_instrument r ON r.id=x.id WHERE x.document_id=d.id)
   AND (EXISTS (SELECT 1 FROM v_structural_adjudication_pending s WHERE s.instrument_id=i.id)
        OR EXISTS (SELECT 1 FROM v_toc_gap_pending g WHERE g.instrument_id=i.id))
   AND NOT EXISTS (SELECT 1 FROM segmentation_curation_patch c WHERE c.retired_at IS NULL
                    AND c.source_observation_id IN (SELECT source_observation_id FROM instrument WHERE document_id=d.id))
   AND NOT EXISTS (SELECT 1 FROM tools_dummy_never)" 2>/dev/null > $1 || \
./nz psql -tA -F ' ' -c "
SELECT DISTINCT d.sha256, d.id, i.year, d.page_count
  FROM document d JOIN instrument i ON i.document_id=d.id AND i.is_active AND i.duplicate_of IS NULL
 WHERE d.is_active AND d.lane='E2' AND coalesce(i.year,0) < 1975
   AND NOT EXISTS (SELECT 1 FROM instrument x JOIN v_release_instrument r ON r.id=x.id WHERE x.document_id=d.id)
   AND (EXISTS (SELECT 1 FROM v_structural_adjudication_pending s WHERE s.instrument_id=i.id)
        OR EXISTS (SELECT 1 FROM v_toc_gap_pending g WHERE g.instrument_id=i.id))
   AND NOT EXISTS (SELECT 1 FROM segmentation_curation_patch c WHERE c.retired_at IS NULL
                    AND c.source_observation_id IN (SELECT source_observation_id FROM instrument WHERE document_id=d.id))" > $1
wc -l < $1; awk '{p+=$4} END {print p, "pages"}' $1
