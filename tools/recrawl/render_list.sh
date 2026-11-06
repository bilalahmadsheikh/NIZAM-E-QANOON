#!/bin/bash
# render_list.sh FILE : render every DOC:PAGE in FILE at 70 dpi
cd /mnt/e/Nizam_e_Qanoon; for x in $(cat "$1"); do bash tools/recrawl/render.sh ${x%%:*} ${x##*:} 70 >/dev/null; done; echo rendered
