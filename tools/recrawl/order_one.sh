#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
read DOC KEY <<< $(./nz psql -tA -F ' ' -c "WITH lo AS (SELECT DISTINCT ON (v.document_id) v.* FROM extraction_verification v WHERE v.verifier LIKE 'nizam.verify_order/%' ORDER BY v.document_id, v.verified_at DESC, v.id DESC)
 SELECT d.id, b.object_key FROM lo JOIN document d ON d.id=lo.document_id JOIN blob b ON b.sha256=d.sha256 JOIN source_observation o ON o.sha256=d.sha256
 WHERE lo.outcome='review' AND o.source_metadata->>'listing'='drs:Act' AND d.page_count BETWEEN 2 AND 6 ORDER BY d.id LIMIT 1")
echo "doc $DOC $KEY"; F=/mnt/e/nizam-data/$KEY
pdfinfo $F | grep -E "Producer|Creator|Pages"
echo "--- pdftotext p1"; pdftotext -f 1 -l 1 $F - | head -25
echo "--- stored p1 blocks"; ./nz psql -tAc "SELECT left(regexp_replace(text,'\s+',' ','g'),140) FROM text_block WHERE document_id=$DOC AND page_no=1 ORDER BY reading_order LIMIT 14"
mkdir -p /tmp/ord; pdftoppm -f 1 -l 1 -r 70 -png $F /tmp/ord/p; cp /tmp/ord/p-1.png /mnt/e/nizam-data/recrawl-2026-10-20/order-sample-$DOC.png 2>/dev/null || cp /tmp/ord/p-01.png /mnt/e/nizam-data/recrawl-2026-10-20/order-sample-$DOC.png; ls /mnt/e/nizam-data/recrawl-2026-10-20/order-sample-*
