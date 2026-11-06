#!/bin/bash
# Lead, 21 Oct 2026: re-read with our own OCR (lane E4, new revision) every recrawl document whose text layer failed the
# reading-order or character checks and that has NO released instrument; verify, re-segment, re-adjudicate S7 by rule.
set -uo pipefail
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
O=/mnt/e/nizam-data/recrawl-2026-10-20
REASON="recrawl 2026-10-20: re-read by OCR (the PDF's own text layer failed reading order / characters) -- new released expression"
q() { ./nz psql -tAc "$1" | tr -d '[:space:]'; }
REL0=$(q "SELECT count(*) FROM v_release_instrument"); echo "released before: $REL0"
./nz psql -tAc "SELECT DISTINCT d.sha256 FROM document d JOIN source_observation o ON o.sha256=d.sha256
   JOIN v_document_quality_status s ON s.document_id=d.id
  WHERE d.is_active AND d.lane<>'E4' AND o.scraper_version='recrawl-2026-10-20/1'
    AND (s.order_outcome IN ('review','unverifiable') OR s.character_outcome IN ('review','unverifiable'))
    AND NOT EXISTS (SELECT 1 FROM instrument i JOIN v_release_instrument r ON r.id=i.id WHERE i.document_id=d.id)" \
  | tr -d ' ' | grep -E '^[0-9a-f]{64}$' > $O/reocr-shas.txt
echo "documents to re-read: $(wc -l < $O/reocr-shas.txt)"
.venv/bin/python -m nizam.workers.ocr --redo --sha256-list $O/reocr-shas.txt --workers 10 > $O/reocr.log 2>&1; tail -2 $O/reocr.log
IDS=$(./nz psql -tAc "SELECT string_agg(d.id::text, ' ') FROM document d WHERE d.is_active AND d.lane='E4' AND d.sha256 IN ($(sed "s/.*/'&'/" $O/reocr-shas.txt | paste -sd,))")
echo "re-read documents: $(wc -w <<< "$IDS")"
.venv/bin/python -m nizam.workers.verify_ocr --document-id $IDS 2>&1 | tail -3
./nz psql -c "SELECT overall_outcome, count(*) FROM v_document_quality_status WHERE document_id IN ($(tr ' ' ',' <<< "$IDS")) GROUP BY 1"
.venv/bin/python -m nizam.workers.segment --documents "$(tr ' ' ',' <<< "$IDS")" --include-review --quiet \
    --approve-release-change "$REASON" 2>&1 | grep -E "segmented [0-9]|failed" | tail -3
.venv/bin/python tools/adjudicate_structural_candidates.py --apply 2>&1 | grep -E 'machine_evidenced|left_for'
.venv/bin/python tools/adjudicate_citation_preserving.py --apply 2>&1 | grep -E 'recorded|left pending'
.venv/bin/python tools/resolve_exact_instrument_duplicates.py --apply 2>&1 | tail -1
.venv/bin/python tools/apply_statutory_repeals.py --apply
REL1=$(q "SELECT count(*) FROM v_release_instrument"); echo "released: $REL0 -> $REL1"
[ "$REL1" -ge "$REL0" ] || echo "STOP: released count fell"
.venv/bin/python tools/released_count_guard.py 2>&1 | tail -1
