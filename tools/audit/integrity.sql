-- Corpus integrity audit -- Document 02 §8, "the seven QA gates".
--
-- Everything here is answerable from the database alone: completeness of the
-- ladder, structural soundness of every document, and internal consistency of
-- the stored evidence. Accuracy against the source PDFs is a separate pass
-- (nizam.workers.verify_extraction) because it has to re-read 4,589 files.
--
--   ./nz psql -f /dev/stdin < tools/audit/integrity.sql
--   docker compose exec -T postgres psql -U nizam -d nizam -f - < tools/audit/integrity.sql
--
-- Every check states what it means for the answer to be wrong. A zero that
-- nobody can interpret is not a check.

\pset border 2
SET paradedb.planner_warnings = 'off';

-- Base tables retain every revision. Integrity metrics below describe the
-- current corpus, while explicit provenance checks may still inspect history.
CREATE TEMP VIEW audit_document AS
SELECT * FROM document WHERE is_active;

CREATE TEMP VIEW audit_block AS
SELECT b.*
  FROM text_block b JOIN audit_document d ON d.id=b.document_id;

\echo ''
\echo '================ 1. COMPLETENESS -- did every source file become a document?'
SELECT (SELECT count(*) FROM source_observation WHERE outcome='landed') AS landed_observations,
       (SELECT count(*) FROM blob)                                      AS distinct_blobs,
       (SELECT count(*) FROM audit_document)                            AS documents,
       (SELECT count(*) FROM v_extract_queue)                           AS still_unread,
       CASE WHEN (SELECT count(*) FROM v_extract_queue) = 0
                 AND (SELECT count(*) FROM blob) = (SELECT count(*) FROM audit_document)
            THEN 'COMPLETE' ELSE 'GAPS REMAIN' END                      AS verdict;

\echo ''
\echo '-- a landed blob with no document is a file we acquired and never read'
SELECT count(*) AS blobs_without_a_document
  FROM blob b LEFT JOIN audit_document d ON d.sha256 = b.sha256
 WHERE d.id IS NULL;

\echo ''
\echo '-- a document whose blob is missing would be text with no provenance'
SELECT count(*) AS documents_without_a_blob
  FROM audit_document d LEFT JOIN blob b ON b.sha256 = d.sha256
 WHERE b.sha256 IS NULL;

\echo ''
\echo '================ 2. STRUCTURE -- is each document whole?'
\echo '-- doc 02 §4.1: a document stored without its pages or blocks is silently truncated'
SELECT count(*) AS documents_missing_pages_or_blocks
  FROM audit_document d
 WHERE NOT EXISTS (SELECT 1 FROM page p WHERE p.document_id = d.id)
    OR NOT EXISTS (SELECT 1 FROM text_block t WHERE t.document_id = d.id);

\echo ''
\echo '-- the page rows stored must equal the page count the extractor reported'
SELECT count(*) AS page_count_mismatches
  FROM audit_document d
 WHERE d.page_count <> (SELECT count(*) FROM page p WHERE p.document_id = d.id);

\echo ''
\echo '-- pages must be numbered 1..n with no hole: a gap is a lost page'
SELECT count(*) AS documents_with_a_page_gap FROM (
  SELECT d.id FROM audit_document d JOIN page p ON p.document_id = d.id
   GROUP BY d.id, d.page_count
  HAVING min(p.page_no) <> 1 OR max(p.page_no) <> d.page_count
) x;

\echo ''
\echo '================ 3. EVIDENCE -- can every stored word be traced to the page it came from?'
\echo '-- doc 02 §4.1 requires {page, bbox, reading_order} on every block'
SELECT count(*) FILTER (WHERE text IS NULL OR btrim(text) = '')                  AS empty_blocks,
       count(*) FILTER (WHERE x1 <= x0 OR y1 <= y0)                             AS impossible_boxes,
       count(*) FILTER (WHERE (x1 <= x0 OR y1 <= y0) AND EXISTS (
           SELECT 1 FROM extraction_assertion a
            WHERE a.sha256=d.sha256
              AND a.kind IN ('decode_damage','visibility_review') AND a.is_active
              AND (a.page_no IS NULL OR a.page_no=b.page_no)))                  AS linked_to_evidence_assertion,
       count(*) FILTER (WHERE page_no IS NULL OR reading_order IS NULL)         AS missing_anchors
  FROM audit_block b JOIN audit_document d ON d.id=b.document_id;

