#!/bin/bash
# render_many.sh DPI DOC:PAGE [DOC:PAGE ...] -> renders + sha (via render.sh)
D=$1; shift
for x in "$@"; do bash /mnt/e/Nizam_e_Qanoon/tools/recrawl/render.sh ${x%%:*} ${x##*:} $D; done
