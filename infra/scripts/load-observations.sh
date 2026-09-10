#!/usr/bin/env bash
# Load the landing tool's observations.csv into source_observation.
#
# The CSV is produced by tools/corpus-land/land.py from the scrapers' manifests
# and the archives themselves; this puts it where it can be queried. Re-runnable:
# rows already present (same source, url, fetch time and hash) are ignored rather
# than duplicated.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # infra/
[ -f .env ] && set -a && . ./.env && set +a

SERVICE=postgres
DB="${NIZAM_TARGET_DB:-${POSTGRES_DB:-nizam_clean}}"
USER_="${POSTGRES_USER:-nizam}"
CSV="/corpus/observations.csv"      # E:\nizam-data\observations.csv, mounted ro

dc() { docker compose -f "$(pwd)/compose.yaml" "$@"; }
psql_() { dc exec -T "$SERVICE" psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 "$@"; }

dc exec -T "$SERVICE" test -f "$CSV" \
  || { echo "not found in the container: ${CSV}"; echo "run tools/corpus-land/land.py first"; exit 1; }

psql_ <<'SQL'
BEGIN;

-- Staging is unlogged and text-typed: the CSV is external input, so it is cast
-- deliberately on the way in rather than trusted to match column types.
CREATE UNLOGGED TABLE IF NOT EXISTS _obs_stage (
  source_id text, canonical_url text, referring_url text,
  discovered_at text, fetched_at text, http_status text, etag text,
  last_modified text, media_type text, byte_length text, sha256 text,
  object_key text, scraper_version text, source_metadata text,
  outcome text, error_code text
);
TRUNCATE _obs_stage;
\copy _obs_stage FROM '/corpus/observations.csv' WITH (FORMAT csv, HEADER true)

INSERT INTO source_observation (
  source_id, canonical_url, referring_url, discovered_at, fetched_at,
  http_status, etag, last_modified, media_type, byte_length, sha256,
  object_key, scraper_version, source_metadata, outcome, error_code)
SELECT
  source_id,
  nullif(canonical_url,''), nullif(referring_url,''),
  nullif(discovered_at,'')::timestamptz,
  nullif(fetched_at,'')::timestamptz,
  nullif(http_status,'')::integer,
  nullif(etag,''), nullif(last_modified,''), nullif(media_type,''),
  nullif(byte_length,'')::bigint,
  nullif(lower(sha256),''),
  nullif(object_key,''),
  nullif(scraper_version,''),
  coalesce(nullif(source_metadata,'')::jsonb, '{}'::jsonb),
  nullif(outcome,'')::observation_outcome,
  nullif(error_code,'')
FROM _obs_stage
-- Column inference, not ON CONSTRAINT: the uniqueness is a unique INDEX
-- (source_observation_identity), and ON CONFLICT ON CONSTRAINT only accepts a
-- table constraint. The index is declared NULLS NOT DISTINCT so the manually
-- added files, which have no manifest row and therefore no URL, still dedupe.
ON CONFLICT (source_id, canonical_url, fetched_at, sha256) DO NOTHING;

DROP TABLE _obs_stage;
COMMIT;
SQL

echo
psql_ -c "
-- pg_search hooks the planner and warns that it cannot accelerate GROUPING
-- SETS. True and harmless here; silence it so up.sh output stays readable.
SET paradedb.planner_warnings = 'off';
SELECT source_id,
       count(*)                                        AS observations,
       count(*) FILTER (WHERE outcome = 'landed')      AS landed,
       count(DISTINCT sha256)                          AS unique_blobs,
       count(*) FILTER (WHERE outcome <> 'landed')     AS needs_review
  FROM source_observation
 GROUP BY ROLLUP (source_id)
 ORDER BY source_id NULLS LAST;"
