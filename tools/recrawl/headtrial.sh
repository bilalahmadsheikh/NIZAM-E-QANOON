#!/bin/bash
# headtrial.sh DOC ... : build running-head fixes (headfix.py) and trial them in memory against the stored tree
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for d in "$@"; do
  P=.artifacts/recrawl-queue/dbg/head-$d
  .venv/bin/python tools/recrawl/headfix.py $d .artifacts/recrawl-queue/patches/patch-${d}head.json $P
  echo "-- stored:"; .venv/bin/python tools/recrawl/trialseg.py $d - part,chapter,section,schedule 2>&1 | head -1
  echo "-- fixed:";  EXTRA_PATCHES=$P.patches.json .venv/bin/python tools/recrawl/trialseg.py $d $P.over.json part,chapter,section,schedule 2>&1 | head -1
  EXTRA_PATCHES=$P.patches.json .venv/bin/python tools/recrawl/trialseg.py $d $P.over.json part,chapter 2>&1 | sed -n 2,8p
done
