-- A third segmentation profile, `unreleased-v3`.
--
-- docs/SEGMENTATION-PROFILES.md: a profile is frozen once something is
-- released under it. A rule may join an existing profile only if every
-- instrument released under that profile rebuilds identically; otherwise the
-- next profile is opened.
--
-- The rule that needs it is `wrapped_bracket_reference`: a line ending in a
-- reference word ("sub-section", "sub-paragraph", "clause") whose bracketed
-- number wraps to the next line, followed by a lower-case word, continues the
-- sentence and opens nothing. Doc 1521 s.17(1) prints "... of section 7,
-- sub-section / (1) of section 8" and doc 2983 "set out in sub-paragraph /
-- (3) shall participate"; both opened a false sub-section. The same rule
-- would also mend doc 2846 standing order 13(3) ("under clause / (1) shall
-- bear"), a tree already released under `unreleased-v2`, so it cannot join
-- that profile -- the released correction is reported, not made.
--
-- `unreleased-v3` = every `unreleased-v2` rule plus `wrapped_bracket_reference`
-- (nizam/corpus/segment.py SEGMENTATION_PROFILES). Existing pins are not
-- touched; a document moves to v3 only by a new, superseding pin.

BEGIN;

ALTER TABLE segmentation_profile_pin
    DROP CONSTRAINT segmentation_profile_pin_profile_check;

ALTER TABLE segmentation_profile_pin
    ADD CONSTRAINT segmentation_profile_pin_profile_check
    CHECK (profile IN ('default', 'unreleased-v1', 'unreleased-v2', 'unreleased-v3'));

COMMIT;
