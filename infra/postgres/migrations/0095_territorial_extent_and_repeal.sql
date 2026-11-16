-- Where a law runs, from its own text: the printed extent clause, and repeals confined to one territory.
--
-- Found 16 Nov 2026 while authoring golden set 3 (docs/SCHEMA.md "Known costs"):
--   1. territory_reach3 reads only a federal law's TITLE. The Hindu Marriage Act, 2017 prints in s.1(2) "It extends
--      to the Islamabad Capital Territory and the Provinces of Balochistan, Khyber Pakhtunkhwa and Punjab", yet it was
--      served in Sindh (which has its own Sindh Hindus Marriage Act, 2016).
--   2. A repeal confined to one territory was not modelled. The ICT Child Marriage Restraint Act, 2025 s.13(1): "The
--      Child Marriage Restraint Act, 1929 is hereby repealed to the extent of Islamabad Capital Territory"; the
--      Balochistan Act of 2025 s.14(1) likewise "to the extent of Balochistan Province"; the Punjab Child Marriage
--      Restraint Act, 2026 s.15 and the Punjab Defamation Act, 2024 s.28 repeal laws a province can repeal only for
--      itself. statutory_repeal (0066) records whole repeals within one jurisdiction, so the federal texts stayed
--      served in those territories.
--
-- 1. instrument_metadata_assertion gains field 'territorial_extent': the territories a law's own extent clause names,
--    as a comma list of punjab | sindh | kp | balochistan | ict, with the verbatim clause and its source block
--    (tools/record_territorial_extent.py). Where one stands it decides the law's reach; otherwise territory_reach3's
--    title reading stands (extent_basis says which).
-- 2. territorial_repeal: a released Act repeals a federal-text law for ONE territory -- the repealing Act's own
--    province, or ICT where an ICT law says so (tools/record_territorial_repeals.py). Append-only, latest wins, keyed
--    like statutory_repeal. It never sets instrument.status: the law stays in force elsewhere.
-- 3. v_instrument_currency carries territory_exits {territory: date} (repealed_on, else the repealing Act's
--    commencement, enactment, or 1 January of its year -- as 0093 dates an undated whole repeal). A law that has left
--    EVERY territory it reached is not_current ('repealed_in_each_territory') from the last exit.
-- 4. mv_instrument_serving copies it; operative_provision stops serving a law in a territory from that date. A read
--    without nzq.territory still returns it (it is law somewhere) and carries territory_exits for the caller.
--
-- REVERSAL: re-create 0094's mv_instrument_serving and operative_provision and 0093's v_instrument_currency; drop
-- territorial_repeal (irreversible once a row exists, docs/03 §9); restore 0083's field constraints.
-- Governing contract: docs/03b §6 (extent), docs/04 §6 (territory), INV-5; migrations 0066, 0070, 0083, 0086-0094.

BEGIN;

SET LOCAL lock_timeout = '10s';

-- ------------------------------------------------------------------------------------------------ 1. extent field
ALTER TABLE instrument_metadata_assertion
    DROP CONSTRAINT instrument_metadata_assertion_field,
    DROP CONSTRAINT instrument_metadata_assertion_printed_fact;

ALTER TABLE instrument_metadata_assertion
    ADD CONSTRAINT instrument_metadata_assertion_field
        CHECK (field IN ('display_title', 'number', 'enacted_on', 'commenced_on', 'text_language', 'status',
                         'long_title', 'territorial_extent')),
    ADD CONSTRAINT instrument_metadata_assertion_printed_fact
        CHECK (assertion = 'withdrawn'
               OR field NOT IN ('number', 'enacted_on', 'commenced_on', 'status', 'long_title', 'territorial_extent')
               OR (quote IS NOT NULL AND btrim(quote) <> '' AND source_block_id IS NOT NULL)),
    ADD CONSTRAINT instrument_metadata_assertion_extent_value
        CHECK (value IS NULL OR field <> 'territorial_extent'
               OR value ~ '^(punjab|sindh|kp|balochistan|ict)(,(punjab|sindh|kp|balochistan|ict))*$');

COMMENT ON TABLE instrument_metadata_assertion IS
  'Append-only: one metadata field of one expression (display_title, number, enacted_on, commenced_on, '
  'text_language, status, long_title, territorial_extent) with its basis and, for printed facts, the verbatim quote '
  'and source block. instrument columns are derived from v_instrument_metadata_current by '
  'tools/apply_instrument_metadata.py; territorial_extent is read by v_instrument_currency. Migrations 0070, 0082, '
  '0083, 0095.';

