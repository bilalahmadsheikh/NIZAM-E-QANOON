#!/bin/bash
# rel.sh [DOC ...] -> released count, and per-document release state
cd /mnt/e/Nizam_e_Qanoon
./nz psql -tAc "SELECT 'released', count(*) FROM v_release_instrument"
for d in "$@"; do
./nz psql -tAc "SELECT i.document_id, EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id),
  (SELECT count(*) FROM v_structural_adjudication_pending s WHERE s.instrument_id=i.id),
  (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id),
  (SELECT count(*) FROM v_boundary_adjudication_pending b WHERE b.instrument_id=i.id)
  FROM instrument i WHERE i.document_id=$d AND i.is_active AND i.duplicate_of IS NULL"
done
