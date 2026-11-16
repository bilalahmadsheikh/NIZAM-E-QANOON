-- How far back the held text of each provision is known to have been the law (INV-5 before capture).
--
-- Found 16 Nov 2026 (golden set 3): every provision_version is written daterange(<source observation date>, NULL)
-- (docs/SCHEMA.md, provision_version), so operative_provision served nothing at an as_of before capture (June-October
-- 2026): "the law of Punjab on 1 June 2020" had no answer, though the Punjab text of the Child Marriage Restraint Act,
-- 1929 held then was the law in force then.
--
-- The held text is the consolidated text AS AT CAPTURE. It was also the law at an earlier date D exactly when no
-- amendment of it took effect after D. So for each provision this derives TEXT_KNOWN_FROM, the latest of:
--   * the law's own start: commencement, else enactment, else 31 December of its year (never earlier than it existed);
--   * every amendment footnote (amendment_reference, migrations 0071/0084) of the law that has no target provision;
--   * every amendment footnote aimed at the provision, an ancestor or a descendant (a change to a subsection is a
--     change to the section's text);
--   * every '(... Amendment) Act/Ordinance/Order' the corpus holds whose title names the law (same jurisdiction, the
--     law's year not later than the amendment's): the amendment is evidence even where no footnote records it.
-- An amendment's date is its recorded effective_from, else the amending law's commencement or enactment, else 31
-- December of its year, of the cited year, or of the latest year printed in the footnote. 'Rep./Subs. by this Act' is
-- the law's own act and adds nothing. A footnote with NO recoverable date ('ibid', an undated notification) leaves the
-- provision unknown before capture: text_known_from is NULL and nothing changes for it.
--
-- operative_provision then also serves the open-ended version of a provision at an as_of in [text_known_from, start of
-- the version), when that version is the provision's only one. Every other test (enactment, commencement, repeal,
-- lapse, currency cut-off, territory, territorial exits) still applies, so a law not yet made is still not served.
-- What this cannot see: an amendment no footnote records and no held '(Amendment)' law names. The rule errs late, never
-- early, where it can.
--
-- mv_provision_text_known_from is refreshed with mv_instrument_serving (tools/refresh_serving.py); audit A16 counts a
-- served provision with no row as stale.
--
-- REVERSAL: re-create 0095's operative_provision; drop mv_provision_text_known_from and the functions.
-- Governing contract: INV-5, docs/03 §2 (provision_version validity), docs/04 (as_of); migrations 0071, 0084, 0094, 0095.

BEGIN;

SET LOCAL lock_timeout = '10s';

-- A materialized view is built and refreshed under a restricted search_path, so a SQL function whose body calls
-- another of ours unqualified (is_number_citation -> is_bare_citation, 0080) fails there. Every function of ours that
-- does not pin its search_path is given the one it always ran under. Behaviour is unchanged.
DO $$
DECLARE f record;
BEGIN
    FOR f IN SELECT p.oid::regprocedure AS sig
               FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
              WHERE n.nspname = 'public' AND p.prokind = 'f'
                AND p.prolang IN (SELECT oid FROM pg_language WHERE lanname IN ('sql', 'plpgsql'))
                AND NOT EXISTS (SELECT 1 FROM unnest(coalesce(p.proconfig, '{}')) c WHERE c LIKE 'search_path=%')
                AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
    LOOP
        EXECUTE format('ALTER FUNCTION %s SET search_path = public, pg_temp', f.sig);
    END LOOP;
END $$;

-- a title folded for matching an amendment law to the law it amends (the SQL twin of record_statutory_repeals.norm)
CREATE FUNCTION nzq_title_key(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT btrim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(t, '')),
               '\d{1,2}\[|[\[\]]', '', 'g'),                         -- footnote markers
               ',?\s*(1[89]\d\d|20\d\d)\s*\.?\s*$', ''),             -- trailing year
               '^the\s+', ''),
               '\msind\M', 'sindh', 'g'),
               '[^a-z0-9]+', ' ', 'g'))
$$;

-- the latest year printed in a footnote, as 31 December of it
CREATE FUNCTION nzq_footnote_year_end(t text) RETURNS date
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT make_date(max(m[1]::int), 12, 31)
      FROM regexp_matches(coalesce(t, ''), '\m(1[89]\d\d|20\d\d)\M', 'g') AS x(m)
$$;

CREATE MATERIALIZED VIEW mv_provision_text_known_from AS
WITH law AS (
    SELECT m.instrument_id, i.jurisdiction::text AS jur, i.year,
           nzq_title_key(coalesce(i.display_title, i.short_title)) AS tkey,
           coalesce(i.commenced_on, i.enacted_on, make_date(i.year, 12, 31)) AS starts
      FROM mv_instrument_serving m JOIN instrument i ON i.id = m.instrument_id),
