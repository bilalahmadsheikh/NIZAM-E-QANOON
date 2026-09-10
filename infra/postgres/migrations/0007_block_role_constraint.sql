-- 0007  correct the provision_block role/provision pairing
--
-- 0006 wrote the rule as (role = 'body') = (provision_id IS NOT NULL), which says
-- only body text may point at a provision. That is wrong, and the first document
-- segmented proved it: a CHAPTER heading block belongs to the chapter provision
-- it opens, so it carries a provision_id while its role is 'heading'.
--
-- The real rule is that some roles MUST resolve to a provision and some MUST NOT:
--
--   must     body, heading, schedule_row, preamble   they are part of a provision
--   must not contents, preface, running_header       they belong to the document
--   must not unassigned                              by definition unplaced
--   either   footnote                                attaches to the provision on
--                                                    its page where one is known
--
-- 0006 is left as applied. A migration that has run is a historical fact; the
-- correction is a new one.

BEGIN;

ALTER TABLE provision_block DROP CONSTRAINT ck_body_has_provision;

ALTER TABLE provision_block ADD CONSTRAINT ck_role_provision CHECK (
    CASE
      WHEN role IN ('body','heading','schedule_row','preamble')
           THEN provision_id IS NOT NULL
      WHEN role IN ('contents','preface','running_header','unassigned')
           THEN provision_id IS NULL
      ELSE true                       -- footnote: either
    END
);

COMMENT ON CONSTRAINT ck_role_provision ON provision_block IS
    'Roles that are part of a provision must resolve to one; roles that belong to '
    'the document as a whole must not. See docs/CORPUS-CRITERIA.md.';

COMMIT;
