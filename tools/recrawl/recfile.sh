#!/bin/bash
# recfile.sh PATCHFILE [...] : fill locators and record each patch file (no replay)
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for f in "$@"; do .venv/bin/python tools/recrawl/fill_patch.py $f >/dev/null && .venv/bin/python tools/record_curation_patch.py --readings $f --apply 2>&1 | tail -2 | tr "
" " "; echo " <- $f"; done
