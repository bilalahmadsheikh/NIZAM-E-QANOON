#!/bin/bash
# G_apply.sh DOC [noanchor] : agent G -- record boundary anchors (anchor.py --apply) then materialize the split (split.sh apply)
cd /mnt/e/Nizam_e_Qanoon
if [ "$2" != noanchor ]; then .venv/bin/python tools/recrawl/anchor.py $1 --apply || exit 1; fi
bash tools/recrawl/split.sh $1 apply
