#!/usr/bin/env bash
# Restore a snapshot or an export into the running database.
#
# This is how a teammate gets the corpus without parsing a single PDF, and it is
# the same procedure that recovers the database after a mistake -- doc 09a §1.1:
# "the procedure that gives a new developer a corpus is the same procedure that
# recovers production, so it gets exercised weekly rather than discovered during
# an incident."
#
#   bash infra/scripts/restore.sh                         # newest snapshot of this database
#   bash infra/scripts/restore.sh nizam_clean-2026...dump  # a specific snapshot
#   bash infra/scripts/restore.sh exports/<name>/<name>.dump   # an export (./nz export)
#   bash infra/scripts/restore.sh --list
#
# Paths are relative to ${CORPUS_ROOT}/snapshots, the directory the container
# sees as /snapshots.
#
# Safety, each learned the hard way:
#   * The newest snapshot is the one for THIS database.  The old default read
#     latest.dump, which belongs to the retired `nizam` database (6 Sep 2026),
#     so a bare restore would have rolled nizam_clean back two months.
#   * A dump made from a different database is refused; pass --any-source only
#     when that is the intent.
#   * A sidecar <file>.sha256 is verified before anything is dropped.
#   * A manifest.json beside the dump carries the corpus signature; the restore
#     recomputes it and fails loudly if the two differ.
#
# Environment:
#   RESTORE_DB=<name>              restore into another database (created if missing),
#                                  e.g. a scratch database for a round-trip check
#   NIZAM_RESTORE_CONFIRM=<name>   skip the interactive prompt (must equal the target)
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # infra/
[ -f .env ] && set -a && . ./.env && set +a

SERVICE=postgres
SOURCE_DB="${POSTGRES_DB:-nizam_clean}"
DB="${RESTORE_DB:-$SOURCE_DB}"
USER_="${POSTGRES_USER:-nizam}"
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/e/nizam-data}"
SNAP_DIR="${CORPUS_ROOT}/snapshots"

# Same naming as snapshot.sh: the historical `nizam` database kept the bare names.
SAFE_DB=$(printf '%s' "$SOURCE_DB" | tr -c 'A-Za-z0-9_.-' '_')
if [ "$SOURCE_DB" = nizam ]; then PREFIX=nizam; LATEST=latest
else PREFIX="$SAFE_DB"; LATEST="latest-${SAFE_DB}"; fi

dc() { docker compose -f "$(pwd)/compose.yaml" "$@"; }
die() { echo "restore: $*" >&2; exit 1; }

ANY_SOURCE=0
args=()
for a in "$@"; do
  case "$a" in --any-source) ANY_SOURCE=1 ;; *) args+=("$a") ;; esac
done
set -- "${args[@]+"${args[@]}"}"

if [ "${1:-}" = "--list" ]; then
  ls -1t "${SNAP_DIR}"/${PREFIX}-*.dump "${SNAP_DIR}"/exports/*/*.dump 2>/dev/null | while read -r f; do
    printf '%8s  %s\n' "$(numfmt --to=iec "$(stat -c%s "$f")" 2>/dev/null)" "${f#${SNAP_DIR}/}"
  done
  [ -f "${SNAP_DIR}/${LATEST}.json" ] && { echo; cat "${SNAP_DIR}/${LATEST}.json"; }
  exit 0
fi

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  TARGET=$(basename "$(readlink -f "${SNAP_DIR}/${LATEST}.dump" 2>/dev/null || true)")
  [ -n "$TARGET" ] && [ "$TARGET" != "${LATEST}.dump" ] \
    || die "no snapshot of ${SOURCE_DB} in ${SNAP_DIR} -- run snapshot.sh first"
fi
TARGET="${TARGET#/snapshots/}"
HOST_FILE="${SNAP_DIR}/${TARGET}"
[ -f "$HOST_FILE" ] || die "not found: ${HOST_FILE}"

if [ -f "${HOST_FILE}.sha256" ]; then
  want=$(cut -d' ' -f1 "${HOST_FILE}.sha256")
  echo "restore: checking sha256 of $(basename "$HOST_FILE")"
  have=$(sha256sum "$HOST_FILE" | cut -d' ' -f1)
  [ "$want" = "$have" ] || die "sha256 mismatch: the file is damaged or incomplete (want ${want:0:16}, have ${have:0:16})"
fi

dc ps --status running --services 2>/dev/null | grep -qx "$SERVICE" \
  || die "postgres is not running (./nz up)"

DUMP_DB=$(dc exec -T "$SERVICE" pg_restore --list "/snapshots/${TARGET}" \
            | sed -n 's/^;[[:space:]]*dbname:[[:space:]]*//Ip' | head -1 | tr -d '\r[:space:]')
