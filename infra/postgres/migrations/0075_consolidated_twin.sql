-- consolidated_twin: an instrument's original text AS MADE, linked to the consolidated text of the same law.
--
-- WHY. About 40 laws are released twice: the Gazette issue as made (Ministry of Law DRS, drs.molaw.gov.pk) and the
-- Pakistan Code consolidated text (as amended, "Updated till ..."). Measured 12 Nov 2026: e.g. the Islamabad Capital
-- Territory (Tax on Services) Ordinance 2001 is 4 pages as made (5171) and 15 pages consolidated (4253). Both are
-- released and both open at their 2026 observation dates, so operative_provision (0071) served the as-made wording as
-- current law beside the consolidated one.
--
-- They are NOT copies: 0036 (byte-identical), 0054 (partial copy), 0062 (same text, page furniture only) and
-- expression source variants (docs/EXPRESSION-SOURCE-VARIANTS.md: "an actual amended/consolidated version ... is
-- refused") all reject them, correctly. Owner decision, 12 Nov 2026 (chat, option "Link; serve consolidated
-- (Recommended)"): keep both released and citable, link each reviewed pair, and let operative_provision serve only
-- the consolidated text.
--
-- WHAT A ROW SAYS. The as-made expression (observation, ordinal) is the original text of the law whose consolidated
-- text is the twin expression. Keyed by sources (as 0054/0062/0066/0067/0070), so a replay does not orphan it. One
-- twin per as-made expression; latest row wins; withdrawal is a later row with assertion 'withdrawn'.
--
-- GUARDS (trigger): append-only; both observations landed and different; a recorded link resolves on both sides to an
-- active canonical instrument of the SAME jurisdiction, kind and year; no chains (a consolidated text is never itself
-- as-made of another standing link, and an as-made text is never anyone's consolidated twin).
--
-- operative_provision (0071) is redefined with one more filter: an instrument that is the as-made side of a standing
-- link is not operative. Its columns are unchanged. The as-made text stays in v_release_instrument / v_release_provision
-- and can still be cited as the original text; v_consolidated_twin_current names its consolidated twin.
--
-- REVERSAL: restore 0071's view body, then drop the view, triggers, function and table (irreversible once rows exist,
-- docs/03 §9). Governing contract: docs/03b §6.2 (operative view), INV-4, INV-5; owner decision 12 Nov 2026.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE consolidated_twin (
    id                              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    as_made_observation_id          bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    as_made_expression_ordinal      smallint NOT NULL CHECK (as_made_expression_ordinal >= 0),
    consolidated_observation_id     bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    consolidated_expression_ordinal smallint NOT NULL CHECK (consolidated_expression_ordinal >= 0),
    as_made_title                   text NOT NULL CHECK (btrim(as_made_title) <> ''),
    consolidated_title              text NOT NULL CHECK (btrim(consolidated_title) <> ''),
    basis                           text NOT NULL CHECK (basis IN ('same_title_number_year', 'same_title_year',
                                                                   'same_number_year_title_overlap')),
    assertion                       text NOT NULL CHECK (assertion IN ('recorded', 'withdrawn')),
    method                          text NOT NULL CHECK (btrim(method) <> ''),
    evidence                        jsonb NOT NULL CHECK (coalesce(jsonb_typeof(evidence) = 'object'
                                                           AND btrim(evidence->>'reviewer_type') <> ''
                                                           AND btrim(evidence->>'owner_decision') <> '', false)),
    recorded_by                     text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at                     timestamptz NOT NULL DEFAULT now(),
    CHECK (as_made_observation_id <> consolidated_observation_id)
);

CREATE INDEX consolidated_twin_key
    ON consolidated_twin (as_made_observation_id, as_made_expression_ordinal, recorded_at DESC, id DESC);

CREATE FUNCTION check_consolidated_twin() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    a instrument%ROWTYPE;
    c instrument%ROWTYPE;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'consolidated_twin is append-only';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext('consolidated_twin'));
    IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.as_made_observation_id AND outcome = 'landed')
       OR NOT EXISTS (SELECT 1 FROM source_observation
                       WHERE id = NEW.consolidated_observation_id AND outcome = 'landed') THEN
        RAISE EXCEPTION 'both observations must have landed';
    END IF;
    IF NEW.assertion = 'withdrawn' THEN
        RETURN NEW;
    END IF;
    SELECT * INTO a FROM instrument
     WHERE source_observation_id = NEW.as_made_observation_id AND expression_ordinal = NEW.as_made_expression_ordinal
       AND is_active AND duplicate_of IS NULL;
    SELECT * INTO c FROM instrument
     WHERE source_observation_id = NEW.consolidated_observation_id
       AND expression_ordinal = NEW.consolidated_expression_ordinal AND is_active AND duplicate_of IS NULL;
    IF a.id IS NULL OR c.id IS NULL THEN
        RAISE EXCEPTION 'both sides must resolve to an active canonical instrument';
    END IF;
    IF a.jurisdiction <> c.jurisdiction OR a.kind <> c.kind OR a.year IS DISTINCT FROM c.year THEN
        RAISE EXCEPTION 'as-made % and consolidated % differ in jurisdiction, kind or year', a.id, c.id;
    END IF;
    -- no chains, against the standing links
    IF EXISTS (SELECT 1 FROM (SELECT DISTINCT ON (as_made_observation_id, as_made_expression_ordinal) *
                                FROM consolidated_twin
                               ORDER BY as_made_observation_id, as_made_expression_ordinal, recorded_at DESC, id DESC) l
                WHERE l.assertion = 'recorded'
                  AND ((l.as_made_observation_id = NEW.consolidated_observation_id
                        AND l.as_made_expression_ordinal = NEW.consolidated_expression_ordinal)
                    OR (l.consolidated_observation_id = NEW.as_made_observation_id
                        AND l.consolidated_expression_ordinal = NEW.as_made_expression_ordinal))) THEN
        RAISE EXCEPTION 'a consolidated twin is never itself as-made, and an as-made text is never a twin';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER consolidated_twin_guard
