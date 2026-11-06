#!/bin/bash
# c_sheet.sh DOC : contact sheet for one document's open S7 units into sheets-C/DOC/ (read-only)
cd /mnt/e/Nizam_e_Qanoon
.venv/bin/python tools/recrawl/s7_sheet.py .artifacts/recrawl-queue/sheets-C/$1 --docs $1 | tail -1
.venv/bin/python - "$1" <<'PY'
import json, sys
m = json.load(open(f".artifacts/recrawl-queue/sheets-C/{sys.argv[1]}/manifest.json"))
for x in m:
    print(f"U{x['u']} sheet{x['sheet']} label {x['printed_label']!r} demoted p{x['demoted_page']} blk {x['demoted_block']} [{x['demoted_len']}c] {x['demoted_text'][:70]!r} | kept p{x['kept_page']} [{x['kept_len']}c] {x['kept_text'][:50]!r}")
PY