amendment_law AS (                  -- held '(... Amendment)' laws, by the title of the law they amend
    SELECT a.jurisdiction::text AS jur, a.year,
           nzq_title_key(regexp_replace(coalesce(a.display_title, a.short_title),
                                        '\s*\((?:[^()]*\s)?amendments?\)\s*', ' ', 'i')) AS base_key,
           coalesce(a.commenced_on, a.enacted_on, make_date(a.year, 12, 31)) AS on_date
      FROM v_release_instrument a
     WHERE coalesce(a.display_title, a.short_title) ~* '\((?:[^()]*\s)?amendments?\)'),
by_title AS (
    SELECT l.instrument_id, max(al.on_date) AS d
      FROM law l JOIN amendment_law al ON al.jur = l.jur AND al.base_key = l.tkey AND al.base_key <> ''
                                       AND (l.year IS NULL OR al.year IS NULL OR l.year <= al.year)
     GROUP BY l.instrument_id),
ref AS (
    SELECT r.amended_instrument_id AS instrument_id, r.target_provision_id,
           (r.footnote_text ~* '\mby\s+this\s+(act|ordinance|order|regulation)\M') AS own_act,
           coalesce(r.effective_from, am.commenced_on, am.enacted_on, make_date(am.year, 12, 31),
                    make_date(r.cited_year, 12, 31), nzq_footnote_year_end(r.footnote_text)) AS d
      FROM v_amendment_reference_current r
      LEFT JOIN instrument am ON am.id = r.amending_instrument_id
     WHERE r.assertion IS DISTINCT FROM 'withdrawn'),
law_refs AS (
    SELECT instrument_id, max(d) AS d, bool_or(d IS NULL AND NOT own_act) AS undatable
      FROM ref WHERE target_provision_id IS NULL GROUP BY instrument_id),
prov_refs AS (                      -- a footnote reaches the target, its ancestors and its descendants
    SELECT q.id AS provision_id, max(r.d) AS d, bool_or(r.d IS NULL AND NOT r.own_act) AS undatable
      FROM ref r
      JOIN provision t ON t.id = r.target_provision_id
      JOIN provision q ON q.instrument_id = t.instrument_id AND q.is_active
                      AND (q.path <@ t.path OR q.path @> t.path)
     GROUP BY q.id),
one_version AS (
    SELECT v.provision_id, min(v.id::text)::uuid AS version_id, bool_and(upper_inf(v.validity)) AS open_ended,
           min(lower(v.validity)) AS version_from
      FROM provision_version v
      JOIN provision p ON p.id = v.provision_id AND p.is_active
      JOIN law l ON l.instrument_id = p.instrument_id
     GROUP BY v.provision_id HAVING count(*) = 1)
SELECT p.id AS provision_id, p.instrument_id,
       CASE WHEN l.starts IS NULL OR coalesce(lr.undatable, false) OR coalesce(pr.undatable, false)
                 OR ov.provision_id IS NULL OR NOT ov.open_ended THEN NULL
            ELSE least(ov.version_from, greatest(l.starts, lr.d, pr.d, bt.d)) END AS text_known_from,
       CASE WHEN l.starts IS NULL THEN 'law_start_unknown'
            WHEN coalesce(lr.undatable, false) OR coalesce(pr.undatable, false) THEN 'an_amendment_is_undated'
            WHEN ov.provision_id IS NULL OR NOT ov.open_ended THEN 'not_a_single_open_version'
            WHEN greatest(lr.d, pr.d, bt.d) IS NULL THEN 'no_amendment_recorded'
            ELSE 'after_latest_recorded_amendment' END AS basis
  FROM law l
  JOIN provision p ON p.instrument_id = l.instrument_id AND p.is_active
  LEFT JOIN one_version ov ON ov.provision_id = p.id
  LEFT JOIN law_refs lr ON lr.instrument_id = l.instrument_id
  LEFT JOIN prov_refs pr ON pr.provision_id = p.id
  LEFT JOIN by_title bt ON bt.instrument_id = l.instrument_id;

CREATE UNIQUE INDEX mv_provision_text_known_from_pk ON mv_provision_text_known_from (provision_id);

COMMENT ON MATERIALIZED VIEW mv_provision_text_known_from IS
  'Per active provision of a served law: the earliest date its held (consolidated-at-capture) text is known to have '
  'been the law -- the law''s start or its latest dated amendment, whichever is later; NULL when unknown. '
  'operative_provision serves the open version back to it. Refreshed by tools/refresh_serving.py. Migration 0096.';

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
   AND NOT (nzq_territory() IS NOT NULL AND m.territory_exits ? nzq_territory()
            AND (m.territory_exits ->> nzq_territory())::date <= nzq_as_of());

DO $$
BEGIN
    IF nzq_title_key('The Punjab Defamation Act, 2024') <> 'punjab defamation act'
       OR nzq_title_key('Child Marriage Restraint (Amendment) Act, 2015') <> 'child marriage restraint amendment act'
       OR nzq_footnote_year_end('Subs. by A. O., 1964, Art. 2 and Sch.') <> DATE '1964-12-31'
       OR nzq_footnote_year_end('ibid') IS NOT NULL THEN
        RAISE EXCEPTION '0096: title key or footnote year misread';
    END IF;
END $$;

COMMIT;
