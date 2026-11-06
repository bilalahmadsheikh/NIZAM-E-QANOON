#!/bin/bash
# lf.sh : convert CRLF line endings to LF in the recrawl/colab tools and the K4 tests (Windows Python rewrites)
cd /mnt/e/Nizam_e_Qanoon
for f in tools/recrawl/*.sh tools/recrawl/*.py tools/colab/*.py tools/colab/*.sh tests/test_k4_rules_rsuv.py; do
  [ -f "$f" ] || continue
  if grep -q $'\r' "$f"; then sed -i 's/\r$//' "$f"; echo "fixed $f"; fi
done
