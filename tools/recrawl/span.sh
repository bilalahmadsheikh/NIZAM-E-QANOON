#!/bin/bash
# span.sh DOC P1 P2 SUFFIX : render pages, build the span patch from spec-DOC.json, apply it
cd /mnt/e/Nizam_e_Qanoon
for p in $(seq $2 $3); do bash tools/recrawl/render.sh $1 $p 70 > /dev/null; done
.venv/bin/python tools/recrawl/span_patch.py .artifacts/recrawl-queue/patches/spec-$1.json && bash tools/recrawl/patch.sh $1 apply $4 2>&1 | grep -v locator | tail -5