-- ------------------------------------------------------------------------------------------------ 2. territorial repeal
CREATE TABLE territorial_repeal (
    id                            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repealed_observation_id       bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    repealed_expression_ordinal   smallint NOT NULL CHECK (repealed_expression_ordinal >= 0),
    repealing_observation_id      bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    repealing_expression_ordinal  smallint NOT NULL CHECK (repealing_expression_ordinal >= 0),
    repealing_source_block_id     bigint NOT NULL CHECK (repealing_source_block_id > 0),
    repealing_relative_path       text NOT NULL CHECK (btrim(repealing_relative_path) <> ''),
    territory                     text NOT NULL CHECK (territory IN ('punjab', 'sindh', 'kp', 'balochistan', 'ict')),
    clause_text                   text NOT NULL CHECK (btrim(clause_text) <> ''),
    matched_title                 text NOT NULL CHECK (btrim(matched_title) <> ''),
    matched_year                  smallint NOT NULL CHECK (matched_year BETWEEN 1800 AND 2100),
    repealed_on                   date,
    repealed_on_basis             text,
    assertion                     text NOT NULL CHECK (assertion IN ('repealed', 'withdrawn')),
    method                        text NOT NULL CHECK (btrim(method) <> ''),
    evidence                      jsonb NOT NULL CHECK (coalesce(jsonb_typeof(evidence) = 'object'
                                                         AND btrim(evidence->>'reviewer_type') <> '', false)),
    recorded_by                   text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at                   timestamptz NOT NULL DEFAULT now(),
    CHECK ((repealed_observation_id, repealed_expression_ordinal)
           <> (repealing_observation_id, repealing_expression_ordinal)),
    CHECK ((repealed_on IS NULL) = (repealed_on_basis IS NULL)),
    CHECK (repealed_on_basis IS NULL OR btrim(repealed_on_basis) <> '')
);

CREATE INDEX territorial_repeal_key
    ON territorial_repeal (repealed_observation_id, repealed_expression_ordinal, territory, repealing_observation_id,
                           repealing_expression_ordinal, repealing_relative_path, recorded_at DESC, id DESC);

CREATE FUNCTION check_territorial_repeal() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'territorial_repeal is append-only';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.repealed_observation_id AND outcome = 'landed')
       OR NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.repealing_observation_id AND outcome = 'landed') THEN
        RAISE EXCEPTION 'both observations must have landed';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER territorial_repeal_guard
BEFORE INSERT OR UPDATE OR DELETE ON territorial_repeal
FOR EACH ROW EXECUTE FUNCTION check_territorial_repeal();

CREATE TRIGGER territorial_repeal_no_truncate
BEFORE TRUNCATE ON territorial_repeal
FOR EACH STATEMENT EXECUTE FUNCTION check_territorial_repeal();

-- standing rows resolved to the active canonical instruments, with the date the territory stops being served
CREATE VIEW v_territorial_repeal_current AS
WITH latest AS (
    SELECT DISTINCT ON (repealed_observation_id, repealed_expression_ordinal, territory, repealing_observation_id,
                        repealing_expression_ordinal, repealing_relative_path) *
      FROM territorial_repeal
     ORDER BY repealed_observation_id, repealed_expression_ordinal, territory, repealing_observation_id,
              repealing_expression_ordinal, repealing_relative_path, recorded_at DESC, id DESC)
SELECT l.*, repealed.id AS repealed_instrument_id, repealing.id AS repealing_instrument_id,
       coalesce(l.repealed_on, repealing.commenced_on, repealing.enacted_on,
                make_date(repealing.year, 1, 1)) AS effective_from
  FROM latest l
  JOIN instrument repealed ON repealed.source_observation_id = l.repealed_observation_id
                          AND repealed.expression_ordinal = l.repealed_expression_ordinal
                          AND repealed.is_active AND repealed.duplicate_of IS NULL
  JOIN instrument repealing ON repealing.source_observation_id = l.repealing_observation_id
                           AND repealing.expression_ordinal = l.repealing_expression_ordinal
                           AND repealing.is_active AND repealing.duplicate_of IS NULL
 WHERE l.assertion = 'repealed';

COMMENT ON TABLE territorial_repeal IS
  'Append-only: a released Act repeals a federal-text law for one territory (its own province, or ICT where an ICT law '
  'says so), clause verbatim. Never sets instrument.status; v_instrument_currency turns it into territory_exits. '
  'Migration 0095.';

