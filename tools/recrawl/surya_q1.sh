#!/bin/bash
# Owner q1 'review-pack' (21 Oct 2026): Surya OCR of the low-confidence scans, smallest first, then review packs.
set -uo pipefail
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
IN=/mnt/e/nizam-data/ocr/q1r-input; OUT=/mnt/e/nizam-data/ocr/q1r-output; mkdir -p $IN $OUT
./nz psql -tA -F ' ' -c "WITH lo AS (SELECT DISTINCT ON (v.document_id) v.* FROM extraction_verification v WHERE v.verifier LIKE 'nizam.verify_ocr/%' ORDER BY v.document_id, v.verified_at DESC, v.id DESC)
  SELECT d.id, b.object_key FROM lo JOIN document d ON d.id=lo.document_id AND d.is_active JOIN blob b ON b.sha256=d.sha256
   WHERE lo.outcome='review' AND EXISTS (SELECT 1 FROM source_observation o WHERE o.sha256=d.sha256 AND o.scraper_version='recrawl-2026-10-20/1')
   ORDER BY d.page_count" > $OUT/targets.txt
echo "targets: $(wc -l < $OUT/targets.txt)"
while read -r id key; do [ -f $IN/$id.pdf ] || cp "/mnt/e/nizam-data/$key" $IN/$id.pdf; done < $OUT/targets.txt
SURYA_LOG=$OUT/run.log bash tools/run_surya_ocr.sh $IN $OUT
