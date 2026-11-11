-- operative_provision: a statutory repeal recorded on either text of a law (as made or consolidated) repeals the law.
--
-- Found 12 Nov 2026 right after 0075: 0066 records a repeal against the ONE released instrument whose title the
-- repealing Act names, and for six linked laws that was the as-made text. The consolidated twin stayed 'unknown' and
-- operative_provision served it as current law:
--   5152 -> 3209 Federal Medical Teaching Institutes Act 2021 (repealed 2023-01-03)
--   5276 -> 2212 Pakistan Health Research Council Act 2016   (2021-07-29)
--   4992 -> 2407 Alternative Energy Development Board Act 2010 (2012-03-02)
--   7707 -> 1993 Territorial Waters and Maritime Zones Act 1976 (2023-04-26)
--   6857 -> 2282 Prevention and Control of Human Trafficking Ordinance 2002 (2018-05-30)
--   8220 -> 3404 National Institute of Health Ordinance 1980 (2021-07-29)
-- A repeal is a fact about the law, not about one copy of its text. The stored status is NOT copied to the twin --
-- audit A14 requires every instrument's 'repealed' to rest on its own statutory_repeal row -- so the view reads the
-- law-level repeal through v_consolidated_twin_current: for the consolidated side, the earliest repeal of either
-- text; instrument_status, repealed_on and repealed_by_id report it. Columns are unchanged.
--
-- REVERSAL: restore 0075's view body. Governing contract: docs/03b §6.2; INV-5; migrations 0066, 0071, 0075.

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
  -- the law's repeal: this text's own, or (for a consolidated text) its as-made twin's, the earlier one
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
   AND (nzq_territory() IS NULL OR i.jurisdiction::text = 'fed' OR i.jurisdiction::text = nzq_territory())
   AND NOT EXISTS (SELECT 1 FROM v_consolidated_twin_current t WHERE t.as_made_instrument_id = i.id);

COMMIT;
