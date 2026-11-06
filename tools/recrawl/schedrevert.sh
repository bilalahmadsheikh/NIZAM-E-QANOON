#!/bin/bash
# schedrevert.sh DOC [...] : retire the schedule-opener trial patch of each doc and replay it
cd /mnt/e/Nizam_e_Qanoon
for d in "$@"; do bash tools/recrawl/retire_file.sh .artifacts/recrawl-queue/patches/patch-${d}sch.json "schedule-opener trial reverted: no gain or more pending units" >/dev/null; bash tools/recrawl/replay.sh $d | head -1; done
