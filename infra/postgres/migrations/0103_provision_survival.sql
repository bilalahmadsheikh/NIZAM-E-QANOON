-- A whole repeal that EXCEPTS named units: the rest of the law goes, those units stay law and stay served.
--
-- Found 17 Nov 2026 while modelling partial repeals (0102). The released corpus prints
--   Companies Act, 2017 (4486) s.509(1): "The Companies Ordinance, 1984 (XLVII of 1984) ... shall stand repealed,
--     except Part VIIIA consisting of sections 282A to 282N" -- the Ordinance was not_current from 2017
--     (replaced_by_later_act), so Part VIIIA, still law for non-banking finance companies, was served nowhere;
--   PIA Corporation (Conversion) (Repeal) Act (3043, 9899) s.2(1): "The Pakistan International Airlines Corporation
--     (Conversion) Act, 2016 (XV of 2016) is hereby repealed except sub-section (1) of section 7" -- record_statutory_
--     repeals.py skips any clause with 'except', so the 2016 Act was presumed in force in full.
-- tools/record_provision_repeals.py now records such a clause twice over: the whole repeal (statutory_repeal, 0066,
-- method nizam.repeal_except_units/1) and each excepted unit here.
--
-- 1. provision_survival: append-only, source-keyed like 0102. subtree = the unit and everything under it; false =
--    that node alone (a sub-section held as its section's own text, the section's later sub-sections being repealed).
-- 2. v_provision_survival_current / mv_provision_survival: resolved to the active provision; refreshed by
--    tools/refresh_serving.py; audit A18 compares them.
-- 3. operative_provision: a provision a standing survival covers is served even after its law is repealed or not
--    current; new last column survives_repeal says so (true only when the law itself is no longer served there).
--
-- REVERSAL: restore 0102's operative_provision; drop mv_provision_survival, v_provision_survival_current and
-- provision_survival (irreversible once a row exists: withdraw rows instead).
-- Governing contract: docs/03b §1.1 (repeals, saves), INV-4, INV-5; migrations 0066, 0094, 0102.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE provision_survival (
    id                            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    survived_observation_id       bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    survived_expression_ordinal   smallint NOT NULL CHECK (survived_expression_ordinal >= 0),
    survived_relative_path        text NOT NULL CHECK (survived_relative_path ~ '^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$'),
    subtree                       boolean NOT NULL,
    unit_as_printed               text NOT NULL CHECK (btrim(unit_as_printed) <> ''),
    repealing_observation_id      bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    repealing_expression_ordinal  smallint NOT NULL CHECK (repealing_expression_ordinal >= 0),
    repealing_source_block_id     bigint NOT NULL CHECK (repealing_source_block_id > 0),
    repealing_relative_path       text NOT NULL CHECK (btrim(repealing_relative_path) <> ''),
    clause_text                   text NOT NULL CHECK (btrim(clause_text) <> ''),
    matched_title                 text NOT NULL CHECK (btrim(matched_title) <> ''),
    matched_year                  smallint NOT NULL CHECK (matched_year BETWEEN 1800 AND 2100),
    assertion                     text NOT NULL CHECK (assertion IN ('survives', 'withdrawn')),
    method                        text NOT NULL CHECK (btrim(method) <> ''),
    evidence                      jsonb NOT NULL CHECK (coalesce(jsonb_typeof(evidence) = 'object'
                                                         AND btrim(evidence->>'reviewer_type') <> '', false)),
    recorded_by                   text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at                   timestamptz NOT NULL DEFAULT now(),
    CHECK ((survived_observation_id, survived_expression_ordinal)
           <> (repealing_observation_id, repealing_expression_ordinal))
);

CREATE INDEX provision_survival_key
    ON provision_survival (survived_observation_id, survived_expression_ordinal, survived_relative_path,
                           repealing_observation_id, repealing_expression_ordinal, repealing_relative_path,
                           recorded_at DESC, id DESC);

CREATE FUNCTION check_provision_survival() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'provision_survival is append-only';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.survived_observation_id AND outcome = 'landed')
       OR NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.repealing_observation_id AND outcome = 'landed') THEN
        RAISE EXCEPTION 'both observations must have landed';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER provision_survival_guard
BEFORE INSERT OR UPDATE OR DELETE ON provision_survival
FOR EACH ROW EXECUTE FUNCTION check_provision_survival();

CREATE TRIGGER provision_survival_no_truncate
BEFORE TRUNCATE ON provision_survival
FOR EACH STATEMENT EXECUTE FUNCTION check_provision_survival();

