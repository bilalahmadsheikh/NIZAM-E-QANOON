#!/bin/bash
# g.sh DOC PATTERN [DOC PATTERN ...] -> grepblk for each pair
cd /mnt/e/Nizam_e_Qanoon
while [ $# -ge 2 ]; do echo "## $1 $2"; ./.venv/bin/python tools/recrawl/grepblk.py "$1" "$2"; shift 2; done
