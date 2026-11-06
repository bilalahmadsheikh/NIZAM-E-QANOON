#!/bin/bash
# c_look.sh DOC [kinds] : release state, open units, and tree of one document (read-only)
cd /mnt/e/Nizam_e_Qanoon
bash tools/recrawl/rel.sh $1
.venv/bin/python tools/recrawl/units_for.py $1
echo "--- tree"
.venv/bin/python tools/recrawl/tree.py $1 ${2:-section,article,part,chapter,clause,schedule}
