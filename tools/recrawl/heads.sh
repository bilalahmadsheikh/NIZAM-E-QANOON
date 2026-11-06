#!/bin/bash
# heads.sh : held documents whose text blocks open with a Gazette running head 'PART <roman>] ... GAZETTE' (read-only)
cd /mnt/e/Nizam_e_Qanoon
L=$(awk -F, 'NR>1{print $1}' .artifacts/recrawl-queue/status-unreleased.csv | tr '\n' ',' | sed 's/,$//')
./nz psql -tA -F'|' -c "SELECT t.document_id, count(*) FROM text_block t WHERE t.document_id IN ($L) AND left(t.text,6)='PART I' AND position('GAZETTE' in left(t.text,60))>0 GROUP BY 1 ORDER BY 2 DESC"
