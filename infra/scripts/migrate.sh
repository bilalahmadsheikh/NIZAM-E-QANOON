#!/usr/bin/env bash
# Apply the SQL migrations in infra/postgres/migrations, in order, exactly once.
#
# Doc 09a §7, stated as plainly as the document does: "Every schema object --
# table, index, constraint, extension, role, policy -- is created by a migration
# file in git and by nothing else. If the answer to 'how do I recreate this on
# the server?' is anything other than 'run the migrations', the local environment
# has stopped being production."
#
# This is the interim mechanism. When the `nizam` package exists it is replaced
# by Alembic; the invariant it protects does not change, so pgAdmin stays a
# viewer either way.
#
#   bash infra/scripts/migrate.sh          # apply anything pending
#   bash infra/scripts/migrate.sh --status # show what is applied
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # infra/
[ -f .env ] && set -a && . ./.env && set +a

SERVICE=postgres
DB="${NIZAM_TARGET_DB:-${POSTGRES_DB:-nizam_clean}}"
USER_="${POSTGRES_USER:-nizam}"
MIG_DIR=postgres/migrations

dc() { docker compose -f "$(pwd)/compose.yaml" "$@"; }
psql_() { dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 "$@"; }

psql_ -qc "
CREATE TABLE IF NOT EXISTS schema_migration (
    version     text        PRIMARY KEY,
    sha256      char(64)    NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
);" >/dev/null

if [ "${1:-}" = "--status" ]; then
  psql_ -c "SELECT version, left(sha256,12) AS sha, applied_at FROM schema_migration ORDER BY version;"
  exit 0
fi

applied=$(psql_ -tAc "SELECT version FROM schema_migration" | tr -d '\r')
pending=0

for f in "$MIG_DIR"/*.sql; do
  [ -e "$f" ] || continue
  version=$(basename "$f" .sql)
  sha=$(sha256sum "$f" | cut -c1-64)

  if grep -qx "$version" <<<"$applied"; then
    # A migration that changed after being applied is drift, not an edit.
    recorded=$(psql_ -tAc "SELECT sha256 FROM schema_migration WHERE version='${version}'" | tr -d '[:space:]')
    if [ "$recorded" != "$sha" ]; then
      echo "ERROR: ${version} was applied as ${recorded:0:12} but the file is now ${sha:0:12}."
      echo "       Add a new migration instead of editing one that has run."
      exit 1
    fi
    continue
  fi

  echo "applying ${version}"
  # Each migration file carries its own BEGIN/COMMIT, so a failure inside one
  # rolls that migration back rather than half-applying it.
  psql_ -q -f "/etc/postgresql/migrations/$(basename "$f")"
  psql_ -qc "INSERT INTO schema_migration (version, sha256) VALUES ('${version}', '${sha}');" >/dev/null
  pending=$((pending + 1))
done

if [ "$pending" -eq 0 ]; then echo "migrate: up to date"; else echo "migrate: applied ${pending}"; fi
