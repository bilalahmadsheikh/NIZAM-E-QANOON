#!/bin/bash
# pgtext.sh DOC PAGE [PAGE ...] : block id + first 140 chars of each block on the pages (read-only)
cd /mnt/e/Nizam_e_Qanoon; D=$1; shift
for p in "$@"; do echo "--- doc $D p$p"; ./nz psql -tA -F ' ' -c "SELECT id, left(regexp_replace(text, E'\\s+', ' ', 'g'), 140) FROM text_block WHERE document_id=$D AND page_no=$p ORDER BY reading_order"; done
