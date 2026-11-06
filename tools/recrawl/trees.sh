#!/bin/bash
# trees.sh KINDS DOC ... : tree.py for each doc with the given kinds, lines cut to 140 (read-only)
cd /mnt/e/Nizam_e_Qanoon; K=$1; shift; for d in "$@"; do echo "== $d"; PYTHONPATH=. .venv/bin/python tools/recrawl/tree.py $d $K 2>/dev/null | cut -c1-140; done
