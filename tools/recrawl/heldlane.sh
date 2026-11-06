#!/bin/bash
# heldlane.sh : held documents (passed quality) by lane with S7 and gap counts, digital lanes first (read-only)
bash /mnt/e/Nizam_e_Qanoon/tools/recrawl/held_list.sh > /tmp/held.txt
cd /mnt/e/Nizam_e_Qanoon
L=$(awk -F'|' '$2=="passed"{print $1}' /tmp/held.txt | tr '\n' ',' | sed 's/,$//')
./nz psql -tA -F'|' -c "SELECT id, lane FROM document WHERE id IN ($L)" | sort > /tmp/lane.txt
awk -F'|' 'NR==FNR{lane[$1]=$2; next} $2=="passed"{print lane[$1]"|"$0}' /tmp/lane.txt /tmp/held.txt | sort -t'|' -k1,1 -k4n | awk -F'|' '{c[$1]++} {print} END{for(k in c) print "#", k, c[k]}' | grep -E "^(E1|E2|E3|#)"
