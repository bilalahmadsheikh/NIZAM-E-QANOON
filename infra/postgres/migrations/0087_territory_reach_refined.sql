-- territory_reach reads five more things, found by reading every 'fed' text 0086 placed outside the default (16 Nov
-- 2026). 0086 is applied and is not edited; this replaces its function and passes the source URL from the view.
--   1. 'Frontier Corps' / 'Frontier Constabulary' are federal forces, not law of the Frontier Province: default reach
--      (2998 Frontier Corps Ordinance, 1959; 6372 Frontier Constabulary (Re-organization) Ordinance, 2025).
--   2. A title naming two provinces reaches both: 'The Balochistan and Sindh (High Courts) Order, 1976' (7680).
--   3. A federal charter of an institution in a city is federal law everywhere, as is a notification that only names
--      a body there: 'Dawood College ... Karachi Act, 2010' (3274), 'Lahore University of Management Sciences Order,
--      1985' (9161), 'Central Board of Revenue Notification S.R.O. ... Karachi' (9690). A city confines only a law of
--      that city (rent, municipal, courts, port, police).
--   4. 'Ex-Employees of the Former Government of East Pakistan (Appointment to Federal Posts) Ordinance, 1983'
--      (1662) is a law of Pakistan about those people: default reach.
--   5. A text Pakistan Code publishes (pakistancode.gov.pk, the official consolidation of the laws of Pakistan) is
--      never placed nowhere: the consolidator's publishing it as current law outweighs a place named in its title.
--      Its title may still confine it to a province or ICT.
-- REVERSAL: re-create 0086's territory_reach / territory_reach_basis and operative_provision.
-- Governing contract: docs/03b Â§6 (extent), docs/04 Â§6; owner rule 16 Nov 2026; migration 0086.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE OR REPLACE FUNCTION territory_reach3(jurisdiction text, title text, source_url text) RETURNS text[]
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    t text := coalesce(title, '');
    all5 constant text[] := ARRAY['punjab', 'sindh', 'kp', 'balochistan', 'ict'];
    r text[] := ARRAY[]::text[];
    institution boolean := t ~* '\m(university|college|institute|academy|school|notification|s\.\s*r\.\s*o)';
BEGIN
    IF jurisdiction <> 'fed' THEN
        RETURN ARRAY[jurisdiction];
    END IF;
    IF t ~* '\mfrontier\s+(corps|constabulary)\M' OR t ~* '\m(ex-|former)\s*(employees\s+of\s+the\s+)?(former\s+)?government\s+of\s+east\s+pakistan' THEN
        RETURN all5;
    END IF;
    IF t ~* ('\m(east\s+pakistan|bengal|madras|bihar|oudh|burma|pegu|rangoon|calcutta|assam|'
             'united\s+provinces|central\s+provinces|ajmer|coorg|orissa|'
             'north[\s-]+western\s+provinces|jhansi|dacca|dhaka|chittagong|delhi)\M') THEN
        RETURN CASE WHEN coalesce(source_url, '') ~* 'pakistancode\.gov\.pk' THEN all5 ELSE ARRAY[]::text[] END;
    END IF;
    IF t ~* '\m(west\s+pakistan|w\.\s*p\.)' THEN
        RETURN ARRAY['punjab', 'sindh', 'kp', 'balochistan'];
    END IF;
    IF t ~* '\m(islamabad|capital\s+territory|federal\s+capital)\M' AND NOT institution THEN
        RETURN ARRAY['ict'];
    END IF;
    IF t ~* '\msindh?\M' OR (NOT institution AND t ~* '\m(karachi|bombay|hyderabad)\M') THEN
        r := array_append(r, 'sindh');
    END IF;
    IF t ~* '\mpunjab' OR (NOT institution AND t ~* '\mlahore\M') THEN
        r := array_append(r, 'punjab');
    END IF;
    IF t ~* '\m(n\.?\s*-?\s*w\.?\s*f\.?\s*p|north[\s-]+west\s+frontier|khyber)' OR (NOT institution AND t ~* '\mpeshawar\M') THEN
        r := array_append(r, 'kp');
    END IF;
    IF t ~* '\m(baluchistan|balochistan)\M' OR (NOT institution AND t ~* '\mquetta\M') THEN
        r := array_append(r, 'balochistan');
    END IF;
    RETURN CASE WHEN cardinality(r) = 0 THEN all5 ELSE r END;
END $$;

CREATE OR REPLACE FUNCTION territory_reach_basis3(jurisdiction text, title text, source_url text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN jurisdiction <> 'fed' THEN 'own_territory'
                WHEN territory_reach3(jurisdiction, title, source_url) = ARRAY['punjab', 'sindh', 'kp', 'balochistan', 'ict']
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
       territory_reach_basis3(i.jurisdiction::text, coalesce(i.display_title, i.short_title), i.source_url)
                                              AS extent_coverage,
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
   AND (nzq_territory() IS NULL
        OR nzq_territory() = ANY (territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                                   i.source_url)))
   AND NOT EXISTS (SELECT 1 FROM v_consolidated_twin_current t WHERE t.as_made_instrument_id = i.id);

DROP FUNCTION territory_reach_basis(text, text);
DROP FUNCTION territory_reach(text, text);

DO $$
DECLARE all5 constant text[] := ARRAY['punjab', 'sindh', 'kp', 'balochistan', 'ict'];
BEGIN
    IF territory_reach3('fed', 'Frontier Corps Ordinance, 1959', NULL) <> all5
       OR territory_reach3('fed', 'The Balochistan and Sindh (High Courts) Order, 1976', NULL) <> ARRAY['sindh', 'balochistan']
       OR territory_reach3('fed', 'Degree Awarding Status to Dawood College of Engineering and Technology, Karachi Act, 2010', NULL) <> all5
       OR territory_reach3('fed', 'Ex-Employees of the Former Government of East Pakistan (Appointment to Federal Posts) Ordinance, 1983', NULL) <> all5
       OR territory_reach3('fed', 'The Bengal State Prisoners Regulation, 1818', 'https://pakistancode.gov.pk/pdffiles/x.pdf') <> all5
       OR territory_reach3('fed', 'The Oudh Courts Act, 1891', 'https://drs.molaw.gov.pk/pdf/x.pdf') <> ARRAY[]::text[]
       OR territory_reach3('fed', 'The Karachi Rent Restriction Act, 1953', NULL) <> ARRAY['sindh']
       OR territory_reach3('fed', 'The Contract Act, 1872', NULL) <> all5
       OR territory_reach3('punjab', 'Punjab Foo Act', NULL) <> ARRAY['punjab'] THEN
        RAISE EXCEPTION '0087: territory_reach3 misplaces a law';
    END IF;
END $$;

COMMIT;
