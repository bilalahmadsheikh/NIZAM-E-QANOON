-- operative_provision: the one view retrieval reads (INV-5; docs/03b §6.2), as built on the corpus that exists.
--
-- WHAT IT RETURNS. Every released provision whose text is valid at the session's as_of date, with the instrument
-- facts needed to cite it (INV-1: title, number, year, jurisdiction from records) and with three COVERAGE flags,
-- because docs/03b ('the two edges that cannot be extracted from statute text') requires an unknown to be declared,
-- never hidden.
--
--   SET nzq.as_of = '2026-11-11';          -- REQUIRED: reading the view without it raises (INV-5: as_of is not optional)
--   SET nzq.territory = 'punjab';          -- optional: punjab | sindh | kp | balochistan | ict
--   SELECT * FROM operative_provision WHERE instrument_id = ...;
--
-- A PROVISION IS EXCLUDED WHEN, AT as_of,
--   * its version is not valid (provision_version.validity does not contain as_of). Consolidated text is valid from
--     the date it was observed (2026), so a question about an earlier date finds no text and the caller abstains --
--     the corpus does not yet hold amendment history to reconstruct earlier wording; 0064 historical expressions
--     are the exception and are gated by their window;
--   * the instrument is a historical expression whose window does not contain as_of (0064);
--   * the instrument was not yet enacted (enacted_on > as_of, or year > the year of as_of);
--   * its ESTABLISHED commencement is after as_of (commenced_on > as_of);
--   * it was repealed on or before as_of (status 'repealed', repealed_on <= as_of; 0066);
--   * a territory is set and the instrument is neither federal nor of that territory.
--
-- AS BUILT -- where this departs from the docs/03b §6.2 sketch, and why:
--   * The sketch requires EXISTS(commencement row). No commencement table exists yet: commencement by notification
--     lives in the Gazette pipeline that has not landed. Requiring it would return nothing. Instead, instrument-level
--     commenced_on (0070, from the instrument's own self-executing text) excludes what has not yet commenced, and
--     commencement_coverage says 'established' or 'not_tracked' for every row. A client must show 'not_tracked'.
--   * The sketch filters invalidated_by edges. No judgment pipeline exists: invalidation_coverage = 'not_tracked'
--     on every row, as docs/03b's note prescribes ("the UI states that invalidation status is not yet tracked").
--   * The sketch filters an `extent` relation. Not built: the territorial filter uses jurisdiction only, and
--     extent_coverage = 'jurisdiction_default' says so. 'Extends to ... except' clauses are not yet read.
--   * The sketch joins i.published. The release gate is v_release_instrument (0036..0069); a released instrument is
--     the published one, so the view reads the release views and `published` is not consulted.
--   * Text language: provision_version.text_en carries every expression's text whatever its language; an Urdu or
--     Sindhi expression (instrument.text_language, measured, 0070) is returned in text_ur and never as English.
--   * An Ordinance linked to a later Act (0067, owner decision q6) stays operative -- status is not changed by that
--     link -- and carries superseded_by_instrument_id so it can be shown as replaced.
--
-- Governing contract: docs/03b §3 and §6.2; INV-1, INV-5; migrations 0064, 0066, 0067, 0069, 0070.
-- REVERSAL: drop the view and the two functions.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE FUNCTION nzq_as_of() RETURNS date
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v text := current_setting('nzq.as_of', true);
BEGIN
    IF v IS NULL OR btrim(v) = '' THEN
        RAISE EXCEPTION 'nzq.as_of is not set: every read of operative_provision is as at a date (INV-5)';
    END IF;
    RETURN v::date;
END $$;

CREATE FUNCTION nzq_territory() RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v text := nullif(btrim(coalesce(current_setting('nzq.territory', true), '')), '');
BEGIN
    IF v IS NOT NULL AND v NOT IN ('punjab', 'sindh', 'kp', 'balochistan', 'ict') THEN
        RAISE EXCEPTION 'nzq.territory % is not one of punjab, sindh, kp, balochistan, ict', v;
    END IF;
    RETURN v;
END $$;

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
   AND (nzq_territory() IS NULL OR i.jurisdiction::text = 'fed' OR i.jurisdiction::text = nzq_territory());

COMMENT ON VIEW operative_provision IS
  'The provisions in force at nzq.as_of (required) in nzq.territory (optional), with commencement / invalidation / '
  'extent coverage flags. Retrieval reads this view only (INV-5, docs/03b §6.2 as built). Migration 0071.';

COMMIT;
