#!/bin/bash
# linkcheck.sh DOC : each contents row with the heading of the provision it is linked to (read-only)
cd /mnt/e/Nizam_e_Qanoon
./nz psql -tA -F '|' <<SQL
SELECT e.ordinal, e.printed_label, left(e.printed_heading,40), p.label, left(coalesce(p.heading, p.marginal_note, NULL),40)
  FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id AND i.is_active LEFT JOIN provision p ON p.id=e.provision_id
 WHERE i.document_id=$1 ORDER BY e.ordinal;
SQL
