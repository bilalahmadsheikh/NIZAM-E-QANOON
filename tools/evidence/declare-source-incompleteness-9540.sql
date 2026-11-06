--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9540, The Native Passenger Ships Act, 1870 (Act No. XII of 1870).
-- Observation 10711, https://drs.molaw.gov.pk/pdf/The%20Native%20Passenger%20Ships%20Act%2C%201870.pdf, SHA-256 0ae24fc3ae023933b03204fb4f2919563e90375ba1bf8925aa5189dbe10eb129.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9540, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 10711 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 10711 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 10711 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 10711, 9540, 'no_complete_copy_acquired', NULL,
       'PDF page 2 (printed page 165) ends with section 6''s opening words ''No Native Passenger Ship shall depart or proceed upon any such voyage from any Port or place appointed under this Act,''; on PDF page 3 (printed page 166) the left column is faded past reading and the right column resumes legibly with section 13.',
       'The rest of section 6, and sections 7 to 12 (with section 12''s opening; the end of 12(2) and 12(3)-(4) show in the right column but cannot be attached to a readable section number).',
       'All six rendered pages read. The copy is complete in its pages, but the left column of printed page 166 is faded almost blank in this scan: only scattered line-ends can be seen, no section number is legible, and no text can be read. Released under the owner''s delegation with the unreadable column recorded; the visible fragments are set aside and nothing is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 0ae24fc3...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '0ae24fc3ae023933b03204fb4f2919563e90375ba1bf8925aa5189dbe10eb129',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc9540-p1.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9540-p2.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9540-p3.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9540-p4.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9540-p5.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9540-p6.png'),
         'render_sha256', jsonb_build_array('24dfe6e1accb5b15793ab3131858cd5e454f5abb5ba7463f3875384ae9ab95d8', 'cf2d9c6492457d9bfa5eeb0d8d23b0aaa3d4d7ee93be3cc576c92942ecb377f2', 'edfd2a400837e7fbb34c0edee8a0d18289aef3fad2aa543a55b234f554d2b953', '23d497f64f4e38f84ca7d8520391c8a2bbc0c8d96ef34cd8a52646909fd68368', '3e8d52ebfb249b0a61bdefce36afd0209d04c0eeda5117394f54182755c535a1', 'c97087ba4781862af0c53263ccd9a03cbc4f9907fc6d3c296cb584c59af3711d'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'printed page 166, left column (faded past reading): rest of section 6, sections 7-11 and the opening of section 12; and the right column''s first lines (end of 12(2), 12(3), 12(4)), set aside with it', 'last_printed_block_id', 2543673, 'resumes_block_id', 2543741)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9540, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'find a legible print of Act No. XII of 1870 (the Gazette of India of 2 April 1870, Part IV, or the Unrepealed General Acts volume) and recover_acquisition.py --alternate-for 10711 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 10711
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10711);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10711) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 10711: run tools/record_source_refetch.py --observation 10711 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 10711;
