-- Where the corpus actually stands, as percentages.
--
--     ./nz state
--
-- `./nz audit` answers "is it sound" -- pass or fail against a stated threshold.
-- This answers the different question "how far along is it", which has no
-- threshold and is a percentage. Both are needed: a corpus can be 100% sound and
-- 40% complete, and reporting either number alone is misleading.

SET paradedb.planner_warnings = 'off';
\pset border 2

-- Current-state reporting must not count retired append-only revisions.  These
-- temporary views deliberately keep the historical base tables untouched.
CREATE TEMP VIEW audit_document AS
SELECT * FROM document WHERE is_active;
CREATE TEMP VIEW audit_instrument AS
SELECT * FROM instrument WHERE is_active;
CREATE TEMP VIEW audit_provision AS
SELECT p.* FROM provision p JOIN audit_instrument i ON i.id=p.instrument_id;
CREATE TEMP VIEW audit_assignment AS
SELECT * FROM block_assignment_set WHERE is_active;
CREATE TEMP VIEW audit_provision_block AS
SELECT pb.* FROM provision_block pb
JOIN audit_assignment s ON s.id=pb.assignment_set_id;

\echo ''
\echo '════════ 1. ACQUISITION -- what came off the portals'
WITH a AS (
  SELECT count(*) FILTER (WHERE outcome='landed') AS landed,
         count(*) FILTER (WHERE outcome<>'landed' AND NOT EXISTS (
           SELECT 1 FROM acquisition_attempt x
            WHERE x.source_observation_id=o.id AND x.outcome='recovered')) AS unresolved
    FROM source_observation o)
SELECT landed + unresolved                                        AS catalog_items,
       landed,
       count(DISTINCT sha256) FILTER (WHERE outcome = 'landed')   AS distinct_files,
       (SELECT count(*) FROM blob)                                AS blobs,
       unresolved,
       round(100.0 * landed / (landed + unresolved), 2)           AS pct_landed
  FROM source_observation CROSS JOIN a
 GROUP BY landed,unresolved;

\echo ''
\echo '════════ 2. EXTRACTION -- bytes to text'
SELECT (SELECT count(*) FROM blob)                                AS files,
       count(*)                                                   AS extracted,
       round(100.0 * count(*) / (SELECT count(*) FROM blob), 2)   AS pct,
       sum(page_count)                                            AS pages,
       sum(char_count)                                            AS characters,
       count(*) FILTER (WHERE lane = 'E2')                        AS born_digital,
       count(*) FILTER (WHERE lane = 'E3')                        AS mixed,
       count(*) FILTER (WHERE lane = 'E4')                        AS ocr
  FROM audit_document;

\echo ''
\echo '════════ 3. SEGMENTATION -- text to a provision tree'
WITH last_run AS (
  SELECT DISTINCT ON (r.source_observation_id) r.document_id, r.outcome, r.toc_found, r.toc_agreement
    FROM segmentation_run r JOIN audit_document d ON d.id=r.document_id
   ORDER BY r.source_observation_id, r.run_at DESC,r.id DESC)
SELECT count(*)                                                   AS documents,
       count(*) FILTER (WHERE outcome = 'segmented')              AS segmented,
       round(100.0 * count(*) FILTER (WHERE outcome = 'segmented')
             / count(*), 2)                                       AS pct_segmented,
       count(*) FILTER (WHERE outcome <> 'segmented')             AS unstructured,
       (SELECT count(*) FROM audit_instrument)                    AS instruments,
       (SELECT count(*) FROM audit_provision)                     AS provisions,
       (SELECT count(*) FROM provision_version v JOIN audit_provision p ON p.id=v.provision_id) AS versions
  FROM last_run;

\echo ''
\echo '-- the tree, by kind'
SELECT kind::text,
       count(*)                                                   AS provisions,
       round(100.0 * count(*) / (SELECT count(*) FROM audit_provision), 2) AS pct,
       count(*) FILTER (WHERE heading IS NOT NULL)                AS with_heading
  FROM audit_provision GROUP BY kind ORDER BY 2 DESC;

