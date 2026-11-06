#!/bin/bash
# perpage.sh DOC : number of active provisions starting on each page (read-only), compact
cd /mnt/e/Nizam_e_Qanoon; PYTHONPATH=. .venv/bin/python tools/recrawl/tree.py $1 part,chapter,section,schedule,subsection,clause,appendix,form 2>/dev/null | awk '{print $1}' | sort | uniq -c | sort -k2.2 -n | awk '{printf "%s:%s ", $2, $1}'; echo
