#!/usr/bin/env bash
# Restore a custom-format dump into an isolated database and prove core counts.
set -euo pipefail

DUMP="${1:?usage: verify_snapshot.sh /snapshots/name.dump}"
DB="nizam_restore_verify"
LIVE_DB="${NIZAM_CLEAN_DB:-nizam_clean}"
CONTAINER="${NIZAM_POSTGRES_CONTAINER:-nizam-postgres}"
USER_="${POSTGRES_USER:-nizam}"

signature_sql="SELECT concat_ws('|',
  (SELECT count(*) FROM source_observation),
  (SELECT count(*) FROM document WHERE is_active),
  (SELECT count(*) FROM instrument WHERE is_active),
  (SELECT count(*) FROM provision p JOIN instrument i
            ON i.id=p.instrument_id WHERE i.is_active),
  (SELECT count(*) FROM v_release_instrument),
  (SELECT count(*) FROM v_release_provision),
  (SELECT count(*) FROM v_release_provision_version),
  (SELECT count(*) FROM v_structural_adjudication_pending),
  (SELECT count(*) FROM v_boundary_adjudication_pending));"

cleanup() {
  docker exec "$CONTAINER" dropdb -U "$USER_" --if-exists "$DB" >/dev/null
}
trap cleanup EXIT

docker exec "$CONTAINER" pg_restore --list "$DUMP" >/dev/null
cleanup
docker exec "$CONTAINER" createdb -U "$USER_" "$DB"
docker exec "$CONTAINER" pg_restore -U "$USER_" -d "$DB" \
  --no-owner --no-acl "$DUMP"
live_signature="$(docker exec "$CONTAINER" psql -U "$USER_" -d "$LIVE_DB" -Atc "$signature_sql")"
restored_signature="$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc "$signature_sql")"
printf '%s\n' 'observations|active_documents|active_instruments|active_provisions|release_instruments|release_provisions|release_versions|s7_pending|s10_pending'
printf '%s\n' "$restored_signature"
if [[ "$restored_signature" != "$live_signature" ]]; then
  printf 'restore signature differs from live %s:\nrestore %s\nlive    %s\n' \
    "$LIVE_DB" "$restored_signature" "$live_signature" >&2
  exit 1
fi
echo "snapshot restore exactly matches $LIVE_DB; temporary database removed"
