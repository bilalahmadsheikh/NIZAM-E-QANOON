#!/bin/bash
# render.sh DOC PAGE [DPI] -> .artifacts/release-work-2026-09-24/claude/renders/docDOC-pPAGE.png ; prints path + sha256
cd /mnt/e/Nizam_e_Qanoon
KEY=$(./nz psql -tAc "SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=$1" | tr -d '[:space:]')
OUT=.artifacts/release-work-2026-09-24/claude/renders/doc$1-p$2.png
pdftoppm -f $2 -l $2 -r ${3:-80} -png -singlefile /mnt/e/nizam-data/$KEY ${OUT%.png}
echo "$OUT $(sha256sum $OUT | cut -c1-64)"
