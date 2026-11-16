-- v_amendment_reference_current resolves four more printed shapes; every other 0080 rule is unchanged.
--
-- Measured 16 Nov 2026: 15,184 recorded amendment footnotes, the amending law resolved for 4,756. Of the 6,740 that
-- cite a law and did not resolve, most cannot: 2,116 name a law the corpus does not hold (Indian amending Acts of
-- 1880-1946 no Pakistani portal publishes), ~2,300 cite a number the corpus's copy does not carry (an OCR'd Gazette
-- scan prints 'ACT No. AXYVI of 1946'), and a number or title shared by a federal and a provincial law stays
-- ambiguous -- a guess between them is a wrong citation (INV-1). The shapes added here each have one answer:
--
--   1. TITLE, 'No.' AND NUMBER, with no comma-year: 'the Repealing Act No. XVI of 1874', 'the Central Laws (Statute
--      Reforms) Ordinance No. XXI of 1960'. The parser read a number and no title (cited_title NULL), and
--      is_number_citation refuses a named form. Resolved by number, kind and year, exactly one candidate, AND the
--      printed words before 'No.' agree with the candidate's title (law_stem containment, either way, >= 6 letters).
--   2. A TRUNCATED TITLE: the parser cut the title at a bracket or comma: 'Revision and Declaration) Ordinance, 1981'
--      for 'The Federal Laws (Revision and Declaration) Ordinance'; 'Deaths and Marriages Registration Act, 1886'
--      for 'Births, Deaths and Marriages Registration Act'. Resolved when the printed key is the END of exactly one
--      candidate's title key of the same year and jurisdiction, and is at least 20 letters.
--   3. A PROVINCIAL LAW CITING ITS OWN PROVINCE'S LAW: when the amended law's title names its province, a candidate in
--      that province is preferred to the federal fallback -- exactly one there. (Not otherwise: a federal Act
--      reprinted in a provincial code, 'Limitation Act, 1908' in the Punjab Code, still refuses two candidates.)
--   4. A CONSTITUTION AMENDMENT held only as a provincial code's reprint ('Constitution (Eighteenth Amendment) Act,
--      2010' in the Punjab Code): the Constitution is federal law, so a federal text's citation may resolve to the one
--      held copy. No other cross-jurisdiction match is made ('Finance Act, 2008' is never the AJK Finance Act, 2008).
--
-- REVERSAL: re-create 0080's view; drop names_own_province.
-- Governing contract: docs/03b §1.1 (amends); INV-1; migrations 0072-0074, 0078, 0080.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE FUNCTION names_own_province(title text, jur text) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE jur
        WHEN 'punjab'      THEN coalesce(title, '') ~* '\mpunjab'
        WHEN 'sindh'       THEN coalesce(title, '') ~* '\msindh?\M'
        WHEN 'kp'          THEN coalesce(title, '') ~* 'khyber|n\.?\s*-?\s*w\.?\s*f\.?\s*p|frontier'
        WHEN 'balochistan' THEN coalesce(title, '') ~* 'baloch|baluch|\mbaln\M'
        ELSE false END
