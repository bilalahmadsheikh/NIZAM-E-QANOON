-- Territorial reach computed once per instrument, not once per provision row.
--
-- 0087's operative_provision called the plpgsql function territory_reach3 in its WHERE clause for every provision row
-- (1.17 million): a whole-territory read took many minutes (measured 16 Nov 2026; docs/SCHEMA.md said retrieval must
-- not pay that). v_instrument_currency already reads each released instrument once; it now also carries the
-- instrument's territory_reach and extent basis, and operative_provision filters and reports from those columns.
-- Meaning is unchanged: same function, same inputs, evaluated per instrument.
-- REVERSAL: re-create 0090's v_instrument_currency and 0088's operative_provision.
-- Governing contract: docs/04 §6 (territory), docs/03 (query cost); migrations 0086-0090.

BEGIN;

SET LOCAL lock_timeout = '10s';

DROP VIEW operative_provision;
DROP VIEW v_instrument_currency;

CREATE VIEW v_instrument_currency AS
SELECT i.id AS instrument_id,
       c.currency,
       c.reason,
       c.not_current_from,
       r.reach                                  AS territory_reach,
       CASE WHEN i.jurisdiction::text <> 'fed' THEN 'own_territory'
            WHEN r.reach = ARRAY['punjab', 'sindh', 'kp', 'balochistan', 'ict'] THEN 'jurisdiction_default'
            ELSE 'title_named_territory' END    AS extent_basis
  FROM v_release_instrument i
  CROSS JOIN LATERAL (SELECT territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                              i.source_url) AS reach) r
  LEFT JOIN v_instrument_metadata_current st ON st.instrument_id = i.id AND st.field = 'status'
  LEFT JOIN instrument rep ON rep.id = i.repealed_by_id
  LEFT JOIN LATERAL (SELECT s.superseding_instrument_id, s.basis FROM v_instrument_supersession_current s
                      WHERE s.superseded_instrument_id = i.id ORDER BY s.recorded_at, s.id LIMIT 1) sup ON true
  LEFT JOIN instrument succ ON succ.id = sup.superseding_instrument_id
  LEFT JOIN source_observation o ON o.id = i.source_observation_id
  CROSS JOIN LATERAL (SELECT
      CASE WHEN i.status = 'repealed' THEN 'not_current'
           WHEN i.status = 'lapsed' THEN 'not_current'
           WHEN i.repealed_by_id IS NOT NULL THEN 'not_current'
           WHEN sup.superseding_instrument_id IS NOT NULL THEN 'not_current'
           WHEN st.basis = 'portal_repeal_note' THEN 'not_current'
           WHEN cardinality(r.reach) = 0 THEN 'historical'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN 'historical'
           WHEN st.basis ~ '^subordinate_[a-z]+_enabling_law_historical$' THEN 'historical'
           WHEN i.status = 'in_force' THEN 'current'
           ELSE 'current_unverified' END AS currency,
      CASE WHEN i.status = 'repealed' THEN 'repealed'
           WHEN i.status = 'lapsed' THEN 'ordinance_lapsed'
           WHEN i.repealed_by_id IS NOT NULL THEN 'repealed_date_not_established'
           WHEN sup.basis = 'supersession_clause' THEN 'superseded_by_later_instrument'
           WHEN sup.superseding_instrument_id IS NOT NULL THEN 'replaced_by_later_act'
           WHEN st.basis = 'portal_repeal_note' THEN 'official_portal_marks_repealed'
           WHEN cardinality(r.reach) = 0 THEN 'law_of_a_place_outside_pakistan'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN 'pre_1947_text_not_in_official_consolidation'
           WHEN i.status = 'in_force' THEN st.basis
           ELSE coalesce(st.basis, 'not_assessed') END AS reason,
      CASE WHEN i.status = 'repealed' THEN i.repealed_on
           WHEN i.status = 'lapsed' THEN ordinance_latest_lapse(i.jurisdiction::text, i.enacted_on, i.year)
           WHEN i.repealed_by_id IS NOT NULL
                THEN coalesce(rep.commenced_on, rep.enacted_on, make_date(rep.year, 1, 1))
           WHEN sup.superseding_instrument_id IS NOT NULL
                THEN coalesce(succ.enacted_on, make_date(succ.year, 1, 1))
           WHEN st.basis = 'portal_repeal_note' THEN coalesce(o.fetched_at::date, current_date)
           WHEN cardinality(r.reach) = 0 THEN DATE '1947-08-15'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN DATE '1947-08-15'
           WHEN st.basis ~ '^subordinate_[a-z]+_enabling_law_historical$' THEN DATE '1947-08-15'
           END AS not_current_from) c;

COMMENT ON VIEW v_instrument_currency IS
  'Per released instrument: currency (current | current_unverified | not_current | historical), reason, the earliest '
  'date the evidence proves it stopped, and its territorial reach. Migrations 0088-0093.';

CREATE VIEW operative_provision AS
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
       cur.extent_basis                       AS extent_coverage,
       nzq_as_of()                            AS as_of,
       cur.currency,
       cur.reason                             AS currency_reason
  FROM v_release_instrument i
  JOIN v_instrument_currency cur ON cur.instrument_id = i.id
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
   AND NOT (cur.currency IN ('not_current', 'historical') AND cur.not_current_from IS NOT NULL
            AND cur.not_current_from <= nzq_as_of())
   AND (nzq_territory() IS NULL OR nzq_territory() = ANY (cur.territory_reach))
   AND NOT EXISTS (SELECT 1 FROM v_consolidated_twin_current t WHERE t.as_made_instrument_id = i.id);

COMMIT;
