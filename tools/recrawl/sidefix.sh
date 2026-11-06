#!/bin/bash
# sidefix.sh DOC [apply] : side notes woven into the text, cut by sidenote_strip.py from the document's own contents
# rows (the contents blocks of the active instrument's toc entries). Dry run prints every cut for review; 'apply'
# renders the pages, records the patch and replays under the release gate (a released document stays released or the
# replay rolls back), then rescans with leakscan.py.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$1; OUT=.artifacts/recrawl-queue/patches/patch-${D}sn.json
C=$(./nz psql -tAc "SELECT DISTINCT e.source_block_id FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id
                    WHERE i.document_id=$D AND i.is_active AND i.duplicate_of IS NULL AND e.source_block_id IS NOT NULL" | tr '\n' ' ')
[ -z "$C" ] && { echo "$D: no contents blocks"; exit 1; }
# 'reviewed' : apply the existing OUT.json as it stands after review (cuts judged wrong already removed from it)
[ "$2" = reviewed ] || .venv/bin/python tools/recrawl/sidenote_strip.py $D $C $OUT ${STRICT:+--strict}
[ "$2" = apply ] || [ "$2" = reviewed ] || exit 0
PG=$(python3 -c "import json;print(' '.join(sorted({str(r['page_no']) for r in json.load(open('$OUT'))})))")
bash .artifacts/recrawl-queue/render_pages.sh $D 60 $PG >/dev/null 2>&1
.venv/bin/python tools/recrawl/fill_patch.py $OUT >/dev/null 2>&1
.venv/bin/python tools/record_curation_patch.py --readings $OUT --apply 2>&1 | grep -oE 'recorded [0-9]+'
.venv/bin/python -m nizam.workers.segment --document $D --redo --include-review \
  --approve-release-change "recrawl 2026-10-29: side notes woven into the text cut (sidenote_strip.py from the contents)" 2>&1 \
  | grep -oE 'segmented [0-9]+, failed [0-9]+|ERROR.*' | head -2 | cut -c1-200
bash tools/recrawl/rel.sh $D | tail -1
.venv/bin/python tools/recrawl/leakscan.py $D | cut -c1-200
