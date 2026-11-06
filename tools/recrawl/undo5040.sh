#!/bin/bash
# undo5040.sh : retire today's 5040 patches (wrong released tree: sections 12-58 filed as clauses) and replay
cd /mnt/e/Nizam_e_Qanoon
for f in patch-5040k5040 patch-5040k5040b patch-5040k5040c patch-5040k5040d patch-5040ro; do bash tools/recrawl/retire_file.sh .artifacts/recrawl-queue/patches/$f.json "withdrawn: the release these patches enabled filed sections 12-58 as clauses of section 11(2); the tree needs a list-boundary rule before release" >/dev/null; done
bash tools/recrawl/replay.sh 5040
