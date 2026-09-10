#!/usr/bin/env bash
# Restore a snapshot into the running database.
#
# This is how a teammate gets the corpus without parsing a single PDF, and it is
# the same procedure that recovers the database after a mistake -- doc 09a §1.1:
# "the procedure that gives a new developer a corpus is the same procedure that
# recovers production, so it gets exercised weekly rather than discovered during
# an incident."
#
#   bash infra/scripts/restore.sh                    # newest snapshot
#   bash infra/scripts/restore.sh nizam-2026...dump  # a specific one
#   bash infra/scripts/restore.sh --list
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # infra/
[ -f .env ] && set -a && . ./.env && set +a

SERVICE=postgres
DB="${POSTGRES_DB:-nizam_clean}"
USER_="${POSTGRES_USER:-nizam}"
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/e/nizam-data}"
SNAP_DIR="${CORPUS_ROOT}/snapshots"

dc() { docker compose -f "$(pwd)/compose.yaml" "$@"; }

if [ "${1:-}" = "--list" ]; then
  ls -1t "${SNAP_DIR}"/nizam-*.dump 2>/dev/null | while read -r f; do
    printf '%s  %s\n' "$(numfmt --to=iec "$(stat -c%s "$f")" 2>/dev/null)" "$(basename "$f")"
  done
  [ -f "${SNAP_DIR}/latest.json" ] && { echo; cat "${SNAP_DIR}/latest.json"; }
  exit 0
fi

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  TARGET=$(basename "$(readlink -f "${SNAP_DIR}/latest.dump" 2>/dev/null || true)")
  [ -n "$TARGET" ] || { echo "no snapshots in ${SNAP_DIR} -- run snapshot.sh first"; exit 1; }
fi
[ -f "${SNAP_DIR}/${TARGET}" ] || { echo "not found: ${SNAP_DIR}/${TARGET}"; exit 1; }

echo "This REPLACES every object in database '${DB}' with the contents of ${TARGET}."
read -rp "type the database name to confirm: " confirm
[ "$confirm" = "$DB" ] || { echo "aborted"; exit 1; }

# --clean --if-exists drops each object before recreating it, so a restore over
# a populated database is deterministic rather than a merge.
dc exec -T "$SERVICE" pg_restore -U "$USER_" -d "$DB" \
  --clean --if-exists --no-owner --no-acl --single-transaction \
  "/snapshots/${TARGET}"

echo
echo "restored ${TARGET}. Tables now present:"
dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -c \
  "SELECT schemaname, relname, n_live_tup AS rows FROM pg_stat_user_tables ORDER BY 1,2;"
