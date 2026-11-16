-- A subordinate instrument made under a HISTORICAL law is historical too (v_instrument_currency, after 0089).
--
-- 0089 linked 1,042 rules, regulations, orders and notifications to the law their enacting formula names, and
-- tools/record_status.py now records each one's reason with its enabling law's currency. Ten were made under a law
-- 0088 classes as historical -- a law of a place outside Pakistan, or a pre-1947 text no official consolidated code
-- publishes. A rule cannot be current law of Pakistan when the law it was made under is not: they are historical,
-- from 1947-08-15, like their parent. A rule whose enabling law is NOT CURRENT (repealed or replaced) is not touched:
-- the General Clauses Acts (s.24) continue rules made under a law that is repealed and re-enacted, so it stays
-- current_unverified with the reason 'subordinate_*_enabling_law_not_current' for the answer to state.
-- REVERSAL: re-create 0089's v_instrument_currency.
-- Governing contract: docs/03b §1.1 (empowers), §3; migrations 0088, 0089.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE OR REPLACE VIEW v_instrument_currency AS
SELECT i.id AS instrument_id,
       c.currency,
       c.reason,
       c.not_current_from
  FROM v_release_instrument i
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
           WHEN cardinality(territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                             i.source_url)) = 0 THEN 'historical'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN 'historical'
           WHEN st.basis ~ '^subordinate_[a-z]+_enabling_law_historical$' THEN 'historical'      -- 0090
           WHEN i.status = 'in_force' THEN 'current'
           ELSE 'current_unverified' END AS currency,
      CASE WHEN i.status = 'repealed' THEN 'repealed'
           WHEN i.status = 'lapsed' THEN 'ordinance_lapsed'
           WHEN i.repealed_by_id IS NOT NULL THEN 'repealed_date_not_established'
           WHEN sup.basis = 'supersession_clause' THEN 'superseded_by_later_instrument'
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
           WHEN st.basis ~ '^subordinate_[a-z]+_enabling_law_historical$' THEN DATE '1947-08-15'   -- 0090
           END AS not_current_from) c;

COMMIT;
