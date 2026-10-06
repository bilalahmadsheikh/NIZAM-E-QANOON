-- A segmentation profile, pinned per source observation.
--
-- By 25 Sep 2026 the remaining blocked instruments (390) were almost all
-- blocked by parser shapes -- contents numbered one off from the body, schedule
-- headings never opened, repeal stubs inside a block, membership tables read as
-- sections -- and every candidate fix also changes trees that are already
-- RELEASED (the mid-block stub shape alone occurs in 80 released documents).
-- Changing a released tree is a correction that needs its own review, so a new
-- rule could only ship if every released document came out identical, which
-- cut most rules down to nothing.
--
-- A profile separates the two. The segmenter keeps one code path; a named
-- profile switches on additional rules. The default profile is exactly today's
-- parser. A document is parsed with a profile only when this table pins its
-- observation to one.
--
-- WHY A PIN AND NOT "IS IT RELEASED?". The corpus is replayed constantly.
-- If the parser chose its rules by asking whether a document is released, a
-- document released under the new rules would, on its next replay, be
-- "released", fall back to the default rules, and silently lose the repair.
-- The choice is therefore made once, recorded here, and honoured by every
-- replay: nizam.workers.segment.build() reads it for the observation it
-- builds, so the worker, the multi-instrument materializer and the stale-tree
-- fingerprints all see the same profile.
--
-- WHAT A PIN MAY TOUCH. Only an observation none of whose instruments is
-- released at the moment of pinning (trigger below). A released tree is never
-- re-parsed under new rules by this route; promoting a profile rule into the
-- default parser is a separate, reviewed correction.
--
-- Append-only like the other decision evidence: a later row supersedes an
-- earlier one for the same observation (profile 'default' returns it to the
-- default parser); rows are never updated or deleted.
--
-- Governing contract: docs/SEGMENTATION-PROFILES.md.

BEGIN;

CREATE TABLE segmentation_profile_pin (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_observation_id bigint NOT NULL REFERENCES source_observation(id)
                              ON DELETE RESTRICT,
    -- Closed list: a new profile is a new migration, never a typo.
    profile               text NOT NULL
                              CHECK (profile IN ('default', 'unreleased-v1')),
    reason                text NOT NULL CHECK (btrim(reason) <> ''),
    evidence              jsonb NOT NULL DEFAULT '{}'::jsonb
                              CHECK (jsonb_typeof(evidence) = 'object'),
    pinned_by             text NOT NULL CHECK (btrim(pinned_by) <> ''),
    pinned_at             timestamptz NOT NULL DEFAULT now(),
    supersedes_id         bigint REFERENCES segmentation_profile_pin(id)
                              ON DELETE RESTRICT
);

CREATE INDEX segmentation_profile_pin_observation
    ON segmentation_profile_pin (source_observation_id, pinned_at DESC, id DESC);

CREATE VIEW v_segmentation_profile_latest AS
SELECT DISTINCT ON (source_observation_id) p.*
  FROM segmentation_profile_pin p
 ORDER BY source_observation_id, pinned_at DESC, id DESC;

CREATE FUNCTION segmentation_profile_pin_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    previous segmentation_profile_pin;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'segmentation_profile_pin is append-only';
    END IF;
    -- A non-default profile may only be pinned while nothing built from the
    -- observation is released: the pin must never re-parse a released tree.
    IF NEW.profile <> 'default' AND EXISTS (
        SELECT 1 FROM v_release_instrument r
         WHERE r.source_observation_id = NEW.source_observation_id
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

CREATE TRIGGER segmentation_profile_pin_guard
BEFORE INSERT OR UPDATE OR DELETE ON segmentation_profile_pin
FOR EACH ROW EXECUTE FUNCTION segmentation_profile_pin_guard();

COMMENT ON TABLE segmentation_profile_pin IS
  'Append-only: which segmentation profile a source observation is parsed with. '
  'Absent or ''default'' = the default parser. Non-default pins are refused for '
  'observations with a released instrument. See docs/SEGMENTATION-PROFILES.md.';

COMMIT;
