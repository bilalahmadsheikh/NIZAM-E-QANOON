#!/usr/bin/env bash
# Export the corpus database as one portable file for a teammate.
#
#   bash infra/scripts/export.sh          # or: ./nz export
#
# Writes ${CORPUS_ROOT}/snapshots/exports/<db>-<stamp>/ containing
#   <db>-<stamp>.dump         pg_dump custom format (compressed, every table,
#                             view, function, materialized view and extension)
#   <db>-<stamp>.dump.sha256  checksum the restore verifies before it touches
#                             anything
#   manifest.json             server version, image digest, git commit and the
#                             corpus signature the restore must reproduce
#   encoder/                  when an embedding generation is active (D-098): the
#                             query encoder it needs (model.onnx, tokenizer.json,
#                             encoder.json, validation evidence) and SHA256SUMS --
#                             the vectors are in the dump, but a question can only
#                             be compared with them through this exact model
#   encoder-gpu/              when the GPU generation is active (D-099): the bundle
#                             its GPU-host encoder service is validated against
#                             (encoder.json, reference question vectors) and SHA256SUMS
#
# A logical dump rather than a copy of the data directory: the dump is ~0.65 GB
# against a 6.4 GB data directory, it does not need the receiver's container to
# be stopped, and indexes are rebuilt on restore -- minutes: the HNSW index alone
# took 3.5 min to build on 19 Nov (D-098).  Doc 09a §1.1 plans a physical pgBackRest backup for the
# judgment-scale corpus; until then this is the transfer format.
#
# Exports live under snapshots/exports/, outside the snapshot timer's
# retention (which prunes only <db>-*.dump at the top level).
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # infra/
[ -f .env ] && set -a && . ./.env && set +a

SERVICE=postgres
DB="${NIZAM_TARGET_DB:-${POSTGRES_DB:-nizam_clean}}"
USER_="${POSTGRES_USER:-nizam}"
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/e/nizam-data}"
SNAP_DIR="${CORPUS_ROOT}/snapshots"

dc() { docker compose -f "$(pwd)/compose.yaml" "$@"; }
psql_() { dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -tAc "$1"; }
. scripts/encoder-bundle.sh

dc ps --status running --services 2>/dev/null | grep -qx "$SERVICE" \
  || { echo "export: postgres is not running (./nz up)"; exit 1; }

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
NAME="${DB}-${STAMP}"
OUT="${SNAP_DIR}/exports/${NAME}"
mkdir -p "$OUT"

echo "export: dumping ${DB} ($(psql_ "SELECT pg_size_pretty(pg_database_size(current_database()))" | tr -d '[:space:]') on disk)"
# Same flags as snapshot.sh.  The dump is consistent: pg_dump reads one MVCC
# snapshot, so writes during the export are simply not in it.
dc exec -T "$SERVICE" pg_dump -U "$USER_" -d "$DB" -Fc --no-owner --no-acl \
  -f "/snapshots/exports/${NAME}/.partial-${NAME}.dump"
dc exec -T "$SERVICE" mv "/snapshots/exports/${NAME}/.partial-${NAME}.dump" \
  "/snapshots/exports/${NAME}/${NAME}.dump"

SIG=$(dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -tA < scripts/corpus-signature.sql | tr -d '\r')
GEN=$(bundle_encoder "$OUT")        # the query encoder the dump's vectors need (D-098); refuses if it is missing
GEN_GPU=$(bundle_encoder_gpu "$OUT")  # the GPU generation's validation bundle (D-099); refuses if it is missing
( cd "$OUT" && sha256sum "${NAME}.dump" > "${NAME}.dump.sha256" )
SHA=$(cut -d' ' -f1 "$OUT/${NAME}.dump.sha256")
SIZE=$(stat -c%s "$OUT/${NAME}.dump")
IMAGE=$(awk '/image: paradedb/ {print $2; exit}' compose.yaml)
COMMIT=$(git -C .. rev-parse HEAD 2>/dev/null || echo unknown)
BRANCH=$(git -C .. rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)

cat > "$OUT/manifest.json" <<JSON
{
  "file": "${NAME}.dump",
  "bytes": ${SIZE},
  "sha256": "${SHA}",
  "database": "${DB}",
  "taken_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "server_version": "$(psql_ 'SHOW server_version' | tr -d '\r')",
  "postgres_image": "${IMAGE}",
  "git_commit": "${COMMIT}",
  "git_branch": "${BRANCH}",
  "signature": "${SIG}",
  "embedding_generation": "${GEN:-none}",
  "embedding_generation_gpu": "${GEN_GPU:-none}"
}
JSON

echo "export: wrote ${OUT}"
echo "  ${NAME}.dump  $(numfmt --to=iec "$SIZE")  sha256 ${SHA:0:16}..."
echo "  signature: ${SIG}"
cat <<EOF

To give this to a teammate:
  1. Send the folder ${NAME}/ (every file, and encoder/ and encoder-gpu/ when present).
  2. They check out commit ${COMMIT:0:12} (${BRANCH}) and run ./nz up.
  3. They copy the folder into \${CORPUS_ROOT}/snapshots/exports/ and run
       ./nz restore exports/${NAME}/${NAME}.dump
     which checks the sha256, restores, and compares the signature.
EOF
