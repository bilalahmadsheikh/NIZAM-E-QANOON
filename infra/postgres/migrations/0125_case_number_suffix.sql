-- 0125  A case number's registry suffix may be up to three letters (DECISION-LOG D-128).
--
-- 0123 allowed one ('801-L'). The Lahore High Court prints longer ones: '2143-CB' (cancellation of bail), '4-RWP'
-- (the Rawalpindi registry), beside '3952-B' (bail). Dropping the letters would give two different cases one key.

BEGIN;
ALTER TABLE judicial_case DROP CONSTRAINT judicial_case_case_number_check;
ALTER TABLE judicial_case ADD CONSTRAINT judicial_case_case_number_check
    CHECK (case_number ~ '^[1-9][0-9]{0,5}(-[A-Z]{1,3})?$');
COMMIT;
