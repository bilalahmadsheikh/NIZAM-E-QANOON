-- Partial repeals: a later law repeals or omits PART of a held law -- named sections, a sub-section, a Part, a
-- Chapter, Articles -- and operative_provision stops serving that unit and everything under it from the repeal.
--
-- Found 16-17 Nov 2026 (docs/CORPUS-STATE-2026-11-17.md, "Open items"): statutory_repeal (0066) and
-- territorial_repeal (0095) record only WHOLE repeals, and both recorders skip a clause that names "section N of"
-- the law. The released corpus prints such clauses, e.g.
--   Karachi Water and Sewerage Board Act, 1996 (2019): "Sections 121 to 147 contained in Chapter XVI of the Sindh
--     Local Government Ordinance 1979 are hereby repealed";
--   Registered Designs Ordinance, 2000 (2722): "section 2 and sections 43, 44, ... 54 of the Patents and Designs Act,
--     1911 ... are hereby repealed";
--   Pakistan Air Safety Investigation Act, 2023 (4001): "section 7 of the Civil Aviation Ordinance, 1960 ... repealed".
-- A consolidated portal text usually already prints such a unit as omitted; where it does not -- an as-made text, or
-- a province repealing part of a federal law for itself -- the unit was served as law after its repeal.
--
-- 1. provision_repeal: append-only, source-keyed like 0066/0095 so a replay does not orphan it. The repealed unit is
--    named by its relative provision path within the repealed expression ('s_27.ss_2', 'ch_XVI'), resolved by
--    tools/record_provision_repeals.py to exactly one held provision. territory NULL = wherever the law runs; a
--    territory = only there (a province repealing part of a federal-text law for itself, or 'to the extent of').
-- 2. v_provision_repeal_current: the standing rows resolved to the active canonical instruments and provision, with
--    the date the unit stops being served (repealed_on, else the repealing law's commencement, enactment, or 1 January
--    of its year -- as 0095 dates a territorial repeal).
-- 3. mv_provision_repeal: that set, materialized (refreshed by tools/refresh_serving.py; audit A18 compares it).
-- 4. operative_provision: a provision at or under a standing repealed unit is not served from effective_from, in its
--    territory (or everywhere). Columns unchanged.
--
-- REVERSAL: restore 0100's operative_provision; drop mv_provision_repeal and v_provision_repeal_current; drop
-- provision_repeal (irreversible once a row exists, docs/03 §9: withdraw rows instead).
-- Governing contract: docs/03b §1.1 (repeals), INV-4 (the provision is the unit), INV-5; migrations 0066, 0095, 0100.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE provision_repeal (
    id                            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repealed_observation_id       bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    repealed_expression_ordinal   smallint NOT NULL CHECK (repealed_expression_ordinal >= 0),
    repealed_relative_path        text NOT NULL CHECK (repealed_relative_path ~ '^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$'),
    repealed_unit_as_printed      text NOT NULL CHECK (btrim(repealed_unit_as_printed) <> ''),
    repealing_observation_id      bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    repealing_expression_ordinal  smallint NOT NULL CHECK (repealing_expression_ordinal >= 0),
    repealing_source_block_id     bigint NOT NULL CHECK (repealing_source_block_id > 0),
    repealing_relative_path       text NOT NULL CHECK (btrim(repealing_relative_path) <> ''),
    territory                     text CHECK (territory IS NULL OR territory IN
                                              ('punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb')),
    clause_text                   text NOT NULL CHECK (btrim(clause_text) <> ''),
    verb                          text NOT NULL CHECK (verb IN ('repealed', 'omitted')),
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

CREATE INDEX provision_repeal_key
    ON provision_repeal (repealed_observation_id, repealed_expression_ordinal, repealed_relative_path,
                         (coalesce(territory, '*')), repealing_observation_id, repealing_expression_ordinal,
                         repealing_relative_path, recorded_at DESC, id DESC);

CREATE FUNCTION check_provision_repeal() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'provision_repeal is append-only';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.repealed_observation_id AND outcome = 'landed')
       OR NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.repealing_observation_id AND outcome = 'landed') THEN
        RAISE EXCEPTION 'both observations must have landed';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER provision_repeal_guard
