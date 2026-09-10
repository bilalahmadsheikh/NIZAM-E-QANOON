#!/usr/bin/env bash
# Bring up the whole local stack and prove it works.
#
#   cd /mnt/e/Nizam_e_Qanoon && bash infra/up.sh
#
# Idempotent. Safe to re-run after a reboot, after `wsl --shutdown`, or after
# pulling changes. Does not need sudo once you are in the docker group.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"          # infra/
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# --- 0. preconditions --------------------------------------------------------
say "0. preconditions"
command -v docker >/dev/null || { echo "docker not installed -- run infra/wsl/setup-docker.sh"; exit 1; }
docker info >/dev/null 2>&1 || {
  echo "cannot talk to the docker daemon."
  echo "  - is it running?           sudo systemctl start docker"
  echo "  - are you in the group?    groups | grep docker"
  echo "    if not, 'wsl --shutdown' from PowerShell and reopen."
  exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  echo "created infra/.env from the example -- set the passwords in it, then re-run."
  exit 1
fi
set -a; . ./.env; set +a
: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in infra/.env}"
: "${PGADMIN_PASSWORD:?set PGADMIN_PASSWORD in infra/.env}"
: "${MINIO_ROOT_PASSWORD:?set MINIO_ROOT_PASSWORD in infra/.env}"

CORPUS_ROOT="${CORPUS_ROOT:-/mnt/e/nizam-data}"
[ -d "${CORPUS_ROOT}/raw" ] || {
  echo "no corpus at ${CORPUS_ROOT}/raw -- run:"
  echo "  python tools/corpus-land/land.py --archives data --out ${CORPUS_ROOT}"
  exit 1; }
mkdir -p "${CORPUS_ROOT}/snapshots"
echo "corpus: $(find "${CORPUS_ROOT}/raw" -type f | wc -l) blobs at ${CORPUS_ROOT}"

# --- 1. start ----------------------------------------------------------------
say "1. starting postgres, pgadmin and minio"
docker compose up -d --quiet-pull

say "2. waiting for postgres to be healthy"
for i in $(seq 1 60); do
  state=$(docker inspect -f '{{.State.Health.Status}}' nizam-postgres 2>/dev/null || echo starting)
  [ "$state" = healthy ] && { echo "healthy after $((i*3))s"; break; }
  [ "$i" -eq 60 ] && { echo "postgres did not become healthy"; docker compose logs --tail=40 postgres; exit 1; }
  sleep 3
done

# --- 3. environment assertions ----------------------------------------------
say "3. verifying the cluster against doc 03 §1"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-nizam}" -d "${POSTGRES_DB:-nizam_clean}" \
  -v ON_ERROR_STOP=1 -f /etc/postgresql/verify.sql

# --- 4. schema ---------------------------------------------------------------
say "4. applying migrations"
bash scripts/migrate.sh

# --- 5. data -----------------------------------------------------------------
say "5. loading acquisition observations"
bash scripts/load-observations.sh

# --- 6. first snapshot -------------------------------------------------------
say "6. taking a snapshot"
bash scripts/snapshot.sh

say "ready"
cat <<EOF

  pgAdmin    http://localhost:${PGADMIN_PORT:-5050}       ${PGADMIN_EMAIL:-dev@nizam.local} / (PGADMIN_PASSWORD)
  MinIO      http://localhost:${MINIO_CONSOLE_PORT:-9001}       ${MINIO_ROOT_USER:-nizam} / (MINIO_ROOT_PASSWORD)
  Postgres   localhost:${POSTGRES_PORT:-5432}             ${POSTGRES_USER:-nizam} / (POSTGRES_PASSWORD)

  All three are bound to 127.0.0.1 and reachable from Windows -- WSL2 forwards
  localhost, so just open the URLs in your browser.

  Snapshots  ${CORPUS_ROOT}/snapshots  (auto, every 15 min, only when the WAL moves)
             bash infra/scripts/restore.sh --list
EOF
