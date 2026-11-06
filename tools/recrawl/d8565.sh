#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
./nz psql -At -F ' | ' -c "SELECT r.id, r.run_at, r.segmenter, r.detail->>'release_change_approval', r.instrument_id FROM segmentation_run r WHERE r.document_id=8565 ORDER BY r.run_at DESC LIMIT 3"
./nz psql -At -F ' | ' -c "SELECT d.id, d.lane, d.supersedes_document_id, o.scraper_version, o.source_metadata->>'title' FROM document d JOIN source_observation o ON o.sha256=d.sha256 WHERE d.id=8565"
sed -n '1,40p' tools/released_count_guard.py | grep -nE "approval|new released expression|run_at|detail" | head
