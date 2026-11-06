#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; for d in "$@"; do echo "== $d"; bash tools/recrawl/lsplit.sh $d 2>&1 | grep -E "^released|^[0-9]+\|"; done
