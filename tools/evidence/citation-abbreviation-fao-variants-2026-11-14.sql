-- F.A.O., 1975: a broader pattern superseding the 0078 row (latest row per abbreviation/year/jurisdiction wins).
-- After 0078 five footnotes still printed the abbreviation in shapes the first pattern refused: 'F.A.O,. 1975',
-- 'F.A.O ., 1975', 'F.A.O,. 1975, Art, 2 and Table', 'F.A.O., 4 of 1975', 'F.A.O., (P. O. No. 4 of 1975)'.
-- The year-only typos 'F.A.O., 1937', 'F.A.O., 1957', 'F.A.O. 1961' are NOT taken: the printed year is wrong and the
-- row resolves only what the page prints.
BEGIN;
DO $$
DECLARE p text := '^\s*(the\s+)?f\.?\s*a\.?\s*o[\s.,]*(of\s+)?\(?\s*((p\.?\s*o\.?|president''?s\s+order)\s*)?(no\.?\s*)?(4\s+of\s+)?1975\M';
BEGIN
    IF NOT ('F.A.O., 1975' ~* p AND 'the F.A.O., 1975' ~* p AND 'F. A. O., 1975' ~* p AND 'F.A.O 1975' ~* p
            AND 'F.A.O,. 1975' ~* p AND 'F.A.O ., 1975 Art. 2 and Tables' ~* p AND 'F.A.O., 4 of 1975' ~* p
            AND 'F.A.O., (P. O. No. 4 of 1975) Art. 2 and Table' ~* p AND 'F.A. O., 1975 (P.O. No. 4 of 1975)' ~* p) THEN
        RAISE EXCEPTION 'pattern misses a printed variant';
    END IF;
    IF 'A.O., 1975' ~* p OR 'F.A.O., 1937' ~* p OR 'F.A.O., 19750' ~* p OR 'F.A.O., 5 of 1975' ~* p
       OR 'the Federal Adaptation of Laws Order, 1975' ~* p THEN
        RAISE EXCEPTION 'pattern matches what it must not';
    END IF;
    INSERT INTO citation_abbreviation (abbreviation, cited_year, jurisdiction, pattern, expands_to, assertion, evidence,
                                       recorded_by)
    SELECT abbreviation, cited_year, jurisdiction, p, expands_to, 'recorded',
           evidence || jsonb_build_object('supersedes_pattern', pattern,
                                          'widened', 'five printed variants read 14 Nov 2026: F.A.O,. 1975 | F.A.O ., '
                                                     '1975 | F.A.O,. 1975, Art, 2 and Table | F.A.O., 4 of 1975 | '
                                                     'F.A.O., (P. O. No. 4 of 1975)'),
           'claude'
      FROM v_citation_abbreviation_current
     WHERE abbreviation = 'F.A.O.' AND cited_year = 1975 AND jurisdiction = 'fed' AND pattern <> p;
END $$;
COMMIT;
