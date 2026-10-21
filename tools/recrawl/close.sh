#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
S=/mnt/c/Users/bilaa/AppData/Local/Temp/claude/e--Nizam-e-Qanoon/33f4a608-f483-46ae-9533-136ae050000b/scratchpad
.venv/bin/python tools/recrawl/dupcheck.py
.venv/bin/python tools/census_heading_mislabel.py --record 2>&1 | tail -1
./nz audit > /tmp/audit.txt 2>&1; echo "audit PASS $(grep -c '| PASS' /tmp/audit.txt)"; grep -E 'FAIL' /tmp/audit.txt | cut -c1-200
./nz psql -tAc "SELECT 'blocked (unreleased canonical): '||count(*) FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)"
./nz psql -tAc "SELECT 'documents '||count(*)||', pages '||sum(page_count) FROM document WHERE is_active"
timeout 3000 .venv/bin/python -m pytest -q --no-header -p no:cacheprovider tests > /tmp/lead-suite.txt 2>&1
echo "tests: $(grep -E '^[.sFE]+ +\[' /tmp/lead-suite.txt | sed -E 's/ +\[.*//' | tr -d '\n' | fold -w1 | sort | uniq -c | tr '\n' ' ')"; grep -E '^(FAILED|ERROR)' /tmp/lead-suite.txt | head
