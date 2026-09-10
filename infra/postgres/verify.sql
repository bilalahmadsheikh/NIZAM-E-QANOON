-- Nizam-e-Qanoon -- environment assertions, Document 03 §1 and 09a §7.
--
-- Run this against a freshly created database BEFORE any migration. It proves
-- the container can supply what L2 depends on, and that this cluster is
-- restore-compatible with the VPS. It creates the five extensions and asserts
-- the three properties that are silent when wrong and expensive to diagnose
-- later: server major version, collation, and extension availability.
--
--   docker compose exec -T postgres psql -U nizam -d nizam -v ON_ERROR_STOP=1 \
--     -f /etc/postgresql/verify.sql
--
-- Once `nizam/` exists this becomes a migration (09a §7: every schema object is
-- created by a migration file in git and by nothing else). Until then it is the
-- honest stand-in, and it is deliberately idempotent.

\set ON_ERROR_STOP on

-- Doc 03 §1: four extensions that make something structurally impossible
-- rather than merely convenient, plus pg_trgm for Roman Urdu aliases.
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector: binary-quantised embeddings, HNSW
CREATE EXTENSION IF NOT EXISTS pg_search;   -- ParadeDB BM25 with length normalisation
CREATE EXTENSION IF NOT EXISTS ltree;       -- provision tree paths, subtree/ancestor queries
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- the EXCLUDE constraint in doc 03 §2.3
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- fuzzy Roman Urdu / misspelled act titles

DO $$
DECLARE
  v_collate text;
BEGIN
  IF current_setting('server_version_num')::int < 170000 THEN
    RAISE EXCEPTION 'PostgreSQL 17 or newer required, got %', current_setting('server_version');
  END IF;

  SELECT datcollate INTO v_collate FROM pg_database WHERE datname = current_database();
  IF v_collate <> 'en_US.UTF-8' THEN
    RAISE EXCEPTION
      'collation mismatch: this cluster is %, the corpus is built on en_US.UTF-8. '
      'Index ordering and text comparison would differ, and a physical restore '
      'onto the server would be invalid. Recreate the volume with the right locale.',
      v_collate;
  END IF;
END $$;

-- btree_gist has to actually work, not merely be installed: this is the
-- constraint that makes overlapping validity intervals impossible (INV-5).
DO $$
BEGIN
  CREATE TEMP TABLE _bt_probe (
    k int,
    valid daterange,
    EXCLUDE USING gist (k WITH =, valid WITH &&)
  ) ON COMMIT DROP;
  INSERT INTO _bt_probe VALUES (1, daterange('2020-01-01','2021-01-01'));
  BEGIN
    INSERT INTO _bt_probe VALUES (1, daterange('2020-06-01','2022-01-01'));
    RAISE EXCEPTION 'btree_gist exclusion did NOT reject an overlapping interval';
  EXCEPTION WHEN exclusion_violation THEN
    NULL;  -- expected
  END;
END $$;

-- pgvector must support bit() and hamming distance: doc 03 stores bit(1024) as
-- the column (136 B/row), not a full-precision vector with an expression index.
DO $$
DECLARE d float8;
BEGIN
  SELECT binary_quantize('[1,-1,1,-1]'::vector) <~> binary_quantize('[1,1,1,1]'::vector)
    INTO d;
  IF d IS NULL THEN
    RAISE EXCEPTION 'pgvector binary quantisation / hamming distance unavailable';
  END IF;
END $$;

\echo ''
\echo '--- environment ---'
SELECT current_setting('server_version')                      AS server_version,
       (SELECT datcollate FROM pg_database
         WHERE datname = current_database())                  AS collation,
       current_setting('shared_buffers')                      AS shared_buffers,
       current_setting('max_parallel_workers')                AS parallel_workers;

\echo ''
\echo '--- extensions ---'
SELECT extname, extversion
  FROM pg_extension
 WHERE extname IN ('vector','pg_search','ltree','btree_gist','pg_trgm','pg_stat_statements')
 ORDER BY extname;

\echo ''
\echo 'OK -- this cluster satisfies doc 03 §1 and is restore-compatible with the VPS.'
