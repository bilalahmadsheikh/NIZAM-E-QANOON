-- A fifth segmentation profile, `unreleased-v5`.
--
-- docs/SEGMENTATION-PROFILES.md: a profile is frozen once something is
-- released under it, so a rule that would change a released v4 tree opens the
-- next profile instead of joining v4.
--
-- The rule that needs it is `toc_promised_next_section`: a dotted number the
-- contents promises, not yet seen, exactly one past the open section, stays a
-- section even when the text layer lost its margin heading (so the printed
-- heading "disagrees" with the contents) and the line is indented -- unless it
-- continues a numbered list one below it. Doc 9127 (the Opium Act, 1878) is the
-- case: p3 prints "15. Any officer of any of the said departments may ...",
-- the contents promise "15. Power to seize opium in open places.", the OCR lost
-- the margin note, and section 15 became a clause of section 14(4), leaving the
-- contents row unlinked.
--
-- `unreleased-v5` = every `unreleased-v4` rule plus `toc_promised_next_section`
-- (nizam/corpus/segment.py SEGMENTATION_PROFILES). Existing pins are not
-- touched; a document moves to v5 only by a new, superseding pin.

BEGIN;

ALTER TABLE segmentation_profile_pin
    DROP CONSTRAINT segmentation_profile_pin_profile_check;

ALTER TABLE segmentation_profile_pin
    ADD CONSTRAINT segmentation_profile_pin_profile_check
    CHECK (profile IN ('default', 'unreleased-v1', 'unreleased-v2', 'unreleased-v3',
                       'unreleased-v4', 'unreleased-v5'));

COMMIT;