-- ------------------------------------------------------------------------------------------------ 3. currency
DROP VIEW operative_provision;
DROP MATERIALIZED VIEW mv_instrument_serving;
DROP VIEW v_instrument_currency;

CREATE VIEW v_instrument_currency AS
SELECT i.id AS instrument_id,
       c.currency,
       c.reason,
       c.not_current_from,
       r.reach                                  AS territory_reach,
       CASE WHEN i.jurisdiction::text <> 'fed' THEN 'own_territory'
            WHEN ext.value IS NOT NULL THEN 'printed_extent_clause'
            WHEN r.reach = ARRAY['punjab', 'sindh', 'kp', 'balochistan', 'ict'] THEN 'jurisdiction_default'
            ELSE 'title_named_territory' END    AS extent_basis,
       tx.exits                                 AS territory_exits
  FROM v_release_instrument i
  LEFT JOIN v_instrument_metadata_current ext ON ext.instrument_id = i.id AND ext.field = 'territorial_extent'
  CROSS JOIN LATERAL (SELECT CASE WHEN i.jurisdiction::text = 'fed' AND ext.value IS NOT NULL
                                  THEN string_to_array(ext.value, ',')
                                  ELSE territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                                        i.source_url) END AS reach) r
  LEFT JOIN LATERAL (SELECT jsonb_object_agg(e.territory, e.from_date) AS exits,
                            array_agg(e.territory) AS gone, max(e.from_date) AS last_exit
                       FROM (SELECT tr.territory, min(tr.effective_from) AS from_date
                               FROM v_territorial_repeal_current tr
                              WHERE tr.repealed_instrument_id = i.id GROUP BY tr.territory) e) tx ON true
  LEFT JOIN v_instrument_metadata_current st ON st.instrument_id = i.id AND st.field = 'status'
  LEFT JOIN instrument rep ON rep.id = i.repealed_by_id
  LEFT JOIN LATERAL (SELECT s.superseding_instrument_id, s.basis FROM v_instrument_supersession_current s
                      WHERE s.superseded_instrument_id = i.id ORDER BY s.recorded_at, s.id LIMIT 1) sup ON true
  LEFT JOIN instrument succ ON succ.id = sup.superseding_instrument_id
  LEFT JOIN source_observation o ON o.id = i.source_observation_id
  CROSS JOIN LATERAL (SELECT
      cardinality(r.reach) > 0 AND tx.gone IS NOT NULL AND r.reach <@ tx.gone AS gone_everywhere) g
  CROSS JOIN LATERAL (SELECT
      CASE WHEN i.status = 'repealed' THEN 'not_current'
           WHEN i.status = 'lapsed' THEN 'not_current'
           WHEN i.repealed_by_id IS NOT NULL THEN 'not_current'
           WHEN sup.superseding_instrument_id IS NOT NULL THEN 'not_current'
           WHEN st.basis = 'portal_repeal_note' THEN 'not_current'
           WHEN g.gone_everywhere THEN 'not_current'
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
           WHEN g.gone_everywhere THEN 'repealed_in_each_territory'
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
           WHEN g.gone_everywhere THEN tx.last_exit
           WHEN cardinality(r.reach) = 0 THEN DATE '1947-08-15'
           WHEN st.basis = 'pre_independence_not_from_a_consolidated_code' THEN DATE '1947-08-15'
           WHEN st.basis ~ '^subordinate_[a-z]+_enabling_law_historical$' THEN DATE '1947-08-15'
           END AS not_current_from) c;

COMMENT ON VIEW v_instrument_currency IS
  'Per released instrument: currency (current | current_unverified | not_current | historical), reason, the earliest '
  'date the evidence proves it stopped, its territorial reach (printed extent clause, else title reading) and the '
  'date it left each territory a territorial repeal removed it from. Migrations 0088-0095.';

-- ------------------------------------------------------------------------------------------------ 4. snapshot + view
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
       cur.extent_basis,
       cur.territory_exits
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
  'Per released canonical law (as-made twins excluded): release, currency, reach, territory exits, twin-level repeal, '
  'supersession and historical window, computed once. Refreshed by tools/refresh_serving.py; audit A16 fails when '
  'stale. Migrations 0094, 0095.';

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
       m.territory_exits
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
   AND (nzq_territory() IS NULL OR nzq_territory() = ANY (m.territory_reach))
   AND NOT (nzq_territory() IS NOT NULL AND m.territory_exits ? nzq_territory()
            AND (m.territory_exits ->> nzq_territory())::date <= nzq_as_of());

COMMIT;
