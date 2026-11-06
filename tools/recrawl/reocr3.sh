#!/bin/bash
# Lead, 24 Oct: re-OCR (E4) held E2 documents whose own text layer is garbled (text-quality review); exclude docs carrying curation patches or any released instrument.
set -uo pipefail
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
O=/mnt/e/nizam-data/recrawl-2026-10-20; DOCS=$(cat .artifacts/recrawl-queue/reocr3-docs.txt)
REASON="queue 2026-10-24: re-read by OCR (the PDF's own text layer jumbled the scan) -- new released expression"
q() { ./nz psql -tAc "$1" | tr -d '[:space:]'; }
REL0=$(q "SELECT count(*) FROM v_release_instrument"); echo "released before: $REL0"
./nz psql -tAc "SELECT DISTINCT d.sha256 FROM document d WHERE d.id IN ($DOCS) AND d.is_active AND d.lane='E2'
   AND NOT EXISTS (SELECT 1 FROM instrument x JOIN v_release_instrument r ON r.id=x.id WHERE x.document_id=d.id)
   AND NOT EXISTS (SELECT 1 FROM segmentation_curation_patch c JOIN instrument i ON i.source_observation_id=c.source_observation_id
                    WHERE i.document_id=d.id AND c.retired_at IS NULL)" | tr -d ' ' | grep -E '^[0-9a-f]{64}$' > $O/reocr3-shas.txt
echo "documents to re-read: $(wc -l < $O/reocr3-shas.txt)"
.venv/bin/python -m nizam.workers.ocr --redo --sha256-list $O/reocr3-shas.txt --workers 10 > $O/reocr3.log 2>&1; tail -2 $O/reocr3.log
IDS=$(./nz psql -tAc "SELECT string_agg(d.id::text, ' ') FROM document d WHERE d.is_active AND d.lane='E4' AND d.sha256 IN ($(sed "s/.*/'&'/" $O/reocr3-shas.txt | paste -sd,))")
echo "re-read documents: $(wc -w <<< "$IDS")"; echo "$IDS" > $O/reocr3-ids.txt
.venv/bin/python -m nizam.workers.verify_ocr --document-id $IDS 2>&1 | tail -3
.venv/bin/python -m nizam.workers.segment --documents "$(tr ' ' ',' <<< "$IDS")" --include-review --quiet \
    --approve-release-change "$REASON" 2>&1 | grep -E "segmented [0-9]|failed" | tail -3
.venv/bin/python tools/adjudicate_structural_candidates.py --apply 2>&1 | grep -E 'machine_evidenced|left_for'
.venv/bin/python tools/adjudicate_citation_preserving.py --apply 2>&1 | grep -E 'recorded|left pending'
.venv/bin/python tools/resolve_exact_instrument_duplicates.py --apply 2>&1 | tail -1
.venv/bin/python tools/apply_statutory_repeals.py --apply
REL1=$(q "SELECT count(*) FROM v_release_instrument"); echo "released: $REL0 -> $REL1"
[ "$REL1" -ge "$REL0" ] || echo "STOP: released count fell"
bash tools/recrawl/declare.sh 2>&1 | tail -2
