-- Ordinances of 1986-2010 lapse under the Art. 89/128 text the Eighteenth Amendment replaced; ordinance_latest_lapse
-- uses the period of the text the Ordinance was made under.
--
-- 0085 asserted 'lapsed' only for Ordinances made under the current text (from 2010-04-20) because doc 4419's footnotes
-- do not print the words the Eighteenth Amendment replaced. The amending Act itself does, and the corpus holds it (doc
-- 4434, expression 13): s.27 -- 'in sub-paragraph (i), for the words "four months" the words "one hundred and twenty
-- days" shall be substituted ... and thereafter the following proviso shall be inserted' (the single extension), and
-- the same for (ii); s.41 -- in Art. 128(2)(a) 'for the words "three months" the words "ninety days"'. Art. 89's
-- footnotes (doc 4419) list every amendment of it: P.O. 14 of 1985, the Constitution (Second Amendment) Order, 1985
-- (P.O. 20 of 1985, which wrote sub-paragraphs (i)/(ii)), and the Eighteenth Amendment. So an Ordinance made between
-- 1 January 1986 and 19 April 2010 stood repealed four months (federal) or three months (provincial) after
-- promulgation, with no extension -- outside Art. 270AA's window (12 October 1999 - 31 December 2003). Before 1986
-- (Art. 270A; the original 1973 wording) nothing is asserted. tools/record_status.py applies it (bases
-- stood_repealed_art89_2_four_months / stood_repealed_art128_2_three_months).
-- REVERSAL: restore 0085's ordinance_latest_lapse.
-- Governing contract: docs/03b §3 (life_stage); migrations 0085, 0088.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE OR REPLACE FUNCTION ordinance_latest_lapse(jurisdiction text, enacted_on date, year integer) RETURNS date
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN coalesce(enacted_on, make_date(year, 12, 31)) >= DATE '2010-04-20' OR (enacted_on IS NULL AND year = 2010)
             THEN coalesce(enacted_on, make_date(year, 12, 31)) + CASE WHEN jurisdiction = 'fed' THEN 240 ELSE 180 END
        ELSE (coalesce(enacted_on, make_date(year, 12, 31))
              + CASE WHEN jurisdiction = 'fed' THEN interval '4 months' ELSE interval '3 months' END)::date END
$$;

DO $$
BEGIN
    IF ordinance_latest_lapse('fed', DATE '2010-01-05', 2010) <> DATE '2010-05-05'
       OR ordinance_latest_lapse('sindh', NULL, 1992) <> DATE '1993-03-31'
       OR ordinance_latest_lapse('fed', DATE '2015-01-01', 2015) <> DATE '2015-08-29' THEN
        RAISE EXCEPTION '0091: ordinance_latest_lapse misreads a period';
    END IF;
END $$;

COMMIT;
