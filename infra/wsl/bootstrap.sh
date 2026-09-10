#!/usr/bin/env bash
# Nizam-e-Qanoon -- local database, native in WSL2 Ubuntu. No Docker.
#
# NOT THE DEFAULT PATH, and not needed if you use the containers. infra/up.sh
# runs Postgres in Docker; this installs a SECOND, native cluster. Running both
# is only confusing -- use this only if you deliberately want Postgres without
# Docker. See infra/README.md.
#
# Builds the same PostgreSQL the VPS will run: PG 17 from PGDG, pgvector from
# PGDG, pg_search from ParadeDB's own .deb. That combination is what makes this
# cluster restore-compatible with production (09a §7 Parity) -- and it is the
# reason this runs inside WSL rather than against the PostgreSQL 17 already
# installed on Windows, which has no pg_search build at all and would need a
# Visual Studio toolchain to get pgvector.
#
#   wsl -d Ubuntu
#   cd /mnt/e/Nizam_e_Qanoon && bash infra/wsl/bootstrap.sh
#
# Idempotent: safe to re-run. Asks for your sudo password once.
set -euo pipefail

PG_MAJOR=17
CLUSTER=nizam
PORT=5433                 # 5432 is taken by the PostgreSQL service on Windows
DB=nizam
DB_USER=nizam
LOCALE=en_US.UTF-8        # doc 03 §1 asserts this exact collation

PARADEDB_VERSION=0.25.6
PARADEDB_DEB="postgresql-${PG_MAJOR}-pg-search_${PARADEDB_VERSION}-1PARADEDB-noble_amd64.deb"
PARADEDB_URL="https://github.com/paradedb/paradedb/releases/download/v${PARADEDB_VERSION}/${PARADEDB_DEB}"
PARADEDB_SHA256=ebc3afb0bdb9f43c250bffee4ff61ee0cda68bc3736b5c276b9d113bc2ab7201

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# --- 0. guards ---------------------------------------------------------------
say "0. checking the machine"
. /etc/os-release
[ "${VERSION_CODENAME:-}" = noble ] || { echo "expected Ubuntu 24.04 (noble), got ${VERSION_CODENAME:-unknown}"; exit 1; }
[ "$(uname -m)" = x86_64 ] || { echo "expected x86_64"; exit 1; }
[ "$(id -u)" -ne 0 ] || { echo "run as your normal user, not root"; exit 1; }
echo "Ubuntu ${VERSION_ID} ${VERSION_CODENAME} x86_64, ok"

# --- 1. locale ---------------------------------------------------------------
# A fresh Ubuntu WSL has only C.utf8. Creating the cluster before generating
# en_US.UTF-8 gives it the wrong collation, which changes index ordering and
# text comparison silently and makes a physical restore onto the VPS invalid.
say "1. generating ${LOCALE}"
if ! locale -a 2>/dev/null | grep -qiE '^en_US\.utf-?8$'; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq locales
  sudo locale-gen "$LOCALE"
  sudo update-locale
fi
locale -a | grep -iE '^en_US\.utf-?8$' >/dev/null && echo "${LOCALE} present"

# --- 2. PGDG repository ------------------------------------------------------
say "2. adding the PostgreSQL (PGDG) apt repository"
sudo apt-get install -y -qq curl ca-certificates gnupg
if [ ! -f /etc/apt/sources.list.d/pgdg.list ] && [ ! -f /etc/apt/sources.list.d/pgdg.sources ]; then
  sudo install -d /usr/share/postgresql-common/pgdg
  sudo apt-get install -y -qq postgresql-common
  sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
fi
sudo apt-get update -qq

# --- 3. PostgreSQL + pgvector ------------------------------------------------
# ltree, btree_gist, pg_trgm and pg_stat_statements are contrib modules and ship
# inside the postgresql-17 package itself on Debian/Ubuntu. There is no
# `postgresql-contrib-17` in PGDG -- asking for it fails the whole install.
say "3. installing PostgreSQL ${PG_MAJOR} and pgvector"
sudo apt-get install -y -qq \
  "postgresql-${PG_MAJOR}" \
  "postgresql-client-${PG_MAJOR}" \
  "postgresql-${PG_MAJOR}-pgvector"

