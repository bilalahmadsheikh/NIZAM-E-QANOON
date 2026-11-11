-- Instrument metadata recorded from evidence: display title, number, enactment and commencement dates, text language.
--
-- WHY. After the release of all 8,851 canonical expressions (Nov 2026) the instrument rows still carry what the
-- segmenter could see and nothing more: enacted_on and commenced_on NULL on every instrument, number NULL on 4,391,
-- short_title as the source catalogue spelled it (junk such as 'NA-' or '(official website)' on ~257, ALL CAPS on
-- ~3,170), and the text of 13 Urdu-language expressions stored in provision_version.text_en with nothing saying it is
-- Urdu. INV-1 renders citations from these records and INV-5 needs the dates, so they have to be filled -- from
-- evidence, never guessed.
--
-- WHAT A ROW SAYS. One field of one expression, named like 0054/0062/0065/0066/0067 by SOURCE (observation,
-- expression ordinal), so a replay does not orphan it:
--   display_title  -- the instrument's name as printed in its own text (docs/03b: citations render from records);
--   number         -- the printed instrument number, e.g. 'XXVI' from 'Act No. XXVI of 1869';
--   enacted_on     -- the printed assent / promulgation / making date ('[18th April, 1956]' under the title);
--   commenced_on   -- only where the instrument's own text commences the WHOLE instrument at once or on a printed
--                     date. docs/03b ('the two edges that cannot be extracted from statute text'): commencement by
--                     notification lives in the Gazette, so it is never inferred here and stays NULL (coverage
--                     'not_tracked' in the operative view);
--   text_language  -- the language the expression's released text is written in, measured from that text
--                     ('en','ur','sd'). NOT docs/03b's authentic_language (which version governs is a legal question
--                     this record does not settle).
-- Printed-evidence fields carry the verbatim quote and the source block it was read from.
--
-- HOW IT REACHES instrument. instrument.display_title, number, enacted_on, commenced_on and text_language are derived
-- from v_instrument_metadata_current after every replay by tools/apply_instrument_metadata.py
-- (tools/post_replay_sequence.sh step 2b4), exactly as 0066's status is. `number` is fill-only: a number the segmenter
-- read stands, and a disagreement is reported, not overwritten. short_title is never changed (identity and replay
-- matching key on it); display_title is the name to render.
--
-- Withdrawal is a later row with assertion 'withdrawn' (append-only, latest wins). The release views keep their
-- semantics; v_release_instrument is re-created only to expose the two new columns.
--
-- REVERSAL (irreversible once a row exists, docs/03 §9): with the table empty, drop the view, triggers, function,
-- table and the two columns. Governing contract: docs/03b §3 and the note on extraction limits; docs/03 §9;
-- docs/SCHEMA.md.

BEGIN;

SET LOCAL lock_timeout = '10s';

ALTER TABLE instrument
    ADD COLUMN display_title text CHECK (display_title IS NULL OR btrim(display_title) <> ''),
    ADD COLUMN text_language text CHECK (text_language IS NULL OR text_language IN ('en', 'ur', 'sd'));

COMMENT ON COLUMN instrument.display_title IS
  'Name to render (INV-1), derived from instrument_metadata_assertion; NULL means render short_title. Migration 0070.';
COMMENT ON COLUMN instrument.text_language IS
  'Language of the released text of this expression, measured from it; not the authentic language. Migration 0070.';

CREATE TABLE instrument_metadata_assertion (
    id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_observation_id  bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    expression_ordinal     smallint NOT NULL CHECK (expression_ordinal >= 0),
    field                  text NOT NULL CHECK (field IN ('display_title', 'number', 'enacted_on', 'commenced_on',
                                                          'text_language')),
    value                  text,
    assertion              text NOT NULL CHECK (assertion IN ('asserted', 'withdrawn')),
    basis                  text NOT NULL CHECK (btrim(basis) <> ''),
    source_block_id        bigint CHECK (source_block_id IS NULL OR source_block_id > 0),
    source_page            integer CHECK (source_page IS NULL OR source_page > 0),
    quote                  text,
    method                 text NOT NULL CHECK (btrim(method) <> ''),
    evidence               jsonb NOT NULL CHECK (coalesce(jsonb_typeof(evidence) = 'object'
                                                      AND btrim(evidence->>'reviewer_type') <> '', false)),
    recorded_by            text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at            timestamptz NOT NULL DEFAULT now(),
    -- an assertion has a value; a withdrawal has none
    CHECK ((assertion = 'asserted') = (value IS NOT NULL)),
    CHECK (value IS NULL OR btrim(value) <> ''),
    CHECK (value IS NULL OR field NOT IN ('enacted_on', 'commenced_on') OR value ~ '^\d{4}-\d{2}-\d{2}$'),
    CHECK (value IS NULL OR field <> 'text_language' OR value IN ('en', 'ur', 'sd')),
    -- a printed fact carries what was printed and where
    CHECK (assertion = 'withdrawn' OR field NOT IN ('number', 'enacted_on', 'commenced_on')
           OR (quote IS NOT NULL AND btrim(quote) <> '' AND source_block_id IS NOT NULL))
);