$$;

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
       -- a number citation only (no name), never West Pakistan; 0084: a provincial law's own province first
       SELECT CASE WHEN count(*) = 1 THEN min(r.id::text)::uuid
                   WHEN names_own_province(coalesce(amended.display_title, amended.short_title),
                                           amended.jurisdiction::text)
                        AND count(*) FILTER (WHERE r.jurisdiction = amended.jurisdiction) = 1
                   THEN min(r.id::text) FILTER (WHERE r.jurisdiction = amended.jurisdiction)::uuid END AS id
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
       -- a named citation: title key and year; 0084: own province first; a Constitution amendment's one copy
       SELECT CASE WHEN count(DISTINCT r.id) = 1 THEN min(r.id::text)::uuid
                   WHEN names_own_province(coalesce(amended.display_title, amended.short_title),
                                           amended.jurisdiction::text)
                        AND count(DISTINCT r.id) FILTER (WHERE r.jurisdiction = amended.jurisdiction) = 1
                   THEN min(r.id::text) FILTER (WHERE r.jurisdiction = amended.jurisdiction)::uuid END AS id
         FROM instrument r
        WHERE NOT is_bare_citation(l.cited_text) AND l.cited_title IS NOT NULL AND l.cited_year IS NOT NULL
          AND r.is_active AND r.duplicate_of IS NULL AND r.year = l.cited_year
          AND (instrument_title_key(r.short_title) = instrument_title_key(l.cited_title)
               OR instrument_title_key(r.display_title) = instrument_title_key(l.cited_title))
          AND (CASE WHEN cited_jurisdiction(l.cited_text) IS NOT NULL
                    THEN r.jurisdiction::text = cited_jurisdiction(l.cited_text)
                    WHEN instrument_title_key(l.cited_title) ~ '^constitution' AND amended.jurisdiction::text <> 'ajk'
                    THEN r.jurisdiction::text <> 'ajk'
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
  LEFT JOIN LATERAL (
       -- 0084 (1): 'the Repealing Act No. XVI of 1874' -- number, kind, year, one candidate, and the printed words
       -- before 'No.' agree with its title
       SELECT CASE WHEN count(*) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE l.cited_title IS NULL AND NOT is_number_citation(l.cited_text)
          AND l.cited_number IS NOT NULL AND l.cited_kind IS NOT NULL AND l.cited_year IS NOT NULL
          AND l.cited_text ~* '^\s*(the\s+)?[a-z].{4,}?\m(act|ordinance|order|regulation)\s+no\.?\s'
          AND l.cited_text !~* '\mw\.?\s*p\.|west\s+pakistan'
          AND r.is_active AND r.duplicate_of IS NULL
          AND r.number = l.cited_number AND r.kind::text = l.cited_kind AND r.year = l.cited_year
          AND (CASE WHEN cited_jurisdiction(l.cited_text) IS NOT NULL
                    THEN r.jurisdiction::text = cited_jurisdiction(l.cited_text)
                    ELSE r.jurisdiction::text = amended.jurisdiction::text
                         OR (r.jurisdiction::text = 'fed' AND amended.jurisdiction::text <> 'ajk') END)
          AND length(coalesce(law_stem(substring(l.cited_text from '(?i)^(.*?)\s+no\.?\s')), '')) >= 6
          AND (strpos(coalesce(law_stem(coalesce(r.display_title, r.short_title)), ''),
                      law_stem(substring(l.cited_text from '(?i)^(.*?)\s+no\.?\s'))) > 0
               OR strpos(law_stem(substring(l.cited_text from '(?i)^(.*?)\s+no\.?\s')),
                         coalesce(law_stem(coalesce(r.display_title, r.short_title)), '~')) > 0)
          AND r.id <> amended.id) by_named_number ON true
  LEFT JOIN LATERAL (
       -- 0084 (2): a title the parser cut at a bracket or comma -- the END of exactly one title of the same year and
       -- jurisdiction, at least 20 letters
       SELECT CASE WHEN count(DISTINCT r.id) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE l.cited_title IS NOT NULL AND l.cited_year IS NOT NULL AND NOT is_bare_citation(l.cited_text)
          AND length(coalesce(instrument_title_key(l.cited_title), '')) >= 20
          AND r.is_active AND r.duplicate_of IS NULL AND r.year = l.cited_year
          AND r.jurisdiction::text = coalesce(cited_jurisdiction(l.cited_text), amended.jurisdiction::text)
          AND (right(instrument_title_key(r.short_title), length(instrument_title_key(l.cited_title)))
                 = instrument_title_key(l.cited_title)
               OR right(instrument_title_key(r.display_title), length(instrument_title_key(l.cited_title)))
                 = instrument_title_key(l.cited_title))
          AND r.id <> amended.id) by_suffix ON true
  LEFT JOIN instrument amending ON amending.id = coalesce(by_number.id, by_title.id, by_abbreviation.id,
                                                          by_named_number.id, by_suffix.id)
 WHERE l.assertion = 'recorded';

COMMIT;