# --- 4. pg_search from ParadeDB ---------------------------------------------
# There is no Windows build of pg_search and no PGDG package; ParadeDB ships
# its own .deb. Pinned by version and verified by hash, because this extension
# decides BM25 ranking and a silent change to it changes retrieval quality.
say "4. installing pg_search ${PARADEDB_VERSION}"
if ! dpkg -s "postgresql-${PG_MAJOR}-pg-search" >/dev/null 2>&1 || \
   [ "$(dpkg-query -W -f='${Version}' "postgresql-${PG_MAJOR}-pg-search" 2>/dev/null)" != "${PARADEDB_VERSION}-1PARADEDB" ]; then
  tmp=$(mktemp -d)
  echo "downloading ${PARADEDB_DEB} (~65 MB)"
  curl -fsSL -o "${tmp}/${PARADEDB_DEB}" "$PARADEDB_URL"
  echo "${PARADEDB_SHA256}  ${tmp}/${PARADEDB_DEB}" | sha256sum -c - \
    || { echo "CHECKSUM MISMATCH -- refusing to install"; rm -rf "$tmp"; exit 1; }
  sudo apt-get install -y -qq "${tmp}/${PARADEDB_DEB}"
  rm -rf "$tmp"
else
  echo "already installed"
fi

# --- 5. the cluster ----------------------------------------------------------
# A separate cluster rather than the auto-created `main`: main was initialised
# with the system locale before step 1 ran, and its collation cannot be changed
# in place. Leaving it alone also leaves any other work on this machine intact.
say "5. creating the '${CLUSTER}' cluster on port ${PORT}"
if ! pg_lsclusters -h | awk '{print $1" "$2}' | grep -qx "${PG_MAJOR} ${CLUSTER}"; then
  sudo pg_createcluster "${PG_MAJOR}" "${CLUSTER}" \
    --port "${PORT}" \
    --locale "${LOCALE}" \
    --encoding UTF8 \
    -- --data-checksums          # cheap, and turns silent corruption into an error
else
  echo "cluster already exists"
fi

# --- 6. configuration --------------------------------------------------------
say "6. applying the developer profile from 09a §4"
CONF_D="/etc/postgresql/${PG_MAJOR}/${CLUSTER}/conf.d"
MAINCONF="/etc/postgresql/${PG_MAJOR}/${CLUSTER}/postgresql.conf"
sudo install -d "$CONF_D"
sudo install -m 0644 "${REPO_ROOT}/infra/postgres/postgresql.dev.conf" "${CONF_D}/10-nizam.conf"

# Debian ships `include_dir = 'conf.d'` near the TOP of postgresql.conf, so its
# own shared_buffers/listen_addresses further down would silently override ours.
# Append a second include at the end -- last one read wins -- so the profile in
# git is the one actually in force.
if ! grep -q "^# nizam: profile last" "$MAINCONF"; then
  printf "\n# nizam: profile last -- keep this at the end of the file\ninclude_dir = 'conf.d'\n" \
    | sudo tee -a "$MAINCONF" >/dev/null
fi

# Local overrides that differ from the Docker profile: bind to loopback only,
# and keep the port pg_createcluster assigned.
sudo tee "${CONF_D}/20-local.conf" >/dev/null <<CONF
listen_addresses = 'localhost'
port = ${PORT}
CONF

say "7. starting the cluster"
sudo pg_ctlcluster "${PG_MAJOR}" "${CLUSTER}" restart || sudo pg_ctlcluster "${PG_MAJOR}" "${CLUSTER}" start
pg_lsclusters | sed -n '1p;/'"${CLUSTER}"'/p'

# --- 8. role and database ----------------------------------------------------
say "8. creating role '${DB_USER}' and database '${DB}'"
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  read -rsp "password for the '${DB_USER}' role: " POSTGRES_PASSWORD; echo
fi
sudo -u postgres psql -p "${PORT}" -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${POSTGRES_PASSWORD}';
  ELSE
    ALTER ROLE ${DB_USER} LOGIN PASSWORD '${POSTGRES_PASSWORD}';
  END IF;
END \$\$;
SQL
sudo -u postgres psql -p "${PORT}" -tAc \
  "SELECT 1 FROM pg_database WHERE datname='${DB}'" | grep -q 1 \
  || sudo -u postgres createdb -p "${PORT}" -O "${DB_USER}" \
       --locale="${LOCALE}" --encoding=UTF8 --template=template0 "${DB}"

# --- 9. prove it -------------------------------------------------------------
say "9. verifying against doc 03 §1"
sudo -u postgres psql -p "${PORT}" -d "${DB}" -v ON_ERROR_STOP=1 \
  -f "${REPO_ROOT}/infra/postgres/verify.sql"

cat <<EOF

Done. Connect from WSL:
    psql -h localhost -p ${PORT} -U ${DB_USER} -d ${DB}
and from Windows (PowerShell), the same, because WSL2 forwards localhost:
    & "C:\\Program Files\\PostgreSQL\\17\\bin\\psql.exe" -h localhost -p ${PORT} -U ${DB_USER} -d ${DB}

The data directory is /var/lib/postgresql/${PG_MAJOR}/${CLUSTER} -- inside ext4,
which is the one hardware rule in 09a §1.2. Do not move it to /mnt/c or /mnt/e.
EOF
