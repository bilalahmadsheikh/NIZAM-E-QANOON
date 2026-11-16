-- text_known_from (0096) also reads the amendment markers printed in the provision's own text.
--
-- Measured right after 0096 (16 Nov 2026): 885,465 provisions of 9,135 laws had no amendment footnote recorded and
-- were dated back to their law's start -- among them the Punjab text of the Child Marriage Restraint Act, 1929 s.4,
-- whose punishment ("six months and fine of fifty thousand rupees.]") is a later Punjab amendment, and the federal
-- Muslim Family Laws Ordinance, 1961 s.7 ("2[:] that where the parties belong to Fiqah-e-Jafria ..."). No footnote
-- reference was parsed for either, but the consolidated text marks each change where it stands: an opening
-- 'N[' / closing ']' pair for words inserted or substituted, 'N* * *' for words omitted. So "no amendment recorded"
-- did not mean "not amended".
--
-- Now a provision whose OWN text carries more amendment markers than there are dated amendment references aimed at it
-- is unknown before capture (basis 'amended_text_undated'): the marks prove it changed, and nothing dates every
-- change. A provision with no marker and no reference keeps its law's start; one whose every marker has a dated
-- reference keeps the latest of them. Markers counted: max(opening 'N[', closing ']') + 'N* * *' omissions.
-- Everything else in 0096 stands.
--
-- REVERSAL: re-create 0096's mv_provision_text_known_from and operative_provision.
-- Governing contract: INV-5; migrations 0096, 0071, 0084.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE FUNCTION nzq_amendment_marks(t text) RETURNS integer
LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = public, pg_temp AS $$
    SELECT greatest((SELECT count(*) FROM regexp_matches(coalesce(t, ''), '\d{1,2}\s*\[', 'g')),
                    (SELECT count(*) FROM regexp_matches(coalesce(t, ''), '\]', 'g')))::int
         + (SELECT count(*) FROM regexp_matches(coalesce(t, ''), '\d{1,2}\s*\*\s*\*\s*\*', 'g'))::int
$$;

DROP VIEW operative_provision;
DROP MATERIALIZED VIEW mv_provision_text_known_from;

CREATE MATERIALIZED VIEW mv_provision_text_known_from AS
WITH law AS (
    SELECT m.instrument_id, i.jurisdiction::text AS jur, i.year,
           nzq_title_key(coalesce(i.display_title, i.short_title)) AS tkey,
           coalesce(i.commenced_on, i.enacted_on, make_date(i.year, 12, 31)) AS starts
      FROM mv_instrument_serving m JOIN instrument i ON i.id = m.instrument_id),
amendment_law AS (
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
prov_refs AS (
    SELECT q.id AS provision_id, max(r.d) AS d, bool_or(r.d IS NULL AND NOT r.own_act) AS undatable,
           count(*) FILTER (WHERE q.id = t.id AND r.d IS NOT NULL) AS own_dated
      FROM ref r
      JOIN provision t ON t.id = r.target_provision_id
      JOIN provision q ON q.instrument_id = t.instrument_id AND q.is_active
                      AND (q.path <@ t.path OR q.path @> t.path)
     GROUP BY q.id),
one_version AS (
    SELECT v.provision_id, bool_and(upper_inf(v.validity)) AS open_ended, min(lower(v.validity)) AS version_from,
           max(nzq_amendment_marks(concat_ws(' ', v.text_en, v.text_ur))) AS marks
      FROM provision_version v
      JOIN provision p ON p.id = v.provision_id AND p.is_active
      JOIN law l ON l.instrument_id = p.instrument_id
     GROUP BY v.provision_id HAVING count(*) = 1),
decided AS (
    SELECT p.id AS provision_id, p.instrument_id, l.starts, ov.provision_id IS NOT NULL AND ov.open_ended AS single,
           ov.version_from, coalesce(ov.marks, 0) AS marks, coalesce(pr.own_dated, 0) AS own_dated,
           coalesce(lr.undatable, false) OR coalesce(pr.undatable, false) AS undatable,
           greatest(lr.d, pr.d, bt.d) AS amended
      FROM law l
      JOIN provision p ON p.instrument_id = l.instrument_id AND p.is_active
      LEFT JOIN one_version ov ON ov.provision_id = p.id
      LEFT JOIN law_refs lr ON lr.instrument_id = l.instrument_id
      LEFT JOIN prov_refs pr ON pr.provision_id = p.id
      LEFT JOIN by_title bt ON bt.instrument_id = l.instrument_id)
SELECT provision_id, instrument_id,
       CASE WHEN starts IS NULL OR undatable OR NOT single OR marks > own_dated THEN NULL
            ELSE least(version_from, greatest(starts, amended)) END AS text_known_from,
       CASE WHEN starts IS NULL THEN 'law_start_unknown'
            WHEN undatable THEN 'an_amendment_is_undated'
            WHEN NOT single THEN 'not_a_single_open_version'
            WHEN marks > own_dated THEN 'amended_text_undated'
            WHEN amended IS NULL THEN 'no_amendment_recorded'
            ELSE 'after_latest_recorded_amendment' END AS basis
  FROM decided;

CREATE UNIQUE INDEX mv_provision_text_known_from_pk ON mv_provision_text_known_from (provision_id);

COMMENT ON MATERIALIZED VIEW mv_provision_text_known_from IS
  'Per active provision of a served law: the earliest date its held (consolidated-at-capture) text is known to have '
  'been the law -- the law''s start or its latest dated amendment; NULL when unknown, including where its own text '
  'carries more amendment markers than dated references. Refreshed by tools/refresh_serving.py. Migrations 0096, 0097.';

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
    IF nzq_amendment_marks('Punishment for marrying a child. If a person ... fine of fifty thousand rupees.]') <> 1
       OR nzq_amendment_marks('Talaq. (1) Any man ... to the wife 2[:] that where') <> 1
       OR nzq_amendment_marks('Interpretation clause In this Act___ 5* * * * * * *') <> 1
       OR nzq_amendment_marks('Whoever commits theft shall be punished') <> 0 THEN
        RAISE EXCEPTION '0097: amendment markers misread';
    END IF;
END $$;

COMMIT;
