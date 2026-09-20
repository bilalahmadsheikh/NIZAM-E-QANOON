-- Every criterion in docs/CORPUS-CRITERIA.md, as a pass/fail table.
--
--     ./nz audit
--
-- A criterion that cannot be measured is not a criterion. Each row states the
-- rule, the number measured, the threshold, and PASS or FAIL -- so the answer to
-- "is the corpus sound" is one query, not a judgement call.

-- Migration 0012 made the corpus append-only: re-segmenting RETIRES the previous
-- instrument and appends a new one, so `provision` holds the trees of every
-- revision ever produced. Every measure below therefore reads through
-- `live_provision` / `live_document`, which are the active revisions only.
-- Counting raw tables here would double every number after the first re-run --
-- the views already learned this lesson; this file had not.

SET paradedb.planner_warnings = 'off';
\pset border 2

CREATE TEMP VIEW audit_document AS
SELECT * FROM document WHERE is_active;
CREATE TEMP VIEW audit_instrument AS
SELECT * FROM instrument WHERE is_active;
CREATE TEMP VIEW audit_provision AS
SELECT p.* FROM provision p JOIN audit_instrument i ON i.id=p.instrument_id;
CREATE TEMP VIEW audit_version AS
SELECT v.* FROM provision_version v JOIN audit_provision p ON p.id=v.provision_id;
CREATE TEMP VIEW audit_block AS
SELECT b.* FROM text_block b JOIN audit_document d ON d.id=b.document_id;
CREATE TEMP VIEW audit_assignment AS
SELECT s.* FROM block_assignment_set s JOIN audit_document d ON d.id=s.document_id
WHERE s.is_active;
CREATE TEMP VIEW audit_provision_block AS
SELECT pb.*,s.source_observation_id FROM provision_block pb
JOIN audit_assignment s ON s.id=pb.assignment_set_id;

CREATE TEMP TABLE audit_result AS
WITH RECURSIVE live_document AS (SELECT * FROM audit_document),
     live_instrument AS (SELECT * FROM audit_instrument),
     live_provision AS (SELECT * FROM audit_provision),
     live_version AS (SELECT * FROM audit_version),
     latest_verification AS (
       SELECT DISTINCT ON (v.document_id) v.*
         FROM extraction_verification v
         JOIN live_document d ON d.id=v.document_id
        WHERE v.reference_extractor='poppler-pdftotext'
        ORDER BY v.document_id,v.verified_at DESC,v.id DESC),
     latest_ocr AS (
       SELECT DISTINCT ON (v.document_id) v.*
         FROM extraction_verification v
         JOIN live_document d ON d.id=v.document_id
        WHERE v.verifier LIKE 'nizam.verify_ocr/%'
        ORDER BY v.document_id,v.verified_at DESC,v.id DESC),
     latest_order AS (
       SELECT DISTINCT ON (v.document_id) v.*
         FROM extraction_verification v
         JOIN live_document d ON d.id=v.document_id
        WHERE v.verifier LIKE 'nizam.verify_order/%'
        ORDER BY v.document_id,v.verified_at DESC,v.id DESC),
     latest_text_quality AS (
       SELECT DISTINCT ON (v.document_id) v.*
         FROM extraction_verification v
         JOIN live_document d ON d.id=v.document_id
        WHERE v.verifier LIKE 'nizam.verify_text_quality/%'
        ORDER BY v.document_id,v.verified_at DESC,v.id DESC),
     latest_segmentation AS (
       SELECT DISTINCT ON (r.instrument_id) r.*
         FROM segmentation_run r
         JOIN live_instrument i ON i.id=r.instrument_id
        ORDER BY r.instrument_id,r.run_at DESC,r.id DESC),
     expected_ancestor(provision_id,ancestor_id,ancestor_path,distance) AS (
       SELECT p.id,p.id,p.path,0::smallint FROM live_provision p
       UNION ALL
       SELECT e.provision_id,parent.id,parent.path,(e.distance+1)::smallint
         FROM expected_ancestor e
         JOIN live_provision child ON child.id=e.ancestor_id
         JOIN live_provision parent ON parent.id=child.parent_id),
