#!/bin/bash
# pt_apply.sh DOC : owner decision q4 on a page-targeted Surya re-read -- accept the agreeing pages
# (tools/recrawl/ocr_policy.py --apply), promote them into a new E4 revision keeping the stored text of every
# other page (--allow-partial), segment the revision for review, and show its tree and pending units.
# verify_ocr is NOT run here: tools/recrawl/ocr_verify.sh, after the tree is read.
set -uo pipefail
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
D=$1; q() { ./nz psql -tAc "$1" | tr -d '[:space:]'; }
# Guards (lesson of 9563 -> 9664, 24 Oct): a re-read of a CONTENTS page changes how the whole contents list is found
# (the promoted revision lost its contents region and gained dozens of pending units), and a page carrying recorded
# curation patches would move their locators. Neither is promoted here.
PAGES=$(./nz psql -tAc "SELECT string_agg(DISTINCT page_no::text, ',') FROM page_ocr_candidate c WHERE document_id=$D AND engine LIKE 'surya%' AND NOT EXISTS (SELECT 1 FROM page_ocr_adjudication a WHERE a.candidate_id=c.id)" | tr -d '[:space:]')
[ -n "$PAGES" ] || PAGES=0
TOCP=$(q "SELECT count(*) FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id AND i.is_active WHERE i.document_id=$D AND e.source_page IN ($PAGES)")
[ "$TOCP" = "0" ] || { echo "STOP: page(s) $PAGES hold $TOCP contents row(s) -- not promoted"; exit 1; }
PAT=$(q "SELECT count(*) FROM segmentation_curation_patch p JOIN instrument i ON i.source_observation_id=p.source_observation_id AND i.is_active WHERE i.document_id=$D AND p.retired_at IS NULL AND p.page_no IN ($PAGES)")
[ "$PAT" = "0" ] || { echo "STOP: page(s) $PAGES carry $PAT recorded patch(es) -- not promoted"; exit 1; }
.venv/bin/python tools/recrawl/pt_trial.py $D || { echo "STOP: the re-read would not improve the tree -- not promoted"; exit 1; }
.venv/bin/python tools/recrawl/ocr_policy.py $D --apply | tail -1
ACC=$(q "SELECT count(DISTINCT c.page_no) FROM page_ocr_candidate c JOIN page_ocr_adjudication a ON a.candidate_id=c.id WHERE c.document_id=$D AND a.decision='accepted'")
[ "$ACC" != "0" ] || { echo "STOP: no accepted page"; exit 1; }
NEW=$(q "SELECT id FROM document WHERE supersedes_document_id=$D AND is_active ORDER BY id DESC LIMIT 1")
if [ -z "$NEW" ]; then
  OUT=$(.venv/bin/python tools/promote_ocr_adjudicated.py --document-id $D --allow-partial --apply 2>&1)
  NEW=$(grep -oE "$D -> [0-9]+" <<< "$OUT" | grep -oE '[0-9]+$' | tail -1)
  [ -n "$NEW" ] || { echo "$OUT" | tail -5; echo "STOP: no promoted revision"; exit 1; }
fi
echo "DOC $D -> NEW=$NEW ($ACC accepted page(s))"
if [ "$(q "SELECT count(*) FROM instrument WHERE document_id=$NEW AND is_active")" = "0" ]; then
  .venv/bin/python -m nizam.workers.segment --documents $NEW --include-review --quiet 2>&1 | grep -E "ERROR|refus|segmented [0-9]|nothing"
fi
.venv/bin/python tools/recrawl/tree.py $NEW section,article,part,chapter,schedule 2>/dev/null
.venv/bin/python tools/recrawl/units_for.py $NEW 2>/dev/null
