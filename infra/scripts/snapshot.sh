#!/usr/bin/env bash
# Snapshot the corpus database -- only after a change, and only once it settles.
#
# Two gates, not one:
#
#   1. CHANGED   -- the write-ahead log position differs from the last snapshot.
#                   pg_current_wal_lsn() advances on every write and on nothing
#                   else, so an idle database costs one query and exits.
#   2. SETTLED   -- the WAL has not moved since the previous tick either.
#
# The second gate is what keeps this cheap. A full corpus ingest writes
# continuously for hours; without it, a 15-minute timer would dump the whole
# database twelve times during that ingest, each dump larger than the last and
# every one of them obsolete before it finished. With it, a long ingest produces
# exactly one snapshot, taken one interval after the writes stop.
#
#   bash infra/scripts/snapshot.sh          # respect both gates
#   bash infra/scripts/snapshot.sh --force  # ignore both
#
# Why a dump and not a rebuilt Docker image: image layers are immutable and
# content-addressed, so every snapshot would rewrite and re-push the whole
# database as a new layer -- no incremental, and ~10 GB once judgments land. Doc
# 09a §1.1 ships the corpus as a backup a teammate restores, not an image they
# pull. At judgment scale, replace this with pgBackRest incrementals, which ship
# only changed blocks; the interface here (snapshot / restore) stays the same.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # infra/
[ -f .env ] && set -a && . ./.env && set +a

SERVICE=postgres
DB="${NIZAM_TARGET_DB:-${POSTGRES_DB:-nizam_clean}}"
USER_="${POSTGRES_USER:-nizam}"
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/e/nizam-data}"
SNAP_DIR="${CORPUS_ROOT}/snapshots"
KEEP="${SNAPSHOT_KEEP:-8}"
BUDGET_GB="${SNAPSHOT_BUDGET_GB:-25}"     # total disk the snapshots may occupy
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

# Keep change cursors, latest pointers and retention independent per database.
# The historical/default nizam names stay unchanged for compatibility.
SAFE_DB=$(printf '%s' "$DB" | tr -c 'A-Za-z0-9_.-' '_')
if [ "$DB" = nizam ]; then
  PREFIX=nizam; TICK_FILE=.tick.lsn; LAST_FILE=last.lsn; LATEST=latest
else
  PREFIX="$SAFE_DB"; TICK_FILE=".tick-${SAFE_DB}.lsn"
  LAST_FILE="last-${SAFE_DB}.lsn"; LATEST="latest-${SAFE_DB}"
fi

dc() { docker compose -f "$(pwd)/compose.yaml" "$@"; }
psql_() { dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -tAc "$1"; }

if ! dc ps --status running --services 2>/dev/null | grep -qx "$SERVICE"; then
  echo "snapshot: postgres is not running, nothing to do"; exit 0
fi

mkdir -p "$SNAP_DIR"
LSN=$(psql_ "SELECT pg_current_wal_lsn()" | tr -d '[:space:]')
SNAP_LSN=$(cat "${SNAP_DIR}/${LAST_FILE}" 2>/dev/null || echo "")
TICK_LSN=$(cat "${SNAP_DIR}/${TICK_FILE}" 2>/dev/null || echo "")
printf '%s' "$LSN" > "${SNAP_DIR}/${TICK_FILE}"

# Distance in bytes, not equality. An idle PostgreSQL still moves the WAL a
# little on its own -- autovacuum, the stats collector, and pg_dump itself all
# write. Comparing LSNs for equality would therefore treat background noise as a
# change and snapshot forever. Comparing distance separates real writes (MBs)
# from housekeeping (KBs).
wal_gap() { psql_ "SELECT pg_wal_lsn_diff('${1}'::pg_lsn, '${2}'::pg_lsn)::bigint" | tr -d '[:space:]'; }
MIN_BYTES=$(( ${SNAPSHOT_MIN_WAL_MB:-1} * 1024 * 1024 ))
SETTLE_BYTES=$(( ${SNAPSHOT_SETTLE_KB:-64} * 1024 ))

