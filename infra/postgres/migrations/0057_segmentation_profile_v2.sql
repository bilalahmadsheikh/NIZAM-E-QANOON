-- A second segmentation profile, `unreleased-v2`.
--
-- docs/SEGMENTATION-PROFILES.md: a profile is frozen once something is
-- released under it. A rule may join an existing profile only if every
-- instrument released under that profile rebuilds identically; otherwise the
-- next profile is opened.
--
-- The rule that needs it is `margin_heading_blocks`: a right-margin block
-- that exactly repeats one of the document's own contents headings is a
-- margin heading, not text. Doc 2386's text layer sets page 15's margin
-- heading "Functions of the Board of Faculty." inside statute 2(3)'s sentence
-- across the page break ("... shall be Functions of the Board of Faculty.
-- one-half of the total number of members"). The same rule would also take
-- the trailing margin heading out of doc 1014's section 3 text, a tree
-- already released under `unreleased-v1`, so it cannot join that profile.
--
-- `unreleased-v2` = every `unreleased-v1` rule plus `margin_heading_blocks`
-- (nizam/corpus/segment.py SEGMENTATION_PROFILES). Existing pins are not
-- touched; a document moves to v2 only by a new, superseding pin.

BEGIN;

ALTER TABLE segmentation_profile_pin
    DROP CONSTRAINT segmentation_profile_pin_profile_check;

ALTER TABLE segmentation_profile_pin
    ADD CONSTRAINT segmentation_profile_pin_profile_check
    CHECK (profile IN ('default', 'unreleased-v1', 'unreleased-v2'));

COMMIT;
