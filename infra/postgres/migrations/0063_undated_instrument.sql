-- An instrument may have no year -- only when the owner said it is undated.
--
-- Doc 02 §7 makes an instrument's identity jurisdiction + kind + number +
-- year, and 0004 made `instrument.year` `smallint NOT NULL CHECK (year BETWEEN
-- 1800 AND 2100)`; 0040 did the same for
-- `instrument_expression_manifest.detected_year`. Document 1973 (the Punjab
-- Excise Powers and Appeal Orders) binds three West Pakistan notifications
-- that print no date of their own. The owner answered
-- (decision-review-2026-10-10-i.json, document 1973, q3 'undated'): release
-- them with no year, cited by description, the year shown as 'undated'. A
-- year inferred from the surrounding text (the draft plan carried 1956 / 1956
-- / 1959, "the earliest the text admits") would be rendered as a fact the
-- source never prints -- INV-1 forbids it.
--
-- WHAT CHANGES
--
--   * `instrument.year` and `instrument_expression_manifest.detected_year`
--     drop NOT NULL. Their range CHECKs stay, and pass NULL.
--   * A manifest may carry detected_year NULL only when its evidence says
--     `year_status` = 'undated' and cites the owner answer as
--     `year_owner_decision` {export, document_id (= the manifest's document),
--     question_id, choice = 'undated'} -- a closed set of one. That the export
--     really holds the answer is checked where the plan enters the system
--     (tools/materialize_multi_instrument.py validate_plan, via
--     nizam.workers.segment.owner_decision_answer), as for every other cited
--     owner decision; the database pins the citation's shape and choice.
--   * An instrument may carry year NULL only while an ACTIVE manifest for its
--     (source_observation_id, expression_ordinal) has detected_year NULL --
--     which the CHECK above ties to the owner's 'undated'. A plain
--     single-expression build has no manifest, so it can never store a NULL
--     year. The check is a DEFERRABLE INITIALLY DEFERRED constraint trigger:
--     the materialiser (nizam.storage.legal_write) inserts the instrument
--     before the manifest that names it, in one transaction, and the check runs
--     at commit. Exact-tree overlays that copy an instrument row keep the
--     active manifest, and pass. It fires on INSERT and on any UPDATE of year,
--     is_active, source_observation_id or expression_ordinal, so re-activating
--     or re-keying an undated row is judged again.
--   * The reverse direction, on the manifest (deferred too): retiring,
--     re-dating or deleting a NULL-year manifest is refused at commit if it
--     would leave an active NULL-year instrument of that (observation,
--     ordinal) with no active undated manifest. A re-materialisation retires
--     the old manifest and inserts its successor in one transaction, and
--     passes.
--   * A NULL-year manifest that names its materialised instrument must name a
--     NULL-year instrument (deferred): an undated manifest cannot vouch for a
--     dated tree.
--   * `v_instrument_duplicates` groups by (jurisdiction, kind, number, year);
--     GROUP BY treats two NULL years as equal, which would report two undated
--     instruments sharing a printed number as one citation claimed twice. An
--     undated instrument has no complete citation identity to collide on, so
--     the view leaves it out.
--
-- Nothing existing changes: no row has a NULL year (both columns are NOT NULL
-- until this migration), so the new CHECK and trigger hold for every stored
-- row, every released tree is untouched, and the release views are not
-- redefined. Path prefixes are built in nizam/workers/segment.py build()
-- ('y' + year, 'yundated' for NULL -- a builder change listed in the review
-- note, not made here). The instrument_citation and instrument_year indexes are
-- unaffected (NULLs index normally, and instrument_citation is not unique).
--
-- LOCKS. ALTER COLUMN ... DROP NOT NULL is catalogue-only but takes ACCESS
-- EXCLUSIVE on `instrument`; lock_timeout makes the migration fail fast
-- rather than queue every corpus reader behind a running replay. Apply when no
-- segmentation run is active.
--
-- REVERSAL (explicitly irreversible once an undated row exists, per docs/03
-- §9): with no NULL year stored in either table, drop the three constraint
-- triggers (instrument_undated_guard, manifest_undated_retirement_guard,
-- manifest_undated_instrument_guard) and their three functions, drop the
-- manifest CHECK instrument_expression_manifest_undated_by_owner, restore
-- v_instrument_duplicates to its 0012 definition (WHERE number IS NOT NULL
-- AND is_active), restore the column comment (instrument.year had none before
-- 0063: COMMENT ON COLUMN instrument.year IS NULL), and SET NOT NULL on
-- instrument.year and instrument_expression_manifest.detected_year.
--
-- Governing contract: INV-1 (citation parts are rendered from records, never
-- generated); docs/02 §7 (instrument identity); docs/03 §9; docs/SCHEMA.md.

BEGIN;

SET LOCAL lock_timeout = '10s';

ALTER TABLE instrument ALTER COLUMN year DROP NOT NULL;
ALTER TABLE instrument_expression_manifest ALTER COLUMN detected_year DROP NOT NULL;

-- Every test is wrapped in coalesce(..., false): a CHECK that evaluates to
-- NULL passes, and ->> of an absent or JSON-null key is NULL.
ALTER TABLE instrument_expression_manifest
    ADD CONSTRAINT instrument_expression_manifest_undated_by_owner CHECK (
        detected_year IS NOT NULL
        OR coalesce(
            evidence->>'year_status' = 'undated'
            AND jsonb_typeof(evidence->'year_owner_decision') = 'object'
            AND evidence->'year_owner_decision' ?& ARRAY['export','document_id',
                                                       'question_id','choice']
            AND jsonb_typeof(evidence->'year_owner_decision'->'export') = 'string'
            AND (evidence->'year_owner_decision'->>'export') LIKE '%.json'
            AND jsonb_typeof(evidence->'year_owner_decision'->'document_id') = 'number'
            AND (evidence->'year_owner_decision'->>'document_id') = document_id::text
            AND (evidence->'year_owner_decision'->>'question_id') ~ '^q[0-9]+$'
            AND evidence->'year_owner_decision'->>'choice' = 'undated',
            false));

COMMENT ON CONSTRAINT instrument_expression_manifest_undated_by_owner
    ON instrument_expression_manifest IS
  'detected_year NULL only with evidence.year_status = undated and '
  'evidence.year_owner_decision citing an owner answer for this document whose '
  'choice is ''undated'' (migration 0063).';

CREATE FUNCTION check_instrument_undated() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    current_row instrument%ROWTYPE;
BEGIN
    -- Deferred: judge the row as it stands at commit, not as first inserted.
    SELECT * INTO current_row FROM instrument WHERE id = NEW.id;
    IF NOT FOUND OR current_row.year IS NOT NULL OR NOT current_row.is_active THEN
        RETURN NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM instrument_expression_manifest m
         WHERE m.source_observation_id = current_row.source_observation_id
           AND m.expression_ordinal    = current_row.expression_ordinal
           AND m.is_active
           AND m.detected_year IS NULL
    ) THEN
        RAISE EXCEPTION
          'instrument % (observation %, expression %) has no year, and no active '
          'expression manifest records the owner''s ''undated'' for it; a year '
          'is never left out or inferred otherwise',
          current_row.id, current_row.source_observation_id,
          current_row.expression_ordinal;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER instrument_undated_guard
