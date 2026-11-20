-- A reference read from a provision's heading or marginal note (D-108): a schedule prints the section it serves in
-- its heading ('[See section 5]'), and that link is the one that ties the schedule to its rule.
--
-- provision_reference (0114) gains `in_heading`: true when the printed words are the provision's heading or
-- marginal note rather than its version's text; char_start/char_end are then offsets into that heading (the
-- heading, then ' ', then the marginal note). The row stays keyed by the provision's version, so a version leaving
-- the release still takes it with it.
-- REVERSAL: ALTER TABLE provision_reference DROP COLUMN in_heading.
-- Governing contract: docs/03b §1.1 (refers_to); migration 0114.

BEGIN;

SET LOCAL lock_timeout = '10s';

ALTER TABLE provision_reference ADD COLUMN in_heading boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN provision_reference.in_heading IS
  'True: the printed words are the provision''s heading (then '' '', then its marginal note); offsets are into that.';

COMMIT;
