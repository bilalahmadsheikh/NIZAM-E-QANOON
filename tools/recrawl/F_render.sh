#!/bin/bash
# F_render.sh DOC PAGE [DPI]: like render.sh, falls back to pymupdf when pdftoppm fails
cd /mnt/e/Nizam_e_Qanoon
KEY=$(./nz psql -tAc "SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=$1" | tr -d '[:space:]')
OUT=.artifacts/release-work-2026-09-24/claude/renders/doc$1-p$2.png
pdftoppm -f $2 -l $2 -r ${3:-80} -png -singlefile /mnt/e/nizam-data/$KEY ${OUT%.png} 2>/dev/null
if [ ! -s $OUT ]; then
  .venv/bin/python -c "import pymupdf,sys; d=pymupdf.open(sys.argv[1]); d[int(sys.argv[2])-1].get_pixmap(dpi=int(sys.argv[3])).save(sys.argv[4])" /mnt/e/nizam-data/$KEY $2 ${3:-80} $OUT
fi
echo "$OUT $(sha256sum $OUT | cut -c1-64)"
