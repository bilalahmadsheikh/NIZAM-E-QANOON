-- Every released law carries a CURRENCY and its reason, and operative_provision stops serving what the evidence says
-- is no longer current law. 'unknown' stops being one silent bucket served as if it were current law.
--
-- Found 16 Nov 2026 by golden set 1 (S1-P12): The Prevention of Electronic Crimes Ordinance, 2008 was served as
-- current law beside the Prevention of Electronic Crimes Act, 2016, because 7,542 released laws are status 'unknown'
-- and the view served every 'unknown'. Owner instruction the same day: "do something about these unknown so it is
-- not a problem". No status is guessed here; each class is derived from records that already stand:
--
--   current             status 'in_force' (record_status.py, 0082)
--   not_current         status 'repealed' (0066, dated)                                  from repealed_on
--                       status 'lapsed' (0085)                                           from the latest possible lapse
--                       a standing repeal without a date (repealed_by_id)                from the repealer's commencement,
--                                                                                        else its enactment, else 1 Jan
--                       replaced by a later Act of the same name (0067; owner decision   from the successor's enactment,
--                       q6 'mark-replaced': "shown as replaced")                         else 1 Jan of its year
--                       the official portal's title marks it repealed (record_status     from the portal observation's
--                       basis portal_repeal_note)                                        fetch date
--   historical          a law of a place outside Pakistan (territory_reach3 = {})         from 1947-08-15
--                       a pre-1947 text no official consolidated code publishes          from 1947-08-15
--                       (record_status basis pre_independence_not_from_a_consolidated_code)
--   current_unverified  everything else: nothing says it is no longer law, and nothing proves it is. The reason is
--                       the standing status assertion's basis (tools/record_status.py now records WHY it could not
--                       assert -- value 'unknown'), e.g. commencement by notification, an Ordinance made before the
--                       current Art. 89 text, a subordinate instrument whose enabling law is not linked.
--
-- For each 'not_current' and 'historical' class the cut-off is the EARLIEST date the evidence proves the law had
-- stopped (a repeal cannot take effect before its repealing Act was enacted; a replaced Ordinance was gone by the time
-- its Act was), so operative_provision drops it only for an as_of on or after that date and serves it before. A
-- current_unverified law is still served, carrying currency and currency_reason on every row: docs/13's
-- uncertainty rules make the answer say so; docs/04's gate may refuse it.
--
-- REVERSAL: restore 0085's status value check and 0087's operative_provision; drop v_instrument_currency.
-- Governing contract: docs/03b §3 (life_stage), §6.2; docs/13 (uncertainty); INV-2, INV-5; owner q6; owner 16 Nov 2026.

BEGIN;

SET LOCAL lock_timeout = '10s';

-- a recorded 'unknown' carries its reason in basis
ALTER TABLE instrument_metadata_assertion
    DROP CONSTRAINT instrument_metadata_assertion_status_value,
    ADD CONSTRAINT instrument_metadata_assertion_status_value
        CHECK (value IS NULL OR field <> 'status' OR value IN ('in_force', 'lapsed', 'unknown'));

CREATE VIEW v_instrument_currency AS
SELECT i.id AS instrument_id,
       c.currency,
       c.reason,
       c.not_current_from
  FROM v_release_instrument i
  LEFT JOIN v_instrument_metadata_current st ON st.instrument_id = i.id AND st.field = 'status'
  LEFT JOIN instrument rep ON rep.id = i.repealed_by_id
  LEFT JOIN LATERAL (SELECT s.superseding_instrument_id FROM v_instrument_supersession_current s
                      WHERE s.superseded_instrument_id = i.id ORDER BY s.recorded_at, s.id LIMIT 1) sup ON true
  LEFT JOIN instrument succ ON succ.id = sup.superseding_instrument_id
  LEFT JOIN source_observation o ON o.id = i.source_observation_id
  CROSS JOIN LATERAL (SELECT
      CASE WHEN i.status = 'repealed' THEN 'not_current'
           WHEN i.status = 'lapsed' THEN 'not_current'
           WHEN i.repealed_by_id IS NOT NULL THEN 'not_current'
           WHEN sup.superseding_instrument_id IS NOT NULL THEN 'not_current'
           WHEN st.basis = 'portal_repeal_note' THEN 'not_current'
           WHEN cardinality(territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                             i.source_url)) = 0 THEN 'historical'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN 'historical'
           WHEN i.status = 'in_force' THEN 'current'
           ELSE 'current_unverified' END AS currency,
      CASE WHEN i.status = 'repealed' THEN 'repealed'
           WHEN i.status = 'lapsed' THEN 'ordinance_lapsed'
           WHEN i.repealed_by_id IS NOT NULL THEN 'repealed_date_not_established'
           WHEN sup.superseding_instrument_id IS NOT NULL THEN 'replaced_by_later_act'
           WHEN st.basis = 'portal_repeal_note' THEN 'official_portal_marks_repealed'
           WHEN cardinality(territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                             i.source_url)) = 0 THEN 'law_of_a_place_outside_pakistan'
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
           WHEN cardinality(territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                             i.source_url)) = 0 THEN DATE '1947-08-15'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN DATE '1947-08-15'
           END AS not_current_from) c;

COMMENT ON VIEW v_instrument_currency IS
  'Per released instrument: current | current_unverified | not_current | historical, the reason, and the earliest date '
  'the evidence proves it stopped being current law. Derived only from standing records. Migration 0088.';

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
       territory_reach_basis3(i.jurisdiction::text, coalesce(i.display_title, i.short_title), i.source_url)
                                              AS extent_coverage,
       nzq_as_of()                            AS as_of,
       cur.currency,                                                          -- 0088
       cur.reason                             AS currency_reason             -- 0088
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
   -- 0088: not current law (or historical) from the earliest date the evidence proves it
   AND NOT (cur.currency IN ('not_current', 'historical') AND cur.not_current_from IS NOT NULL
            AND cur.not_current_from <= nzq_as_of())
   AND (nzq_territory() IS NULL
        OR nzq_territory() = ANY (territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                                   i.source_url)))
   AND NOT EXISTS (SELECT 1 FROM v_consolidated_twin_current t WHERE t.as_made_instrument_id = i.id);

COMMIT;