BEFORE INSERT OR UPDATE OR DELETE ON consolidated_twin
FOR EACH ROW EXECUTE FUNCTION check_consolidated_twin();

CREATE TRIGGER consolidated_twin_no_truncate
BEFORE TRUNCATE ON consolidated_twin
FOR EACH STATEMENT EXECUTE FUNCTION check_consolidated_twin();

CREATE VIEW v_consolidated_twin_current AS
WITH latest AS (
    SELECT DISTINCT ON (as_made_observation_id, as_made_expression_ordinal) *
      FROM consolidated_twin
     ORDER BY as_made_observation_id, as_made_expression_ordinal, recorded_at DESC, id DESC)
SELECT l.*, a.id AS as_made_instrument_id, c.id AS consolidated_instrument_id
  FROM latest l
  JOIN instrument a ON a.source_observation_id = l.as_made_observation_id
                   AND a.expression_ordinal = l.as_made_expression_ordinal AND a.is_active AND a.duplicate_of IS NULL
  JOIN instrument c ON c.source_observation_id = l.consolidated_observation_id
                   AND c.expression_ordinal = l.consolidated_expression_ordinal AND c.is_active
                   AND c.duplicate_of IS NULL
 WHERE l.assertion = 'recorded';

COMMENT ON TABLE consolidated_twin IS
  'Append-only: an expression''s text as made (original Gazette issue) linked to the consolidated text of the same '
  'law. operative_provision serves the consolidated text only. Owner decision 12 Nov 2026. Migration 0075.';

-- operative_provision: 0071's body plus one filter (the as-made side of a standing link is not operative)
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
       i.status::text                         AS instrument_status,
       i.enacted_on,
       i.commenced_on,
       i.repealed_on,
       i.repealed_by_id,
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
 WHERE (h.instrument_id IS NULL OR h.historical_validity @> nzq_as_of())
   AND (i.enacted_on IS NULL OR i.enacted_on <= nzq_as_of())
   AND (i.year IS NULL OR i.year <= extract(year FROM nzq_as_of()))
   AND (i.commenced_on IS NULL OR i.commenced_on <= nzq_as_of())
   AND NOT (i.status = 'repealed' AND i.repealed_on <= nzq_as_of())
   AND (nzq_territory() IS NULL OR i.jurisdiction::text = 'fed' OR i.jurisdiction::text = nzq_territory())
   AND NOT EXISTS (SELECT 1 FROM v_consolidated_twin_current t WHERE t.as_made_instrument_id = i.id);

COMMIT;
