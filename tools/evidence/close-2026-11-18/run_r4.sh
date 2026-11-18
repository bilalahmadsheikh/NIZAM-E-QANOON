#!/usr/bin/env bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
C=.artifacts/close-2026-11-18; W=$C/sindh-r4
rm -rf $W; mkdir -p $W
.venv/bin/python tools/recrawl/sindh_title_patch.py $W/patches 1245,2206,2505,2765,2902,3243,3919,3992 $C/residual-pages.json
for f in $W/patches/*.json; do .venv/bin/python -c "
import json,sys; r=json.load(open(sys.argv[1])); print(sys.argv[1].split('/')[-1], [(x['page_no'], 'aside+boundary' if x.get('source_head_boundary_blocks') else 'cut') for x in r])" $f; done
LABEL="Sindh running heads, round 4 (head boundaries)" bash $C/round.sh $W $W/patches t
