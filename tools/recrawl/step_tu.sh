#!/bin/bash
# step_tu.sh : retire the ineffective o2a no_cut/table_row patches, then record + replay the text-unit patches (o2d)
cd /mnt/e/Nizam_e_Qanoon
for d in 7373 5871 5775 9276 6090 9284 7650 7820; do
  echo "retire $d: $(bash tools/recrawl/retire_file.sh .artifacts/recrawl-queue/patches/patch-${d}o2a.json 'the block-level no_cut / table_row patch had no effect on a unit opening at the block start; replaced by a reviewed_text_unit patch' | tr '\n' ' ')"
done
bash tools/recrawl/batch_one.sh /dev/null .artifacts/recrawl-queue/lines/p-one2d.txt o2d ${1:-dry} 2>&1 | grep -E "== patch|^released|recorded|\|[tf]\||rror|refused|not reached|block now"
