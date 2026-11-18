#!/usr/bin/env bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
C=.artifacts/close-2026-11-19
SD=986,1245,1864,2022,2206,2339,2505,2765,2902,3243,3880,3914,3919,3992
rm -rf $C/sindh-r1; .venv/bin/python tools/recrawl/sindh_title_patch.py $C/sindh-r1/patches $SD
echo "== Sindh round 1"; LABEL="Sindh running heads, round 1" bash $C/round.sh $C/sindh-r1 $C/sindh-r1/patches t
echo "== AJK round 1";   LABEL="AJK folios, round 1" bash $C/round.sh $C/ajk-r1 $C/ajk-r1/patches f
