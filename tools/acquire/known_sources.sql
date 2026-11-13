-- known_sources.sql : every URL and title the corpus already holds, for tools/acquire/portal_diff.py (read-only).
-- One row per key: kind (url|title), value. Titles are raw; the diff tool normalises them.
-- URLs: every observation's canonical URL, and any detail/listing URL carried in its source metadata.
-- Titles: the catalogue title of every observation, and every instrument's short and display title (any state:
-- a title retired by a later replay still names a law we hold).
COPY (
  SELECT DISTINCT 'url', canonical_url FROM source_observation WHERE canonical_url IS NOT NULL
  UNION
  SELECT DISTINCT 'url', v FROM source_observation,
         LATERAL (VALUES (source_metadata->>'detail_url'), (source_metadata->>'listing_url'), (source_metadata->>'url')) x(v)
   WHERE v IS NOT NULL
  UNION
  SELECT DISTINCT 'title', source_metadata->>'title' FROM source_observation WHERE source_metadata->>'title' IS NOT NULL
  UNION
  SELECT DISTINCT 'title', short_title FROM instrument WHERE short_title IS NOT NULL
  UNION
  SELECT DISTINCT 'title', value FROM v_instrument_metadata_current WHERE field = 'display_title'
) TO STDOUT WITH (FORMAT csv, HEADER false);
