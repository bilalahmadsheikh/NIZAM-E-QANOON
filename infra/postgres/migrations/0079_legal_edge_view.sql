-- legal_edge: docs/03b §6's typed edge relation, as built -- a VIEW over the source-keyed relation records, not a table.
--
-- WHY A VIEW (lead decision, 14 Nov 2026, under the owner's standing delegation to take the recommended option).
-- docs/03b §6 designs legal_edge as a table of provision/instrument uuids with ON DELETE CASCADE. In this corpus a
-- replay retires a released tree and builds new provision ids (append-only, CLAUDE.md "Two rules the corpus taught"),
-- so a stored uuid edge is either cascaded away or left pointing at a retired row on the next repair -- the failure
-- 0054/0062/0065-0067/0070/0072/0075 each avoided by keying their records on SOURCES (observation, expression ordinal,
-- block ids) and resolving them through a view. The relations are already recorded that way:
--   amends   amendment_reference (0072-0074, 0078)  -> v_amendment_reference_current
--   repeals  statutory_repeal                        -> v_statutory_repeal_current
-- legal_edge resolves both to the current instrument and provision ids, in docs/03b's columns, so a reader gets the
-- documented shape and a replay never orphans an edge. An edge is emitted only when BOTH ends resolve.
--
-- Columns as docs/03b: kind, src_provision | src_instrument (exactly one), dst_provision | dst_instrument | dst_judgment
-- | dst_schedule (exactly one), validity, raw_text, confidence, method ('grammar' -- both are parsed from printed text by
-- a fixed grammar), verified_by. Added: source_relation and source_id name the record behind the edge (INV-3 replay).
--   amends : src_instrument = the amending law; dst_provision = the provision whose body block carries the footnote
--            marker, else dst_instrument = the amended law. validity [w.e.f., ) when printed, else (,).
--   repeals: src_provision = the repealing clause when its recorded path resolves, else src_instrument; dst_instrument
--            = the repealed law. validity [repealed_on, ) when dated, else (,).
-- Not edges here: 'contains' is the ltree (provision.path); instrument_supersession and consolidated_twin relate
-- versions of ONE law, not two laws; the other ten kinds have no recorded relation yet.
-- REVERSAL: DROP VIEW legal_edge; DROP TYPE edge_kind.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TYPE edge_kind AS ENUM (
    'contains', 'amends', 'repeals', 'saves', 'commences', 'empowers', 'defines',
    'defaults_from', 'notwithstanding', 'subject_to', 'refers_to',
    'interpreted_by', 'invalidated_by', 'attracts');

CREATE VIEW legal_edge AS
SELECT 'amends'::edge_kind                                    AS kind,
       NULL::uuid                                             AS src_provision,
       a.amending_instrument_id                               AS src_instrument,
       a.target_provision_id                                  AS dst_provision,
       CASE WHEN a.target_provision_id IS NULL THEN a.amended_instrument_id END AS dst_instrument,
       NULL::uuid                                             AS dst_judgment,
       NULL::uuid                                             AS dst_schedule,
       CASE WHEN a.effective_from IS NOT NULL THEN daterange(a.effective_from, NULL, '[)')
            ELSE '(,)'::daterange END                          AS validity,
       a.footnote_text                                        AS raw_text,
       1.0::real                                              AS confidence,
       'grammar'::text                                        AS method,
       NULL::text                                             AS verified_by,
       'amendment_reference'::text                            AS source_relation,
       a.id                                                   AS source_id
  FROM v_amendment_reference_current a
 WHERE a.amending_instrument_id IS NOT NULL
UNION ALL
SELECT 'repeals'::edge_kind,
       src.id,
       CASE WHEN src.id IS NULL THEN r.repealing_instrument_id END,
       NULL::uuid,
       r.repealed_instrument_id,
       NULL::uuid,
       NULL::uuid,
       CASE WHEN r.repealed_on IS NOT NULL THEN daterange(r.repealed_on, NULL, '[)') ELSE '(,)'::daterange END,
       r.clause_text,
       1.0::real,
       'grammar'::text,
       NULL::text,
       'statutory_repeal'::text,
       r.id
  FROM v_statutory_repeal_current r
  LEFT JOIN LATERAL (
       SELECT p.id
         FROM provision p
        WHERE r.repealing_relative_path IS NOT NULL
          AND p.instrument_id = r.repealing_instrument_id AND p.is_active
          AND nlevel(p.path) > nlevel(r.repealing_relative_path::ltree)
          AND subpath(p.path, nlevel(p.path) - nlevel(r.repealing_relative_path::ltree)) = r.repealing_relative_path::ltree
        LIMIT 1) src ON true
 WHERE r.repealing_instrument_id IS NOT NULL AND r.repealed_instrument_id IS NOT NULL;

COMMENT ON VIEW legal_edge IS
  'docs/03b §6 legal_edge as built (0079): amends and repeals edges resolved from the source-keyed records '
  'amendment_reference and statutory_repeal to current instrument/provision ids; both ends resolved or no edge.';

COMMIT;
