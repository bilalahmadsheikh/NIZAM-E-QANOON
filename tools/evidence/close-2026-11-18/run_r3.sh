#!/usr/bin/env bash
# Round N (Sindh): regenerate every page with fresh locators, drop the pages the latest dumps show offending, prove,
# release the passes (round.sh -> batch_stage2.sh).
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
C=.artifacts/close-2026-11-18; N=$1; SD=$2; W=$C/sindh-r$N
rm -rf $W; mkdir -p $W/prevdump
.venv/bin/python tools/recrawl/sindh_title_patch.py $W/all $SD
for d in $(echo $SD | tr , ' '); do       # the newest dump of each document
  for src in $(ls -d $C/sindh-r*/dump $C/sindh-r*/current/dump .artifacts/heritage-2026-11-18/sindh-batch/dump 2>/dev/null | sort -r); do
    [ "$src" = "$W/dump" ] && continue
    if ls $src/${d}_*.json >/dev/null 2>&1; then cp $src/${d}_*.json $W/prevdump/; break; fi
  done
done
.venv/bin/python tools/recrawl/furniture_rounds.py $W/prevdump $W/all /dev/null $W/patches t
LABEL="Sindh running heads, round $N" bash $C/round.sh $W $W/patches t
