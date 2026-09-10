-- Source-review evidence records exact block hashes inside PostgreSQL.  Keep
-- the digest implementation database-local and reproducible on a clean build.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
COMMIT;
