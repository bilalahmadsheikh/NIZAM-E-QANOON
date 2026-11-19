#!/usr/bin/env bash
# Export the WHOLE PostgreSQL cluster byte-for-byte, for an exact copy.
#
#   bash infra/scripts/export-physical.sh        # or: ./nz export --physical
#
# Writes ${CORPUS_ROOT}/snapshots/exports/physical-<stamp>/
#   base.tar.gz       the data directory: every database, table, index, view,
#                     materialized view, function, statistic and setting stored
#                     in the cluster, exactly as the pages lie on disk
#   pg_wal.tar.gz     the write-ahead log needed to make that copy consistent
#   backup_manifest   PostgreSQL's own per-file checksums for the backup
#   SHA256SUMS        sha256 of the three files above
#   manifest.json     image digest, server version, git commit, corpus signature
#   encoder/          when an embedding generation is active (D-098): its query
#                     encoder and SHA256SUMS (scripts/encoder-bundle.sh) -- the
#                     vectors are in the cluster, the model that reads questions
#                     into their space is not
#
# pg_basebackup takes it online: the database keeps running and the copy is
# consistent as of the end of the backup (-X stream carries the WAL).  The
# receiver must run the SAME image (compose.yaml pins it by digest) on the same
# CPU architecture; restore-physical.sh refuses otherwise.
#
# Compared with export.sh (a logical pg_dump): ~3x larger, but nothing is
# rebuilt on arrival -- indexes, statistics and bloat arrive as they are.  Doc
# 09a §1.1 plans exactly this (as pgBackRest) for the judgment-scale corpus.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # infra/
[ -f .env ] && set -a && . ./.env && set +a

SERVICE=postgres
DB="${POSTGRES_DB:-nizam_clean}"
USER_="${POSTGRES_USER:-nizam}"
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/e/nizam-data}"
SNAP_DIR="${CORPUS_ROOT}/snapshots"

dc() { docker compose -f "$(pwd)/compose.yaml" "$@"; }
psql_() { dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -tAc "$1" | tr -d '\r'; }
. scripts/encoder-bundle.sh

dc ps --status running --services 2>/dev/null | grep -qx "$SERVICE" \
  || { echo "export-physical: postgres is not running (./nz up)"; exit 1; }

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
NAME="physical-${STAMP}"
OUT="${SNAP_DIR}/exports/${NAME}"
mkdir -p "${SNAP_DIR}/exports"

echo "export-physical: base backup of the cluster (data directory $(dc exec -T "$SERVICE" du -sh /var/lib/postgresql/data | cut -f1))"
# Written to a partial directory, promoted only when complete.
dc exec -T "$SERVICE" pg_basebackup -U "$USER_" -h /var/run/postgresql \
  -D "/snapshots/exports/.partial-${NAME}" -Ft -z -X stream -c fast \
  --manifest-checksums=SHA256
dc exec -T "$SERVICE" mv "/snapshots/exports/.partial-${NAME}" "/snapshots/exports/${NAME}"

# The signature is read after the backup finished; the restore compares it.
# If the database was written during the backup the two can differ, and the
# restore says so rather than passing quietly.
SIG=$(dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -tA < scripts/corpus-signature.sql | tr -d '\r')
GEN=$(bundle_encoder "$OUT")        # refuses if a generation is active and its encoder is not installed
( cd "$OUT" && sha256sum base.tar.gz pg_wal.tar.gz backup_manifest > SHA256SUMS )
IMAGE=$(awk '/image: paradedb/ {print $2; exit}' compose.yaml)
COMMIT=$(git -C .. rev-parse HEAD 2>/dev/null || echo unknown)
BRANCH=$(git -C .. rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)
SIZE=$(du -cb "$OUT"/base.tar.gz "$OUT"/pg_wal.tar.gz | tail -1 | cut -f1)

cat > "$OUT/manifest.json" <<JSON
{
  "kind": "physical",
  "files": ["base.tar.gz", "pg_wal.tar.gz", "backup_manifest"],
  "bytes": ${SIZE},
  "database": "${DB}",
  "taken_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "server_version": "$(psql_ 'SHOW server_version')",
  "server_version_num": "$(psql_ 'SHOW server_version_num')",
  "architecture": "$(dc exec -T "$SERVICE" uname -m | tr -d '\r')",
  "postgres_image": "${IMAGE}",
  "git_commit": "${COMMIT}",
  "git_branch": "${BRANCH}",
  "signature": "${SIG}",
  "embedding_generation": "${GEN}"
}
JSON

echo "export-physical: wrote ${OUT} ($(numfmt --to=iec "$SIZE"))"
echo "  signature: ${SIG}"
cat <<EOF

To give this to a teammate:
  1. Send the folder ${NAME}/ (all five files, and encoder/ when present).
  2. They check out commit ${COMMIT:0:12} (${BRANCH}) and run ./nz up once.
  3. They copy the folder into \${CORPUS_ROOT}/snapshots/exports/ and run
       ./nz restore --physical exports/${NAME}
     which checks every checksum and the image, replaces their cluster with
     this one, and compares the signature.
EOF
