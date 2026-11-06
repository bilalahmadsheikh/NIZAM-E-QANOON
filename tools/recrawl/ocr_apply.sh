#!/bin/bash
# ocr_apply.sh DOC : owner's OCR review export (all pages accepted) -> adjudicate -> promote -> segment --include-review
# (stays blocked) -> show tree + pending. Re-runnable. verify_ocr is NOT run here (ocr_verify.sh, after the tree is read).
set -uo pipefail
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
DOC0=$1; E=.artifacts/ocr-review-exports/ocr-review-doc-$DOC0.json; PACK=.artifacts/ocr-review-pack-q1; [ -d $PACK/doc-$DOC0 ] || PACK=.artifacts/ocr-review-pack-q1b; [ -d $PACK/doc-$DOC0 ] || PACK=.artifacts/ocr-review-pack-q1c; [ -d $PACK/doc-$DOC0 ] || PACK=.artifacts/ocr-review-pack-q1d
stop() { echo "STOP: $*"; exit 1; }
q() { ./nz psql -tAc "$1" | tr -d '[:space:]'; }
PAGES=$(.venv/bin/python -c "import json;d=json.load(open('$E',encoding='utf-8-sig'));a=[x for x in d['decisions'] if x['decision']=='accepted'];print(len(a) if len(a)==len(d['decisions'])==d['source_page_count'] else 0)")
[ "$PAGES" != "0" ] || stop "not every page accepted -- handle by hand"
.venv/bin/python tools/validate_ocr_review_export.py $E --pack $PACK | tail -1
if [ "$(q "SELECT count(*) FROM page_ocr_adjudication a JOIN page_ocr_candidate c ON c.id=a.candidate_id WHERE c.document_id=$DOC0 AND a.decision='accepted'")" != "$PAGES" ]; then
  .venv/bin/python tools/evidence/adjudicate_ocr_review_export.py $E --apply | tail -1
fi
NEW=$(q "SELECT id FROM document WHERE supersedes_document_id=$DOC0 AND is_active ORDER BY id DESC LIMIT 1")
if [ -z "$NEW" ]; then
  DRY=$(.venv/bin/python tools/promote_ocr_adjudicated.py --document-id $DOC0 2>&1)
  grep -q "$DOC0: would promote $PAGES/$PAGES pages" <<< "$DRY" || { echo "$DRY" | tail -3; stop "promotion dry run is not $PAGES/$PAGES"; }
  OUT=$(.venv/bin/python tools/promote_ocr_adjudicated.py --document-id $DOC0 --apply 2>&1)
  NEW=$(grep -oE "$DOC0 -> [0-9]+" <<< "$OUT" | grep -oE '[0-9]+$' | tail -1)
fi
[ -n "$NEW" ] || stop "no promoted revision"; echo "DOC $DOC0 -> NEW=$NEW"
if [ "$(q "SELECT count(*) FROM instrument WHERE document_id=$NEW AND is_active")" = "0" ]; then
  [ "$(q "SELECT count(*) FROM extraction_verification WHERE document_id=$NEW")" = "0" ] || stop "$NEW already OCR-verified"
  .venv/bin/python -m nizam.workers.segment --documents $NEW --include-review --quiet 2>&1 | grep -E "ERROR|refus|segmented [0-9]|nothing"
fi
.venv/bin/python tools/recrawl/tree.py $NEW section,article,part,chapter,schedule 2>/dev/null
.venv/bin/python tools/recrawl/units_for.py $NEW 2>/dev/null
