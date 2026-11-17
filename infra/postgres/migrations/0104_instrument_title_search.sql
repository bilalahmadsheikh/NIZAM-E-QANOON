-- Title search for the library catalogue (17 Nov 2026).
--
-- The catalogue was ordered by instrument UUID -- effectively random -- and searched with an unindexed ILIKE over
-- every law. It is now ordered by title, with titles that START with the query first, and matched through a trigram
-- index on the rendered title (display_title when reviewed, else the catalogue short title: what the reader sees).
-- pg_trgm is installed (docs/03 §1). Active rows only: retired revisions are never listed.
--
-- REVERSAL: DROP INDEX instrument_title_trgm, instrument_title_sort.
-- Governing contract: docs/07 (catalogue endpoint), docs/08 (library browse); migration 0070 (display_title).

CREATE INDEX IF NOT EXISTS instrument_title_trgm
    ON instrument USING gin (lower(coalesce(display_title, short_title)) gin_trgm_ops)
 WHERE is_active;

CREATE INDEX IF NOT EXISTS instrument_title_sort
    ON instrument (lower(coalesce(display_title, short_title)), id)
 WHERE is_active;
