#!/bin/bash
# tocnear.sh DOC LABEL [N] : contents rows within N ordinals of the pending row LABEL (read-only)
cd /mnt/e/Nizam_e_Qanoon; N=${3:-4}
./nz psql -tA -F '|' <<SQL
WITH g AS (SELECT e.instrument_id, e.ordinal FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id AND i.is_active
            WHERE i.document_id=$1 AND e.printed_label='$2' AND e.provision_id IS NULL LIMIT 1)
SELECT e.ordinal, e.source_page, e.source_block_id, e.printed_label, left(e.printed_heading,60), (SELECT p.path FROM provision p WHERE p.id=e.provision_id)
  FROM instrument_toc_entry e, g WHERE e.instrument_id=g.instrument_id AND e.ordinal BETWEEN g.ordinal-$N AND g.ordinal+$N ORDER BY e.ordinal;
SQL
