#!/bin/bash
O=/mnt/e/nizam-data/recrawl-2026-10-20
for s in sindh balochistan drs0 drs1; do echo "== $s"; tail -8 $O/land-$s.log | cut -c1-300; done
echo "== processes"; ps -eo pid,etime,args | grep land_missing | grep -v grep | cut -c1-150