m AS (
  SELECT
    -- completeness
    -- 4,710 landed observations carry 4,589 distinct hashes: the same statute
    -- published on two portals is two correct observations of one file. The
    -- criterion is that every landed hash became a blob and every blob came
    -- from a landed observation -- not that the two counts are equal.
    (SELECT count(DISTINCT sha256) FROM source_observation WHERE outcome='landed') AS landed_sha,
    (SELECT count(*) FROM blob)                                                 AS blobs,
    (SELECT count(*) FROM blob b WHERE NOT EXISTS (
        SELECT 1 FROM source_observation o
         WHERE o.sha256=b.sha256 AND o.outcome='landed'))                       AS blob_unsourced,
    (SELECT count(*) FROM source_observation o WHERE o.outcome='landed'
       AND NOT EXISTS (SELECT 1 FROM blob b WHERE b.sha256=o.sha256))           AS landed_unstored,
    (SELECT count(*) FROM blob b LEFT JOIN live_document d ON d.sha256=b.sha256
      WHERE d.id IS NULL)                                                       AS blobs_unread,
    (SELECT count(*) FROM source_observation o JOIN live_document d ON d.sha256=o.sha256
      WHERE o.outcome='landed'
        AND NOT EXISTS (SELECT 1 FROM audit_assignment a
                         WHERE a.source_observation_id=o.id AND a.document_id=d.id)
        AND NOT EXISTS (SELECT 1 FROM segmentation_run r
                         WHERE r.source_observation_id=o.id AND r.document_id=d.id
                           AND r.reason IS NOT NULL))                           AS doc_no_reason,
    (SELECT count(*) FROM source_observation o
      JOIN live_document d ON d.sha256=o.sha256
      JOIN audit_block t ON t.document_id=d.id
      LEFT JOIN audit_provision_block pb ON pb.block_id=t.id
                                        AND pb.source_observation_id=o.id
      WHERE o.outcome='landed' AND pb.block_id IS NULL)                         AS blocks_unaccounted,
    (SELECT coalesce(sum(chars),0) FROM audit_provision_block WHERE role='unassigned') AS chars_unassigned,
    -- A section whose whole content is its subsections has no text of its own,
    -- and that is correct, not a defect. What must never happen is a provision
    -- with no text AND no children AND no block: nothing to read, nowhere to
    -- look. 419 leaves carry their text only in provision.heading -- reachable,
    -- but invisible to a retrieval layer that reads provision_version.
    (SELECT count(*) FROM live_provision p
      WHERE NOT EXISTS (SELECT 1 FROM live_version v WHERE v.provision_id=p.id)
        AND NOT EXISTS (SELECT 1 FROM live_provision c WHERE c.parent_id=p.id)
        AND p.first_block IS NULL
        AND p.heading IS NULL)                                                  AS prov_no_text,
    (SELECT count(*) FROM live_provision p
      WHERE NOT EXISTS (SELECT 1 FROM live_version v WHERE v.provision_id=p.id)
        AND NOT EXISTS (SELECT 1 FROM live_provision c WHERE c.parent_id=p.id))  AS empty_leaves,
    (SELECT count(*) FROM audit_provision_block WHERE role='unstructured')      AS unstructured,
    (SELECT count(DISTINCT document_id) FROM audit_provision_block
      WHERE role='unstructured')                                                AS unstructured_docs,
    -- C8 asserts the PROPERTY, not a count. The first version hardcoded
    -- "<= 9 documents" and failed the moment the number moved, which is exactly
    -- how C1 was wrong too: a criterion that encodes today's measurement rather
    -- than the rule it stands for is a tripwire, not a test.
    (SELECT count(DISTINCT pb.document_id) FROM audit_provision_block pb
      WHERE pb.role='unstructured'
        AND NOT EXISTS (SELECT 1 FROM segmentation_run r
                         WHERE r.document_id=pb.document_id
                           AND r.source_observation_id=pb.source_observation_id
                           AND r.reason IS NOT NULL))
                                                                                AS unstructured_unexplained,
    -- S6. Labels need only be unique among siblings. The same label under two
    -- separately printed containers is addressable; two under one parent is not.
    (SELECT count(*) FROM (SELECT instrument_id,parent_id,kind,label
                            FROM live_provision
                           WHERE kind IN ('section','article')
                           GROUP BY 1,2,3,4 HAVING count(*) > 1) x)             AS dup_labels,
    (SELECT count(DISTINCT instrument_id) FROM (
        SELECT instrument_id,parent_id,kind,label FROM live_provision
         WHERE kind IN ('section','article')
         GROUP BY 1,2,3,4 HAVING count(*) > 1) y)                               AS dup_instruments,
    (SELECT count(DISTINCT source_observation_id)
       FROM v_structural_adjudication_pending)                                   AS demoted_instruments,
    (SELECT count(*) FROM v_structural_adjudication_pending)                     AS demoted_labels,
    (SELECT count(DISTINCT source_observation_id)
       FROM v_boundary_adjudication_pending)                                    AS boundary_observations,
    (SELECT count(*) FROM v_boundary_adjudication_pending)                      AS boundary_candidates,
    (SELECT count(*) FROM (
       SELECT r.instrument_id,
              coalesce((r.detail->>'repeated_labels_demoted')::integer,0) expected,
              count(c.id) actual
         FROM latest_segmentation r
         LEFT JOIN segmentation_structural_candidate c
           ON c.instrument_id=r.instrument_id
        GROUP BY r.instrument_id,r.detail
       HAVING coalesce((r.detail->>'repeated_labels_demoted')::integer,0)
              <> count(c.id)
     ) x)                                                                       AS structural_itemization_mismatches,
    (SELECT count(*) FROM (
       SELECT p.source_observation_id,count(*) AS expected,
              coalesce(applied.n,0) AS applied
         FROM segmentation_curation_patch p
         LEFT JOIN (
           SELECT source_observation_id,
                  sum(coalesce((detail->>'curation_patches_applied')::integer,0)) n
             FROM latest_segmentation GROUP BY source_observation_id
         ) applied ON applied.source_observation_id=p.source_observation_id
        WHERE p.retired_at IS NULL
          AND p.review_state IN ('source_verified','human_verified')
        GROUP BY p.source_observation_id,applied.n
       HAVING count(*) <> coalesce(applied.n,0)
     ) x)                                                                       AS patch_mismatches,
    (SELECT count(*) FROM extraction_attempt WHERE outcome<>'extracted' AND reason IS NULL)
      + (SELECT count(*) FROM segmentation_run WHERE outcome<>'segmented' AND reason IS NULL)
                                                                                AS silent_failures,
    -- accuracy
    (SELECT count(*) FROM live_provision p
      WHERE p.first_block IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM text_block t WHERE t.id=p.first_block))   AS invented,
    (SELECT count(*) FROM live_provision p JOIN instrument i ON i.id=p.instrument_id
       JOIN document d ON d.id=i.document_id
      WHERE p.first_page IS NOT NULL
        AND (p.first_page < 1 OR p.first_page > d.page_count))                  AS bad_pages,
    (SELECT count(*) FROM instrument_toc_entry e
      JOIN live_instrument i ON i.id=e.instrument_id
      LEFT JOIN text_block t ON t.id=e.source_block_id
       AND t.document_id=i.document_id AND t.page_no=e.source_page
     WHERE e.source_block_id IS NULL OR e.source_page IS NULL OR t.id IS NULL
        OR (e.source_char_offset IS NOT NULL
            AND e.source_char_offset >= length(coalesce(t.text,'')))) AS toc_bad_source,
    (SELECT round(percentile_cont(0.5) WITHIN GROUP (ORDER BY toc_agreement)::numeric,4)
       FROM latest_segmentation WHERE toc_found)                                AS toc_median,
    (SELECT count(*) FROM v_toc_gap_pending)                                    AS toc_pending,
    -- A10: a contents entry that resolves to EDITORIAL APPARATUS rather than
    -- law. A5 asks whether a promised entry resolved; it does not ask what it
    -- resolved TO. Document 4242, the KP Public Service Commission Ordinance,
    -- is released and answers sections 1, 2 and 3 with
    -- 'Substituted vide the Khyber Pakhtunkhwa Act No. IV of 2011.' while its
    -- contents promises 'Short title and commencement', 'Definitions' and
    -- 'Composition of Commission etc.' The law is present in text_block; the
    -- citation renders the footnote. That is INV-4 failing while A5 passes.
    --
    -- Anchored at the START of the provision's text, deliberately: an
    -- unanchored `contains` over the same vocabulary flags 4,613 entries in
    -- 1,691 released instruments, because ordinary sections quote Gazettes and
    -- amending Acts. A bare `Omitted by...` / `Rep. by...` opener is excluded,
    -- because an omitted section's printed body IS that sentence.
    -- The entry's own printed heading must not be apparatus too -- that case is
    -- a contents-boundary defect, counted separately, not a bad link.
    (SELECT count(*)
       FROM instrument_toc_entry t
       JOIN v_release_instrument ri ON ri.id = t.instrument_id
       JOIN v_provision pv ON pv.provision_id = t.provision_id
      WHERE t.provision_id IS NOT NULL
        AND coalesce(pv.text,'') <> ''
        AND pv.text ~* ('^\s*(?:\d{1,3}\s*[.:-]?\s*)?('
        || 'Subs\.|Subs,|Substituted\s+(?:for|by|vide)'
        || '|Ins\.|Inserted\s+(?:by|vide)|Added\s+(?:by|vide)'
        || '|Ibid\b|See\s+now\b'
        || '|For\s+(?:the\s+)?Statement\s+of\s+Objects'
        || '|This\s+(?:Act|Ordinance|section)\s+(?:has\s+been\s+extended'
        ||   '|was\s+(?:assented|published|originally|previously)|previously)'
        || '|Pakistan\s+Code\b'
        || '|The\s+(?:original\s+)?(?:words?|brackets|provisions?|figures?|letters?|commas?)\b'
        ||   '[^\n]{0,200}\b(?:rep\.|omitted\s+by|substituted|subs\.|ins\.)'
        || '|Certain\s+words\b[^\n]{0,200}\bomitted\s+by'
        || '|S\.?\s*\d{1,4}\s*[-\u2013]?\s*[A-Z]?\s*,?\s*'
        ||   '(?:ins\.|inserted|subs\.|substituted|omitted|deleted)\b'
        || '|Proviso\s+omitted\b'
        || '|For\s+rules\s+see\b|See\s+[Nn]otification\b'
        || ')')
        AND coalesce(t.printed_heading,'') !~* ('^\s*(?:\d{1,3}\s*[.:-]?\s*)?('
        || 'Subs\.|Subs,|Substituted\s+(?:for|by|vide)'
        || '|Ins\.|Inserted\s+(?:by|vide)|Added\s+(?:by|vide)'
        || '|Ibid\b|See\s+now\b'
        || '|For\s+(?:the\s+)?Statement\s+of\s+Objects'
        || '|This\s+(?:Act|Ordinance|section)\s+(?:has\s+been\s+extended'
        ||   '|was\s+(?:assented|published|originally|previously)|previously)'
        || '|Pakistan\s+Code\b'
        || '|The\s+(?:original\s+)?(?:words?|brackets|provisions?|figures?|letters?|commas?)\b'
        ||   '[^\n]{0,200}\b(?:rep\.|omitted\s+by|substituted|subs\.|ins\.)'
        || '|Certain\s+words\b[^\n]{0,200}\bomitted\s+by'
        || '|S\.?\s*\d{1,4}\s*[-\u2013]?\s*[A-Z]?\s*,?\s*'
        ||   '(?:ins\.|inserted|subs\.|substituted|omitted|deleted)\b'
        || '|Proviso\s+omitted\b'
        || '|For\s+rules\s+see\b|See\s+[Nn]otification\b'
        || ')')
    )                                                                           AS toc_links_apparatus,
    (SELECT count(*) FROM live_version v WHERE NOT (v.validity @> current_date))
                                                                                AS not_operative,
    (SELECT count(*) FROM live_version)                                         AS versions,
    (SELECT count(*) FROM audit_block b JOIN audit_document d ON d.id=b.document_id
       JOIN page pg ON pg.document_id=b.document_id AND pg.page_no=b.page_no
      WHERE (d.lane='E4' OR pg.lane='E4') AND b.confidence IS NULL)             AS ocr_no_conf,
    -- structure
    (SELECT count(*) FROM live_provision p WHERE p.parent_id IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM live_provision q WHERE q.id=p.parent_id)) AS orphans,
    (SELECT count(*) FROM live_provision p JOIN live_provision q ON q.id=p.parent_id
      WHERE q.instrument_id <> p.instrument_id)                                 AS cross_inst,
    (SELECT count(*) - count(DISTINCT path) FROM live_provision)                AS dup_paths,
    (SELECT count(*) FROM live_document d
      WHERE d.page_count <> (SELECT count(*) FROM page p WHERE p.document_id=d.id)) AS page_mismatch,
    -- S4: reading order must be dense and monotonic. A gap means a block was
    -- dropped after its neighbours were numbered -- which is exactly what a
    -- discarded OCR page did before the counter learned to roll back.
    (SELECT count(*) FROM (
        SELECT document_id FROM audit_block GROUP BY document_id
         HAVING max(reading_order) - min(reading_order) + 1 <> count(*)) g)      AS order_gaps,
    -- A6 is not measured, it is enforced. Assert the constraint still exists:
    -- an invariant that quietly stops being a constraint is worse than one that
    -- was never claimed.
    (SELECT count(*) FROM pg_constraint
      WHERE conname='no_overlap' AND contype='x')                                AS excl_present
    ,(SELECT count(*) FROM live_document WHERE lane<>'E4')                       AS verify_expected
    ,(SELECT count(*) FROM latest_verification)                                  AS verify_recorded
    ,(SELECT count(*) FROM latest_verification WHERE outcome='unverifiable')     AS verify_unverifiable
    -- A document Poppler cannot read is not automatically a defect: some
    -- official PDFs are structurally malformed, and no second extractor exists
    -- to cross-check them. What must never happen is one passing UNEXAMINED.
    -- So A1 counts unverifiable documents that carry no active
    -- extraction_assertion -- the same shape as C8's "0 unexplained".
    -- Document 4608 is the worked example: Poppler reports a missing
    -- trailer/xref, the render is a corrupt black canvas, OCR yields nothing,
    -- and one text block is leaked PDF operators. It is declared, not passed.
    ,(SELECT count(*) FROM latest_verification v
        JOIN live_document d ON d.id = v.document_id
       WHERE v.outcome='unverifiable'
         AND NOT EXISTS (SELECT 1 FROM extraction_assertion a
                          WHERE a.sha256 = d.sha256 AND a.is_active))            AS verify_undeclared
    ,(SELECT count(*) FROM latest_verification WHERE char_recall < 0.999)        AS recall_below
    ,(SELECT count(*) FROM latest_verification
       WHERE outcome='review' AND char_precision < 0.999)                       AS precision_below
    ,(SELECT min(char_recall) FROM latest_verification
       WHERE char_recall IS NOT NULL)                                            AS min_recall
    ,(SELECT min(char_precision) FROM latest_verification
       WHERE char_precision IS NOT NULL)                                         AS min_precision
    ,(SELECT count(*) FROM live_document d WHERE d.lane='E4' OR EXISTS
        (SELECT 1 FROM audit_block b WHERE b.document_id=d.id
                                      AND b.confidence IS NOT NULL))              AS ocr_verify_expected
    ,(SELECT count(*) FROM latest_ocr)                                            AS ocr_verify_recorded
    ,(SELECT count(*) FROM latest_ocr WHERE outcome<>'passed')                    AS ocr_review
    ,(SELECT count(*) FROM live_document WHERE lane<>'E4')                        AS order_verify_expected
    ,(SELECT count(*) FROM latest_order)                                          AS order_verify_recorded
    -- Same rule as A1: a document Poppler cannot read is not an order defect,
    -- provided a person has examined it and said so. Document 4608's PDF has a
    -- missing trailer/xref, renders to a black canvas, and yields no OCR; it
    -- carries an active decode_damage assertion. Counting it as an unreviewed
    -- word-order failure would be measuring the wrong thing forever.
    ,(SELECT count(*) FROM latest_order o
        JOIN live_document d ON d.id = o.document_id
       WHERE o.outcome<>'passed'
         AND NOT (o.outcome='unverifiable'
                  AND EXISTS (SELECT 1 FROM extraction_assertion a
                               WHERE a.sha256 = d.sha256 AND a.is_active)))       AS order_review
    ,(SELECT count(*) FROM live_document WHERE lane<>'E4')                        AS text_verify_expected
    ,(SELECT count(*) FROM latest_text_quality)                                   AS text_verify_recorded
    ,(SELECT count(*) FROM latest_text_quality WHERE outcome<>'passed')           AS text_review
    -- A11 is recorded by the Python census because its per-token comparison
    -- cannot be reproduced honestly in this SQL. MEASURED: written as SQL here,
    -- with guards 1-3 plus prefix containment and no token comparison, the rule
    -- reported 472 rows in 221 documents against a true count of 101 -- 4.7x,
    -- and concentrated in the CrPC (44), the Customs Act (14), the PAF Act
    -- (13), the Army Act (11), the Constitution (11) and the PPC (11), every
    -- one of them one name spelt two ways. An A11 printing 472 would be a worse
    -- artefact than no A11. So the value is READ from the recorded census.
    --
    -- A stored number is a claim about a corpus, not a fact about this one.
    -- `is_stale` compares the census's digest of the exact provision population
    -- it read against that population now, so a replay, a retirement, a
    -- duplicate resolution or a restore all invalidate it. Three states, three
    -- answers: never measured, measured for a corpus that has since moved, and
    -- measured for this one. Only the third may report a pass.
    ,(SELECT mislabelled FROM v_heading_mislabel_census_current)                  AS heading_not_own
    ,(SELECT mislabelled_documents FROM v_heading_mislabel_census_current)        AS heading_not_own_docs
    ,(SELECT variant_spellings FROM v_heading_mislabel_census_current)            AS heading_variants
    ,(SELECT never_measured FROM v_heading_mislabel_census_current)               AS heading_census_absent
    ,(SELECT is_stale FROM v_heading_mislabel_census_current)                     AS heading_census_stale
    ,(SELECT to_char(measured_at,'YYYY-MM-DD HH24:MI')
        FROM v_heading_mislabel_census_current)                                   AS heading_census_at
    -- S9: the disposable subtree accelerator must be the exact closure of the
    -- real provision parent graph. Synthetic jurisdiction/kind/instrument path
    -- prefixes are not legal nodes and must consume no closure rows.
    ,(SELECT count(*) FROM expected_ancestor)                                     AS ancestor_expected
    ,(SELECT count(*) FROM provision_ancestor a
       JOIN live_provision p ON p.id=a.provision_id)                              AS ancestor_recorded
    ,(SELECT count(*) FROM provision_ancestor a
       WHERE NOT EXISTS (SELECT 1 FROM live_provision p WHERE p.id=a.provision_id))
                                                                                  AS ancestor_stale
    ,(SELECT count(*) FROM expected_ancestor e
       LEFT JOIN provision_ancestor a
         ON a.ancestor_path=e.ancestor_path AND a.provision_id=e.provision_id
        AND a.distance=e.distance
      WHERE a.provision_id IS NULL)                                                AS ancestor_missing
    ,(SELECT count(*) FROM provision_ancestor a
       JOIN live_provision p ON p.id=a.provision_id
       LEFT JOIN expected_ancestor e
         ON e.ancestor_path=a.ancestor_path AND e.provision_id=a.provision_id
        AND e.distance=a.distance
      WHERE e.provision_id IS NULL)                                                AS ancestor_extra
)
SELECT * FROM (
  SELECT 'C1' AS id, 'every acquired file becomes a blob'      AS criterion,
         landed_unstored||' unstored / '||blob_unsourced||' unsourced' AS measured,
         '0 / 0' AS expected,
         CASE WHEN landed_unstored=0 AND blob_unsourced=0 AND blobs=landed_sha
              THEN 'PASS' ELSE 'FAIL' END AS result FROM m
  UNION ALL SELECT 'C2','every blob is read', blobs_unread::text,'0',
         CASE WHEN blobs_unread=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'C3','no document silently unsegmented', doc_no_reason::text,'0',
         CASE WHEN doc_no_reason=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'C4','EVERY text block accounted for', blocks_unaccounted::text,'0',
         CASE WHEN blocks_unaccounted=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'C5','EVERY character reachable', chars_unassigned::text,'0',
         CASE WHEN chars_unassigned=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'C6','every provision has text, children or a block',
         prov_no_text::text,'0',
         CASE WHEN prov_no_text=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'C8','unstructured text is named, not dropped',
         unstructured||' blocks in '||unstructured_docs||' docs, '||
         unstructured_unexplained||' unexplained', '0 unexplained',
         CASE WHEN unstructured_unexplained=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'C7','failures are never silent', silent_failures::text,'0',
         CASE WHEN silent_failures=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'A3','no invented provisions', invented::text,'0',
         CASE WHEN invented=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'A4','page anchors inside the document', bad_pages::text,'0',
         CASE WHEN bad_pages=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'A5','contents agreement (median; pending gaps reported)',
         toc_median||'; '||toc_pending||' pending','>= 0.95; queue reported',
         CASE WHEN toc_median >= 0.95 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'A9','contents entries retain exact source anchors',
         toc_bad_source::text,'0',
         CASE WHEN toc_bad_source=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'A10','contents entries resolve to law, not apparatus',
         toc_links_apparatus::text,'0',
         CASE WHEN toc_links_apparatus=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'A11','provision headings match their printed opener (reported)',
         CASE WHEN heading_census_stale THEN 'census missing or stale'
              ELSE heading_not_own||' in '||heading_not_own_docs||
                   ' docs; '||heading_variants||' spelling variants' END,
         'fresh census; count reported (0 before promotion)',
         CASE WHEN heading_census_stale THEN 'FAIL' ELSE 'PASS' END FROM m
  UNION ALL SELECT 'A7','as-at query returns the corpus',
         (versions - not_operative)||' / '||versions, 'all',
         CASE WHEN not_operative=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'A8','OCR blocks carry a confidence', ocr_no_conf::text,'0',
         CASE WHEN ocr_no_conf=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'Q1','OCR quality evidence complete and accepted',
         ocr_verify_recorded||' / '||ocr_verify_expected||'; '||ocr_review||' review',
         'complete; 0 review',
         CASE WHEN ocr_verify_recorded=ocr_verify_expected AND ocr_review=0
              THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'Q2','word-order evidence complete and accepted',
         order_verify_recorded||' / '||order_verify_expected||'; '||order_review||
         ' unresolved',
         'complete; 0 review',
         CASE WHEN order_verify_recorded=order_verify_expected AND order_review=0
              THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'Q3','text plausibility evidence complete and accepted',
         text_verify_recorded||' / '||text_verify_expected||'; '||text_review||' review',
         'complete; 0 review',
         CASE WHEN text_verify_recorded=text_verify_expected AND text_review=0
              THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S1','no orphan provisions', orphans::text,'0',
         CASE WHEN orphans=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S2','no tree spans two instruments', cross_inst::text,'0',
         CASE WHEN cross_inst=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S3','every path unique', dup_paths::text,'0',
         CASE WHEN dup_paths=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S4','reading order dense and monotonic', order_gaps::text,'0',
         CASE WHEN order_gaps=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S5','page rows match page count', page_mismatch::text,'0',
         CASE WHEN page_mismatch=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S6','no sibling sections share one citation label',
         dup_labels||' labels in '||dup_instruments||' instruments','0',
         CASE WHEN dup_labels=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S7','automatic repeated-label demotions adjudicated',
         demoted_labels||' pending units in '||demoted_instruments||
         ' observations; '||structural_itemization_mismatches||' itemization mismatches',
         '0 pending; 0 mismatches',
         CASE WHEN demoted_labels=0 AND structural_itemization_mismatches=0
              THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S8','approved source corrections applied exactly once',
         patch_mismatches::text,'0 mismatched observations',
         CASE WHEN patch_mismatches=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S9','ancestor closure contains real provision nodes only',
         ancestor_recorded||' / '||ancestor_expected||'; '||ancestor_missing||
         ' missing; '||ancestor_extra||' extra; '||ancestor_stale||' stale',
         'exact; 0 missing / extra / stale',
         CASE WHEN ancestor_recorded=ancestor_expected AND ancestor_missing=0
                   AND ancestor_extra=0 AND ancestor_stale=0
              THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'S10','multi-instrument boundaries resolved and materialized',
         boundary_candidates||' pending boundaries in '||boundary_observations||' observations',
         '0 pending',
         CASE WHEN boundary_candidates=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'A6','no overlapping law (enforced, not tested)',
         CASE WHEN excl_present=1 THEN 'EXCLUDE constraint present'
              ELSE 'CONSTRAINT MISSING' END, 'enforced',
         CASE WHEN excl_present=1 THEN 'PASS' ELSE 'FAIL' END FROM m
  -- A1/A2 are produced by the independent Poppler verifier and persisted as
  -- append-only evidence. The audit consumes the newest record per live doc;
  -- it never embeds a result copied from an earlier run.
  UNION ALL SELECT 'A1','character recall vs pdftotext',
         min_recall||' min; '||(verify_expected-verify_recorded)||' missing; '||
         verify_unverifiable||' unverifiable ('||verify_undeclared||' undeclared)',
         '>= 0.999; complete; 0 undeclared',
         CASE WHEN verify_recorded=verify_expected AND verify_undeclared=0
                    AND recall_below=0 THEN 'PASS' ELSE 'FAIL' END FROM m
  UNION ALL SELECT 'A2','character precision vs pdftotext',
         min_precision||' min; '||precision_below||' below threshold', '>= 0.999',
         CASE WHEN verify_recorded=verify_expected AND precision_below=0
              THEN 'PASS' ELSE 'FAIL' END FROM m
) x ORDER BY id;

