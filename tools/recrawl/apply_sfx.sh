#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
for d in "$@"; do echo "== $d"; bash tools/recrawl/patch.sh $d apply ${SFX:-o2d} 2>&1 | grep -E "^released|recorded|\|[tf]\||rror|refused|not reached"; done
