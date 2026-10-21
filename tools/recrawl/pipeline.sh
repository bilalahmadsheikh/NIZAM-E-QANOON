#!/bin/bash
# Lead, 20 Oct 2026: take every observation landed by the recrawl (scraper_version 'recrawl-2026-10-20/1') through
# extraction, verification, segmentation and the post-replay steps. Release only through the ordinary gates; the
# release count may rise, never fall.
set -uo pipefail
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
O=/mnt/e/nizam-data/recrawl-2026-10-20
REASON="recrawl 2026-10-20: newly landed official text (portal listing diff, tools/recrawl) -- new released expression"
q() { ./nz psql -tAc "$1" | tr -d '[:space:]'; }
REL0=$(q "SELECT count(*) FROM v_release_instrument"); echo "released before: $REL0"
echo "== 1. extract (text layer), then OCR the scans E2 rejected"
.venv/bin/python -m nizam.workers.extract --all --quiet 2>&1 | tail -3
.venv/bin/python -m nizam.workers.ocr --all --workers 6 2>&1 | tail -3
# only documents still missing verification evidence, and only observations not yet segmented (a re-run is incremental)
DOCS=$(./nz psql -tAc "SELECT string_agg(DISTINCT d.id::text, ' ') FROM document d JOIN source_observation o ON o.sha256=d.sha256
                        JOIN v_document_quality_status q ON q.document_id=d.id
                        WHERE d.is_active AND o.scraper_version='recrawl-2026-10-20/1' AND q.overall_outcome='missing_evidence'")
OBS=$(./nz psql -tAc "SELECT string_agg(o.id::text, ',') FROM source_observation o JOIN document d ON d.sha256=o.sha256 AND d.is_active
                       WHERE o.scraper_version='recrawl-2026-10-20/1'
                         AND NOT EXISTS (SELECT 1 FROM block_assignment_set a WHERE a.source_observation_id=o.id AND a.is_active)
                         AND NOT EXISTS (SELECT 1 FROM instrument i WHERE i.source_observation_id=o.id AND i.is_active)" | tr -d '[:space:]')
echo "new documents: $(wc -w <<< "$DOCS")"
echo "== 2. verification evidence"
E2=$(./nz psql -tAc "SELECT string_agg(id::text,' ') FROM document WHERE id IN ($(tr ' ' ',' <<< "$DOCS")) AND lane<>'E4'")
E4=$(./nz psql -tAc "SELECT string_agg(id::text,' ') FROM document WHERE id IN ($(tr ' ' ',' <<< "$DOCS")) AND lane='E4'")
[ -n "$E2" ] && .venv/bin/python -m nizam.workers.verify_extraction --document-id $E2 2>&1 | tail -2
[ -n "$E2" ] && .venv/bin/python -m nizam.workers.verify_order --document-id $E2 2>&1 | tail -2
[ -n "$E2" ] && .venv/bin/python -m nizam.workers.verify_text_quality --document-id $E2 2>&1 | tail -2
[ -n "$E4" ] && .venv/bin/python -m nizam.workers.verify_ocr --document-id $E4 2>&1 | tail -3
[ -n "$DOCS" ] && ./nz psql -c "SELECT overall_outcome, count(*) FROM v_document_quality_status WHERE document_id IN ($(tr ' ' ',' <<< "$DOCS")) GROUP BY 1"
[ -z "$OBS" ] && { echo "nothing new to segment"; exit 0; }
echo "== 3. segment every new observation (review documents too: segmented, still unreleasable)"
.venv/bin/python -m nizam.workers.segment --observations "$OBS" --include-review --quiet \
    --approve-release-change "$REASON" 2>&1 | grep -E "segmented [0-9]|ERROR|failed" | tail -5
echo "== 4. post-replay derivations"
.venv/bin/python tools/resolve_exact_instrument_duplicates.py --apply 2>&1 | tail -1
.venv/bin/python tools/apply_source_incompleteness.py --apply 2>&1 | tail -1
.venv/bin/python tools/apply_source_same_text_copy.py --apply 2>&1 | tail -1
.venv/bin/python tools/apply_source_non_authoritative_copy.py --apply 2>&1 | tail -1
.venv/bin/python tools/record_statutory_repeals.py --apply 2>&1 | grep -E "recordable|dated|recorded"
.venv/bin/python tools/apply_statutory_repeals.py --apply
echo "== 5. result"
REL1=$(q "SELECT count(*) FROM v_release_instrument"); echo "released: $REL0 -> $REL1"
[ "$REL1" -ge "$REL0" ] || echo "STOP: the release count FELL"
./nz psql -c "SELECT o.source_id, count(DISTINCT i.id) instruments, count(DISTINCT r.id) released
                FROM source_observation o JOIN instrument i ON i.source_observation_id=o.id AND i.is_active AND i.duplicate_of IS NULL
                LEFT JOIN v_release_instrument r ON r.id=i.id WHERE o.scraper_version='recrawl-2026-10-20/1' GROUP BY 1"
.venv/bin/python tools/released_count_guard.py 2>&1 | tail -2
