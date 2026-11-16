-- instrument_metadata_assertion gains a 'long_title' field: the law's printed long title, 'An Act to provide for ...'.
--
-- Found 16 Nov 2026: instrument.long_title was empty for all 10,312 released instruments -- the segment worker always
-- writes NULL (nizam/workers/segment.py), and no recorder read it. The long title is printed text and INV-1 renders
-- what is printed from a record, so it is recorded like the other printed facts: tools/record_long_titles.py reads
-- it from the instrument's own title region with its verbatim quote and source block, and
-- tools/apply_instrument_metadata.py derives instrument.long_title both ways. Audit A15 covers it.
--
-- REVERSAL: restore 0082's field list and printed-fact constraint; set instrument.long_title to NULL.
-- Governing contract: docs/03 §2 (instrument), INV-1; migrations 0070, 0082.

BEGIN;

SET LOCAL lock_timeout = '10s';

ALTER TABLE instrument_metadata_assertion
    DROP CONSTRAINT instrument_metadata_assertion_field,
    DROP CONSTRAINT instrument_metadata_assertion_printed_fact;

ALTER TABLE instrument_metadata_assertion
    ADD CONSTRAINT instrument_metadata_assertion_field
        CHECK (field IN ('display_title', 'number', 'enacted_on', 'commenced_on', 'text_language', 'status',
                         'long_title')),
    ADD CONSTRAINT instrument_metadata_assertion_printed_fact
        CHECK (assertion = 'withdrawn' OR field NOT IN ('number', 'enacted_on', 'commenced_on', 'status', 'long_title')
               OR (quote IS NOT NULL AND btrim(quote) <> '' AND source_block_id IS NOT NULL));

COMMENT ON TABLE instrument_metadata_assertion IS
  'Append-only: one metadata field of one expression (display_title, number, enacted_on, commenced_on, '
  'text_language, status, long_title) with its basis and, for printed facts, status and long titles, the verbatim '
  'quote and source block. instrument columns are derived from v_instrument_metadata_current by '
  'tools/apply_instrument_metadata.py. Migrations 0070, 0082, 0083.';

COMMIT;
