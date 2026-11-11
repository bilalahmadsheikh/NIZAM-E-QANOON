-- consolidated_twin: a fourth basis for a pair whose titles differ in words but are shown to be one law.
--
-- 12 Nov 2026, first run of tools/record_consolidated_twins.py: two pairs share number, kind, year and jurisdiction
-- but fail the automatic title-word test (overlap < 0.75), and are one law on the evidence of the texts themselves:
--   5171 -> 4253  'Islamabad Capital Territory (Tax on Services) Ordinance' / 'ICT (Tax on Services) Ordinance'
--                 (XLII of 2001): ICT is the abbreviation;
--   9024 -> 2305  'Land Control (Capital of the Federation) Act' / 'Land Control (Karachi Division) Act' (XI of 1952):
--                 the consolidated text cites its own amending 'Land Control (Capital of the Federation) (Amdt.) Act
--                 No. XXXIV of 1952' and records the title substituted by A.O., 1964.
-- Such a pair is recorded with basis 'same_number_year_title_reviewed' and the evidence for the title in `evidence`.
BEGIN;
SET LOCAL lock_timeout = '10s';
ALTER TABLE consolidated_twin DROP CONSTRAINT consolidated_twin_basis_check;
ALTER TABLE consolidated_twin ADD CONSTRAINT consolidated_twin_basis_check
    CHECK (basis IN ('same_title_number_year', 'same_title_year', 'same_number_year_title_overlap',
                     'same_number_year_title_reviewed'));
COMMIT;
