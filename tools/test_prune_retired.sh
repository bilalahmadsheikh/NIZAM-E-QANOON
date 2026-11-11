#!/usr/bin/env bash
# Restore one dump, exercise retired-instrument pruning in isolation, and prove
# that all active/release queues are unchanged.  The live database is never
# opened by this script.
set -euo pipefail

DUMP="${1:?usage: tools/test_prune_retired.sh /snapshots/name.dump SHA256}"
SHA="${2:?usage: tools/test_prune_retired.sh /snapshots/name.dump SHA256}"
DB=nizam_prune_verify
CONTAINER="${NIZAM_POSTGRES_CONTAINER:-nizam-postgres}"
USER_="${POSTGRES_USER:-nizam}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() { docker exec "$CONTAINER" dropdb -U "$USER_" --force --if-exists "$DB" >/dev/null; }
trap cleanup EXIT

cleanup
docker exec "$CONTAINER" createdb -U "$USER_" "$DB"
docker exec "$CONTAINER" pg_restore -U "$USER_" -d "$DB" --no-owner --no-acl "$DUMP"

before=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT concat_ws(',',
      (SELECT count(*) FROM source_observation),
      (SELECT count(*) FROM blob),
      (SELECT count(*) FROM document),
      (SELECT count(*) FROM page),
      (SELECT count(*) FROM text_block),
      (SELECT count(*) FROM instrument_expression_manifest),
      (SELECT count(*) FROM instrument_expression_manifest WHERE is_active),
      (SELECT count(*) FROM instrument WHERE is_active),
      (SELECT count(*) FROM provision p JOIN instrument i ON i.id=p.instrument_id WHERE i.is_active),
      (SELECT count(*) FROM v_release_instrument),
      (SELECT count(*) FROM v_release_provision),
      (SELECT count(*) FROM v_structural_adjudication_pending),
      (SELECT count(*) FROM v_boundary_adjudication_pending),
      (SELECT count(*) FROM v_toc_gap_pending),
      (SELECT count(*) FROM toc_gap_adjudication),
      (SELECT count(*) FROM toc_disposition_assertion),
      (SELECT count(*) FROM instrument_identity_resolution),
      (SELECT count(*) FROM heading_mislabel_finding),
      (SELECT count(*) FROM segmentation_curation_patch),
      (SELECT count(*) FROM extraction_verification),
      (SELECT count(*) FROM extraction_assertion),
      (SELECT md5(string_agg(pv.id::text||':'||md5(coalesce(pv.text_en,'')),',' ORDER BY pv.id))
         FROM provision_version pv JOIN v_release_provision r ON r.id=pv.provision_id));")
size=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT pg_database_size(current_database())")
manifest_check="SELECT count(*) FROM instrument_expression_manifest m
     LEFT JOIN instrument i ON i.id=m.materialized_instrument_id
    WHERE m.is_active AND (i.id IS NULL OR NOT i.is_active);"
bad_manifest_before=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc "$manifest_check")

docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -c \
  "INSERT INTO revision_archive_batch
     (archive_file,archive_sha256,database_size_before,detail)
   VALUES ('$DUMP','$SHA',$size,
           jsonb_build_object('scope','retired segmentation revisions only',
                              'restore_verified',true,'purpose','isolated prune test'));"

docker cp "$ROOT/tools/prune_retired_instruments.sql" \
  "$CONTAINER:/tmp/prune_retired_instruments.sql" >/dev/null
docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 \
  -f /tmp/prune_retired_instruments.sql

after=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT concat_ws(',',
      (SELECT count(*) FROM source_observation),
      (SELECT count(*) FROM blob),
      (SELECT count(*) FROM document),
      (SELECT count(*) FROM page),
      (SELECT count(*) FROM text_block),
      (SELECT count(*) FROM instrument_expression_manifest),
      (SELECT count(*) FROM instrument_expression_manifest WHERE is_active),
      (SELECT count(*) FROM instrument WHERE is_active),
      (SELECT count(*) FROM provision p JOIN instrument i ON i.id=p.instrument_id WHERE i.is_active),
      (SELECT count(*) FROM v_release_instrument),
      (SELECT count(*) FROM v_release_provision),
      (SELECT count(*) FROM v_structural_adjudication_pending),
      (SELECT count(*) FROM v_boundary_adjudication_pending),
      (SELECT count(*) FROM v_toc_gap_pending),
      (SELECT count(*) FROM toc_gap_adjudication),
      (SELECT count(*) FROM toc_disposition_assertion),
      (SELECT count(*) FROM instrument_identity_resolution),
      (SELECT count(*) FROM heading_mislabel_finding),
      (SELECT count(*) FROM segmentation_curation_patch),
      (SELECT count(*) FROM extraction_verification),
      (SELECT count(*) FROM extraction_assertion),
      (SELECT md5(string_agg(pv.id::text||':'||md5(coalesce(pv.text_en,'')),',' ORDER BY pv.id))
         FROM provision_version pv JOIN v_release_provision r ON r.id=pv.provision_id));")

if [[ "$before" != "$after" ]]; then
  echo "source/evidence/active/release state changed: before=$before after=$after" >&2
  exit 1
fi

# Compared with the restored baseline: a manifest that already named a retired
# materialization before the prune is a pre-existing defect, not a prune effect;
# the prune retains that retired tree.  Any new break fails.
bad_manifest=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc "$manifest_check")
[[ "$bad_manifest" == "$bad_manifest_before" ]] || {
  echo "active expression manifest lost its materialization ($bad_manifest_before before, $bad_manifest after)" >&2
  exit 1
}
[[ "$bad_manifest_before" == 0 ]] || echo "note: $bad_manifest_before active manifest(s) already named a retired materialization before the prune"

# The full corpus audit must still pass on the pruned copy.
docker exec -i "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -f - \
  < "$ROOT/tools/audit/criteria.sql" > /tmp/prune_verify_audit.log 2>&1 || {
  grep -E "FAIL|ERROR" /tmp/prune_verify_audit.log | head -40 >&2
  echo "corpus audit fails on the pruned copy" >&2
  exit 1
}
echo "corpus audit passes on the pruned copy"

dangling=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT count(*) FROM heading_mislabel_finding h
    WHERE (h.instrument_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM instrument i WHERE i.id=h.instrument_id))
       OR (h.provision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM provision p WHERE p.id=h.provision_id));")
[[ "$dangling" == 0 ]] || { echo "heading census finding lost its instrument/provision" >&2; exit 1; }

docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -P pager=off -c \
  "SELECT '$before' AS source_evidence_active_release_signature,
          (SELECT count(*) FROM instrument WHERE NOT is_active) retained_identity_endpoints,
          (SELECT count(*) FROM instrument_revision_archive_manifest) archived_instruments,
          pg_database_size(current_database()) AS bytes_before_vacuum;"
echo "isolated prune verified; temporary database removed"
