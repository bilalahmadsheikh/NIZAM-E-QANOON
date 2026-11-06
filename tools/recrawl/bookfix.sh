#!/bin/bash
# bookfix.sh DOC [SUFFIX] : the mechanical repairs a code-book or Gazette reprint needs, in one pass --
#   renders of every page (evidence), page furniture found from the document itself (pagefurniture.py --auto:
#   running heads and their variants, folios, sheet marks, margin citations, running section guides, catchwords),
#   the unreleased-v4 pin (apparatus_contents_rows: a set-aside block is never a contents row), the replay, the
#   machine S7 adjudicators; then what is left (units_for.py). Side notes are NOT stripped here (sidenote_strip.py
#   needs its list read). Releases nothing.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$1; S=${2:-pf}
bash .artifacts/recrawl-queue/renderall.sh $D 70 >/dev/null
.venv/bin/python tools/recrawl/pagefurniture.py $D .artifacts/recrawl-queue/patches/patch-$D$S.json --auto | tail -1
.venv/bin/python tools/pin_segmentation_profile.py --documents $D --profile unreleased-v4 \
  --reason "doc $D: apparatus_contents_rows -- running heads set aside are no contents rows (bookfix)" --apply >/dev/null 2>&1
bash tools/recrawl/patch.sh $D apply $S 2>&1 | tail -1
.venv/bin/python tools/adjudicate_structural_candidates.py --apply >/dev/null 2>&1
.venv/bin/python tools/adjudicate_citation_preserving.py --apply >/dev/null 2>&1
.venv/bin/python tools/recrawl/units_for.py $D | cut -c1-200
