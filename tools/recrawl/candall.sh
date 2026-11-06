#!/bin/bash
# candall.sh DOC PAGE... : candblocks.py for each page
cd /mnt/e/Nizam_e_Qanoon; D=$1; shift; for p in "$@"; do echo "##### doc $D p$p"; PYTHONPATH=. .venv/bin/python tools/recrawl/candblocks.py $D $p; done