\echo ''
\echo '════════ 4. TEXT COVERAGE -- how much of the corpus is inside the tree'
SELECT role::text,
       count(*)                                                   AS blocks,
       sum(chars)                                                 AS characters,
       round(100.0 * sum(chars) / (SELECT sum(chars) FROM audit_provision_block), 2) AS pct
  FROM audit_provision_block GROUP BY role ORDER BY 3 DESC;

\echo ''
\echo '-- the three numbers that matter'
SELECT round(100.0 * sum(chars) FILTER (WHERE role IN ('body','heading','schedule_row','preamble'))
             / sum(chars), 2)                                     AS pct_in_provision_tree,
       round(100.0 * sum(chars) FILTER (WHERE role IN ('contents','preface','running_header','footnote'))
             / sum(chars), 2)                                     AS pct_apparatus,
       round(100.0 * sum(chars) FILTER (WHERE role IN ('unstructured','unassigned'))
             / sum(chars), 4)                                     AS pct_unplaced
  FROM audit_provision_block;

\echo ''
\echo '════════ 5. SEGMENTATION CORRECTNESS -- against the document''s own contents list'
WITH last_run AS (
  SELECT DISTINCT ON (r.source_observation_id) r.* FROM segmentation_run r
   JOIN audit_document d ON d.id=r.document_id
   ORDER BY r.source_observation_id, r.run_at DESC,r.id DESC)
SELECT count(*) FILTER (WHERE toc_found)                          AS documents_with_contents,
       round(100.0 * count(*) FILTER (WHERE toc_found) / count(*), 1) AS pct_of_corpus,
       round(avg(toc_agreement), 4)                               AS mean_agreement,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY toc_agreement)::numeric, 4) AS median,
       sum(toc_matched)                                           AS sections_matched,
       sum(toc_missing)                                           AS promised_not_found,
       sum(toc_extra)                                             AS found_not_promised
  FROM last_run;

\echo ''
\echo '-- the distribution: how many documents parse how well'
WITH last_run AS (
  SELECT DISTINCT ON (r.source_observation_id) r.* FROM segmentation_run r
   JOIN audit_document d ON d.id=r.document_id
   ORDER BY r.source_observation_id, r.run_at DESC,r.id DESC),
t AS (SELECT toc_agreement a FROM last_run WHERE toc_found)
SELECT band, n, round(100.0 * n / (SELECT count(*) FROM t), 1) AS pct
  FROM (
    SELECT '1.00  exact'          AS band, count(*) n, 1 o FROM t WHERE a >= 1.0
    UNION ALL SELECT '0.99+',  count(*), 2 FROM t WHERE a >= 0.99 AND a < 1.0
    UNION ALL SELECT '0.95-0.99', count(*), 3 FROM t WHERE a >= 0.95 AND a < 0.99
    UNION ALL SELECT '0.90-0.95', count(*), 4 FROM t WHERE a >= 0.90 AND a < 0.95
    UNION ALL SELECT '0.50-0.90', count(*), 5 FROM t WHERE a >= 0.50 AND a < 0.90
    UNION ALL SELECT 'below 0.50  REVIEW', count(*), 6 FROM t WHERE a < 0.50
  ) x ORDER BY o;

\echo ''
\echo '════════ 6. INDEPENDENT QUALITY EVIDENCE'
\echo '-- verifier evidence; review/unverifiable are deliberately not passes'
SELECT overall_outcome,count(*) AS documents,
       round(100.0*count(*)/(SELECT count(*) FROM v_document_quality_status),2) AS pct
  FROM v_document_quality_status GROUP BY overall_outcome ORDER BY overall_outcome;

\echo ''
\echo '-- citation-label ambiguity after segmentation'
WITH ambiguous AS (
  SELECT DISTINCT instrument_id FROM (
    SELECT p.instrument_id,p.parent_id,p.kind,p.label FROM audit_provision p
     WHERE p.kind IN ('section','article')
     GROUP BY p.instrument_id,p.parent_id,p.kind,p.label HAVING count(*)>1) x)
SELECT (SELECT count(*) FROM audit_instrument) AS instruments,
       count(*) AS ambiguous,
       (SELECT count(*) FROM audit_instrument)-count(*) AS unambiguous,
       round(100.0*((SELECT count(*) FROM audit_instrument)-count(*))
             /(SELECT count(*) FROM audit_instrument),2) AS pct_unambiguous
  FROM ambiguous;

