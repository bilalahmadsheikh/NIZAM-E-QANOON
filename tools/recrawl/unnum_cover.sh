#!/bin/bash
# unnum_cover.sh : docs whose every pending gap is an unnumbered-heading candidate (from /tmp/unnum.txt, /tmp/held.txt)
cut -d'|' -f1 /tmp/unnum.txt | grep -E '^[0-9]+$' | sort | uniq -c | while read n d; do
  line=$(grep -E "^$d\|" /tmp/held.txt); [ -z "$line" ] && continue
  g=$(echo "$line" | cut -d'|' -f4); s=$(echo "$line" | cut -d'|' -f3); q=$(echo "$line" | cut -d'|' -f2)
  echo "$d cand=$n gaps=$g s7=$s q=$q $(echo "$line" | cut -d'|' -f5)"
done | sort -t= -k3 -n
