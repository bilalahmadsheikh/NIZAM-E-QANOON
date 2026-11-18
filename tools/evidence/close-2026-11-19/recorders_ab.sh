#!/usr/bin/env bash
# D-092 A/B: every title-region recorder dry-run on the raw extracted text and on the page-read text.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
O=.artifacts/close-2026-11-19/recorders; mkdir -p $O
for r in record_instrument_numbers record_long_titles record_enacted_dates; do
  for mode in raw read; do
    FLAG=""; [ $mode = raw ] && FLAG=--raw-text
    .venv/bin/python tools/$r.py $FLAG $([ $r != record_enacted_dates ] && echo --show 0) --dump $O/$r.$mode.json > $O/$r.$mode.log 2>&1
    echo "$r $mode: $(tr -d '\n ' < $O/$r.$mode.log | grep -o '{[^}]*}' | head -1)"
  done
done
