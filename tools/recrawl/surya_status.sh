#!/bin/bash
# surya_status.sh : per q1r output doc -- pages in the PDF, pages with Surya output, candidates imported (read-only)
cd /mnt/e/Nizam_e_Qanoon; Q=/mnt/e/nizam-data/ocr
for d in $(ls $Q/q1r-output | grep -E '^[0-9]+$'); do
  n=$(find $Q/q1r-output/$d -name '*.json' 2>/dev/null | wc -l)
  imp=$(./nz psql -tA -c "SELECT count(DISTINCT page_no) FROM page_ocr_candidate WHERE document_id=$d AND engine LIKE 'surya%'" 2>/dev/null)
  pages=$(./nz psql -tA -c "SELECT count(*) FROM page WHERE document_id=$d" 2>/dev/null)
  rel=$(./nz psql -tA -c "SELECT count(*) FROM v_release_instrument r JOIN instrument i ON i.id=r.id WHERE i.document_id=$d" 2>/dev/null)
  echo "$d pages=$pages json=$n imported=$imp released=$rel"
done
