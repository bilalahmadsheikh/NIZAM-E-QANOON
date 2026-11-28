#!/usr/bin/env bash
# Apply the restore-tested retired judgment-read prune (D-183) to nizam_clean. Run only after
# tools/test_prune_retired.sh passed on the SAME archive (it restores the archive and proves both prunes), and after
# tools/prune_retired_live.sh (the statute prune) has closed its batch. Documents, page blocks, sources and every
# reviewed or evidence row are outside the delete set.
set -euo pipefail

DUMP="${1:?usage: tools/prune_retired_judgments_live.sh /snapshots/name.dump SHA256}"
SHA="${2:?usage: tools/prune_retired_judgments_live.sh /snapshots/name.dump SHA256}"
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
[[ "$pending" == 0 ]] || { echo "an archive batch is still open: close it first" >&2; exit 1; }
fk_ix=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT count(*) FROM pg_indexes WHERE indexname IN ('ix_jsr_paragraph','ix_jcr_paragraph','ix_jcr_judgment',
     'ix_judgment_paragraph_opinion','ix_judgment_lineage_upper','ix_lineage_link_upper','ix_invalidation_candidate_judgment')")
[[ "$fk_ix" == 7 ]] || { echo "apply migration 0149 first (foreign-key indexes: $fk_ix of 7)" >&2; exit 1; }
size=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc "SELECT pg_database_size(current_database())")
signature=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT concat_ws(',', (SELECT count(*) FROM judgment WHERE is_active), (SELECT count(*) FROM v_release_judgment),
                         (SELECT count(*) FROM v_release_judgment_paragraph), (SELECT count(*) FROM judgment_document),
                         (SELECT count(*) FROM judgment_block));")
docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -c \
  "INSERT INTO revision_archive_batch (archive_file,archive_sha256,database_size_before,detail)
   VALUES ('$DUMP','$SHA',$size, jsonb_build_object('scope','retired judgment reads only','restore_verified',true,
                                                    'restore_signature','$signature'));"
docker cp "$ROOT/tools/prune_retired_judgments.sql" "$CONTAINER:/tmp/prune_retired_judgments.sql" >/dev/null
docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -f /tmp/prune_retired_judgments.sql
after=$(docker exec "$CONTAINER" psql -U "$USER_" -d "$DB" -Atc \
  "SELECT concat_ws(',', (SELECT count(*) FROM judgment WHERE is_active), (SELECT count(*) FROM v_release_judgment),
                         (SELECT count(*) FROM v_release_judgment_paragraph), (SELECT count(*) FROM judgment_document),
                         (SELECT count(*) FROM judgment_block));")
[[ "$signature" == "$after" ]] || { echo "release signature changed: $signature -> $after" >&2; exit 1; }
echo "judgment prune applied; release signature unchanged: $after"
