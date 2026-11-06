#!/bin/bash
# autofix.sh OLD:NEW... : the mechanical repairs, then release through gatefinish.sh when nothing is pending, the text
# gate passes and leakscan.py is clean -- one document at a time:
#   bookfix.sh   running heads, folios, sheet marks, margin citations, catchwords (pagefurniture --auto), v4 pin,
#                machine S7 adjudicators
#   sweep.py     blocks that are attributed amendment notes or Gazette heads read into provisions
#   sidefix.sh   STRICT side-note cuts from the document's own contents (a note ending in its stop or comma, the
#                sentence going on in lower case; division headings never set aside)
# Appends to autofix-log.txt; releases nothing that fails a check.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
LOG=.artifacts/recrawl-queue/autofix-log.txt
for pair in "$@"; do
  old=${pair%%:*}; new=${pair##*:}
  bash tools/recrawl/bookfix.sh $new >/dev/null 2>&1
  S=.artifacts/recrawl-queue/specs/sweep-$new.json
  if ! .venv/bin/python tools/recrawl/sweep.py $new $S | grep -q ': 0 blocks'; then
    PG=$(python3 -c "import json;print(' '.join(json.load(open('$S'))['pages']))")
    bash .artifacts/recrawl-queue/render_pages.sh $new 60 $PG >/dev/null 2>&1
    .venv/bin/python tools/recrawl/blockfix.py $S .artifacts/recrawl-queue/patches/patch-${new}sw.json >/dev/null 2>&1 &&
      bash tools/recrawl/patch.sh $new apply sw >/dev/null 2>&1
  fi
  OUT=.artifacts/recrawl-queue/patches/patch-${new}sn.json
  if STRICT=1 bash tools/recrawl/sidefix.sh $new 2>/dev/null | grep -qE '^[1-9][0-9]* text patches|[1-9][0-9]* note blocks'; then
    bash tools/recrawl/sidefix.sh $new reviewed >/dev/null 2>&1
  fi
  .venv/bin/python tools/adjudicate_structural_candidates.py --apply >/dev/null 2>&1
  .venv/bin/python tools/adjudicate_citation_preserving.py --apply >/dev/null 2>&1
  echo "$(bash .artifacts/recrawl-queue/gatefinish.sh $old:$new)" >> $LOG
done
echo "autofix done: $(bash tools/recrawl/rel.sh 0 | head -1)" >> $LOG
