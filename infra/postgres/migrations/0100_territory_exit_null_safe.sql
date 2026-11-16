-- operative_provision's territory-exit test (0095) must be NULL-safe.
--
-- Found 16 Nov 2026 by the golden-set build (every necessary unit of sets 1-4 "NOT served"): for a law with no
-- territorial repeal, territory_exits is NULL, so "m.territory_exits ? nzq_territory()" is NULL, the conjunction is
-- NULL and "NOT (NULL)" is NULL -- the row is filtered out. From 0095 until this migration every read with
-- nzq.territory set returned only laws that HAD a territory exit (and had not yet reached it). The test is now
-- coalesced to false, so a law without exits is served as before 0095.
--
-- REVERSAL: none wanted (0098's view is the broken one).
-- Governing contract: INV-5, docs/04 §6 (territory); migrations 0095, 0098.

BEGIN;

SET LOCAL lock_timeout = '10s';

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
       CASE WHEN m.text_language IN ('ur', 'sd') THEN NULL ELSE v.text_en END                         AS text_en,
       CASE WHEN m.text_language IN ('ur', 'sd') THEN coalesce(v.text_ur, v.text_en) ELSE v.text_ur END AS text_ur,
       m.text_language,
       v.id                                   AS version_id,
       v.validity,
       v.operation::text                      AS operation,
       m.jurisdiction,
       m.instrument_kind,
       m.instrument_title,
       m.instrument_number,
       m.instrument_year,
       CASE WHEN m.law_repealed_on IS NOT NULL THEN 'repealed' ELSE m.status END AS instrument_status,
       m.enacted_on,
       m.commenced_on,
       m.law_repealed_on                      AS repealed_on,
       m.repealed_by_id,
       m.superseded_by_instrument_id,
       m.source_url,
       m.document_id,
       CASE WHEN m.commenced_on IS NOT NULL THEN 'established' ELSE 'not_tracked' END AS commencement_coverage,
       'not_tracked'::text                    AS invalidation_coverage,
       m.extent_basis                         AS extent_coverage,
       nzq_as_of()                            AS as_of,
       m.currency,
       m.currency_reason,
       m.territory_exits,
       kf.text_known_from,
       kf.basis                               AS text_known_from_basis
  FROM mv_instrument_serving m
  JOIN provision p ON p.instrument_id = m.instrument_id AND p.is_active
  LEFT JOIN mv_provision_text_known_from kf ON kf.provision_id = p.id
  JOIN provision_version v ON v.provision_id = p.id
                          AND (v.validity @> nzq_as_of()
                               OR (upper_inf(v.validity) AND kf.text_known_from IS NOT NULL
                                   AND nzq_as_of() >= kf.text_known_from AND nzq_as_of() < lower(v.validity)))
 WHERE (m.historical_validity IS NULL OR m.historical_validity @> nzq_as_of())
   AND (m.enacted_on IS NULL OR m.enacted_on <= nzq_as_of())
   AND (m.instrument_year IS NULL OR m.instrument_year <= extract(year FROM nzq_as_of()))
   AND (m.commenced_on IS NULL OR m.commenced_on <= nzq_as_of())
   AND NOT (m.law_repealed_on IS NOT NULL AND m.law_repealed_on <= nzq_as_of())
   AND NOT (m.currency IN ('not_current', 'historical') AND m.not_current_from IS NOT NULL
            AND m.not_current_from <= nzq_as_of())
   AND (nzq_territory() IS NULL OR nzq_territory() = ANY (m.territory_reach))
   AND NOT coalesce(nzq_territory() IS NOT NULL AND m.territory_exits ? nzq_territory()
                    AND (m.territory_exits ->> nzq_territory())::date <= nzq_as_of(), false);

COMMIT;
