-- instrument_metadata_assertion gains a 'status' field: 'in_force', asserted only on positive evidence.
--
-- Why (16 Nov 2026). 0012 reset every ingestion-default 'in_force' to 'unknown', and 0066 made the statutory repeal
-- the corpus's only lifecycle source: at that point 10,244 of 10,312 released instruments were 'unknown'. docs/03b §3
-- derives life stage from the temporal model (enacted, commenced, repealed, spent, lapsed, invalidated); what this
-- corpus can now establish from its own text is COMMENCEMENT and the ABSENCE OF A KNOWN REPEAL. tools/record_status.py
-- asserts 'in_force' for an expression only when all of these hold, and records which:
--   * commenced, by its own text or a general clauses statute the corpus holds: an established commenced_on on or
--     before the recording date; or a self-executing 'shall come into force at once' (the day may be unknown, the
--     fact that it is in force is not); or the general clauses default for a silent Act (record_commencement.py);
--   * not an Ordinance (whether an Ordinance lapsed or was continued is a constitutional question its text does not
--     settle) and not commenced by notification, appointment or in parts;
--   * no statutory repeal of it stands (0066), dated or undated;
--   * the official portal's catalogue title carries no repeal note ('(Repealed by Act XIV of 2016)');
--   * NO released provision anywhere in the corpus names it -- its title and year -- beside the words repeal,
--     supersession or rescind, in any instrument of any kind, qualified or not. This is a screen, deliberately wider
--     than 0066's recording rule: a mention it cannot read stops the claim.
-- What 'in_force' does NOT cover, carried on the row and declared by operative_provision as before: repeal by a law
-- the corpus does not hold, judicial invalidation (invalidation_coverage 'not_tracked'), and territorial extent.
-- Anything else stays 'unknown' -- a declared limitation, never a guess.
--
-- The value must be 'in_force', with the quote and source block of the commencement evidence (the commencement
-- sentence, or section 1 for a silent Act). tools/apply_instrument_metadata.py derives instrument.status both ways
-- ('in_force' from a standing assertion; back to 'unknown' when none stands), never over a 'repealed' status or a
-- standing repeal (apply_statutory_repeals.py owns those). Audit A15 checks it with the other fields.
--
-- REVERSAL: restore 0070's two CHECK constraints (field list; printed-fact quote) and drop the status value check;
-- set every status 'in_force' back to 'unknown'.
-- Governing contract: docs/03b §3 (life_stage), §6.2; INV-5; migrations 0012, 0066, 0070.

BEGIN;

SET LOCAL lock_timeout = '10s';

DO $$
DECLARE c record;
BEGIN
    FOR c IN SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint
              WHERE conrelid = 'instrument_metadata_assertion'::regclass AND contype = 'c' LOOP
        IF c.def ~ 'field = ANY' AND c.def ~ 'display_title' AND c.def !~ 'quote' THEN
            EXECUTE format('ALTER TABLE instrument_metadata_assertion DROP CONSTRAINT %I', c.conname);
        ELSIF c.def ~ 'quote IS NOT NULL' THEN
            EXECUTE format('ALTER TABLE instrument_metadata_assertion DROP CONSTRAINT %I', c.conname);
        END IF;
    END LOOP;
END $$;

ALTER TABLE instrument_metadata_assertion
    ADD CONSTRAINT instrument_metadata_assertion_field
        CHECK (field IN ('display_title', 'number', 'enacted_on', 'commenced_on', 'text_language', 'status')),
    ADD CONSTRAINT instrument_metadata_assertion_status_value
        CHECK (value IS NULL OR field <> 'status' OR value = 'in_force'),
    ADD CONSTRAINT instrument_metadata_assertion_printed_fact
        CHECK (assertion = 'withdrawn' OR field NOT IN ('number', 'enacted_on', 'commenced_on', 'status')
               OR (quote IS NOT NULL AND btrim(quote) <> '' AND source_block_id IS NOT NULL));

COMMENT ON TABLE instrument_metadata_assertion IS
  'Append-only: one metadata field of one expression (display_title, number, enacted_on, commenced_on, '
  'text_language, status) with its basis and, for printed facts and status, the verbatim quote and source block. '
  'instrument columns are derived from v_instrument_metadata_current by tools/apply_instrument_metadata.py. '
  'Migrations 0070, 0082.';

DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM pg_constraint
     WHERE conrelid = 'instrument_metadata_assertion'::regclass AND contype = 'c'
       AND pg_get_constraintdef(oid) ~ 'quote IS NOT NULL';
    IF n <> 1 THEN RAISE EXCEPTION '0082: expected exactly one printed-fact constraint, found %', n; END IF;
    SELECT count(*) INTO n FROM pg_constraint
     WHERE conrelid = 'instrument_metadata_assertion'::regclass AND contype = 'c'
       AND pg_get_constraintdef(oid) ~ 'field = ANY' AND pg_get_constraintdef(oid) ~ 'display_title'
       AND pg_get_constraintdef(oid) !~ 'quote';
    IF n <> 1 THEN RAISE EXCEPTION '0082: expected exactly one field-list constraint, found %', n; END IF;
END $$;

COMMIT;
