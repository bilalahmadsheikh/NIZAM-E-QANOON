-- 0117  A statutory notification that numbers no paragraph is one provision (DECISION-LOG D-115).
--
-- 'S.R.O. 959 (I)/2022.- In exercise of the powers conferred by ..., the Commission hereby makes the following
-- amendments ..., namely:- In the aforesaid Regulations,- (1) in regulation 18, ...' numbers nothing above its items,
-- so the parse put every block before the first item into the preface (reachable, never served): the notification's
-- operative words were not law in the corpus, and its items hung from the root with no head. 238 of the 307 such
-- texts in the 21 Nov regulator drops (D-113) are notifications of this shape.
--
--   * provision kind `notification`: the notification's own text, from its number line to its file number. It is
--     labelled 'Notification' from the heading the page prints, as a preamble is labelled 'Preamble' -- no number is
--     invented (INV-1) -- and is cited as '<title>, Notification'. Its items are its children.
--   * segmentation profile `notification-v1`: the default rules plus `notification_unit` and `gazette_masthead_part`
--     (the Gazette's 'PART II / Statutory Notification (S. R. O)' masthead read as a Part is dissolved into the
--     preface). Only an observation pinned to it parses under it; no released tree changes.

ALTER TYPE provision_kind ADD VALUE IF NOT EXISTS 'notification';

BEGIN;

ALTER TABLE segmentation_profile_pin
    DROP CONSTRAINT segmentation_profile_pin_profile_check;

ALTER TABLE segmentation_profile_pin
    ADD CONSTRAINT segmentation_profile_pin_profile_check
    CHECK (profile IN ('default', 'unreleased-v1', 'unreleased-v2', 'unreleased-v3',
                       'unreleased-v4', 'unreleased-v5', 'notification-v1'));

COMMIT;
