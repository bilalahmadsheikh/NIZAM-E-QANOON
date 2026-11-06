#!/bin/bash
# blockfix.sh DOC SUFFIX [apply] : build patch-DOC{SUFFIX}.json from specs/blockfix-DOC.json (blockfix.py), dry-run or
# record it (patch.sh), then the machine S7 adjudicators and what is left (units_for.py)
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$1; S=$2
.venv/bin/python tools/recrawl/blockfix.py .artifacts/recrawl-queue/specs/blockfix-$D.json .artifacts/recrawl-queue/patches/patch-$D$S.json || exit 1
if [ "$3" = apply ]; then
  bash tools/recrawl/patch.sh $D apply $S 2>&1 | tail -2
  .venv/bin/python tools/adjudicate_structural_candidates.py --apply >/dev/null 2>&1
  .venv/bin/python tools/adjudicate_citation_preserving.py --apply >/dev/null 2>&1
  .venv/bin/python tools/recrawl/units_for.py $D | cut -c1-220
else
  bash tools/recrawl/patch.sh $D dry $S 2>&1 | grep -iE "refus|error|assert|not found|dry run" | head -20
fi