COMMENT ON TABLE provision_survival IS
  'Append-only: a unit a whole repeal expressly excepts ("repealed, except Part VIIIA ..."), clause verbatim, unit by '
  'relative provision path; subtree false = the node alone. operative_provision serves it after its law has gone. '
  'Migration 0103.';

CREATE VIEW v_provision_survival_current AS
WITH latest AS (
    SELECT DISTINCT ON (survived_observation_id, survived_expression_ordinal, survived_relative_path,
                        repealing_observation_id, repealing_expression_ordinal, repealing_relative_path) *
      FROM provision_survival
     ORDER BY survived_observation_id, survived_expression_ordinal, survived_relative_path,
              repealing_observation_id, repealing_expression_ordinal, repealing_relative_path,
              recorded_at DESC, id DESC)
SELECT l.*, survived.id AS survived_instrument_id, repealing.id AS repealing_instrument_id,
       p.id AS provision_id, p.path AS provision_path
  FROM latest l
  JOIN instrument survived ON survived.source_observation_id = l.survived_observation_id
                          AND survived.expression_ordinal = l.survived_expression_ordinal
                          AND survived.is_active AND survived.duplicate_of IS NULL
  JOIN instrument repealing ON repealing.source_observation_id = l.repealing_observation_id
                           AND repealing.expression_ordinal = l.repealing_expression_ordinal
                           AND repealing.is_active AND repealing.duplicate_of IS NULL
  JOIN provision p ON p.instrument_id = survived.id AND p.is_active
                  AND subpath(p.path, 3)::text = l.survived_relative_path
 WHERE l.assertion = 'survives';

CREATE MATERIALIZED VIEW mv_provision_survival AS
SELECT survived_instrument_id AS instrument_id, provision_id, provision_path AS path, bool_or(subtree) AS subtree
  FROM v_provision_survival_current
 GROUP BY 1, 2, 3;

CREATE UNIQUE INDEX mv_provision_survival_pk ON mv_provision_survival (provision_id);
CREATE INDEX mv_provision_survival_instrument ON mv_provision_survival (instrument_id);

COMMENT ON MATERIALIZED VIEW mv_provision_survival IS
  'Serving snapshot of v_provision_survival_current: units served after their law has gone. Refreshed by '
  'tools/refresh_serving.py; audit A18. Migration 0103.';

CREATE OR REPLACE VIEW operative_provision AS
WITH base AS (
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
       kf.basis                               AS text_known_from_basis,
       ((m.law_repealed_on IS NOT NULL AND m.law_repealed_on <= nzq_as_of())
        OR (m.currency IN ('not_current', 'historical') AND m.not_current_from IS NOT NULL
            AND m.not_current_from <= nzq_as_of()))                                   AS law_gone,
       m.historical_validity, m.territory_reach
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
   AND (nzq_territory() IS NULL OR nzq_territory() = ANY (m.territory_reach))
   AND NOT coalesce(nzq_territory() IS NOT NULL AND m.territory_exits ? nzq_territory()
                    AND (m.territory_exits ->> nzq_territory())::date <= nzq_as_of(), false)
   -- 0102: a repealed unit and everything under it, from the repeal, everywhere or in its territory
   AND NOT EXISTS (SELECT 1 FROM mv_provision_repeal r
                    WHERE r.instrument_id = p.instrument_id AND p.path <@ r.path
                      AND r.effective_from <= nzq_as_of()
                      AND (r.territory_key = '*' OR r.territory_key = nzq_territory()))
)
SELECT b.provision_id, b.instrument_id, b.parent_id, b.path, b.provision_kind, b.label, b.heading, b.marginal_note,
       b.ordinal, b.first_page, b.text_en, b.text_ur, b.text_language, b.version_id, b.validity, b.operation,
       b.jurisdiction, b.instrument_kind, b.instrument_title, b.instrument_number, b.instrument_year,
       b.instrument_status, b.enacted_on, b.commenced_on, b.repealed_on, b.repealed_by_id,
       b.superseded_by_instrument_id, b.source_url, b.document_id, b.commencement_coverage, b.invalidation_coverage,
       b.extent_coverage, b.as_of, b.currency, b.currency_reason, b.territory_exits, b.text_known_from,
       b.text_known_from_basis,
       b.law_gone AS survives_repeal
  FROM base b
 WHERE NOT b.law_gone
    -- 0103: a unit its law's repeal expressly excepts stays served
    OR EXISTS (SELECT 1 FROM mv_provision_survival s
                WHERE s.instrument_id = b.instrument_id
                  AND (b.path = s.path OR (s.subtree AND b.path <@ s.path)));

COMMIT;
