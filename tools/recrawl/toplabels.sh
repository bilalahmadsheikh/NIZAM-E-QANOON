#!/bin/bash
# toplabels.sh DOC : the document's section/article paths in order, compact (read-only)
cd /mnt/e/Nizam_e_Qanoon && PYTHONPATH=. .venv/bin/python tools/recrawl/tree.py $1 section,article,schedule,chapter | awk '{print $1, $3}' | tr '\n' ' '
