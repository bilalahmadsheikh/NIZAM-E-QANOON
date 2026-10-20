-- WITHDRAWN, NEVER APPLIED (builder BZ, 16 Oct 2026). Drafted as migration 0065 for the owner's option (a) (a
-- released-pin exception for doc 3696); the owner then chose (b) -- "try to release 3696 in the best way ... retire old
-- and then do it default also" -- so it was moved out of infra/postgres/migrations before any database applied it.
-- The 0056 rule (no non-default pin on a released observation) stands unchanged.
--
-- A non-default profile pin on a RELEASED observation -- only by an owner-decided, recorded exception.
--
-- 0056 refuses any non-default pin on an observation with a released
-- instrument: "the pin must never re-parse a released tree" (docs/
-- SEGMENTATION-PROFILES.md). That stays the rule. Document 3696 (observation
-- 4624, the Sindh Govt. Gazette Extraordinary of 22 September 1998, six
-- instruments) is released under `default` from a legacy manifest whose E1/E2
-- start two blocks late and whose E2 swallows the Pension Regulation. Its
-- reviewed realignment (agent K4; owner export j q1 'split', delegated q2
-- 'split-and-realign', q3 'keep-both') is built under `unreleased-v4`, and every
-- released path it moves is listed and approved (claude/agK4/3696-path-moves.json:
-- same 68, text 22, moved 128, gone 5 -- no reuse, nothing of law dropping out).
-- The owner decided (chat, 16 Oct 2026): "for 3696 allow the pin".
--
-- WHAT CHANGES
--
--   * New append-only table `segmentation_released_pin_exception`: one row per
--     (source_observation_id, profile) the owner has admitted, carrying the
--     owner's decision (an export answer or a dated chat quote), the approved
--     path-move list (artifact path + SHA-256) and who recorded it. UPDATE and
--     DELETE are refused; a withdrawn exception is a new migration, not an edit.
--   * `segmentation_profile_pin_guard()` (0056) is replaced: a non-default pin
--     on an observation with a released instrument is admitted ONLY when an
--     exception row exists for exactly that observation and that profile.
--     Everything else is unchanged: append-only pins, the superseded pin's
--     observation check, and the refusal for every other released observation
--     and every other profile.
--
-- WHAT DOES NOT CHANGE. No pin is written here, no exception row is recorded
-- here (the builder records 3696's after this migration is applied and
-- reviewed), and no release view is redefined. The pin tool
-- (tools/pin_segmentation_profile.py) applies the same rule before the trigger.

BEGIN;

CREATE TABLE segmentation_released_pin_exception (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_observation_id bigint NOT NULL REFERENCES source_observation(id)
                              ON DELETE RESTRICT,
    -- a non-default profile from the closed list of 0059
    profile               text NOT NULL
                              CHECK (profile IN ('unreleased-v1', 'unreleased-v2',
                                                 'unreleased-v3', 'unreleased-v4')),
    -- the owner's decision: an export answer {export, document_id, question_id, choice}
    -- or a dated chat quote {source: 'owner chat', date, quote}
    owner_decision        jsonb NOT NULL
                              CHECK (jsonb_typeof(owner_decision) = 'object'
                                     AND (   (owner_decision ? 'export'
                                              AND owner_decision ? 'question_id'
                                              AND btrim(owner_decision->>'export') <> '')
                                          OR (owner_decision->>'source' = 'owner chat'
                                              AND owner_decision->>'date' ~ '^\d{4}-\d{2}-\d{2}$'
                                              AND btrim(coalesce(owner_decision->>'quote', '')) <> ''))),
    path_moves_artifact   text NOT NULL CHECK (btrim(path_moves_artifact) <> ''),
    path_moves_sha256     text NOT NULL CHECK (path_moves_sha256 ~ '^[0-9a-f]{64}$'),
    reason                text NOT NULL CHECK (btrim(reason) <> ''),
    recorded_by           text NOT NULL CHECK (btrim(recorded_by) <> ''),
    created_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_observation_id, profile)
);

CREATE FUNCTION segmentation_released_pin_exception_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'segmentation_released_pin_exception is append-only';
END $$;

CREATE TRIGGER segmentation_released_pin_exception_append_only
BEFORE UPDATE OR DELETE ON segmentation_released_pin_exception
FOR EACH ROW EXECUTE FUNCTION segmentation_released_pin_exception_append_only();

CREATE OR REPLACE FUNCTION segmentation_profile_pin_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    previous segmentation_profile_pin;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'segmentation_profile_pin is append-only';
    END IF;
    -- A non-default profile may only be pinned while nothing built from the
    -- observation is released: the pin must never re-parse a released tree --
    -- unless the owner admitted exactly this observation and profile (0065).
    IF NEW.profile <> 'default' AND EXISTS (
        SELECT 1 FROM v_release_instrument r
         WHERE r.source_observation_id = NEW.source_observation_id
    ) AND NOT EXISTS (
        SELECT 1 FROM segmentation_released_pin_exception x
         WHERE x.source_observation_id = NEW.source_observation_id
           AND x.profile = NEW.profile
    ) THEN
        RAISE EXCEPTION
          'observation % has a released instrument; a profile pin cannot re-parse it',
          NEW.source_observation_id;
    END IF;
    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT * INTO previous FROM segmentation_profile_pin
         WHERE id = NEW.supersedes_id;
        IF NOT FOUND
           OR previous.source_observation_id <> NEW.source_observation_id THEN
            RAISE EXCEPTION 'superseded pin belongs to another observation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

COMMENT ON TABLE segmentation_released_pin_exception IS
  'Append-only (0065): the owner-admitted exceptions to 0056''s rule that a released '
  'observation takes no non-default pin -- one row per (observation, profile), citing '
  'the owner''s decision and the approved path-move list (artifact + SHA-256).';

COMMENT ON TABLE segmentation_profile_pin IS
  'Append-only: which segmentation profile a source observation is parsed with. '
  'Absent or ''default'' = the default parser. Non-default pins are refused for '
  'observations with a released instrument, except an observation and profile the '
  'owner admitted in segmentation_released_pin_exception (0065). See '
  'docs/SEGMENTATION-PROFILES.md.';

COMMIT;
