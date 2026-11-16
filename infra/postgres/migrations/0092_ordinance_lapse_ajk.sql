-- ordinance_latest_lapse reads the AJK period: eight months (AJK Interim Constitution, 1974, Art. 41(2)(a)).
--
-- tools/record_status.py now asserts 'lapsed' for AJK Ordinances of 1975 onward from the Interim Constitution's own text
-- (the official file https://law.gok.pk/wp-content/uploads/2023/10/AJK-interim-constitution.pdf, sha256 5901ea06...):
-- 'shall stand repealed at the expiration of four months from its promulgation', with the proviso that the Assembly
-- may 'extend the Ordinance for a further period of four months'. operative_provision (through v_instrument_currency)
-- stops serving a lapsed AJK Ordinance after its latest possible lapse, promulgation (or 31 December of its year) plus
-- eight months. Federal and provincial periods are 0091's.
-- REVERSAL: restore 0091's ordinance_latest_lapse.
-- Governing contract: docs/03b §3; migrations 0085, 0091.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE OR REPLACE FUNCTION ordinance_latest_lapse(jurisdiction text, enacted_on date, year integer) RETURNS date
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN jurisdiction = 'ajk'
             THEN (coalesce(enacted_on, make_date(year, 12, 31)) + interval '8 months')::date
        WHEN coalesce(enacted_on, make_date(year, 12, 31)) >= DATE '2010-04-20' OR (enacted_on IS NULL AND year = 2010)
             THEN coalesce(enacted_on, make_date(year, 12, 31)) + CASE WHEN jurisdiction = 'fed' THEN 240 ELSE 180 END
        ELSE (coalesce(enacted_on, make_date(year, 12, 31))
              + CASE WHEN jurisdiction = 'fed' THEN interval '4 months' ELSE interval '3 months' END)::date END
$$;

DO $$
BEGIN
    IF ordinance_latest_lapse('ajk', NULL, 1983) <> DATE '1984-08-31'
       OR ordinance_latest_lapse('fed', DATE '2010-01-05', 2010) <> DATE '2010-05-05' THEN
        RAISE EXCEPTION '0092: ordinance_latest_lapse misreads a period';
    END IF;
END $$;

COMMIT;
