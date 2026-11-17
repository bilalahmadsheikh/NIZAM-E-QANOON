#!/usr/bin/env bash
# Restore an exact physical copy made by export-physical.sh.
#
#   bash infra/scripts/restore-physical.sh exports/physical-<stamp>            # replace this cluster
#   bash infra/scripts/restore-physical.sh --verify exports/physical-<stamp>   # prove it, touch nothing
#
# (or ./nz restore --physical ... / ./nz restore --physical --verify ...)
#
# Replace mode stops postgres and pgAdmin. It empties the pgdata volume,
# unpacks the base backup and its WAL into it, and starts postgres again;
# PostgreSQL then replays the WAL to the consistent point the backup recorded.
# The login password is reset to this machine's infra/.env (the copy carries
# the sender's), and the corpus signature is compared with the manifest.
#
# Verify mode unpacks into a throwaway volume, starts a throwaway container
# from the same image (no published port, small shared_buffers), compares the
# signature, runs the full corpus audit, and removes both.
#
# Refuses before touching anything if a checksum fails, the image digest
# differs from compose.yaml, or the CPU architecture differs.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # infra/
[ -f .env ] && set -a && . ./.env && set +a

SERVICE=postgres
DB="${POSTGRES_DB:-nizam_clean}"
USER_="${POSTGRES_USER:-nizam}"
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/e/nizam-data}"
SNAP_DIR="${CORPUS_ROOT}/snapshots"
IMAGE=$(awk '/image: paradedb/ {print $2; exit}' compose.yaml)

dc() { docker compose -f "$(pwd)/compose.yaml" "$@"; }
die() { echo "restore-physical: $*" >&2; exit 1; }

VERIFY=0
[ "${1:-}" = "--verify" ] && { VERIFY=1; shift; }
TARGET="${1:?usage: restore-physical.sh [--verify] exports/physical-<stamp>}"
TARGET="${TARGET#/snapshots/}"; TARGET="${TARGET%/}"
DIR="${SNAP_DIR}/${TARGET}"
[ -f "${DIR}/manifest.json" ] || die "no manifest.json in ${DIR}"
field() { sed -n "s/^ *\"$1\": *\"\{0,1\}\([^\",]*\)\"\{0,1\},\{0,1\}$/\1/p" "${DIR}/manifest.json" | head -1; }

[ "$(field kind)" = physical ] || die "${TARGET} is not a physical export (use ./nz restore for a dump)"
echo "restore-physical: checking checksums"
( cd "$DIR" && sha256sum --quiet -c SHA256SUMS ) || die "checksum mismatch: the copy is damaged or incomplete"
[ "$(field postgres_image)" = "$IMAGE" ] \
  || die "image differs: backup made with $(field postgres_image), compose.yaml pins ${IMAGE}"
ARCH=$(docker run --rm --entrypoint uname "$IMAGE" -m)
[ "$(field architecture)" = "$ARCH" ] || die "architecture differs: backup $(field architecture), this machine ${ARCH}"
WANT_SIG=$(sed -n 's/^ *"signature": *"\(.*\)",\{0,1\}$/\1/p' "${DIR}/manifest.json")

# Unpack the backup into a named volume, as root, then hand it to postgres.
unpack() {
  docker run --rm --user root --entrypoint bash \
    -v "$1":/var/lib/postgresql/data -v "${SNAP_DIR}":/snapshots:ro "$IMAGE" -c "
      set -e; d=/var/lib/postgresql/data
      find \"\$d\" -mindepth 1 -delete
      tar -xzf '/snapshots/${TARGET}/base.tar.gz' -C \"\$d\"
      tar -xzf '/snapshots/${TARGET}/pg_wal.tar.gz' -C \"\$d/pg_wal\"
      chown -R postgres:postgres \"\$d\"; chmod 700 \"\$d\""
}
wait_ready() {   # $1 = container
  for _ in $(seq 1 180); do
    docker exec "$1" pg_isready -U "$USER_" -d "$DB" -q 2>/dev/null && return 0
    sleep 2
  done
  docker logs --tail 40 "$1" >&2; die "postgres in $1 did not become ready"
}
check_signature() {   # $1 = container
  local sig
  sig=$(docker exec -i "$1" psql -U "$USER_" -d "$DB" -tA < scripts/corpus-signature.sql | tr -d '\r')
  echo "restore-physical: signature ${sig}"
  if [ "$sig" = "$WANT_SIG" ]; then echo "restore-physical: signature matches manifest.json"
  else echo "restore-physical: SIGNATURE DIFFERS from manifest.json" >&2; echo "  want ${WANT_SIG}" >&2; return 1; fi
}