[ -n "$DUMP_DB" ] || die "not a pg_dump custom-format archive: ${TARGET}"
if [ "$DUMP_DB" != "$SOURCE_DB" ] && [ "$ANY_SOURCE" -eq 0 ]; then
  die "${TARGET} was dumped from database '${DUMP_DB}', not '${SOURCE_DB}' (pass --any-source if that is intended)"
fi

echo "This REPLACES every object in database '${DB}' with the contents of ${TARGET} (from '${DUMP_DB}')."
if [ "${NIZAM_RESTORE_CONFIRM:-}" != "$DB" ]; then
  read -rp "type the database name to confirm: " confirm
  [ "$confirm" = "$DB" ] || die "aborted"
fi

exists=$(dc exec -T "$SERVICE" psql -U "$USER_" -d postgres -tAc \
           "SELECT 1 FROM pg_database WHERE datname='${DB}'" | tr -d '[:space:]')
if [ "$exists" != 1 ]; then
  echo "restore: creating database ${DB}"
  dc exec -T "$SERVICE" createdb -U "$USER_" -T template0 -E UTF8 \
    --locale=en_US.UTF-8 "$DB"
fi

# --clean --if-exists drops each object before recreating it, so a restore over
# a populated database is deterministic rather than a merge.  One transaction:
# a failure leaves the database exactly as it was.
#
# pg_restore -d would refresh the materialized views (the serving snapshot,
# migrations 0094/0096) right after building indexes, on tables with NO planner
# statistics.  On 17 Nov 2026 that refresh of mv_instrument_serving ran past 35
# minutes before it was stopped.  So the archive is replayed as SQL through psql, with
# an ANALYZE injected before the first REFRESH MATERIALIZED VIEW.  ANALYZE is
# legal inside a transaction, so the restore stays atomic.
started=$(date +%s)
dc exec -T "$SERVICE" bash -o pipefail -c "
  pg_restore --clean --if-exists --no-owner --no-acl -f - '/snapshots/${TARGET}' \
  | awk '/^REFRESH MATERIALIZED VIEW/ && !done { print \"ANALYZE;\"; done = 1 } { print }' \
  | psql -U '$USER_' -d '$DB' -q -X -v ON_ERROR_STOP=1 --single-transaction >/dev/null"
dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -qc "ANALYZE"
echo "restore: restored ${TARGET} into ${DB} in $(( $(date +%s) - started ))s"

SIG=$(dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -tA < scripts/corpus-signature.sql | tr -d '\r')
echo "restore: signature ${SIG}"
MANIFEST="$(dirname "$HOST_FILE")/manifest.json"
if [ -f "$MANIFEST" ]; then
  WANT_SIG=$(sed -n 's/^ *"signature": *"\(.*\)",\{0,1\}$/\1/p' "$MANIFEST")
  if [ "$WANT_SIG" = "$SIG" ]; then
    echo "restore: signature matches manifest.json"
  else
    echo "restore: SIGNATURE DIFFERS from manifest.json" >&2
    echo "  want ${WANT_SIG}" >&2
    exit 1
  fi
fi
