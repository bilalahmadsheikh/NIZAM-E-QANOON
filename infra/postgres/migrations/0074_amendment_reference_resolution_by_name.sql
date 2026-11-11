-- v_amendment_reference_current: a named citation resolves by its name; only a bare citation resolves by number.
--
-- Measured after 0073 (11 Nov 2026): numbering series overlap in this corpus -- West Pakistan, Bombay and other
-- provincial Acts are filed under 'fed', so 'XI of 1923' is two different laws. Number-first resolution therefore
-- sent named citations to the wrong law:
--   'the Repealing and Amending Act, 1923 (11 of 1923)'          -> The Bombay Prevention of Prostitution Act, 1923
--   'the Pakistan Atomic Energy Commission (Amdt.) Act, 1974'     -> The Pakistan Maritime Shipping (...) Act
--   'the University of South Asia, Lahore (Amendment) Act 20..'  -> a Hyderabad institute Act
--   'W P. Ord. XLVI of 1959'                                       -> a federal Ordinance XLVI of 1959
-- Now:
--   * a citation that carries a NAME resolves only by title key and year (cited_title, as before);
--   * number, kind and year are used only for a BARE citation -- the cited text is nothing but
--     '[the] [jurisdiction] Act|Ordinance|Ord.|Order|P.O.|President's Order|Regulation [No.] N of YYYY';
--   * a West Pakistan citation ('W.P.', 'West Pakistan') never resolves by number: that series is not filed
--     consistently.
-- Both still need exactly one candidate within the jurisdiction rule of 0073. Columns are unchanged.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE FUNCTION is_bare_citation(cited text) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT coalesce(cited, '') ~* ('^\s*(the\s+)?((khyber\s+pakhtunkhwa|n\.?\s*-?\s*w\.?\s*f\.?\s*p\.?|balochistan|'
                                   'baluchistan|baln\.?|sindh?|punjab|federal|central)\s+)?'
                                   '(act|ordinance|ord\.?|order|p\.\s*o\.?|president''?s\s+order|regulation|reg\.?)'
                                   '\.?\s*(no\.?\s*)?([ivxlc]+|\d{1,3})\s+of\s+(\d{2}|\d{4})\.?\s*$')
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
       -- a bare citation only, never West Pakistan
       SELECT CASE WHEN count(*) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE is_bare_citation(l.cited_text) AND l.cited_text !~* '\mw\.?\s*p\.|west\s+pakistan'
          AND l.cited_number IS NOT NULL AND l.cited_kind IS NOT NULL AND l.cited_year IS NOT NULL
          AND r.is_active AND r.duplicate_of IS NULL
          AND r.number = l.cited_number AND r.kind::text = l.cited_kind AND r.year = l.cited_year
          AND (CASE WHEN cited_jurisdiction(l.cited_text) IS NOT NULL
                    THEN r.jurisdiction::text = cited_jurisdiction(l.cited_text)
                    ELSE r.jurisdiction::text IN (amended.jurisdiction::text, 'fed') END)
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
                    ELSE r.jurisdiction::text IN (amended.jurisdiction::text, 'fed') END)
          AND r.id <> amended.id) by_title ON true
  LEFT JOIN instrument amending ON amending.id = coalesce(by_number.id, by_title.id)
 WHERE l.assertion = 'recorded';

COMMIT;
