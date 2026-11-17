-- A law's year and kind are recorded evidence too, when the catalogue got them wrong.
--
-- Found 16-17 Nov 2026 (docs/CORPUS-STATE-2026-11-17.md, "Open items"): five released laws carry a year or kind the
-- catalogue supplied, and their own text says otherwise --
--   6688   catalogued act, 1942   prints 'This Ordinance may be called the Civil Pioneer ... Force (Amendment)
--                                 Ordinance, 1943' (the year of the Ordinance it amends was taken);
--   8846   catalogued 1883        prints 'Act No. I OF 1896' (it amends the Indian Emigration Act, 1883);
--   9067   catalogued 1860        prints 'Act No. XXVII of 1870' (it amends the Indian Penal Code, 1860);
--   11382  catalogued 2016        prints 'Environmental Protection Act, 2014' (2016 is the file's upload year);
--   11379  catalogued act         prints 'These rules may be called ... Finance Committee Rules-2010'.
-- instrument.year and instrument.kind are written by the segmenter from the catalogue, and every replay writes them
-- again, so a correction cannot be an UPDATE: like number (0070, printed_number_corrects_stored) it is an append-only
-- assertion carrying the verbatim clause and its source block, re-applied after every replay by
-- tools/apply_instrument_metadata.py, and audited by A15 (reflected, both counts reported).
--
-- The provision path (ltree) keeps the catalogue year and kind it was minted with: it is the immutable lineage key
-- (docs/03 §2A, INV-4), never a rendered citation. Citations render instrument.kind/number/year (INV-1).
--
-- REVERSAL: restore 0095's field constraints (irreversible once a year/kind row exists, docs/03 §9: withdraw it
-- instead, then a replay writes the catalogue value back).
-- Governing contract: docs/03b §2 (instrument identity), INV-1; migrations 0070, 0082, 0083, 0095.

BEGIN;

SET LOCAL lock_timeout = '10s';

ALTER TABLE instrument_metadata_assertion
    DROP CONSTRAINT instrument_metadata_assertion_field,
    DROP CONSTRAINT instrument_metadata_assertion_printed_fact;

ALTER TABLE instrument_metadata_assertion
    ADD CONSTRAINT instrument_metadata_assertion_field
        CHECK (field IN ('display_title', 'number', 'enacted_on', 'commenced_on', 'text_language', 'status',
                         'long_title', 'territorial_extent', 'year', 'kind')),
    ADD CONSTRAINT instrument_metadata_assertion_printed_fact
        CHECK (assertion = 'withdrawn'
               OR field NOT IN ('number', 'enacted_on', 'commenced_on', 'status', 'long_title', 'territorial_extent',
                                'year', 'kind')
               OR (quote IS NOT NULL AND btrim(quote) <> '' AND source_block_id IS NOT NULL)),
    ADD CONSTRAINT instrument_metadata_assertion_year_value
        CHECK (value IS NULL OR field <> 'year' OR (value ~ '^\d{4}$' AND value::int BETWEEN 1800 AND 2100)),
    ADD CONSTRAINT instrument_metadata_assertion_kind_value
        CHECK (value IS NULL OR field <> 'kind'
               OR value IN ('constitution', 'act', 'ordinance', 'order', 'regulation', 'rules', 'sro', 'notification'));

COMMENT ON TABLE instrument_metadata_assertion IS
  'Append-only: one metadata field of one expression (display_title, number, enacted_on, commenced_on, '
  'text_language, status, long_title, territorial_extent, year, kind) with its basis and, for printed facts, the '
  'verbatim quote and source block. instrument columns are derived from v_instrument_metadata_current by '
  'tools/apply_instrument_metadata.py (year and kind correct the catalogue value, re-applied after every replay); '
  'territorial_extent is read by v_instrument_currency. Migrations 0070, 0082, 0083, 0095, 0101.';

COMMIT;