\echo ''
\echo '-- a block must sit on a page that exists (enforced by FK, checked anyway)'
SELECT count(*) AS blocks_on_a_missing_page
  FROM audit_block t LEFT JOIN page p
    ON p.document_id = t.document_id AND p.page_no = t.page_no
 WHERE p.document_id IS NULL;

\echo ''
\echo '-- reading order must be dense and start at 0, or the text reassembles wrongly'
SELECT count(*) AS documents_with_broken_reading_order FROM (
  SELECT document_id FROM audit_block GROUP BY document_id
  HAVING min(reading_order) <> 0
      OR max(reading_order) <> count(*) - 1
      OR count(DISTINCT reading_order) <> count(*)
) x;

\echo ''
\echo '================ 4. QUALITY BY LANE -- the two lanes mean different things'
SELECT d.lane,
       count(*)                                   AS documents,
       sum(d.page_count)                          AS pages,
       sum(d.char_count)                          AS characters,
       round(avg(d.printable_ratio), 4)           AS mean_quality,
       min(d.printable_ratio)                     AS worst,
       count(*) FILTER (WHERE d.lane IN ('E2','E3') AND d.printable_ratio < 0.95)
         + count(*) FILTER (WHERE d.lane = 'E4' AND d.printable_ratio < 0.70)
                                                  AS below_own_threshold
  FROM audit_document d GROUP BY d.lane ORDER BY d.lane;

\echo ''
\echo '-- E2/E3: printable_ratio is the share of characters that are not extraction damage'
\echo '-- E4   : the same column holds mean OCR word confidence. Different quantity, same column.'

\echo ''
\echo '================ 5. ACQUISITION -- what never arrived, and why'
SELECT outcome, count(*) AS observations
  FROM source_observation GROUP BY outcome ORDER BY 2 DESC;

\echo ''
\echo '-- doc 02 §3.1: failures are kept as rows. These are review items, not silence.'
SELECT source_id, count(*) AS failed_or_missing
  FROM source_observation WHERE outcome <> 'landed'
 GROUP BY source_id ORDER BY 2 DESC;

\echo ''
\echo '================ 6. EXTRACTION ATTEMPTS -- every try is recorded (doc 02 §8)'
SELECT outcome, count(*) AS attempts,
       round(avg(duration_ms)/1000.0, 1) AS mean_seconds
  FROM extraction_attempt GROUP BY outcome ORDER BY 2 DESC;

\echo ''
\echo '-- every document should have a successful attempt behind it'
SELECT count(*) AS documents_with_no_recorded_attempt
  FROM audit_document d
 WHERE NOT EXISTS (SELECT 1 FROM extraction_attempt a
                    WHERE a.sha256 = d.sha256 AND a.outcome = 'extracted');

\echo ''
\echo '================ 7. CORPUS SHAPE -- per jurisdiction'
SELECT * FROM v_corpus_health ORDER BY source_id;

\echo ''
\echo '================ 8. WHAT NEEDS A HUMAN'
WITH latest_ocr AS (
  SELECT DISTINCT ON (v.document_id) v.document_id,v.outcome
    FROM extraction_verification v JOIN audit_document d ON d.id=v.document_id
   WHERE v.verifier LIKE 'nizam.verify_ocr/%'
   ORDER BY v.document_id,v.verified_at DESC,v.id DESC)
SELECT (SELECT count(*) FROM latest_ocr WHERE outcome='review')        AS ocr_quality_review,
       count(*) FILTER (WHERE lane = 'E4' AND language = 'ur')         AS urdu_ocr_documents,
       count(*) FILTER (WHERE lane = 'E3' AND verification_state='review'
                         AND EXISTS (SELECT 1 FROM text_block b
                                      WHERE b.document_id=audit_document.id
                                        AND b.confidence IS NOT NULL)) AS hybrid_ocr_review,
       count(*) FILTER (WHERE empty_pages > 0)                         AS documents_with_unread_pages,
       (SELECT coalesce(sum(empty_pages), 0) FROM audit_document)      AS pages_never_read
  FROM audit_document;