if [ "$VERIFY" -eq 1 ]; then
  VOL=nizam_physical_verify; CT=nizam-physical-verify
  cleanup() { docker rm -f "$CT" >/dev/null 2>&1 || true; docker volume rm -f "$VOL" >/dev/null 2>&1 || true; }
  trap cleanup EXIT
  cleanup
  docker volume create "$VOL" >/dev/null
  started=$(date +%s)
  echo "restore-physical: unpacking into scratch volume ${VOL}"
  unpack "$VOL"
  # shm_size matches compose.yaml: parallel query needs more than Docker's 64 MB default.
  docker run -d --name "$CT" --shm-size=1g -e POSTGRES_PASSWORD=unused \
    -v "$VOL":/var/lib/postgresql/data \
    -v "$(pwd)/postgres/postgresql.dev.conf":/etc/postgresql/postgresql.conf:ro \
    "$IMAGE" postgres -c config_file=/etc/postgresql/postgresql.conf -c shared_buffers=256MB >/dev/null
  wait_ready "$CT"
  echo "restore-physical: scratch copy up in $(( $(date +%s) - started ))s"
  check_signature "$CT"
  echo "restore-physical: running the corpus audit on the copy"
  docker exec -i "$CT" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -f - \
    < ../tools/audit/criteria.sql > /tmp/physical-verify-audit.txt 2>&1 || true
  pass=$(grep -cw PASS /tmp/physical-verify-audit.txt || true)
  fail=$(grep -cw FAIL /tmp/physical-verify-audit.txt || true)
  echo "restore-physical: audit on the copy: ${pass} PASS, ${fail} FAIL"
  [ "$fail" = 0 ] && [ "$pass" -gt 0 ] || { grep -w FAIL /tmp/physical-verify-audit.txt >&2 || tail -20 /tmp/physical-verify-audit.txt >&2; exit 1; }
  echo "restore-physical: verified; scratch container and volume removed"
  exit 0
fi

CID=$(dc ps -q "$SERVICE" 2>/dev/null || true)
[ -n "$CID" ] || die "the postgres container does not exist yet: run ./nz up once first"
VOL=$(docker inspect "$CID" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')
[ -n "$VOL" ] || die "could not find the pgdata volume of ${CID}"

echo "This REPLACES the whole PostgreSQL cluster in volume '${VOL}' (every database) with ${TARGET}."
if [ "${NIZAM_RESTORE_CONFIRM:-}" != "$VOL" ]; then
  read -rp "type the volume name to confirm: " confirm
  [ "$confirm" = "$VOL" ] || die "aborted"
fi
started=$(date +%s)
dc stop pgadmin "$SERVICE"
unpack "$VOL"
dc up -d "$SERVICE" pgadmin
wait_ready nizam-postgres
# The copy carries the sender's password; set this machine's.
printf 'ALTER ROLE :"u" PASSWORD :%s;\n' "'pw'" \
  | docker exec -i nizam-postgres psql -U "$USER_" -d postgres -q -v u="$USER_" -v pw="$POSTGRES_PASSWORD"
echo "restore-physical: cluster replaced in $(( $(date +%s) - started ))s; password set from infra/.env"
check_signature nizam-postgres
