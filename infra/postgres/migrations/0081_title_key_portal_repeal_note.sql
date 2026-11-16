-- instrument_title_key reads past the official portal's repeal annotation in a catalogue title.
--
-- Found 16 Nov 2026 while filling legal status: 40 released laws carry Pakistan Code's (and once AJK's) repeal note in
-- the title the catalogue gave them -- 'Pakistan Commissions of Inquiry Act, 1956(Repeal by Act IX of 2017 s.19)',
-- 'Agricultural Census Act, 1958)' (the note cut, its bracket left), '(Repealed vide Act XVIII of 2020) THE AZAD JAMMU
-- AND KASHMIR ...'. The note is the portal's, not part of the law's title. With it in the key, the as-made Gazette text
-- of the Commissions of Inquiry Act (8384) and its consolidated text (2678) could not be linked as twins (0075), and
-- an amendment footnote citing the law by name could not resolve to it (0072). The Python title key used by
-- tools/record_statutory_repeals.py strips the same note (PORTAL_REPEAL_NOTE), so both sides read titles alike.
--
-- Only the note and an unmatched closing bracket at the end are removed; every other step of 0080's key is unchanged.
-- The two title-key indexes are rebuilt because the function changed.
-- REVERSAL: restore 0080's instrument_title_key body; REINDEX the two indexes.
-- Governing contract: docs/03b §1.1; migrations 0072, 0075, 0080.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE OR REPLACE FUNCTION instrument_title_key(t text) RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE k text := lower(coalesce(t, ''));
BEGIN
    -- the portal's repeal note, anywhere in the title, closed or cut off (0081)
    k := regexp_replace(k, '[(\[]\s*(rep\.|repeal(ed)?)\s*(by|vide|through)\M[^)\]]*([)\]]|$)', ' ', 'g');
    -- a closing bracket the catalogue left with no opening one (0081)
    IF length(k) - length(replace(k, ')', '')) > length(k) - length(replace(k, '(', '')) THEN
        k := regexp_replace(k, '\)+\s*$', '');
    END IF;
    k := btrim(k);
    -- the law's own citation printed after its title, once or twice: '(Act No. V of 1960)', '(ORDINANCE XXV OF 1974)'
    k := regexp_replace(k, '(\s*\(\s*(act|ordinance|ord|regulation|order|p\.\s*o|president''?s\s+order)\.?\s*'
                           '(no\.?\s*)?[ivxlc0-9]+\s+of\s+\d{4}\s*\)\s*\.?)+\s*$', '');
    k := regexp_replace(k, ',?\s*\(?\d{4}\)?\s*\.?\s*$', '');          -- the year (0072)
    k := regexp_replace(k, '^\s*the\s+', '');                           -- (0072)
    k := regexp_replace(k, '\maj\s*&\s*k\M', 'azad jammu and kashmir', 'g');
    k := regexp_replace(k, '&', ' and ', 'g');
    k := regexp_replace(k, '\mamdt\M', 'amendment', 'g');
    k := regexp_replace(k, '\m2nd\M', 'second', 'g');
    k := regexp_replace(k, '\m3rd\M', 'third', 'g');
    k := regexp_replace(k, '\m4th\M', 'fourth', 'g');
    k := regexp_replace(k, '\m5th\M', 'fifth', 'g');
    k := regexp_replace(k, '[^a-z0-9]+', '', 'g');
    k := regexp_replace(k, '^(azadjammuandkashmir|azadkashmir)', '');
    RETURN nullif(k, '');
END $$;

REINDEX INDEX instrument_title_key_short;
REINDEX INDEX instrument_title_key_display;

DO $$
BEGIN
    IF instrument_title_key('Pakistan Commissions of Inquiry Act, 1956(Repeal by Act IX of 2017 s.19)')
       IS DISTINCT FROM instrument_title_key('The Pakistan Commissions of Inquiry Act, 1956') THEN
        RAISE EXCEPTION '0081: the portal repeal note is still in the key';
    END IF;
    IF instrument_title_key('Agricultural Census Act, 1958)') IS DISTINCT FROM 'agriculturalcensusact' THEN
        RAISE EXCEPTION '0081: an unmatched closing bracket is still in the key';
    END IF;
    IF instrument_title_key('The Azad Jammu & Kashmir Land Reforms Act, 1960 (Act No V of 1960)')
       IS DISTINCT FROM 'landreformsact' THEN
        RAISE EXCEPTION '0081: 0080''s key changed';
    END IF;
END $$;

COMMIT;