SELECT * FROM audit_result ORDER BY id;

\echo ''
\echo '──── where every character went (C5 in detail)'
SELECT role, count(*) AS blocks, sum(chars) AS chars,
       round(100.0*sum(chars)/(SELECT sum(chars) FROM audit_provision_block),2) AS pct
  FROM audit_provision_block GROUP BY role ORDER BY 3 DESC;

\echo ''
\echo '──── the arithmetic: expression text expected vs accounted'
-- Byte-identical PDFs can be separate official observations. Their document
-- blocks are stored once but assigned once per expression, so the denominator
-- must count each landed observation rather than each distinct blob.
SELECT (SELECT sum(d.char_count) FROM source_observation o
          JOIN audit_document d ON d.sha256=o.sha256
         WHERE o.outcome='landed')                            AS chars_expected,
       (SELECT sum(chars) FROM audit_provision_block)         AS chars_accounted,
       (SELECT sum(d.char_count) FROM source_observation o
          JOIN audit_document d ON d.sha256=o.sha256
         WHERE o.outcome='landed')
         - (SELECT sum(chars) FROM audit_provision_block)     AS difference;

\echo ''
\echo '──── the third of the corpus that prints no contents list (S6 is its only check)'
WITH lr AS (SELECT DISTINCT ON (instrument_id) document_id, instrument_id, toc_found
              FROM segmentation_run r
             WHERE EXISTS (SELECT 1 FROM audit_instrument i WHERE i.id=r.instrument_id)
             ORDER BY instrument_id, run_at DESC),
