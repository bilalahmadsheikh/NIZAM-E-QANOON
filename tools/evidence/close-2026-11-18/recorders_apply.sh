#!/usr/bin/env bash
set -e
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
for r in record_instrument_numbers record_long_titles record_enacted_dates; do
  echo "== $r"; .venv/bin/python tools/$r.py --apply 2>&1 | tr -d '\n' | grep -o '{[^}]*}' | head -1; echo
done
echo "== apply_instrument_metadata"; .venv/bin/python tools/apply_instrument_metadata.py --apply 2>&1 | tail -4
echo "== refresh_serving"; .venv/bin/python tools/refresh_serving.py 2>&1 | tail -2
echo "== audit"; ./nz audit 2>&1 | grep -cw PASS; ./nz audit 2>&1 | grep -w FAIL || echo "no FAIL"
