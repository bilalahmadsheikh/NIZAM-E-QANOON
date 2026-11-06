#!/bin/bash
# kinds.sh DOC : every active provision of the doc -- path, kind, text start (read-only)
cd /mnt/e/Nizam_e_Qanoon
./nz psql -tA -F '|' -c "SELECT subpath(p.path, 3)::text, p.kind, left(regexp_replace(coalesce(p.heading,'') || ' :: ' || coalesce((SELECT string_agg(t.text,' ') FROM text_block t WHERE t.id=p.first_block),''), '\s+', ' ', 'g'), 110) FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active WHERE i.document_id=$1 AND p.is_active ORDER BY p.path"
