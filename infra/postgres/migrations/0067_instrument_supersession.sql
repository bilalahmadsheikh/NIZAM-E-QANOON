-- An Ordinance superseded by a later Act of the same name, recorded as a link and nothing more.
--
-- WHY. The 20 Oct recrawl landed ~680 federal Ordinances from the Ministry of Law archive. An Ordinance lapses after
-- 120 days unless replaced, re-promulgated or extended -- a legal fact the text alone does not prove, so every one
-- carries lifecycle status 'unknown'. The owner decided (decision-review-2026-10-21 q6 'mark-replaced'): "Where the
-- corpus holds a later Act with the same title, the Ordinance is linked to it and shown as replaced; all others stay
-- 'unknown'."
--
-- WHAT A ROW SAYS -- and what it does not. The predecessor (an instrument whose title is an Ordinance) and the
-- successor (an Act of the same jurisdiction, the same folded title, year >= the Ordinance's) are linked as
-- docs/03b's `superseded_by` relation (named in §2 "Constructs a generic legal schema will miss", devolution row; the fourteen edge types of §1.1 have no closer
-- edge, and `repeals` needs the repealing clause, which migration 0066 records where the Act prints it). It does
-- NOT set instrument.status: 03b's life_stage has no 'replaced' value, and 'lapsed' or 'repealed' would assert a date
-- and a mechanism this record does not establish. `basis` says how strong the link is:
--   act_text_names_ordinance  -- the successor Act's own released text names the Ordinance by title and year;
--   same_title_successor_act  -- only the owner-approved inference: one later Act carries the same title.
-- Ambiguous cases (two or more candidate Acts) are not recorded.
--
-- Like 0054/0062/0065/0066 the record is about SOURCES: both sides are named by (source observation, expression
-- ordinal), so a replay does not orphan it. Withdrawal is a later row with assertion 'withdrawn' (append-only,
-- latest wins). The release views are untouched.
--
-- REVERSAL (irreversible once a row exists, docs/03 §9): with the table empty, drop the view, triggers, function
-- and table. Governing contract: docs/03b §2 (superseded_by, devolution row) and §1.1; docs/03 §9; owner decision q6.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE instrument_supersession (
    id                              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    superseded_observation_id       bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    superseded_expression_ordinal   smallint NOT NULL CHECK (superseded_expression_ordinal >= 0),
    superseding_observation_id      bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    superseding_expression_ordinal  smallint NOT NULL CHECK (superseding_expression_ordinal >= 0),
    superseded_title                text NOT NULL CHECK (btrim(superseded_title) <> ''),
    superseded_year                 smallint NOT NULL CHECK (superseded_year BETWEEN 1800 AND 2100),
    superseding_title               text NOT NULL CHECK (btrim(superseding_title) <> ''),
    superseding_year                smallint NOT NULL CHECK (superseding_year BETWEEN 1800 AND 2100),
    matched_key                     text NOT NULL CHECK (btrim(matched_key) <> ''),
    basis                           text NOT NULL CHECK (basis IN ('act_text_names_ordinance', 'same_title_successor_act')),
    assertion                       text NOT NULL CHECK (assertion IN ('superseded', 'withdrawn')),
    method                          text NOT NULL CHECK (btrim(method) <> ''),
    evidence                        jsonb NOT NULL CHECK (coalesce(jsonb_typeof(evidence) = 'object'
                                                           AND btrim(evidence->>'reviewer_type') <> ''
                                                           AND btrim(evidence->>'owner_decision') <> '', false)),
    recorded_by                     text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at                     timestamptz NOT NULL DEFAULT now(),
    CHECK ((superseded_observation_id, superseded_expression_ordinal)
           <> (superseding_observation_id, superseding_expression_ordinal)),
    CHECK (superseding_year >= superseded_year)
);

CREATE INDEX instrument_supersession_key
    ON instrument_supersession (superseded_observation_id, superseded_expression_ordinal, superseding_observation_id,
                                superseding_expression_ordinal, recorded_at DESC, id DESC);

CREATE FUNCTION check_instrument_supersession() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'instrument_supersession is append-only';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.superseded_observation_id AND outcome = 'landed')
       OR NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.superseding_observation_id AND outcome = 'landed') THEN
        RAISE EXCEPTION 'both observations must have landed';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER instrument_supersession_guard
BEFORE INSERT OR UPDATE OR DELETE ON instrument_supersession
FOR EACH ROW EXECUTE FUNCTION check_instrument_supersession();

CREATE TRIGGER instrument_supersession_no_truncate
BEFORE TRUNCATE ON instrument_supersession
FOR EACH STATEMENT EXECUTE FUNCTION check_instrument_supersession();

-- The standing links (latest per pair), resolved to the ACTIVE canonical instruments on both sides.
CREATE VIEW v_instrument_supersession_current AS
WITH latest AS (
    SELECT DISTINCT ON (superseded_observation_id, superseded_expression_ordinal, superseding_observation_id,
                        superseding_expression_ordinal) *
      FROM instrument_supersession
     ORDER BY superseded_observation_id, superseded_expression_ordinal, superseding_observation_id,
              superseding_expression_ordinal, recorded_at DESC, id DESC)
SELECT l.*, old.id AS superseded_instrument_id, new.id AS superseding_instrument_id
  FROM latest l
  JOIN instrument old ON old.source_observation_id = l.superseded_observation_id
                     AND old.expression_ordinal = l.superseded_expression_ordinal
                     AND old.is_active AND old.duplicate_of IS NULL
  JOIN instrument new ON new.source_observation_id = l.superseding_observation_id
                     AND new.expression_ordinal = l.superseding_expression_ordinal
                     AND new.is_active AND new.duplicate_of IS NULL
 WHERE l.assertion = 'superseded';

COMMENT ON TABLE instrument_supersession IS
  'Append-only: an Ordinance linked to a later Act of the same jurisdiction and folded title (docs/03b superseded_by; '
  'owner decision 2026-10-21 q6). basis act_text_names_ordinance when the Act''s text names it, else '
  'same_title_successor_act. Does not set lifecycle status. Migration 0067.';

COMMIT;
