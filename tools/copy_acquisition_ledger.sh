#!/usr/bin/env bash
# Copy only authoritative acquisition provenance between databases in one cluster.
set -euo pipefail
SOURCE_DB="${1:-nizam}"
TARGET_DB="${2:-nizam_clean}"
CONTAINER="${NIZAM_POSTGRES_CONTAINER:-nizam-postgres}"
USER_="${POSTGRES_USER:-nizam}"

docker exec "$CONTAINER" psql -U "$USER_" -d "$TARGET_DB" \
  -v ON_ERROR_STOP=1 -c \
  'TRUNCATE acquisition_attempt,source_observation RESTART IDENTITY CASCADE'
docker exec "$CONTAINER" pg_dump -U "$USER_" -d "$SOURCE_DB" \
  --data-only --table=source_observation --table=acquisition_attempt \
  --column-inserts --no-owner --no-acl \
  | docker exec -i "$CONTAINER" psql -U "$USER_" -d "$TARGET_DB" \
      -v ON_ERROR_STOP=1
docker exec "$CONTAINER" psql -U "$USER_" -d "$TARGET_DB" -P pager=off -c \
  "SELECT count(*) observations,
          count(*) FILTER (WHERE outcome='landed') landed,
          count(DISTINCT sha256) FILTER (WHERE outcome='landed') distinct_landed
     FROM source_observation;"
