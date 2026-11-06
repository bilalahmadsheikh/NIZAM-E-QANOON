#!/bin/bash
# batch_one.sh READLINES PATCHLINES NAME [apply] : readings (sheets-one2 manifest) + compact patches; dry unless apply
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
M=${MAN:-.artifacts/recrawl-queue/sheets-one2/manifest.json}
[ -s "$1" ] && bash tools/recrawl/readings.sh $M $1 $3 $4 | tail -25
if [ -s "$2" ]; then
  DOCS=$(.venv/bin/python tools/recrawl/mkpatch.py $2 $3)
  for d in $DOCS; do echo "== patch $d"; bash tools/recrawl/patch.sh $d ${4:-dry} $3 2>&1 | tail -4; done
fi
