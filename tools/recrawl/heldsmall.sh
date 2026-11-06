#!/bin/bash
# heldsmall.sh [MAX] : held docs with contents gaps and s7+gaps <= MAX (default 4), then the quality-held ones (read-only)
bash /mnt/e/Nizam_e_Qanoon/tools/recrawl/held_list.sh > /tmp/held.txt
awk -F'|' -v M=${1:-4} '$2=="passed" && $4>0 && $3+$4<=M' /tmp/held.txt; echo "-- quality"
awk -F'|' '$2!="passed"' /tmp/held.txt
