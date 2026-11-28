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
# Replayed through psql with ANALYZE before the first materialized-view refresh:
# plain pg_restore refreshes the serving snapshot on tables with no statistics,
# and that refresh ran past 35 minutes on 17 Nov 2026 (infra/scripts/restore.sh).
# No parallel index build (27 Nov 2026): the HNSW indexes' parallel build keeps its graph in /dev/shm, filled the
# container's 1 GB and failed the restore, with the live database's own queries refused beside it.
docker exec -e PGOPTIONS='-c max_parallel_maintenance_workers=0' "$CONTAINER" bash -o pipefail -c "
  pg_restore --no-owner --no-acl -f - '$DUMP' \
  | awk '/^REFRESH MATERIALIZED VIEW/ && !done { print \"ANALYZE;\"; done = 1 } { print }' \
  | psql -U '$USER_' -d '$DB' -q -X -v ON_ERROR_STOP=1 --single-transaction >/dev/null"

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
# the precedent side's signature (D-183): sources, documents, blocks, every active judgment and its paragraph
# texts, and every link, review and evidence row; the judgment prune must leave all of it unchanged
jbefore=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT concat_ws(',',
      (SELECT count(*) FROM judgment_source),
      (SELECT count(*) FROM judgment_document),
      (SELECT count(*) FROM judgment_block),
      (SELECT count(*) FROM judgment WHERE is_active),
      (SELECT count(*) FROM v_release_judgment),
      (SELECT count(*) FROM v_release_judgment_paragraph),
      (SELECT count(*) FROM judgment_statute_reference),
      (SELECT count(*) FROM judgment_case_reference),
      (SELECT count(*) FROM judgment_chunk),
      (SELECT count(*) FROM case_treatment),
      (SELECT count(*) FROM judicial_invalidation_candidate),
      (SELECT count(*) FROM judgment_recorded_outcome),
      (SELECT count(*) FROM judgment_lineage l JOIN judgment j ON j.id=l.upper_judgment_id WHERE j.is_active),
      (SELECT md5(string_agg(p.id::text||':'||md5(coalesce(p.text,'')),',' ORDER BY p.id))
         FROM judgment_paragraph p JOIN judgment j ON j.id=p.judgment_id AND j.decided_on IS NOT DISTINCT FROM p.decided_on
        WHERE j.is_active));")
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

# D-183: retired judgment reads, in the same restored copy (PRUNE_JUDGMENTS=0 skips)
if [[ "${PRUNE_JUDGMENTS:-1}" != 0 ]]; then
  docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -f /etc/postgresql/migrations/0148_judgment_revision_archive_manifest.sql >/dev/null
  # 0149: without indexes under the foreign keys, the paragraph DELETE ran 5 h 14 min and was stopped (28 Nov 2026)
  docker exec -e PGOPTIONS='-c max_parallel_maintenance_workers=0' "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -f /etc/postgresql/migrations/0149_judgment_foreign_key_indexes.sql >/dev/null
  docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -c \
    "INSERT INTO revision_archive_batch
       (archive_file,archive_sha256,database_size_before,detail)
     VALUES ('$DUMP','$SHA',$size,
             jsonb_build_object('scope','retired judgment reads only',
                                'restore_verified',true,'purpose','isolated prune test'));"
  docker cp "$ROOT/tools/prune_retired_judgments.sql" "$CONTAINER:/tmp/prune_retired_judgments.sql" >/dev/null
  docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -f /tmp/prune_retired_judgments.sql
  jafter=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
    "SELECT concat_ws(',',
      (SELECT count(*) FROM judgment_source),
      (SELECT count(*) FROM judgment_document),
      (SELECT count(*) FROM judgment_block),
      (SELECT count(*) FROM judgment WHERE is_active),
      (SELECT count(*) FROM v_release_judgment),
      (SELECT count(*) FROM v_release_judgment_paragraph),
      (SELECT count(*) FROM judgment_statute_reference),
      (SELECT count(*) FROM judgment_case_reference),
      (SELECT count(*) FROM judgment_chunk),
      (SELECT count(*) FROM case_treatment),
      (SELECT count(*) FROM judicial_invalidation_candidate),
      (SELECT count(*) FROM judgment_recorded_outcome),
      (SELECT count(*) FROM judgment_lineage l JOIN judgment j ON j.id=l.upper_judgment_id WHERE j.is_active),
      (SELECT md5(string_agg(p.id::text||':'||md5(coalesce(p.text,'')),',' ORDER BY p.id))
         FROM judgment_paragraph p JOIN judgment j ON j.id=p.judgment_id AND j.decided_on IS NOT DISTINCT FROM p.decided_on
        WHERE j.is_active));")
  if [[ "$jbefore" != "$jafter" ]]; then
    echo "precedent source/evidence/active/release state changed: before=$jbefore after=$jafter" >&2
    exit 1
  fi
  echo "precedent signature unchanged: $jafter"
fi

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