BEFORE INSERT OR UPDATE OR DELETE ON provision_repeal
FOR EACH ROW EXECUTE FUNCTION check_provision_repeal();

CREATE TRIGGER provision_repeal_no_truncate
BEFORE TRUNCATE ON provision_repeal
FOR EACH STATEMENT EXECUTE FUNCTION check_provision_repeal();

COMMENT ON TABLE provision_repeal IS
  'Append-only: a released law repeals or omits a named unit of another held law (a section, sub-section, Part, '
  'Chapter or Article), clause verbatim, unit by relative provision path. territory NULL = wherever the law runs. '
  'operative_provision stops serving the unit and its subtree from the repeal. Migration 0102.';

CREATE VIEW v_provision_repeal_current AS
WITH latest AS (
    SELECT DISTINCT ON (repealed_observation_id, repealed_expression_ordinal, repealed_relative_path,
                        coalesce(territory, '*'), repealing_observation_id, repealing_expression_ordinal,
                        repealing_relative_path) *
      FROM provision_repeal
     ORDER BY repealed_observation_id, repealed_expression_ordinal, repealed_relative_path, coalesce(territory, '*'),
              repealing_observation_id, repealing_expression_ordinal, repealing_relative_path,
              recorded_at DESC, id DESC)
SELECT l.*, repealed.id AS repealed_instrument_id, repealing.id AS repealing_instrument_id,
       p.id AS provision_id, p.path AS provision_path,
       coalesce(l.repealed_on, repealing.commenced_on, repealing.enacted_on,
                make_date(repealing.year, 1, 1)) AS effective_from
  FROM latest l
  JOIN instrument repealed ON repealed.source_observation_id = l.repealed_observation_id
                          AND repealed.expression_ordinal = l.repealed_expression_ordinal
                          AND repealed.is_active AND repealed.duplicate_of IS NULL
  JOIN instrument repealing ON repealing.source_observation_id = l.repealing_observation_id
                           AND repealing.expression_ordinal = l.repealing_expression_ordinal
                           AND repealing.is_active AND repealing.duplicate_of IS NULL
  JOIN provision p ON p.instrument_id = repealed.id AND p.is_active
                  AND subpath(p.path, 3)::text = l.repealed_relative_path
 WHERE l.assertion = 'repealed';

-- one row per repealed unit and territory key ('*' = everywhere), the earliest standing date
CREATE MATERIALIZED VIEW mv_provision_repeal AS
SELECT repealed_instrument_id AS instrument_id, provision_id, provision_path AS path,
       coalesce(territory, '*') AS territory_key, min(effective_from) AS effective_from
  FROM v_provision_repeal_current
 GROUP BY 1, 2, 3, 4;

CREATE UNIQUE INDEX mv_provision_repeal_pk ON mv_provision_repeal (provision_id, territory_key);
CREATE INDEX mv_provision_repeal_instrument ON mv_provision_repeal (instrument_id);

COMMENT ON MATERIALIZED VIEW mv_provision_repeal IS
  'Serving snapshot of v_provision_repeal_current: repealed units and the date they stop being served, per '
  'territory key (* = everywhere). Refreshed by tools/refresh_serving.py; audit A18. Migration 0102.';

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
                    AND (m.territory_exits ->> nzq_territory())::date <= nzq_as_of(), false)
   -- 0102: a repealed unit and everything under it, from the repeal, everywhere or in its territory
   AND NOT EXISTS (SELECT 1 FROM mv_provision_repeal r
                    WHERE r.instrument_id = p.instrument_id AND p.path <@ r.path
                      AND r.effective_from <= nzq_as_of()
                      AND (r.territory_key = '*' OR r.territory_key = nzq_territory()));

COMMIT;
