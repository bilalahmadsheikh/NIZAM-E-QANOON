#!/bin/bash
# retire_patch.sh DOC MATCH_TEXT REASON : retire (never delete) this session's own curation patch on DOC with MATCH_TEXT
cd /mnt/e/Nizam_e_Qanoon
./nz psql -v ON_ERROR_STOP=1 -v doc="$1" -v m="$2" -v why="$3" <<'SQL'
UPDATE segmentation_curation_patch p
   SET retired_at = now(),
       evidence = p.evidence || jsonb_build_object('retired_reason', :'why', 'retired_by', 'claude.recrawl-queue/1')
 WHERE p.retired_at IS NULL AND p.match_text = :'m'
   AND p.source_observation_id IN (SELECT source_observation_id FROM instrument WHERE document_id = :doc AND is_active)
   AND p.created_at > now() - interval '2 days'
RETURNING id, page_no, match_text;
SQL
