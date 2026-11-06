#!/bin/bash
# pdry.sh DOC SUFFIX... : dry-run the recorder on patch-DOC{SUFFIX}.json and show only the refusals
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$1; shift
for s in "$@"; do
  echo "== $D$s"
  .venv/bin/python tools/record_curation_patch.py --readings .artifacts/recrawl-queue/patches/patch-$D$s.json 2>&1 \
    | awk '/^  (will record|refused)/{print; next} /^    doc /{line=$0; getline nxt; if (nxt !~ /block now reads/) print substr(line,1,220) " :: " substr(nxt,1,160)}'
done
