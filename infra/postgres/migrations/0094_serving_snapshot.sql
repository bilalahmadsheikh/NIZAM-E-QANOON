-- mv_instrument_serving: the per-law serving facts computed once; operative_provision reads the snapshot.
--
-- Measured 16 Nov 2026 after 0093: one territory read of operative_provision took 7 min 25 s, because every read
-- re-derived, per law, the release gates (v_release_instrument: quality status, pending TOC, S7 and boundary work), the
-- standing status assertion, supersession, the twin-level repeal and the currency. Retrieval (docs/04) cannot sit on
-- that. These facts change only when the corpus or a record changes, so they are materialised here, per released
-- canonical instrument, and operative_provision joins the snapshot to provisions. The as_of- and territory-dependent
-- tests stay in the view; nothing is pre-filtered by date or territory.
--
-- STALENESS IS NOT ALLOWED TO BE SILENT: tools/refresh_serving.py refreshes it (REFRESH ... CONCURRENTLY) and runs at
-- the end of tools/post_replay_sequence.sh; audit A16 compares the snapshot with the live views and fails on any
-- difference -- a law released, withdrawn or re-classed since the last refresh.
--
-- REVERSAL: re-create 0093's operative_provision; drop mv_instrument_serving.
-- Governing contract: docs/03 (storage, query cost), docs/04 (retrieval reads operative_provision), INV-5;
-- migrations 0071-0093.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE MATERIALIZED VIEW mv_instrument_serving AS
SELECT i.id                                     AS instrument_id,
       i.document_id,
       i.jurisdiction::text                     AS jurisdiction,
       i.kind::text                             AS instrument_kind,
       coalesce(i.display_title, i.short_title) AS instrument_title,
       i.number                                 AS instrument_number,
       i.year                                   AS instrument_year,
       i.text_language,
       i.status::text                           AS status,
       i.enacted_on,
       i.commenced_on,
       i.source_url,
       law.repealed_on                          AS law_repealed_on,
       coalesce(law.repealed_by_id, i.repealed_by_id) AS repealed_by_id,
       s.superseding_instrument_id              AS superseded_by_instrument_id,
       h.historical_validity,
       cur.currency,
       cur.reason                               AS currency_reason,
       cur.not_current_from,
       cur.territory_reach,
       cur.extent_basis
  FROM v_release_instrument i
  JOIN v_instrument_currency cur ON cur.instrument_id = i.id
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
 WHERE NOT EXISTS (SELECT 1 FROM v_consolidated_twin_current t WHERE t.as_made_instrument_id = i.id);

CREATE UNIQUE INDEX mv_instrument_serving_pk ON mv_instrument_serving (instrument_id);
CREATE INDEX mv_instrument_serving_reach ON mv_instrument_serving USING gin (territory_reach);
CREATE INDEX mv_instrument_serving_currency ON mv_instrument_serving (currency);

COMMENT ON MATERIALIZED VIEW mv_instrument_serving IS
  'Per released canonical law (as-made twins excluded): release, currency, reach, twin-level repeal, supersession and '
  'historical window, computed once. Refreshed by tools/refresh_serving.py; audit A16 fails when stale. Migration 0094.';

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
       m.currency_reason
  FROM mv_instrument_serving m
  JOIN provision p ON p.instrument_id = m.instrument_id AND p.is_active
  JOIN provision_version v ON v.provision_id = p.id AND v.validity @> nzq_as_of()
 WHERE (m.historical_validity IS NULL OR m.historical_validity @> nzq_as_of())
   AND (m.enacted_on IS NULL OR m.enacted_on <= nzq_as_of())
   AND (m.instrument_year IS NULL OR m.instrument_year <= extract(year FROM nzq_as_of()))
   AND (m.commenced_on IS NULL OR m.commenced_on <= nzq_as_of())
   AND NOT (m.law_repealed_on IS NOT NULL AND m.law_repealed_on <= nzq_as_of())
   AND NOT (m.currency IN ('not_current', 'historical') AND m.not_current_from IS NOT NULL
            AND m.not_current_from <= nzq_as_of())
   AND (nzq_territory() IS NULL OR nzq_territory() = ANY (m.territory_reach));

COMMIT;
