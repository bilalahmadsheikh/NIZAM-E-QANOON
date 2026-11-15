-- v_amendment_reference_current reads AJK citations: the 0072-0078 resolution rules, extended to how the AJK
-- revised volumes print their amendment footnotes. Measured 15 Nov 2026, after AJK landed (54dd8cd): 117 recorded
-- footnotes in AJK texts, 0 resolved. Three reasons, each fixed here and nothing else:
--
--   1. NUMBER CITATIONS WITH A PROVISION PREFIX. AJK footnotes name the amending law by number behind the section that
--      did the amending, and carry a date or the superseded words after it:
--        'Sec 2 of Act V of 1986. Original words', 'section 2(a) of Act I of 1975 original word was ...',
--        'Act XXIII of 1995 dt. 23-10-1995'.
--      is_bare_citation (0074) accepts only the citation alone. is_number_citation accepts the same citation behind
--      'Sec[tion] N[(x)] of' and before a terminator ('.', ',', 'dt.', 'original', 'note', end). It carries no NAME, so
--      it is still a bare citation in 0074's sense: number, kind and year, never a title.
--      AJK NUMBERS ALONE ARE NOT ENOUGH. Measured in the trial of this migration: the Minimum Wages for Unskilled
--      Workers Act's footnote 'section 2 of act I of 2010' would have resolved to the only AJK Act I of 2010 held --
--      the Grant of Khalsa Waste Land as Shamilat-Deh (Amendment) Act -- while the corpus files the Minimum Wages
--      (Amendment) Act, 2010 as Act II of 2010. So for an AJK text a number citation resolves only when the one
--      candidate's title also names the law amended (law_stem of the amended title inside the candidate's); a
--      law amended by a general Act ('... Legislative Assembly (Amendment) Act' amending the State Council Ordinance)
--      stays unresolved rather than guessed.
--   2. TITLE KEYS. AJK short titles print the law's own citation after the title -- 'The Azad Jammu & Kashmir Land
--      Reforms Act, 1960 (Act No V of 1960)' -- and AJK footnotes abbreviate: 'AJ&K', '(Amdt.)', '(2nd Amdt.)'.
--      instrument_title_key now strips a trailing printed citation, reads '&' as 'and', 'AJ&K' as 'Azad Jammu and
--      Kashmir', 'Amdt.' as 'Amendment', '2nd'-'5th' as words, and drops a leading 'Azad Jammu and Kashmir' /
--      'Azad Kashmir' (both sides alike) because AJK footnotes cite their own laws with or without the territory's
--      name ('the Local Government (Amdt.) Act, 2001' for 'The Azad Jammu and Kashmir Local Government (Amendment)
--      Act, 2001'). The year is still required to match, and still exactly one candidate.
--   3. JURISDICTION. cited_jurisdiction did not know AJK; a citation naming Azad Jammu & Kashmir (or AJ&K) is 'ajk'.
--      An AJK law is amended by AJK law only: an uncited AJK footnote no longer falls back to 'fed' candidates (a
--      federal Act V of 1986 is not the AJK Act V of 1986). Every other jurisdiction keeps 0073's fallback.
--
-- Not resolved, by design: 'Ibid' (the previous footnote's citation -- a different grammar), truncated cited texts
-- ('Sec', 'section'), and a citation whose law is filed twice (exactly one candidate, the 0072 rule).
-- The two title-key indexes are rebuilt because the function changed.
-- REVERSAL: restore 0074's is_bare_citation use, 0072's instrument_title_key and 0073's cited_jurisdiction, re-create
-- the 0078 view, REINDEX the two indexes, drop is_number_citation.
-- Governing contract: docs/03b §1.1 (amends); docs/03 §9; migration 0072's resolution rule.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE FUNCTION is_number_citation(cited text) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT is_bare_citation(cited)
        OR coalesce(cited, '') ~* ('^\s*(sec(tion)?\.?\s*\d+[a-z]?(\s*\(\s*[a-z0-9]+\s*\))*\s*of\s+)?'
                                   '(the\s+)?((khyber\s+pakhtunkhwa|n\.?\s*-?\s*w\.?\s*f\.?\s*p\.?|balochistan|'
                                   'baluchistan|baln\.?|sindh?|punjab|federal|central)\s+)?'
                                   '(act|ordinance|ord\.?|order|p\.\s*o\.?|president''?s\s+order|regulation|reg\.?)'
                                   '\.?\s*(no\.?\s*)?([ivxlc]+|\d{1,3})\s+of\s+(\d{2}|\d{4})\M'
                                   '\s*([.,;:]|\(?\s*dt\M|original|note|$)')
$$;

CREATE OR REPLACE FUNCTION instrument_title_key(t text) RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE k text := lower(coalesce(t, ''));
BEGIN
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

CREATE OR REPLACE FUNCTION cited_jurisdiction(cited text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN cited ~* '\mazad\s+(jammu|kashmir)|\maj\s*&\s*k\M|\majk\M'   THEN 'ajk'
        WHEN cited ~* 'khyber|n\.?\s*-?\s*w\.?\s*f\.?\s*p|frontier' THEN 'kp'
        WHEN cited ~* 'baloch|baluch|\mbaln\M'                        THEN 'balochistan'
        WHEN cited ~* '\msindh?\M'                                    THEN 'sindh'
        WHEN cited ~* '\mpunjab'                                      THEN 'punjab'
        WHEN cited ~* '\mfederal\M|\mcentral\M|president|\mp\.\s*o\.|governor.general' THEN 'fed'
    END
$$;

-- the name a law's amending Acts repeat: title key with a leading bracket ('(Repealed vide Act XVIII of 2020)'), the
-- words 'the', 'of', 'and' and the terminal kind word removed. Used only as a containment guard, never to match.
CREATE FUNCTION law_stem(t text) RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE k text;
BEGIN
    k := coalesce(instrument_title_key(regexp_replace(coalesce(t, ''), '^\s*\([^)]*\)\s*', '')), '');
    k := regexp_replace(k, '(the|of|and)', '', 'g');
    k := regexp_replace(k, '(act|ordinance|order|regulations?|rules|code)$', '');
    RETURN nullif(k, '');
END $$;

REINDEX INDEX instrument_title_key_short;
REINDEX INDEX instrument_title_key_display;

-- the functions read the printed forms met, and refuse what they must not
DO $$
BEGIN
    IF NOT (is_number_citation('Sec 2 of Act V of 1986. Original words')
            AND is_number_citation('section 2(a) of Act I of 1975 original word was ''sixcteen''')
            AND is_number_citation('Section 2(b) of Act VII of 1987')
            AND is_number_citation('section2 of Act X of 2006,original are as twenty')
            AND is_number_citation('Act XXIII of 1995 dt. 23-10-1995')
            AND is_number_citation('Sec 2 of Ord I of 1974')
            AND is_number_citation('Act XII of 1950')) THEN
        RAISE EXCEPTION 'is_number_citation misses a printed number citation';
    END IF;
    IF is_number_citation('the Land Reforms (Amdt.) Act, 1975 (Act VII of 1975)')
       OR is_number_citation('Sec 2 of Act V of 1986 of the Punjab Code')
       OR is_number_citation('Act ………') OR is_number_citation('Sec') THEN
        RAISE EXCEPTION 'is_number_citation accepts a named or truncated citation';
    END IF;
    IF instrument_title_key('The Azad Jammu & Kashmir Land Reforms Act, 1960 (Act No V of 1960)')
         <> instrument_title_key('Azad Jammu and Kashmir Land Reforms Act')
       OR instrument_title_key('The Azad Jammu And Kashmir Land Reforms (Amendment) Act, 1975 (ACT VII OF 1975)')
         <> instrument_title_key('The Azad Jammu and Kashmir Land Reforms (Amdt.) Act')
       OR instrument_title_key('The Azad Jammu and Kashmir Board of Revenue (Amendment) Act, 1997')
         <> instrument_title_key('AJ&K Board of Revenue (Amdt.) Act')
       OR instrument_title_key('The Azad Jammu and Kashmir Government (Second Amendment) Act, 1965')
         <> instrument_title_key('The Azad Jammu and Kashmir Government (2nd Amdt.) Act')
       OR instrument_title_key('The Azad Jammu and Kashmir Land Reforms (Amendment) Act, 1972 (Act VI of 1972) '
                               '(Act No. VI Of 1972)') <> 'landreformsamendmentact'
       OR instrument_title_key('The Pakistan Penal Code, 1860') <> 'pakistanpenalcode' THEN
        RAISE EXCEPTION 'instrument_title_key does not read an AJK title as printed';
    END IF;
    IF instrument_title_key('The Land Reforms Act') = instrument_title_key('The Land Reforms (Amendment) Act')
       OR instrument_title_key('The Government Act, 1964') = instrument_title_key('The Government (Second Amendment) Act') THEN
        RAISE EXCEPTION 'instrument_title_key merges two different laws';
    END IF;
    IF strpos(law_stem('The Azad Jammu & Kashmir De-Limitation of the Constituencies (Amendment) Act, 2006 (ACT II OF 2006)'),
              law_stem('(Repealed vide Act XVIII of 2020) THE AZAD JAMMU AND KASHMIR DELIMITATION OF CONSTITUENCIES '
                       'ORDINANCE, 1970')) = 0
       OR strpos(law_stem('The Azad Jammu and Kashmir Grant of Khalsa Waste Land as Shamilat-Deh (Amendment) Act, 2010'),
                 law_stem('The Azad Jammu and Kashmir Minimum Wages for Unskilled Workers Act, 1975')) > 0 THEN
        RAISE EXCEPTION 'law_stem guard misreads an amending title';
    END IF;
    IF cited_jurisdiction('the AJ&K Board of Revenue (Amdt.) Act, 1997') IS DISTINCT FROM 'ajk'
       OR cited_jurisdiction('the Azad Kashmir Emergency Powers (Amdt.) Act, 1959') IS DISTINCT FROM 'ajk'
       OR cited_jurisdiction('the Punjab Laws (Amendment) Act, 1975') IS DISTINCT FROM 'punjab'
       OR cited_jurisdiction('Act V of 1986') IS NOT NULL THEN
        RAISE EXCEPTION 'cited_jurisdiction misreads a citation';
    END IF;
END $$;

CREATE OR REPLACE VIEW v_amendment_reference_current AS
WITH latest AS (
    SELECT DISTINCT ON (source_observation_id, expression_ordinal, footnote_block_id, entry_ordinal) *
      FROM amendment_reference
     ORDER BY source_observation_id, expression_ordinal, footnote_block_id, entry_ordinal, recorded_at DESC, id DESC)
SELECT l.*,
       amended.id AS amended_instrument_id,
       target.provision_id AS target_provision_id,
       amending.id AS amending_instrument_id,
       cited_jurisdiction(l.cited_text) AS cited_jurisdiction
  FROM latest l
  JOIN instrument amended ON amended.source_observation_id = l.source_observation_id
                         AND amended.expression_ordinal = l.expression_ordinal
                         AND amended.is_active AND amended.duplicate_of IS NULL
  LEFT JOIN LATERAL (
       SELECT pb.provision_id
         FROM provision_block pb
         JOIN block_assignment_set s ON s.id = pb.assignment_set_id AND s.is_active
         JOIN provision p ON p.id = pb.provision_id AND p.is_active AND p.instrument_id = amended.id
        WHERE pb.block_id = l.target_block_id
        LIMIT 1) target ON l.target_block_id IS NOT NULL
  LEFT JOIN LATERAL (
       -- a number citation only (no name), never West Pakistan
       SELECT CASE WHEN count(*) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE is_number_citation(l.cited_text) AND l.cited_text !~* '\mw\.?\s*p\.|west\s+pakistan'
          AND l.cited_number IS NOT NULL AND l.cited_kind IS NOT NULL AND l.cited_year IS NOT NULL
          AND r.is_active AND r.duplicate_of IS NULL
          AND r.number = l.cited_number AND r.kind::text = l.cited_kind AND r.year = l.cited_year
          AND (CASE WHEN cited_jurisdiction(l.cited_text) IS NOT NULL
                    THEN r.jurisdiction::text = cited_jurisdiction(l.cited_text)
                    ELSE r.jurisdiction::text = amended.jurisdiction::text
                         OR (r.jurisdiction::text = 'fed' AND amended.jurisdiction::text <> 'ajk') END)
          AND (amended.jurisdiction::text <> 'ajk'
               OR (length(law_stem(coalesce(amended.display_title, amended.short_title))) >= 6
                   AND strpos(coalesce(law_stem(coalesce(r.display_title, r.short_title)), ''),
                              law_stem(coalesce(amended.display_title, amended.short_title))) > 0))
          AND r.id <> amended.id) by_number ON true
  LEFT JOIN LATERAL (
       -- a named citation: title key and year
       SELECT CASE WHEN count(DISTINCT r.id) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE NOT is_bare_citation(l.cited_text) AND l.cited_title IS NOT NULL AND l.cited_year IS NOT NULL
          AND r.is_active AND r.duplicate_of IS NULL AND r.year = l.cited_year
          AND (instrument_title_key(r.short_title) = instrument_title_key(l.cited_title)
               OR instrument_title_key(r.display_title) = instrument_title_key(l.cited_title))
          AND (CASE WHEN cited_jurisdiction(l.cited_text) IS NOT NULL
                    THEN r.jurisdiction::text = cited_jurisdiction(l.cited_text)
                    ELSE r.jurisdiction::text = amended.jurisdiction::text
                         OR (r.jurisdiction::text = 'fed' AND amended.jurisdiction::text <> 'ajk') END)
          AND r.id <> amended.id) by_title ON true
  LEFT JOIN LATERAL (
       -- an abbreviated citation with no parsed title: a reviewed citation_abbreviation row, then title key and year
       SELECT CASE WHEN count(DISTINCT r.id) = 1 THEN min(r.id::text)::uuid END AS id
         FROM v_citation_abbreviation_current a
         JOIN instrument r ON r.year = a.cited_year AND r.jurisdiction::text = a.jurisdiction
                          AND r.is_active AND r.duplicate_of IS NULL
                          AND (instrument_title_key(r.short_title) = instrument_title_key(a.expands_to)
                               OR instrument_title_key(r.display_title) = instrument_title_key(a.expands_to))
        WHERE l.cited_title IS NULL AND NOT is_bare_citation(l.cited_text)
          AND l.cited_text ~* a.pattern
          AND r.id <> amended.id) by_abbreviation ON true
  LEFT JOIN instrument amending ON amending.id = coalesce(by_number.id, by_title.id, by_abbreviation.id)
 WHERE l.assertion = 'recorded';

COMMIT;
