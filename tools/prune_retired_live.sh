#!/usr/bin/env bash
# Apply the restore-tested retired *derived instrument* prune to nizam_clean.
# Source PDFs, observations, documents, pages, text blocks, OCR and extraction
# evidence are outside the delete set.
set -euo pipefail

DUMP="${1:?usage: tools/prune_retired_live.sh /snapshots/name.dump SHA256}"
SHA="${2:?usage: tools/prune_retired_live.sh /snapshots/name.dump SHA256}"
DB="${NIZAM_CLEAN_DB:-nizam_clean}"
CONTAINER="${NIZAM_POSTGRES_CONTAINER:-nizam-postgres}"
USER_="${POSTGRES_USER:-nizam}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_DUMP="/mnt/e/nizam-data/snapshots/${DUMP#/snapshots/}"

[[ "$DB" == "nizam_clean" ]] || { echo "refusing target database: $DB" >&2; exit 1; }
[[ "$DUMP" == /snapshots/nizam_clean-*.dump ]] || { echo "refusing archive path: $DUMP" >&2; exit 1; }
[[ -f "$HOST_DUMP" ]] || { echo "archive not found: $HOST_DUMP" >&2; exit 1; }
actual=$(sha256sum "$HOST_DUMP" | awk '{print $1}')
[[ "$actual" == "$SHA" ]] || { echo "archive SHA mismatch" >&2; exit 1; }
docker exec "$CONTAINER" pg_restore --list "$DUMP" >/dev/null

pending=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT count(*) FROM revision_archive_batch WHERE pruned_at IS NULL")
size=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT pg_database_size(current_database())")
signature=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT concat_ws(',',
      (SELECT count(*) FROM instrument WHERE is_active),
      (SELECT count(*) FROM provision p JOIN instrument i ON i.id=p.instrument_id WHERE i.is_active),
      (SELECT count(*) FROM v_release_instrument),
      (SELECT count(*) FROM v_release_provision),
      (SELECT count(*) FROM v_structural_adjudication_pending),
      (SELECT count(*) FROM v_boundary_adjudication_pending));")

if [[ "$pending" == 0 ]]; then
  docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -c \
    "INSERT INTO revision_archive_batch
       (archive_file,archive_sha256,database_size_before,detail)
     VALUES ('$DUMP','$SHA',$size,
             jsonb_build_object('scope','retired segmentation revisions only',
                                'restore_verified',true,
                                'restore_signature','$signature'));"
elif [[ "$pending" == 1 ]]; then
  reusable=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
    "SELECT count(*) FROM revision_archive_batch b
      WHERE b.pruned_at IS NULL AND b.archive_file='$DUMP'
        AND b.archive_sha256='$SHA'
        AND b.detail->>'scope'='retired segmentation revisions only'
        AND NOT EXISTS (SELECT 1 FROM instrument_revision_archive_manifest m
                         WHERE m.batch_id=b.id)")
  [[ "$reusable" == 1 ]] || { echo "pending archive batch is not safely reusable" >&2; exit 1; }
  echo "reusing empty archive batch left by the rolled-back prune"
else
  echo "multiple unresolved archive batches" >&2; exit 1
fi
docker cp "$ROOT/tools/prune_retired_instruments.sql" \
  "$CONTAINER:/tmp/prune_retired_instruments.sql" >/dev/null
docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 \
  -f /tmp/prune_retired_instruments.sql