\echo '-- item-level structural decisions; aggregate run counters are diagnostic only'
SELECT (SELECT count(*) FROM v_active_structural_candidate) AS active_candidates,
       (SELECT count(*) FROM v_active_structural_candidate c
         WHERE EXISTS (
           SELECT 1 FROM v_structural_adjudication_latest a
            WHERE a.candidate_id=c.id)) AS adjudicated,
       (SELECT count(*) FROM v_structural_adjudication_pending) AS pending,
       (SELECT count(DISTINCT source_observation_id)
          FROM v_structural_adjudication_pending) AS pending_observations;

\echo '-- every active aggregate decision must have an exact item-level candidate'
WITH lr AS (
  -- One source observation may now materialize several legal expressions.
  -- Compare each active canonical instrument's own latest run, exactly as the
  -- acceptance audit does; collapsing by observation under-counts S10 splits.
  SELECT DISTINCT ON (r.instrument_id) r.instrument_id,r.source_observation_id,r.detail
    FROM segmentation_run r
    JOIN instrument i ON i.id=r.instrument_id
                     AND i.is_active
                     AND i.duplicate_of IS NULL
   ORDER BY r.instrument_id,r.run_at DESC,r.id DESC),
expected AS (
  SELECT coalesce(sum((detail->>'repeated_labels_demoted')::integer),0) n FROM lr),
actual AS (
  SELECT count(*) n FROM v_active_structural_candidate)
SELECT expected.n AS expected_candidates, actual.n AS itemized_candidates,
       abs(expected.n-actual.n) AS mismatch
  FROM expected CROSS JOIN actual;

\echo '-- application-safe legal release scope'
SELECT (SELECT count(*) FROM v_release_instrument) AS instruments,
       (SELECT count(*) FROM v_release_provision) AS provisions,
       (SELECT count(*) FROM v_release_provision_version) AS versions;

\echo '-- source-evidenced multi-instrument boundaries (blocking until split or disproved)'
SELECT count(*) AS pending_boundaries,
       count(DISTINCT source_observation_id) AS observations,
       count(DISTINCT document_id) AS documents
  FROM v_boundary_adjudication_pending;

\echo ''
\echo '════════ 7. BY JURISDICTION'
SELECT i.jurisdiction::text,
       count(DISTINCT i.id)                                       AS instruments,
       count(p.id)                                                AS provisions,
       count(p.id) FILTER (WHERE p.kind = 'section')              AS sections,
       round(avg(r.toc_agreement), 4)                             AS mean_toc
  FROM audit_instrument i
  LEFT JOIN audit_provision p ON p.instrument_id = i.id
  LEFT JOIN LATERAL (SELECT toc_agreement FROM segmentation_run s
                      WHERE s.instrument_id = i.id AND s.toc_found
                      ORDER BY s.run_at DESC LIMIT 1) r ON true
 GROUP BY i.jurisdiction ORDER BY 3 DESC;

\echo ''
\echo '════════ 8. BY INSTRUMENT TYPE'
SELECT kind::text AS instrument_kind, count(*) AS instruments,
       round(100.0 * count(*) / (SELECT count(*) FROM audit_instrument), 1) AS pct
  FROM audit_instrument GROUP BY kind ORDER BY 2 DESC;

\echo ''
\echo '════════ 9. THE TEN LARGEST INSTRUMENTS'
SELECT left(i.short_title, 46) AS instrument, i.jurisdiction::text AS jur, i.year,
       count(p.id) AS provisions,
       count(p.id) FILTER (WHERE p.kind = 'section') AS sections,
       (SELECT round(toc_agreement, 3) FROM segmentation_run s
         WHERE s.instrument_id = i.id ORDER BY s.run_at DESC LIMIT 1) AS toc
  FROM audit_instrument i JOIN audit_provision p ON p.instrument_id = i.id
 GROUP BY i.id, i.short_title, i.jurisdiction, i.year
 ORDER BY 4 DESC LIMIT 10;
