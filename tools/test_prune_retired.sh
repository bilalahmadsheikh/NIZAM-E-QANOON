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
      (SELECT count(*) FROM v_boundary_adjudication_pending));")
size=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT pg_database_size(current_database())")

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
      (SELECT count(*) FROM v_boundary_adjudication_pending));")

if [[ "$before" != "$after" ]]; then
  echo "source/evidence/active/release state changed: before=$before after=$after" >&2
  exit 1
fi

bad_manifest=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT count(*) FROM instrument_expression_manifest m
     LEFT JOIN instrument i ON i.id=m.materialized_instrument_id
    WHERE m.is_active AND (i.id IS NULL OR NOT i.is_active);")
[[ "$bad_manifest" == 0 ]] || {
  echo "active expression manifest lost its active materialization" >&2
  exit 1
}

docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -P pager=off -c \
  "SELECT '$before' AS source_evidence_active_release_signature,
          (SELECT count(*) FROM instrument WHERE NOT is_active) retained_identity_endpoints,
          (SELECT count(*) FROM instrument_revision_archive_manifest) archived_instruments,
          pg_database_size(current_database()) AS bytes_before_vacuum;"
echo "isolated prune verified; temporary database removed"
