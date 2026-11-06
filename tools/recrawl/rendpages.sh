#!/bin/bash
# rendpages.sh DOC PAGE... : render pages at 70 dpi (quiet)
cd /mnt/e/Nizam_e_Qanoon; D=$1; shift; for p in "$@"; do bash tools/recrawl/render.sh $D $p 70 >/dev/null 2>&1; done; echo rendered $#
