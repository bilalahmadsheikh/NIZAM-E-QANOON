-- A legal expression may be released as a dated HISTORICAL text, never as
-- current law -- only when the owner said so.
--
-- Document 4434 (observation 2810) prints, as its expression 0, the
-- Constitution of Pakistan as amended to the Constitution (Twenty-second
-- Amendment) Act, 2016. The corpus's current Constitution is document 4419
-- (observation 507, expression 0), amended to the Twenty-seventh Amendment
-- Act, 2025. They are different versions of one work. The owner answered
-- (decision-review-2026-10-12-k.json, document 4434, q3
-- 'historical-expression'): release 4434 e0 as a dated historical text, never
-- shown as current law. Schema review: claude/schema-review-4434-q3.md
-- (APPROVE WITH CHANGES; this migration follows it).
--
-- WHAT EXISTS. Valid time is already modelled: provision_version.validity is a
-- daterange under the per-provision EXCLUDE `no_overlap` (0004, docs/03 §2.3).
-- Every version is written today as daterange(<observation date>, NULL) -- an
-- honest proxy for "consolidated current text". A historical expression's
-- versions are instead written with the reviewed, bounded window
-- daterange(from, to, '[)') (nizam.storage.legal_write), so
-- `validity @> as_of` returns its text only inside the window: INV-5 already
-- holds at the version level. What has no temporal gate is the instrument
-- level (library listings and opens ignore as_of), and nothing ties a bounded
-- window to the owner's word or keeps it through a replay.
--
-- WHAT CHANGES
--
--   * `instrument_expression_manifest` gains three nullable columns:
--       historical_validity           daterange -- the reviewed window [from, to)
--       current_source_observation_id bigint    -- the current expression of
--       current_expression_ordinal    smallint  --   the same work, by its stable
--                                                    key, never by a revision id
--     The manifest, not `instrument`, is the carrier: it is the append-only,
--     retire-and-append record that already holds owner-decision citations and
--     survives a replay (0063's pattern). `instrument` rows are re-inserted by
--     three explicit-column INSERT sites that would silently drop a new column,
--     and an instrument-level range would read as lifecycle (`repealed_on`
--     would wrongly say the Constitution was repealed). The current-expression
--     link is (observation, ordinal), not `instrument(id)`: a revision id is
--     retired by every replay of 4419 and an FK would block restore-proof
--     pruning. No FK is possible on the pair (the active target is only
--     partially unique); the plan validator and audit criterion A13 enforce it.
--   * CHECK instrument_expression_manifest_historical_shape: either all three
--     columns are NULL, or the window is non-empty and bounded on both sides,
--     the target is set and is not the manifest's own (observation, ordinal),
--     evidence.historical_basis is an object, and
--     evidence.historical_owner_decision cites the owner's answer
--     {export, document_id (= the manifest's document), question_id,
--      choice = 'historical-expression'} -- a closed set of one. That the
--     export really holds the answer is checked where the plan enters the
--     system (tools/materialize_multi_instrument.py validate_plan, via
--     nizam.workers.segment.owner_decision_answer), as for 0063.
--   * CHECK instrument_expression_manifest_historical_withdrawal_shape: the one
--     explicit way to stop treating an expression as historical. A successor
--     manifest with no window may carry evidence.historical_withdrawal
--     {withdraws_manifest_id, reason, owner_decision {export, document_id,
--      question_id, choice}}; it is written only by an explicit migration (the
--     0061 discipline), never by a replay.
--   * check_historical_versions(), a DEFERRABLE INITIALLY DEFERRED constraint
--     trigger on BOTH tables: while an active manifest for (observation,
--     ordinal) carries a window, every provision_version of every active
--     instrument of that (observation, ordinal) must lie inside it
--     (`validity <@ historical_validity`; an open-ended version never does).
--     It fires on the manifest (INSERT, or UPDATE of the window or is_active)
--     and on the instrument (INSERT, or UPDATE of is_active,
--     source_observation_id or expression_ordinal) -- an exact-tree overlay
--     copies the instrument row and never touches the manifest. Deferred,
--     because the materialiser writes the instrument and its versions before
--     the manifest that names them, in one transaction.
--   * check_historical_retention(), deferred, on the manifest: retiring,
--     un-windowing or deleting a historical manifest is refused at commit if
--     an active instrument of that (observation, ordinal) is left with no
--     active historical manifest -- unless the active successor carries an
--     explicit historical_withdrawal of a historical manifest of that key. A
--     re-materialisation that retires the manifest and inserts a windowed
--     successor passes. Without this, a replay that forgot the plan field
--     would silently release the old text as current law.
--   * v_instrument_historical: one row per active instrument that an active
--     manifest declares historical, joined on (source_observation_id,
--     expression_ordinal) and i.is_active -- never on
--     materialized_instrument_id, which an exact-tree overlay leaves pointing
--     at the copied-from revision. Library reads gate on it; A7 and A13 read
--     it.
--
-- WHAT DOES NOT CHANGE. No release view is redefined: v_release_instrument is
-- the release proof (`SELECT i.*` from instrument, untouched here). No row is
-- rewritten: every stored manifest has the three columns NULL, which the
-- CHECKs pass; no stored version is bounded (measured 13 Oct: 0 versions with
-- a finite upper bound), so the triggers hold for every stored row. The
-- `legal_edge` vocabulary (docs/03b §1.1, 14 kinds) is not extended; the link
-- lives in the typed manifest columns until legal_edge is built.
--
-- LOCKS. ADD COLUMN with no default and ADD CONSTRAINT CHECK take ACCESS
-- EXCLUSIVE on instrument_expression_manifest only briefly (the CHECK scans
-- 182 active + retired rows); CREATE CONSTRAINT TRIGGER on `instrument` takes
-- SHARE ROW EXCLUSIVE. lock_timeout makes the migration fail fast rather than
-- queue corpus readers behind a running replay. Apply when no segmentation or
-- materialisation run is active.
--
-- REVERSAL (safe only while no manifest has the columns set, per docs/03 §9):
-- DROP VIEW v_instrument_historical; drop the three constraint triggers
-- (manifest_historical_versions_guard, instrument_historical_versions_guard,
-- manifest_historical_retention_guard) and the two functions; drop the two
-- CHECKs; drop the three columns. No release view needs recreating.
--
-- Governing contract: INV-5 (law is answered as at a date); INV-1 (the window
-- and the current-expression link are rendered from records); docs/03 §2.3
-- (validity is valid time) and §9; docs/03b §1.1; docs/SCHEMA.md;
-- docs/CORPUS-CRITERIA.md A7, A13.

BEGIN;

SET LOCAL lock_timeout = '10s';

ALTER TABLE instrument_expression_manifest
    ADD COLUMN historical_validity           daterange,
    ADD COLUMN current_source_observation_id bigint
        REFERENCES source_observation(id) ON DELETE RESTRICT,
    ADD COLUMN current_expression_ordinal    smallint
        CHECK (current_expression_ordinal >= 0);

-- Every test is wrapped in coalesce(..., false): a CHECK that evaluates to
-- NULL passes, and ->> of an absent or JSON-null key is NULL.
ALTER TABLE instrument_expression_manifest
    ADD CONSTRAINT instrument_expression_manifest_historical_shape CHECK (
        (historical_validity IS NULL
         AND current_source_observation_id IS NULL
         AND current_expression_ordinal IS NULL)
        OR coalesce(
            NOT isempty(historical_validity)
            AND NOT lower_inf(historical_validity)
            AND NOT upper_inf(historical_validity)
            AND current_source_observation_id IS NOT NULL
            AND current_expression_ordinal IS NOT NULL
            AND (current_source_observation_id, current_expression_ordinal)
                IS DISTINCT FROM (source_observation_id, expression_ordinal)
            AND jsonb_typeof(evidence->'historical_basis') = 'object'
            AND jsonb_typeof(evidence->'historical_owner_decision') = 'object'
            AND evidence->'historical_owner_decision' ?& ARRAY['export','document_id',
                                                             'question_id','choice']
            AND jsonb_typeof(evidence->'historical_owner_decision'->'export') = 'string'
            AND (evidence->'historical_owner_decision'->>'export') LIKE '%.json'
            AND jsonb_typeof(evidence->'historical_owner_decision'->'document_id') = 'number'
            AND (evidence->'historical_owner_decision'->>'document_id') = document_id::text
            AND (evidence->'historical_owner_decision'->>'question_id') ~ '^q[0-9]+$'
            AND evidence->'historical_owner_decision'->>'choice' = 'historical-expression',
            false));

COMMENT ON CONSTRAINT instrument_expression_manifest_historical_shape
    ON instrument_expression_manifest IS
  'historical_validity, current_source_observation_id and current_expression_ordinal '
  'are all NULL, or: a non-empty window bounded on both sides, a current-expression '
  'target that is not this (observation, ordinal), evidence.historical_basis, and '
  'evidence.historical_owner_decision citing an owner answer for this document whose '
  'choice is ''historical-expression'' (migration 0064).';

ALTER TABLE instrument_expression_manifest
    ADD CONSTRAINT instrument_expression_manifest_historical_withdrawal_shape CHECK (
        NOT (evidence ? 'historical_withdrawal')
        OR coalesce(
            historical_validity IS NULL
            AND jsonb_typeof(evidence->'historical_withdrawal') = 'object'
            AND (evidence->'historical_withdrawal'->>'withdraws_manifest_id')
                ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            AND btrim(evidence->'historical_withdrawal'->>'reason') <> ''
            AND jsonb_typeof(evidence->'historical_withdrawal'->'owner_decision') = 'object'
            AND evidence->'historical_withdrawal'->'owner_decision'
                ?& ARRAY['export','document_id','question_id','choice']
            AND (evidence->'historical_withdrawal'->'owner_decision'->>'export') LIKE '%.json'
            AND (evidence->'historical_withdrawal'->'owner_decision'->>'document_id')
                = document_id::text
            AND (evidence->'historical_withdrawal'->'owner_decision'->>'question_id') ~ '^q[0-9]+$'
            AND btrim(evidence->'historical_withdrawal'->'owner_decision'->>'choice') <> '',
            false));

COMMENT ON CONSTRAINT instrument_expression_manifest_historical_withdrawal_shape
    ON instrument_expression_manifest IS
  'evidence.historical_withdrawal (the only route that ends a historical declaration, '
  'written by an explicit migration) sits on a manifest with no window and names the '
  'withdrawn manifest, a reason and an owner decision for this document (0064).';

COMMENT ON COLUMN instrument_expression_manifest.historical_validity IS
  'NULL: the expression is current consolidated text. Otherwise the reviewed window '
  '[from, to) in which this historical text was the law; every version of the '
  'expression lies inside it, and it is never shown as current law (0064).';
COMMENT ON COLUMN instrument_expression_manifest.current_source_observation_id IS
  'With current_expression_ordinal: the stable key of the current expression of the '
  'same work, resolved at read time to the active, released revision (0064).';
COMMENT ON COLUMN instrument_expression_manifest.current_expression_ordinal IS
  'See current_source_observation_id (0064).';

-- One function, two tables. Deferred: judge the key as it stands at commit,
-- not as first inserted (0063's convention).
CREATE FUNCTION check_historical_versions() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    obs        bigint;
    ord        smallint;
    live       boolean;
    win        daterange;
    offender   record;
BEGIN
    IF TG_TABLE_NAME = 'instrument' THEN
        SELECT i.source_observation_id, i.expression_ordinal, i.is_active
          INTO obs, ord, live
          FROM instrument i WHERE i.id = NEW.id;
    ELSE
        SELECT m.source_observation_id, m.expression_ordinal, m.is_active
          INTO obs, ord, live
          FROM instrument_expression_manifest m WHERE m.id = NEW.id;
    END IF;
    IF NOT FOUND OR NOT live THEN
        RETURN NULL;
    END IF;
    SELECT m.historical_validity INTO win
      FROM instrument_expression_manifest m
     WHERE m.source_observation_id = obs
       AND m.expression_ordinal    = ord
       AND m.is_active
       AND m.historical_validity IS NOT NULL;
    IF win IS NULL THEN
        RETURN NULL;                       -- current text: nothing to bound
    END IF;
    SELECT i.id AS instrument_id, v.id AS version_id, v.validity
      INTO offender
      FROM instrument i
      JOIN provision p          ON p.instrument_id = i.id
      JOIN provision_version v  ON v.provision_id  = p.id
     WHERE i.source_observation_id = obs
       AND i.expression_ordinal    = ord
       AND i.is_active
       AND NOT (v.validity <@ win)
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION
          'instrument % (observation %, expression %) is a historical expression in '
          'force %, but its version % has validity %; a historical text is never '
          'written as open-ended current law',
          offender.instrument_id, obs, ord, win, offender.version_id, offender.validity;
    END IF;
    RETURN NULL;
END $$;

COMMENT ON FUNCTION check_historical_versions() IS
  'Deferred guard (0064), fired from instrument_expression_manifest and from '
  'instrument: while an active manifest gives (observation, ordinal) a historical '
  'window, every version of every active instrument of that key lies inside it.';

CREATE CONSTRAINT TRIGGER manifest_historical_versions_guard
AFTER INSERT OR UPDATE OF historical_validity, is_active
ON instrument_expression_manifest
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW WHEN (NEW.historical_validity IS NOT NULL AND NEW.is_active)
EXECUTE FUNCTION check_historical_versions();

CREATE CONSTRAINT TRIGGER instrument_historical_versions_guard
AFTER INSERT OR UPDATE OF is_active, source_observation_id, expression_ordinal
ON instrument
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW WHEN (NEW.is_active)
EXECUTE FUNCTION check_historical_versions();

-- The reverse direction: a historical declaration is never lost by a replay.
CREATE FUNCTION check_historical_retention() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    exposed uuid;
BEGIN
    SELECT i.id INTO exposed
      FROM instrument i
     WHERE i.source_observation_id = OLD.source_observation_id
       AND i.expression_ordinal    = OLD.expression_ordinal
       AND i.is_active
       AND NOT EXISTS (
           SELECT 1 FROM instrument_expression_manifest m
            WHERE m.source_observation_id = i.source_observation_id
              AND m.expression_ordinal    = i.expression_ordinal
              AND m.is_active
              AND m.historical_validity IS NOT NULL)
       AND NOT EXISTS (
           SELECT 1
             FROM instrument_expression_manifest s
             JOIN instrument_expression_manifest w
               ON w.id::text = s.evidence->'historical_withdrawal'->>'withdraws_manifest_id'
            WHERE s.source_observation_id = i.source_observation_id
              AND s.expression_ordinal    = i.expression_ordinal
              AND s.is_active
              AND w.source_observation_id = i.source_observation_id
              AND w.expression_ordinal    = i.expression_ordinal
              AND w.historical_validity IS NOT NULL)
     LIMIT 1;
    IF exposed IS NOT NULL THEN
        RAISE EXCEPTION
          'manifest % (observation %, expression %) declared a historical text in '
          'force %; active instrument % would be left with no historical manifest '
          'and read as current law. Carry the window forward, or withdraw it '
          'explicitly (evidence.historical_withdrawal, by migration)',
          OLD.id, OLD.source_observation_id, OLD.expression_ordinal,
          OLD.historical_validity, exposed;
    END IF;
    RETURN NULL;
END $$;

COMMENT ON FUNCTION check_historical_retention() IS
  'Deferred guard (0064): retiring, un-windowing or deleting a historical manifest '
  'is refused at commit while an active instrument of its (observation, ordinal) '
  'has no active historical manifest and no explicit historical_withdrawal.';

CREATE CONSTRAINT TRIGGER manifest_historical_retention_guard
AFTER UPDATE OF is_active, historical_validity, current_source_observation_id,
                current_expression_ordinal OR DELETE
ON instrument_expression_manifest
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW WHEN (OLD.historical_validity IS NOT NULL)
EXECUTE FUNCTION check_historical_retention();

-- The instrument-level gate's source. Joined on the stable key and the active
-- instrument, never on materialized_instrument_id.
CREATE VIEW v_instrument_historical AS
SELECT i.id                              AS instrument_id,
       i.document_id,
       i.source_observation_id,
       i.expression_ordinal,
       m.id                              AS manifest_id,
       m.historical_validity,
       lower(m.historical_validity)      AS valid_from,
       upper(m.historical_validity)      AS valid_to,
       m.current_source_observation_id,
       m.current_expression_ordinal,
       m.evidence->'historical_basis'          AS historical_basis,
       m.evidence->'historical_owner_decision' AS historical_owner_decision
  FROM instrument_expression_manifest m
  JOIN instrument i
    ON i.source_observation_id = m.source_observation_id
   AND i.expression_ordinal    = m.expression_ordinal
   AND i.is_active
 WHERE m.is_active
   AND m.historical_validity IS NOT NULL;

COMMENT ON VIEW v_instrument_historical IS
  'Active instruments an active expression manifest declares historical (0064): the '
  'window [valid_from, valid_to) and the current expression of the same work. A '
  'library read lists or opens such an instrument only for an as_of inside the window.';

COMMIT;