if [ "$FORCE" -eq 0 ]; then
  if [ -n "$SNAP_LSN" ]; then
    written=$(wal_gap "$LSN" "$SNAP_LSN")
    if [ "${written:-0}" -lt "$MIN_BYTES" ]; then
      echo "snapshot: only $(numfmt --to=iec "${written:-0}" 2>/dev/null || echo "${written}B") written since the last snapshot (threshold $(numfmt --to=iec $MIN_BYTES)), skipping"
      exit 0
    fi
  fi
  if [ -n "$TICK_LSN" ]; then
    moving=$(wal_gap "$LSN" "$TICK_LSN")
    if [ "${moving:-0}" -gt "$SETTLE_BYTES" ]; then
      echo "snapshot: still being written ($(numfmt --to=iec "${moving:-0}" 2>/dev/null) since the last check), waiting for it to settle"
      exit 0
    fi
  else
    echo "snapshot: first check, recording position -- will snapshot next tick if it settles"
    exit 0
  fi
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
NAME="${PREFIX}-${STAMP}.dump"
echo "snapshot: settled at ${LSN} (last snapshot ${SNAP_LSN:-none}) -- dumping to ${NAME}"

# -Fc is the custom format: compressed, and pg_restore can read it selectively.
# Written inside the container to /snapshots, which is bind-mounted to E:.
dc exec -T "$SERVICE" pg_dump -U "$USER_" -d "$DB" -Fc --no-owner --no-acl \
  -f "/snapshots/.partial-${NAME}"
# Promote atomically so a half-written dump is never mistaken for a good one.
dc exec -T "$SERVICE" mv "/snapshots/.partial-${NAME}" "/snapshots/${NAME}"

ln -sfn "$NAME" "${SNAP_DIR}/${LATEST}.dump"
printf '%s' "$LSN" > "${SNAP_DIR}/${LAST_FILE}"

SIZE=$(stat -c%s "${SNAP_DIR}/${NAME}" 2>/dev/null || echo 0)
cat > "${SNAP_DIR}/${LATEST}.json" <<JSON
{
  "file": "${NAME}",
  "bytes": ${SIZE},
  "wal_lsn": "${LSN}",
  "taken_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "database": "${DB}",
  "database_size": "$(psql_ "SELECT pg_size_pretty(pg_database_size(current_database()))" | tr -d '[:space:]')",
  "server_version": "$(psql_ 'SHOW server_version' | tr -d '[:space:]')",
  "collation": "$(psql_ "SELECT datcollate FROM pg_database WHERE datname=current_database()" | tr -d '[:space:]')"
}
JSON

# --- retention: a count cap and a disk budget --------------------------------
# The count alone is not enough. Eight snapshots of today's 17 MB database is
# 4 MB; eight of the full judgment corpus would be tens of gigabytes. Prune on
# whichever limit bites first, newest always kept.
prune() { echo "snapshot: pruning $(basename "$1")"; rm -f "$1"; }

ls -1t "${SNAP_DIR}"/${PREFIX}-*.dump 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  prune "$old"
done

BUDGET=$((BUDGET_GB * 1024 * 1024 * 1024))
while :; do
  files=$(ls -1t "${SNAP_DIR}"/${PREFIX}-*.dump 2>/dev/null) || break
  [ -z "$files" ] && break
  total=$(du -cb $files 2>/dev/null | tail -1 | cut -f1)
  count=$(printf '%s\n' "$files" | wc -l)
  { [ "${total:-0}" -le "$BUDGET" ] || [ "$count" -le 1 ]; } && break
  prune "$(printf '%s\n' "$files" | tail -1)"
done

TOTAL=$(du -cb "${SNAP_DIR}"/${PREFIX}-*.dump 2>/dev/null | tail -1 | cut -f1)
echo "snapshot: wrote ${NAME} ($(numfmt --to=iec "$SIZE" 2>/dev/null || echo "${SIZE}B")); \
$(ls -1 "${SNAP_DIR}"/${PREFIX}-*.dump 2>/dev/null | wc -l) kept, \
$(numfmt --to=iec "${TOTAL:-0}" 2>/dev/null || echo "${TOTAL}B") total \
(cap ${KEEP} files / ${BUDGET_GB} GB)"
