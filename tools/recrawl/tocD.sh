#!/bin/bash
# tocD.sh DOC [apply] -> dry run / record .artifacts/recrawl-queue/readings/D-DOC.json, then release state
cd /mnt/e/Nizam_e_Qanoon
F=.artifacts/recrawl-queue/readings/D-$1.json
if [ "$2" = "apply" ]; then A=--apply; else A=; fi
PYTHONPATH=. ./.venv/bin/python tools/adjudicate_toc_from_source.py --readings $F $A
bash tools/recrawl/rel.sh $1