AFTER INSERT OR UPDATE OF year, is_active, source_observation_id, expression_ordinal
ON instrument
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW WHEN (NEW.year IS NULL)
EXECUTE FUNCTION check_instrument_undated();

COMMENT ON FUNCTION check_instrument_undated() IS
  'Deferred guard (0063): an active instrument with year NULL needs an active '
  'manifest for its observation and expression with detected_year NULL, which '
  'the manifest CHECK ties to an owner answer whose choice is ''undated''.';

-- The reverse direction: a NULL-year manifest may not be retired, re-dated or
-- deleted while an active NULL-year instrument of its (observation, ordinal)
-- would be left without an active undated manifest. Judged at commit, so a
-- re-materialisation (retire the old manifest, insert its successor) passes.
CREATE FUNCTION check_manifest_undated_retirement() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    orphan uuid;
BEGIN
    SELECT i.id INTO orphan
      FROM instrument i
     WHERE i.source_observation_id = OLD.source_observation_id
       AND i.expression_ordinal    = OLD.expression_ordinal
       AND i.is_active AND i.year IS NULL
       AND NOT EXISTS (
           SELECT 1 FROM instrument_expression_manifest m
            WHERE m.source_observation_id = i.source_observation_id
              AND m.expression_ordinal    = i.expression_ordinal
              AND m.is_active AND m.detected_year IS NULL)
     LIMIT 1;
    IF orphan IS NOT NULL THEN
        RAISE EXCEPTION
          'manifest % (observation %, expression %) was the owner''s ''undated'' '
          'for active instrument %, which has no year; no active undated manifest '
          'is left to vouch for it',
          OLD.id, OLD.source_observation_id, OLD.expression_ordinal, orphan;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER manifest_undated_retirement_guard
AFTER UPDATE OF is_active, detected_year OR DELETE ON instrument_expression_manifest
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW WHEN (OLD.detected_year IS NULL)
EXECUTE FUNCTION check_manifest_undated_retirement();

-- An undated manifest that names its materialised instrument names an undated
-- one.
CREATE FUNCTION check_manifest_undated_instrument() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    current_row instrument_expression_manifest%ROWTYPE;
    named_year  smallint;
BEGIN
    SELECT * INTO current_row FROM instrument_expression_manifest WHERE id = NEW.id;
    IF NOT FOUND OR current_row.detected_year IS NOT NULL
       OR current_row.materialized_instrument_id IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT i.year INTO named_year FROM instrument i
     WHERE i.id = current_row.materialized_instrument_id;
    IF named_year IS NOT NULL THEN
        RAISE EXCEPTION
          'manifest % records the owner''s ''undated'' but names instrument %, '
          'which has year %', current_row.id,
          current_row.materialized_instrument_id, named_year;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER manifest_undated_instrument_guard
AFTER INSERT OR UPDATE OF detected_year, materialized_instrument_id
ON instrument_expression_manifest
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW WHEN (NEW.detected_year IS NULL AND NEW.materialized_instrument_id IS NOT NULL)
EXECUTE FUNCTION check_manifest_undated_instrument();

-- Same columns; an undated instrument has no complete citation identity, so it
-- cannot be reported as a citation claimed twice.
CREATE OR REPLACE VIEW v_instrument_duplicates AS
SELECT jurisdiction, kind, number, year,
       count(*) AS documents,
       array_agg(id ORDER BY created_at) AS instrument_ids,
       array_agg(document_id ORDER BY created_at) AS document_ids,
       min(short_title) AS a_title
  FROM instrument
 WHERE number IS NOT NULL AND year IS NOT NULL AND is_active
 GROUP BY jurisdiction, kind, number, year
HAVING count(*) > 1;

COMMENT ON COLUMN instrument.year IS
  'Year of the instrument as printed or reviewed (1800-2100). NULL only for an '
  'owner-declared undated instrument (0063); render ''undated'', never infer one.';

COMMIT;