sec AS (SELECT p.instrument_id, (regexp_match(p.label,'^([0-9]+)'))[1]::int AS n
          FROM audit_provision p WHERE p.kind='section' AND p.parent_id IS NULL
            AND p.label ~ '^[0-9]+')
SELECT lr.toc_found AS has_contents, count(*) AS documents,
       round(avg(c.dn::numeric/NULLIF(c.mx,0)),4) AS numbering_continuity,
       count(*) FILTER (WHERE c.dups > 0) AS with_repeated_numeric_stems
  FROM lr LEFT JOIN (SELECT instrument_id, count(DISTINCT n) dn, max(n) mx,
                            count(*)-count(DISTINCT n) dups
                       FROM sec GROUP BY 1) c ON c.instrument_id=lr.instrument_id
 GROUP BY 1 ORDER BY 1 DESC;
\echo 'continuity is REPORTED, not a threshold: measured against contents agreement'
\echo 'over 2,789 documents it correlates at only 0.18, so it is a review signal.'

-- A release audit must be executable policy, not only a report. Preserve all
-- detail above, then make CI/callers fail closed when any row failed.
SELECT EXISTS (SELECT 1 FROM audit_result WHERE result='FAIL') AS audit_failed \gset
\if :audit_failed
  DO $$ BEGIN RAISE EXCEPTION 'corpus release audit has failing criteria'; END $$;
\endif
