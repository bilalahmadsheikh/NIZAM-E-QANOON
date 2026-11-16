-- status 'lapsed' for an Ordinance the Constitution itself has repealed by lapse of time; operative_provision stops
-- serving it after its latest possible lapse.
--
-- The rule is the corpus's own Constitution text (doc 4419, Pakistan Code consolidated), read 16 Nov 2026:
--   Art. 89(2)  a President's Ordinance 'shall stand repealed at the expiration of one hundred and twenty days from
--               its promulgation', extendable 'for a further period of one hundred and twenty days', 'only once':
--               at most 240 days;
--   Art. 128(2) a Governor's Ordinance: 'ninety days', extendable once by ninety: at most 180 days.
-- Not under that rule, and so never 'lapsed' here: Ordinances Art. 270A affirms and continues (made 5 July 1977 to
-- 1985), those Art. 270AA continues (12 October 1999 to 31 December 2003 'and still in force'), Ordinances before the
-- 1973 Constitution (the corpus does not hold the earlier regimes' rules), and AJK and GB Ordinances (their
-- constitutions are not in the corpus). tools/record_status.py asserts 'lapsed' only for a federal or provincial
-- Ordinance of 2004 or later whose year its own title prints, at least a year past its latest possible lapse, with no
-- statutory repeal standing and no law in the corpus continuing it or deeming it an Act.
--
-- The exact lapse day is not known (disapproval or an Act can end it sooner; an extension can carry it to the
-- maximum), so operative_provision drops a lapsed Ordinance only for an as_of after its LATEST possible lapse --
-- promulgation (or 31 December of its year) plus the maximum -- and keeps serving it before, as it would have been.
--
-- REVERSAL: restore 0082's status value check and 0077's operative_provision body.
-- Governing contract: docs/03b §3 (life_stage 'lapsed'), §6.2; INV-5; migrations 0077, 0082.

BEGIN;

SET LOCAL lock_timeout = '10s';

ALTER TABLE instrument_metadata_assertion
    DROP CONSTRAINT instrument_metadata_assertion_status_value,
    ADD CONSTRAINT instrument_metadata_assertion_status_value
        CHECK (value IS NULL OR field <> 'status' OR value IN ('in_force', 'lapsed'));

CREATE FUNCTION ordinance_latest_lapse(jurisdiction text, enacted_on date, year integer) RETURNS date
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT coalesce(enacted_on, make_date(year, 12, 31))
           + CASE WHEN jurisdiction = 'fed' THEN 240 ELSE 180 END
$$;

CREATE OR REPLACE VIEW operative_provision AS
SELECT p.id                                   AS provision_id,
       p.instrument_id,
       p.parent_id,
       p.path,
       p.kind::text                           AS provision_kind,
       p.label,
       p.heading,
       p.marginal_note,
       p.ordinal,
       p.first_page,
       CASE WHEN i.text_language IN ('ur', 'sd') THEN NULL ELSE v.text_en END                         AS text_en,
       CASE WHEN i.text_language IN ('ur', 'sd') THEN coalesce(v.text_ur, v.text_en) ELSE v.text_ur END AS text_ur,
       i.text_language,
       v.id                                   AS version_id,
       v.validity,
       v.operation::text                      AS operation,
       i.jurisdiction::text                   AS jurisdiction,
       i.kind::text                           AS instrument_kind,
       coalesce(i.display_title, i.short_title) AS instrument_title,
       i.number                               AS instrument_number,
       i.year                                 AS instrument_year,
       CASE WHEN law.repealed_on IS NOT NULL THEN 'repealed' ELSE i.status::text END AS instrument_status,
       i.enacted_on,
       i.commenced_on,
       law.repealed_on,
       coalesce(law.repealed_by_id, i.repealed_by_id) AS repealed_by_id,
       s.superseding_instrument_id            AS superseded_by_instrument_id,
       i.source_url,
       i.document_id,
       CASE WHEN i.commenced_on IS NOT NULL THEN 'established' ELSE 'not_tracked' END AS commencement_coverage,
       'not_tracked'::text                    AS invalidation_coverage,
       'jurisdiction_default'::text           AS extent_coverage,
       nzq_as_of()                            AS as_of
  FROM v_release_instrument i
  JOIN provision p ON p.instrument_id = i.id AND p.is_active
  JOIN provision_version v ON v.provision_id = p.id AND v.validity @> nzq_as_of()
  LEFT JOIN v_instrument_historical h ON h.instrument_id = i.id
  LEFT JOIN LATERAL (SELECT sc.superseding_instrument_id FROM v_instrument_supersession_current sc
                      WHERE sc.superseded_instrument_id = i.id
                      ORDER BY sc.recorded_at, sc.id LIMIT 1) s ON true
  LEFT JOIN LATERAL (
       SELECT r.repealed_on, r.repealed_by_id
         FROM (SELECT i.repealed_on, i.repealed_by_id WHERE i.status = 'repealed'
               UNION ALL
               SELECT a.repealed_on, a.repealed_by_id
                 FROM v_consolidated_twin_current t JOIN instrument a ON a.id = t.as_made_instrument_id
                WHERE t.consolidated_instrument_id = i.id AND a.status = 'repealed') r
        ORDER BY r.repealed_on LIMIT 1) law ON true
 WHERE (h.instrument_id IS NULL OR h.historical_validity @> nzq_as_of())
   AND (i.enacted_on IS NULL OR i.enacted_on <= nzq_as_of())
   AND (i.year IS NULL OR i.year <= extract(year FROM nzq_as_of()))
   AND (i.commenced_on IS NULL OR i.commenced_on <= nzq_as_of())
   AND NOT (law.repealed_on IS NOT NULL AND law.repealed_on <= nzq_as_of())
   -- 0085: a lapsed Ordinance is not served after its latest possible lapse
   AND NOT (i.status = 'lapsed'
            AND ordinance_latest_lapse(i.jurisdiction::text, i.enacted_on, i.year) < nzq_as_of())
   AND (nzq_territory() IS NULL OR i.jurisdiction::text = 'fed' OR i.jurisdiction::text = nzq_territory())
   AND NOT EXISTS (SELECT 1 FROM v_consolidated_twin_current t WHERE t.as_made_instrument_id = i.id);

COMMIT;
