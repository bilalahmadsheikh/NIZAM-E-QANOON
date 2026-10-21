-- A statute repealed by another statute the corpus holds, recorded from the repealing text.
--
-- Until now every released instrument carried lifecycle status 'unknown' (migration 0012 withdrew the ingestion
-- default 'in_force', which no evidence supported). docs/03b ('the two edges that cannot be extracted') draws the
-- line this record keeps: from statute text alone the corpus can say that an enactment was REPEALED BY ANOTHER
-- STATUTE, but not reliably whether a law ever came into force (commencement notifications live in the Gazette) nor
-- whether a court struck it down. So this records only the first, and only where the text proves it.
--
-- WHAT A ROW SAYS. A released Act of the corpus prints, in one provision, '<Title>, <year> ... is (hereby) repealed'
-- (or 'shall stand repealed'), naming a whole enactment; the title and year match exactly one released instrument of
-- the same jurisdiction; the clause carries no partial or qualifying words ('in its application to', 'so far as',
-- 'section N of', 'except'); and no released provision speaks of reviving that enactment. The repealing clause is
-- kept verbatim. Ordinances are not used as repealing evidence: a lapsed Ordinance's repeal is a legal question the
-- recorder does not settle.
--
-- THE DATE. instrument's ck_repeal (0004) lets status be 'repealed' only with a repealed_on date, so that a question
-- asked as at a date (INV-5) can place the repeal. The date is recorded only where the repealing Act prints it: one
-- bracketed assent/publication date under its title ('[6th October, 1996]') AND a commencement clause 'shall come
-- into force at once'. Otherwise repealed_on is NULL: the instrument still carries repealed_by_id (the repeal is
-- certain) but its status stays 'unknown' (the date is not established).
--
-- Like 0054/0062/0065 the record is about SOURCES: both sides are named by (source observation, expression
-- ordinal), and the repealing provision by its first source block and its path below the identity labels, so a
-- replay or an identity correction does not orphan it. instrument.status / repealed_on / repealed_by_id are derived from it after
-- every replay by tools/apply_statutory_repeals.py (tools/post_replay_sequence.sh step 2b3); audit A14 checks the
-- derivation both ways. Withdrawal is a later row with assertion 'withdrawn' (append-only, latest wins).
--
-- The release views are untouched: a repealed law stays released and queryable (docs/03b 'Repeal with savings');
-- operative filtering by status belongs to the retrieval layer's operative view.
--
-- REVERSAL (irreversible once a row exists, docs/03 §9): with the table empty, drop the view, triggers, function
-- and table. Governing contract: docs/03b (repeals edge; lifecycle); docs/03 §9; docs/SCHEMA.md.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE statutory_repeal (
    id                            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repealed_observation_id       bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    repealed_expression_ordinal   smallint NOT NULL CHECK (repealed_expression_ordinal >= 0),
    repealing_observation_id      bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    repealing_expression_ordinal  smallint NOT NULL CHECK (repealing_expression_ordinal >= 0),
    repealing_source_block_id     bigint NOT NULL CHECK (repealing_source_block_id > 0),
    repealing_relative_path       text NOT NULL CHECK (btrim(repealing_relative_path) <> ''),
    clause_text                   text NOT NULL CHECK (btrim(clause_text) <> ''),
    matched_title                 text NOT NULL CHECK (btrim(matched_title) <> ''),
    matched_year                  smallint NOT NULL CHECK (matched_year BETWEEN 1800 AND 2100),
    -- the repealing Act's printed date, only with its 'come into force at once' clause; NULL when not printed
    repealed_on                   date,
    repealed_on_basis             text,
    assertion                     text NOT NULL CHECK (assertion IN ('repealed', 'withdrawn')),
    method                        text NOT NULL CHECK (btrim(method) <> ''),
    evidence                      jsonb NOT NULL CHECK (coalesce(jsonb_typeof(evidence) = 'object'
                                                         AND btrim(evidence->>'reviewer_type') <> '', false)),
    recorded_by                   text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at                   timestamptz NOT NULL DEFAULT now(),
    CHECK ((repealed_observation_id, repealed_expression_ordinal)
           <> (repealing_observation_id, repealing_expression_ordinal)),
    CHECK ((repealed_on IS NULL) = (repealed_on_basis IS NULL)),
    CHECK (repealed_on_basis IS NULL OR btrim(repealed_on_basis) <> '')
);

CREATE INDEX statutory_repeal_key
    ON statutory_repeal (repealed_observation_id, repealed_expression_ordinal, repealing_observation_id,
                         repealing_expression_ordinal, repealing_relative_path, recorded_at DESC, id DESC);

CREATE FUNCTION check_statutory_repeal() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'statutory_repeal is append-only';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.repealed_observation_id AND outcome = 'landed')
       OR NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.repealing_observation_id AND outcome = 'landed') THEN
        RAISE EXCEPTION 'both observations must have landed';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER statutory_repeal_guard
BEFORE INSERT OR UPDATE OR DELETE ON statutory_repeal
FOR EACH ROW EXECUTE FUNCTION check_statutory_repeal();

CREATE TRIGGER statutory_repeal_no_truncate
BEFORE TRUNCATE ON statutory_repeal
FOR EACH STATEMENT EXECUTE FUNCTION check_statutory_repeal();

-- The standing assertions (latest per repealed expression and repealing provision), resolved to the ACTIVE
-- canonical instruments on both sides. A side that does not resolve drops the row (and A14 reports nothing for it).
CREATE VIEW v_statutory_repeal_current AS
WITH latest AS (
    SELECT DISTINCT ON (repealed_observation_id, repealed_expression_ordinal, repealing_observation_id,
                        repealing_expression_ordinal, repealing_relative_path) *
      FROM statutory_repeal
     ORDER BY repealed_observation_id, repealed_expression_ordinal, repealing_observation_id,
              repealing_expression_ordinal, repealing_relative_path, recorded_at DESC, id DESC)
SELECT l.*, repealed.id AS repealed_instrument_id, repealing.id AS repealing_instrument_id
  FROM latest l
  JOIN instrument repealed ON repealed.source_observation_id = l.repealed_observation_id
                          AND repealed.expression_ordinal = l.repealed_expression_ordinal
                          AND repealed.is_active AND repealed.duplicate_of IS NULL
  JOIN instrument repealing ON repealing.source_observation_id = l.repealing_observation_id
                           AND repealing.expression_ordinal = l.repealing_expression_ordinal
                           AND repealing.is_active AND repealing.duplicate_of IS NULL
 WHERE l.assertion = 'repealed';

COMMENT ON TABLE statutory_repeal IS
  'Append-only: a released Act of the corpus repeals a whole named enactment the corpus holds (same jurisdiction, '
  'exact unique title and year, no qualifying words, no revival), with the clause verbatim. instrument.status and '
  'repealed_by_id are derived from it after every replay by tools/apply_statutory_repeals.py. Migration 0066.';

COMMIT;
