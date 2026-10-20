--
-- DRAFT by agent JC (13 Oct 2026, prepare mode; NOT RUN). Pattern: declare-source-incompleteness-2211.sql.
--
-- Document 3551, Nippon Institute of Advanced Sciences Act, 2026 -- a Pakistan Code copy, 32 pages.
-- Section 44 breaks off mid-sentence on p30: '44. First Statutes and Regulations.- Notwithstanding anything to the
-- contrary contained in this Act, the President of Pakistan shall promulgate the First Statues and' -- then a stray
-- run of First Statutes text (statute 2(3)-(7), p30, and statute 3, p31) that the Schedule prints again (pp31-32).
-- The rest of s.44 is printed nowhere.
--
-- Observation 880 (source_id pk-federal),
-- https://pakistancode.gov.pk/pdffiles/administratorbd29a0c74895412eb54fbc9bff81b02a.pdf,
-- SHA-256 83a1902269a1e29419e6af74c227d532ac4390462d45e06b5fb6e2bc96f7e666.
-- A dry run of tools/record_source_refetch.py --observation 880 on 2026-10-13 returned HTTP 200, application/pdf,
-- 378717 bytes, SHA-256 83a19022... = the held blob ('unchanged_copy'); it recorded nothing (prepare mode).
--
-- Owner decision: decision-review-2026-10-12-j.json (export k is a superset and may be cited), document 3551, q1
-- 'release-as-is': s.44 is kept with its printed words only and recorded as cut short in this copy (source
-- incompleteness); the stray run between s.44 and the Schedule is set aside as non-citable duplicate text; the
-- Schedule's First Statutes 1-3 are the citable statutes and contents row '3' links to Schedule statute 3.
--
-- Readings: .artifacts/release-work-2026-09-24/claude/agJC/patch-3551.json (p30 blocks 408417-408426 and p31 block
-- 408428 set aside; dry run 2 will record / 0 refused). Under unreleased-v4 with no extra rule: 487 paths, dup [],
-- S7 [], contents row '3' (ordinal 44) linked to Schedule statute 3 (block 408459).
--
-- Read from the renders on 2026-10-13 (agent JC): p30 (s.42, s.43, s.44 cut, the stray (3)-(7)), p31 (stray
-- statute 3, then SCHEDULE / THE FIRST STATUTES 1-2), p32 (statute 2(2)-(7) and 3). The render SHA-256 values are
-- those recorded in agJC/pin-3551.json (pages 2, 30, 31, 32) -- copy them into render_sha256 below before running.
--
-- ORDER (see migration 0060):
--   1. python tools/record_source_refetch.py --observation 880 --apply
--      If it reports a DIFFERENT valid PDF it records nothing: land and read that copy first -- this file then
--      refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   No contents reading follows: contents row 44 links to s.44 as printed, row '3' to Schedule statute 3.
--
-- Idempotent: a second run inserts nothing once a record stands for 880.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 880 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 880 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 880, 3551, 'no_complete_copy_acquired', NULL,
       'Page 30 ends section 44 mid-sentence: "... the President of Pakistan shall promulgate the First Statues and"; '
       'the next printed text is a stray copy of First Statute 2(3)-(7) and statute 3, then the Schedule.',
       'The rest of section 44 ("First Statutes and Regulations"), named in the contents (p2) as row 44.',
       'All 32 rendered pages available; pages 30-32 read for this record. p30: ss.42, 43 and 44, s.44 stopping at '
       '"... shall promulgate the First Statues and", then "(3) The quorum for a meeting of a board of faculty ..." to '
       '"(7) The Dean shall have such powers and duties ..." (word for word statute 2(3)-(7) of the Schedule). p31: '
       '"3. Appointment of committees by Authorities.--..." (statute 3 again), then "SCHEDULE (See section 2, 30 and '
       '31) THE FIRST STATUTES" with statutes 1 and 2. p32: statute 2(2)-(7) and statute 3. The end of s.44 is printed '
       'nowhere. The stray run is set aside as non-citable duplicate text (owner); released as printed, nothing '
       'supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same 32-page PDF (SHA-256 83a19022...); no copy '
                 'printing the rest of section 44 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing the rest of section 44 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '83a1902269a1e29419e6af74c227d532ac4390462d45e06b5fb6e2bc96f7e666',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc3551-p30.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3551-p31.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3551-p32.png'),
         'render_sha256', jsonb_build_array(
           '4e98e1765269020184dd3f7046914f57e20c2134a0ecc9cf1801275926427855',
           'fd60177d4dd8162a9cf3b7cba985f302024783a9125ecc895a63b14d5d825771',
           '3f16cd4a3215b0d29e5fe90720809faf632bfa31ed71038aeca98604f9c3b842'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', 'the end of section 44 after "... shall promulgate the First Statues and"',
                              'last_printed_block_id', 408416)),
         'set_aside_duplicate_run', jsonb_build_object(
           'blocks', jsonb_build_array(408417, 408418, 408419, 408420, 408421, 408422, 408423, 408424, 408425,
                                       408426, 408428),
           'what', 'First Statute 2(3)-(7) (p30) and statute 3 (p31), printed again in the Schedule (pp31-32)',
           'treatment', 'set aside (source_apparatus_blocks), kept in the source, not citable'),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
           'document_id', 3551, 'question_id', 'q1',
           'choice', 'release-as-is', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record; the end of '
                         's.44 is not supplied.',
         'recovery_path', 'find a Gazette copy of the Nippon Institute of Advanced Sciences Act, 2026 printing s.44 '
                          'in full, then recover_acquisition.py --alternate-for 880 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 880
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 880);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 880) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 880: run '
                        'tools/record_source_refetch.py --observation 880 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 880;
