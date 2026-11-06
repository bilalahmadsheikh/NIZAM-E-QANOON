#!/bin/bash
# retire_file.sh PATCHFILE REASON : retire every patch recorded from PATCHFILE (by doc + match_text)
cd /mnt/e/Nizam_e_Qanoon
.venv/bin/python -c "
import json,sys
for r in json.load(open(sys.argv[1],encoding='utf-8')): print(str(r['document_id'])+'\t'+r['match_text'])" "$1" |
while IFS=$'\t' read -r d m; do bash tools/recrawl/retire_patch.sh "$d" "$m" "$2" | grep -c '^ *[0-9]' ; done
