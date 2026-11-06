#!/bin/bash
# gapsD.sh DOC... -> near-gap contents listing for each doc
cd /mnt/e/Nizam_e_Qanoon
for d in "$@"; do ./.venv/bin/python tools/recrawl/gapsD.py $d --near; done
