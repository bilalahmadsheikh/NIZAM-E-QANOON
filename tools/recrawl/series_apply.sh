#!/bin/bash
# series_apply.sh DOC FIRST_BODY_PAGE CONTENTS_PAGE "first,last,body"|- [dry|apply] [BARE] : rule reviewed_series_regulation for one
# SBP document -- openers (series_openers.py), optional reviewed contents region on its contents page, patch file,
# renders, then patch.sh (dry by default)
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$1; FIRST=$2; CP=$3; C=$4; MODE=${5:-dry}; BARE=${6:-}
F=.artifacts/recrawl-queue/patches/patch-$D-sr.json
.venv/bin/python tools/recrawl/series_openers.py $D $FIRST $BARE 2>/dev/null | .venv/bin/python -c "import json,sys;print(json.dumps({'source_printed_rule_openers':json.load(sys.stdin)}))" > .artifacts/recrawl-queue/series-$D.over.json
.venv/bin/python tools/recrawl/series_patch.py $D -sr
if [ "$C" != "-" ]; then
  IFS=, read f l b <<< "$C"
  .venv/bin/python tools/recrawl/series_extra.py $F $D $CP source_contents_region "{\"first_block_id\": $f, \"last_block_id\": $l, \"body_start_block_id\": $b, \"rows\": \"none\"}" \
    "the contents list was read on into the body, so the regulation headings were filed as contents" \
    "Page $CP prints the contents list (Definitions, Regulations with page numbers, Annexures); the body opens after it"
fi
bash .artifacts/recrawl-queue/rendall.sh $D >/dev/null
bash tools/recrawl/patch.sh $D $MODE -sr 2>&1 | tail -3
