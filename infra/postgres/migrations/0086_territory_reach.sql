-- Territorial reach: each province's law in its own province, federal law in every province and ICT -- and a text
-- filed 'fed' that is not federal law no longer served everywhere. AJK and GB can now be asked for: their own laws.
--
-- Owner rule (16 Nov 2026): "each provincial jurisdiction in their own provinces while federal is for all". 0071's
-- filter already served jurisdiction = territory OR 'fed'. Two defects remained:
--   * the corpus files under 'fed' texts that are not federal law of Pakistan (docs/SCHEMA.md, 'number series
--     collide'): West Pakistan Acts (law of the four provinces), Acts of one old province ('Karachi Cattle Slaughter
--     Control Act, 1950', 'Punjab ... Act'), Islamabad-only law, and Indian-era Acts for places outside Pakistan
--     ('The Oudh Courts Act, 1891', 'The Pegu and Sittang Canal Act, 1881', Bengal and East Pakistan law). Each was
--     served as federal law in every province;
--   * nzq_territory refused 'ajk' and 'gb'. A federal Act runs in AJK only as AJK law adapts it, and in GB only as
--     extended by notification (docs/SCHEMA.md, Territories): the accurate reach there is the territory's OWN law.
--     Serving federal law there would be a wrong answer; not serving it is an abstention (docs/04 §6).
-- territory_reach(jurisdiction, title) reads the territory a 'fed' text's own printed title names; otherwise federal
-- law reaches all four provinces and ICT. operative_provision reports which rule placed a row (extent_coverage:
-- 'own_territory', 'title_named_territory', 'jurisdiction_default'). Printed extent clauses ('extends to the whole of
-- Pakistan') are a later refinement (docs/03b §6 extent relation); this reads only what the title prints.
--
-- Note on 0085 (recorded here because an applied migration is never edited): the recorder's 'lapsed' rule was
-- narrowed the same day to Ordinances made under the CURRENT Art. 89/128 text -- an established promulgation date on
-- or after 2010-04-20, or a printed year 2011+. The 120/90-day wording was inserted by the Eighteenth Amendment (doc
-- 4419's footnotes: 'Ins. and subs. by the Constitution (Eighteenth Amendment) Act, 2010 ... s. 27'), commenced
-- 2010-04-20 (doc 4434), and the footnotes do not print the words it replaced, so the corpus states no rule for an
-- Ordinance of 2004-2010. 0085's comment ('2004 or later') describes the first, wider trial.
--
-- REVERSAL: restore 0071's nzq_territory and 0085's operative_provision; drop territory_reach.
-- Governing contract: docs/03b §6 (extent), docs/04 §6 (territory), INV-5; owner rule 16 Nov 2026.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE OR REPLACE FUNCTION nzq_territory() RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v text := nullif(btrim(coalesce(current_setting('nzq.territory', true), '')), '');
BEGIN
    IF v IS NOT NULL AND v NOT IN ('punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb') THEN
        RAISE EXCEPTION 'nzq.territory % is not one of punjab, sindh, kp, balochistan, ict, ajk, gb', v;
    END IF;
    RETURN v;
END $$;

CREATE FUNCTION territory_reach(jurisdiction text, title text) RETURNS text[]
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN jurisdiction <> 'fed' THEN ARRAY[jurisdiction]
        -- places outside Pakistan, or East Pakistan: no territory of Pakistan today
        WHEN coalesce(title, '') ~* ('\m(east\s+pakistan|bengal|madras|bihar|oudh|burma|pegu|rangoon|calcutta|assam|'
                                     'united\s+provinces|central\s+provinces|ajmer|coorg|orissa|'
                                     'north[\s-]+western\s+provinces|jhansi|dacca|dhaka|chittagong|delhi)\M')
             THEN ARRAY[]::text[]
        WHEN coalesce(title, '') ~* '\m(west\s+pakistan|w\.\s*p\.)'
             THEN ARRAY['punjab', 'sindh', 'kp', 'balochistan']
        WHEN coalesce(title, '') ~* '\m(islamabad|capital\s+territory|federal\s+capital)\M' THEN ARRAY['ict']
        WHEN coalesce(title, '') ~* '\m(sindh?|karachi|bombay|hyderabad)\M' THEN ARRAY['sindh']
        WHEN coalesce(title, '') ~* '\m(punjab|lahore)\M' THEN ARRAY['punjab']
        WHEN coalesce(title, '') ~* '\m(n\.?\s*-?\s*w\.?\s*f\.?\s*p|frontier|khyber|peshawar)' THEN ARRAY['kp']
        WHEN coalesce(title, '') ~* '\m(baluchistan|balochistan|quetta)\M' THEN ARRAY['balochistan']
        ELSE ARRAY['punjab', 'sindh', 'kp', 'balochistan', 'ict'] END
$$;

CREATE FUNCTION territory_reach_basis(jurisdiction text, title text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN jurisdiction <> 'fed' THEN 'own_territory'
                WHEN territory_reach(jurisdiction, title) = ARRAY['punjab', 'sindh', 'kp', 'balochistan', 'ict']
                THEN 'jurisdiction_default'
                ELSE 'title_named_territory' END
$$;

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
       CASE WHEN law.repealed_on IS NOT NULL THEN 'repealed' ELSE i.status::text END AS instrument_status,
       i.enacted_on,
       i.commenced_on,
       law.repealed_on,
       coalesce(law.repealed_by_id, i.repealed_by_id) AS repealed_by_id,
       s.superseding_instrument_id            AS superseded_by_instrument_id,
       i.source_url,
       i.document_id,
       CASE WHEN i.commenced_on IS NOT NULL THEN 'established' ELSE 'not_tracked' END AS commencement_coverage,
       'not_tracked'::text                    AS invalidation_coverage,
       territory_reach_basis(i.jurisdiction::text, coalesce(i.display_title, i.short_title)) AS extent_coverage,
       nzq_as_of()                            AS as_of
  FROM v_release_instrument i
  JOIN provision p ON p.instrument_id = i.id AND p.is_active
  JOIN provision_version v ON v.provision_id = p.id AND v.validity @> nzq_as_of()
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
 WHERE (h.instrument_id IS NULL OR h.historical_validity @> nzq_as_of())
   AND (i.enacted_on IS NULL OR i.enacted_on <= nzq_as_of())
   AND (i.year IS NULL OR i.year <= extract(year FROM nzq_as_of()))
   AND (i.commenced_on IS NULL OR i.commenced_on <= nzq_as_of())
   AND NOT (law.repealed_on IS NOT NULL AND law.repealed_on <= nzq_as_of())
   AND NOT (i.status = 'lapsed'
            AND ordinance_latest_lapse(i.jurisdiction::text, i.enacted_on, i.year) < nzq_as_of())
   -- 0086: provincial law in its own province; federal law where its title does not confine it
   AND (nzq_territory() IS NULL
        OR nzq_territory() = ANY (territory_reach(i.jurisdiction::text, coalesce(i.display_title, i.short_title))))
   AND NOT EXISTS (SELECT 1 FROM v_consolidated_twin_current t WHERE t.as_made_instrument_id = i.id);

DO $$
BEGIN
    IF territory_reach('punjab', 'Punjab Foo Act') <> ARRAY['punjab']
       OR territory_reach('fed', 'The Contract Act, 1872') <> ARRAY['punjab', 'sindh', 'kp', 'balochistan', 'ict']
       OR territory_reach('fed', 'The Oudh Courts Act, 1891') <> ARRAY[]::text[]
       OR territory_reach('fed', 'The West Pakistan Land Revenue Act, 1967') <> ARRAY['punjab', 'sindh', 'kp', 'balochistan']
       OR territory_reach('fed', 'The Karachi Cattle Slaughter Control Act, 1950') <> ARRAY['sindh']
       OR territory_reach('fed', 'Islamabad Capital Territory Local Government Act, 2015') <> ARRAY['ict']
       OR territory_reach('ajk', 'The Azad Jammu and Kashmir Foo Act') <> ARRAY['ajk'] THEN
        RAISE EXCEPTION '0086: territory_reach misplaces a law';
    END IF;
END $$;

COMMIT;
