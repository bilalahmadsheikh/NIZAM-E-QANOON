#!/bin/bash
# rend.sh DPI DOC:PAGE ... : render each page
cd /mnt/e/Nizam_e_Qanoon; D=$1; shift; for x in "$@"; do bash tools/recrawl/render.sh ${x%%:*} ${x##*:} $D | cut -d' ' -f1; done
