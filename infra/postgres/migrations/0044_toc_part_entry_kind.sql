-- A numbered contents row can name a structural Part rather than a section.
-- Preserve that printed meaning instead of lying in entry_kind merely because
-- the original v1 constraint anticipated only sections and schedules.
BEGIN;

ALTER TABLE instrument_toc_entry
    DROP CONSTRAINT instrument_toc_entry_entry_kind_check;

ALTER TABLE instrument_toc_entry
    ADD CONSTRAINT instrument_toc_entry_entry_kind_check
    CHECK (entry_kind IN ('section', 'schedule', 'part'));

COMMENT ON COLUMN instrument_toc_entry.entry_kind IS
  'Kind named by the printed contents row: section, schedule, or structural part.';

COMMIT;
