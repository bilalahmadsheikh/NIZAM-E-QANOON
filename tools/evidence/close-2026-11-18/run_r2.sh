#!/usr/bin/env bash
# Round 2 (Sindh): fresh locators, then the same readings dry-run under the current profile, v4 and v5, each proven.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
C=.artifacts/close-2026-11-18; W=$C/sindh-r2; P=$W/patches
SD=1245,2022,2206,2339,2505,2765,2902,3243,3919,3992
rm -rf $W; mkdir -p $W; date -u +%Y-%m-%dT%H:%M:%SZ > $W/started_at
.venv/bin/python tools/recrawl/sindh_title_patch.py $P $SD
: > $W/record.log
for f in $P/patch-*t.json; do
  .venv/bin/python tools/record_curation_patch.py --readings $f --apply 2>&1 \
    | grep -E 'recorded|refused  *: [1-9]|^    doc .*:' | sed "s#^#$(basename $f) #" >> $W/record.log
done
echo "recorded: $(grep -c 'recorded [1-9]' $W/record.log) files; refusals: $(grep -c 'refused' $W/record.log)"
grep -E 'refused|    doc' $W/record.log | head -8
DOCS=$(ls $P | sed -nE 's/patch-([0-9]+)t.json/\1/p' | paste -sd, -)
for PR in current unreleased-v4 unreleased-v5; do
  mkdir -p $W/$PR/dump
  FLAG=""; [ $PR != current ] && FLAG="--profile $PR"
  .venv/bin/python -m nizam.workers.segment --documents $DOCS --redo --include-review --dry-run --quiet $FLAG \
    --release-diff $W/$PR/diff.jsonl --release-tree-dump $W/$PR/dump 2>&1 | grep -E 'ERROR|analysed' | cut -c1-200 > $W/$PR/dry.log
  echo "== $PR: $(tail -1 $W/$PR/dry.log)"
  .venv/bin/python tools/recrawl/sindh_title_proof.py $W/$PR/dump $P $W/$PR/proof.json t | head -1
  .venv/bin/python -c "import json; print('   pass', json.load(open('$W/$PR/proof.json'))['pass'])"
done
