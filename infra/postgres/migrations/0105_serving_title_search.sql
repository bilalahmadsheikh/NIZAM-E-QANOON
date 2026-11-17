-- Catalogue search reads the serving snapshot, not the release view (17 Nov 2026).
--
-- 0104 indexed instrument titles, but the catalogue query still had to prove release for every matching row before
-- it could sort and stop: ~0.9 s per search, 12 s cold. mv_instrument_serving (0094) already holds exactly the
-- released, served laws with their rendered titles, so the catalogue filters and sorts that 10k-row snapshot and
-- joins instrument details for one page only. The trigram index moves to the snapshot; 0104's indexes, unused now,
-- are dropped so the schema carries no dead weight.
--
-- REVERSAL: re-create 0104's indexes; drop mv_instrument_serving_title_trgm.
-- Governing contract: docs/07 (catalogue endpoint); migrations 0094, 0104.

DROP INDEX IF EXISTS instrument_title_trgm;
DROP INDEX IF EXISTS instrument_title_sort;

CREATE INDEX IF NOT EXISTS mv_instrument_serving_title_trgm
    ON mv_instrument_serving USING gin (lower(instrument_title) gin_trgm_ops);
