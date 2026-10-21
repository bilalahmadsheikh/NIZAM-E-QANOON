#!/bin/bash
S=/mnt/c/Users/bilaa/AppData/Local/Temp/claude/e--Nizam-e-Qanoon/33f4a608-f483-46ae-9533-136ae050000b/scratchpad
cd /mnt/e/Nizam_e_Qanoon
bash $S/verify-full.sh claude-baseline-87 2>&1 | grep -E 'released_baseline|removed_released|changed_released' | cut -c1-300
./nz psql -tAc "SELECT 'released from non-passed documents: '||count(*) FROM v_release_instrument r JOIN instrument i ON i.id=r.id JOIN v_document_quality_status q ON q.document_id=i.document_id WHERE q.overall_outcome<>'passed'"
