-- text_known_from is decided per LAW, not per provision.
--
-- 0097 dated each provision separately. Read against the corpus the same day, that trusted one provision's marks too
-- far: the Punjab text of the Child Marriage Restraint Act, 1929 s.2 ("... if a female, is under sixteen years of
-- age") carries no surviving marker and was dated to 1930, although that age is itself an amendment (the original
-- text said fourteen); its s.4 carries an undated Punjab amendment. Where one provision of a text proves an amendment
-- the corpus cannot date, the other provisions' silence proves nothing about theirs.
--
-- So, per law:
--   * any provision whose own text carries more amendment markers than the dated amendment references aimed at it or
--     its ancestors or descendants, or any amendment reference with no recoverable date  -> the WHOLE law is unknown
--     before capture (basis 'an_amendment_is_undated');
--   * otherwise every provision is known from the latest of the law's start, its dated amendment references and the
--     held '(... Amendment)' laws naming it ('after_latest_recorded_amendment'), or from the law's start when there is
--     no evidence of amendment at all ('no_amendment_recorded');
--   * a provision that is not one open-ended version stays as it is ('not_a_single_open_version').
-- The residual risk, stated in docs/SCHEMA.md: a text that was amended but prints no marker, has no footnote and no
-- held amending law is served back to its start.
--
-- REVERSAL: re-create 0097's mv_provision_text_known_from and operative_provision.
-- Governing contract: INV-5; migrations 0096, 0097.

BEGIN;

SET LOCAL lock_timeout = '10s';

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
      FROM ref GROUP BY instrument_id),
family_dated AS (                   -- dated references aimed at a provision, its ancestors or its descendants
    SELECT q.id AS provision_id, count(*) AS n
      FROM ref r
      JOIN provision t ON t.id = r.target_provision_id
      JOIN provision q ON q.instrument_id = t.instrument_id AND q.is_active
                      AND (q.path <@ t.path OR q.path @> t.path)
     WHERE r.d IS NOT NULL
     GROUP BY q.id),
versions AS (
    SELECT v.provision_id, p.instrument_id, count(*) AS n, bool_and(upper_inf(v.validity)) AS open_ended,
           min(lower(v.validity)) AS version_from,
           max(nzq_amendment_marks(concat_ws(' ', v.text_en, v.text_ur))) AS marks
      FROM provision_version v
      JOIN provision p ON p.id = v.provision_id AND p.is_active
      JOIN law l ON l.instrument_id = p.instrument_id
     GROUP BY v.provision_id, p.instrument_id),
undated_marks AS (
    SELECT v.instrument_id, bool_or(v.marks > coalesce(f.n, 0)) AS any
      FROM versions v LEFT JOIN family_dated f ON f.provision_id = v.provision_id
     GROUP BY v.instrument_id),
law_decided AS (
    SELECT l.instrument_id, l.starts,
           coalesce(lr.undatable, false) OR coalesce(um.any, false) AS undated,
           greatest(lr.d, bt.d) AS amended
      FROM law l
      LEFT JOIN law_refs lr ON lr.instrument_id = l.instrument_id
      LEFT JOIN undated_marks um ON um.instrument_id = l.instrument_id
      LEFT JOIN by_title bt ON bt.instrument_id = l.instrument_id)
SELECT p.id AS provision_id, p.instrument_id,
       CASE WHEN d.starts IS NULL OR d.undated OR v.n IS DISTINCT FROM 1 OR NOT v.open_ended THEN NULL
            ELSE least(v.version_from, greatest(d.starts, d.amended)) END AS text_known_from,
       CASE WHEN d.starts IS NULL THEN 'law_start_unknown'
            WHEN d.undated THEN 'an_amendment_is_undated'
            WHEN v.n IS DISTINCT FROM 1 OR NOT v.open_ended THEN 'not_a_single_open_version'
            WHEN d.amended IS NULL THEN 'no_amendment_recorded'
            ELSE 'after_latest_recorded_amendment' END AS basis
  FROM law_decided d
  JOIN provision p ON p.instrument_id = d.instrument_id AND p.is_active
  LEFT JOIN versions v ON v.provision_id = p.id;

CREATE UNIQUE INDEX mv_provision_text_known_from_pk ON mv_provision_text_known_from (provision_id);

COMMENT ON MATERIALIZED VIEW mv_provision_text_known_from IS
  'Per active provision of a served law: the earliest date its held (consolidated-at-capture) text is known to have '
  'been the law, decided per law -- its start, or its latest dated amendment; NULL when any amendment of the law is '
  'undated (a footnote without a date, or more markers in a provision than dated references). Refreshed by '
  'tools/refresh_serving.py. Migrations 0096-0098.';

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

COMMIT;