CREATE INDEX instrument_metadata_assertion_key
    ON instrument_metadata_assertion (source_observation_id, expression_ordinal, field, recorded_at DESC, id DESC);

CREATE FUNCTION check_instrument_metadata_assertion() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    d date;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'instrument_metadata_assertion is append-only';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.source_observation_id AND outcome = 'landed') THEN
        RAISE EXCEPTION 'observation % has not landed', NEW.source_observation_id;
    END IF;
    IF NEW.value IS NOT NULL AND NEW.field IN ('enacted_on', 'commenced_on') THEN
        d := NEW.value::date;                       -- raises on an impossible date such as 1956-02-30
        IF d < DATE '1800-01-01' OR d > current_date THEN
            RAISE EXCEPTION '% % is outside 1800..today', NEW.field, NEW.value;
        END IF;
    END IF;
    IF NEW.source_block_id IS NOT NULL AND NOT EXISTS (
           SELECT 1 FROM text_block t JOIN document doc ON doc.id = t.document_id
             JOIN source_observation o ON o.sha256 = doc.sha256
            WHERE t.id = NEW.source_block_id AND o.id = NEW.source_observation_id) THEN
        RAISE EXCEPTION 'block % is not a block of observation %', NEW.source_block_id, NEW.source_observation_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER instrument_metadata_assertion_guard
BEFORE INSERT OR UPDATE OR DELETE ON instrument_metadata_assertion
FOR EACH ROW EXECUTE FUNCTION check_instrument_metadata_assertion();

CREATE TRIGGER instrument_metadata_assertion_no_truncate
BEFORE TRUNCATE ON instrument_metadata_assertion
FOR EACH STATEMENT EXECUTE FUNCTION check_instrument_metadata_assertion();

-- The standing value per expression and field, resolved to the ACTIVE canonical instrument. A withdrawn latest row,
-- or an expression with no active canonical instrument, yields nothing.
CREATE VIEW v_instrument_metadata_current AS
WITH latest AS (
    SELECT DISTINCT ON (source_observation_id, expression_ordinal, field) *
      FROM instrument_metadata_assertion
     ORDER BY source_observation_id, expression_ordinal, field, recorded_at DESC, id DESC)
SELECT l.*, i.id AS instrument_id
  FROM latest l
  JOIN instrument i ON i.source_observation_id = l.source_observation_id
                   AND i.expression_ordinal = l.expression_ordinal
                   AND i.is_active AND i.duplicate_of IS NULL
 WHERE l.assertion = 'asserted';

-- Same definition as 0069; re-created so i.* exposes display_title and text_language.
CREATE OR REPLACE VIEW v_release_instrument AS
SELECT i.*
  FROM instrument i
  JOIN v_document_quality_status q ON q.document_id=i.document_id
 WHERE i.is_active
   AND i.duplicate_of IS NULL
   AND q.overall_outcome='passed'
   AND EXISTS (
       SELECT 1 FROM segmentation_run r
        WHERE r.instrument_id=i.id AND r.outcome='segmented')
   AND NOT EXISTS (
       SELECT 1 FROM v_toc_gap_pending t WHERE t.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_structural_adjudication_pending s
        WHERE s.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_boundary_adjudication_pending b
        WHERE b.instrument_id=i.id);

COMMENT ON TABLE instrument_metadata_assertion IS
  'Append-only: one metadata field of one expression (display_title, number, enacted_on, commenced_on, '
  'text_language) with its basis and, for printed facts, the verbatim quote and source block. instrument columns '
  'are derived from v_instrument_metadata_current by tools/apply_instrument_metadata.py. Migration 0070.';

COMMIT;
