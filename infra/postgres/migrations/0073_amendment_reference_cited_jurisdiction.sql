-- v_amendment_reference_current: a citation that names its jurisdiction resolves only within it.
--
-- 0072 resolved the amending law among instruments of the amended instrument's jurisdiction OR federal, accepting
-- exactly one match. Measured the same day (11 Nov 2026), that let 'Khyber Pakhtunkhwa Act No. I of 2019' resolve to
-- a FEDERAL Act I of 2019 and 'Khyber Pakhtunkhwa Act No. XXII of 2022' to the federal Export-Import Bank of Pakistan
-- Act, 2022: the KP Acts are not in the corpus, so the only candidate left was the wrong one.
--
-- Now the citation's own words decide where to look:
--   'Khyber Pakhtunkhwa', 'N.-W.F.P.', 'Frontier'  -> kp only
--   'Balochistan', 'Baluchistan', 'Baln'           -> balochistan only
--   'Sind', 'Sindh'                                -> sindh only
--   'Punjab'                                       -> punjab only
--   'Federal', 'Central', 'President', 'P.O.', 'Governor-General' -> fed only
--   anything else (a bare 'Act IV of 2004', 'W.P. Ord. ...')   -> as 0072: the amended instrument's jurisdiction or
--                                                                 federal, exactly one match.
-- The column cited_jurisdiction exposes the reading. Nothing else changes; the record table is untouched.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE FUNCTION cited_jurisdiction(cited text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN cited ~* 'khyber|n\.?\s*-?\s*w\.?\s*f\.?\s*p|frontier' THEN 'kp'
        WHEN cited ~* 'baloch|baluch|\mbaln\M'                        THEN 'balochistan'
        WHEN cited ~* '\msindh?\M'                                    THEN 'sindh'
        WHEN cited ~* '\mpunjab'                                      THEN 'punjab'
        WHEN cited ~* '\mfederal\M|\mcentral\M|president|\mp\.\s*o\.|governor.general' THEN 'fed'
    END
$$;

DROP VIEW v_amendment_reference_current;

CREATE VIEW v_amendment_reference_current AS
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
       SELECT CASE WHEN count(*) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE l.cited_number IS NOT NULL AND l.cited_kind IS NOT NULL AND l.cited_year IS NOT NULL
          AND r.is_active AND r.duplicate_of IS NULL
          AND r.number = l.cited_number AND r.kind::text = l.cited_kind AND r.year = l.cited_year
          AND (CASE WHEN cited_jurisdiction(l.cited_text) IS NOT NULL
                    THEN r.jurisdiction::text = cited_jurisdiction(l.cited_text)
                    ELSE r.jurisdiction::text IN (amended.jurisdiction::text, 'fed') END)
          AND r.id <> amended.id) by_number ON true
  LEFT JOIN LATERAL (
       SELECT CASE WHEN count(DISTINCT r.id) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE by_number.id IS NULL AND l.cited_title IS NOT NULL AND l.cited_year IS NOT NULL
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
