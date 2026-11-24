-- 0135  A judgment read from an official HTML page is lane E1 (docs/02 §4; DECISION-LOG D-138).
--
-- The High Court of Sindh's archive carries 4,279 judgments as the portal's Word-HTML pages, not PDFs. MuPDF lays an
-- HTML page out into pages and blocks; the same parser reads them. The reading records lane E1 ("Official HTML"),
-- as docs/02 §4 names it, so a reader can tell an HTML reading from a PDF one.

--
-- Also two printed forms read in the HTML judgments: 'Criminal Special Anti-Terrorism Appeal No. 294 of 2015' and 'Cr.
-- Anti Terrorism Appeal No.95 of 2014'.

--
-- And a case number may open with the register letter the High Court of Sindh prints before it: 'C.P. No. D-1544 of
-- 2026' (a Division Bench petition) is not 'C.P. No. S-1544 of 2026' (a Single Bench one), so the letter is part of the
-- number, as 0125's trailing letters are (DECISION-LOG D-138). 0125 allowed only trailing letters.

BEGIN;
ALTER TABLE judicial_case DROP CONSTRAINT judicial_case_case_number_check;
ALTER TABLE judicial_case ADD CONSTRAINT judicial_case_case_number_check
    CHECK (case_number ~ '^([A-Z]-)?[1-9][0-9]{0,5}(-[A-Z]{1,3})?$');
ALTER TABLE judgment_document DROP CONSTRAINT IF EXISTS judgment_document_lane_check;
ALTER TABLE judgment_document ADD CONSTRAINT judgment_document_lane_check CHECK (lane IN ('E1', 'E2', 'E4'));
UPDATE case_type SET printed_forms = printed_forms || '{"criminal special anti terrorism appeal",'
  '"cr anti terrorism appeal","crl anti terrorism appeal","criminal anti terrorism appeal"}' WHERE code = 'SHC:SPLATA';
COMMIT;
