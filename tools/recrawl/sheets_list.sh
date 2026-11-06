#!/bin/bash
# sheets_list.sh LISTFILE OUTDIR [PER_SHEET] : S7 sheets for the docs in LISTFILE
cd /mnt/e/Nizam_e_Qanoon
D=$(tr -d '\r\357\273\277' < "$1" | tr -s ' \n' ' ')
[ -z "$D" ] && { echo "empty list"; exit 1; }
rm -rf "$2"; PER_SHEET=${3:-5} .venv/bin/python tools/recrawl/s7_sheet.py "$2" --docs $D 2>&1 | tail -2
ls "$2" | wc -l
