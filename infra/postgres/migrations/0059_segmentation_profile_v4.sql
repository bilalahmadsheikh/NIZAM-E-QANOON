-- A fourth segmentation profile, `unreleased-v4`.
--
-- docs/SEGMENTATION-PROFILES.md: a profile is frozen once something is
-- released under it. A rule may join an existing profile only if every
-- instrument released under that profile rebuilds identically; otherwise the
-- next profile is opened.
--
-- The rule that needs it is `level_margin_heading_text`: a provision with no
-- heading takes the margin heading printed level with its opener. Doc 876's
-- statute 10 prints "Finance and Planning Committee." beside "10. (1) The
-- Finance and Planning Committee shall consist of--", emitted after the
-- opener; the contents lists label 10 twice (s.10 "Visitation." and statute
-- 10), and with no heading the statute's row found nothing to link by. The
-- same rule would also name doc 2983's Scheme paragraphs 4 and 6 -- a tree
-- released under `unreleased-v3` -- so it cannot join that profile.
--
-- `unreleased-v4` = every `unreleased-v3` rule plus `level_margin_heading_text`
-- (nizam/corpus/segment.py SEGMENTATION_PROFILES). Existing pins are not
-- touched; a document moves to v4 only by a new, superseding pin.

BEGIN;

ALTER TABLE segmentation_profile_pin
    DROP CONSTRAINT segmentation_profile_pin_profile_check;

ALTER TABLE segmentation_profile_pin
    ADD CONSTRAINT segmentation_profile_pin_profile_check
    CHECK (profile IN ('default', 'unreleased-v1', 'unreleased-v2', 'unreleased-v3',
                       'unreleased-v4'));

COMMIT;
