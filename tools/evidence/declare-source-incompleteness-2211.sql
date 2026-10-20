--
-- Drafted by agent CR (10 Oct 2026, prepare mode); renamed without the draft suffix and run by builder BZ on
-- 10 Oct 2026 after the dated refetch.
-- Pattern: tools/evidence/declare-source-incompleteness-510.sql / -1121.sql / -1247.sql / -1822.sql.
--
-- Document 2211, SINDH COUNCILS UNIFIED GRADE SERVICE DEPARTMENTAL EXAMINATION & TRAINING RULES, 1996: the landed
-- copy prints rules 1, 2 and 3(1) and then jumps to the tail of Schedule-II's syllabus; everything between is not
-- printed. Pages 3-4 bind a second, earlier and equally incomplete instrument.
--
-- Observation 4665, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-16-000496.pdf,
-- SHA-256 9b68c550dbe5db43f43680ddf92bfe30ccdfd78c50baafc54bdd232fce602d7b, five pages (p5 blank).
--
-- Owner decision: decision-review-2026-10-10-i.json, document 2211, q1, choice "release-as-is" (reviewer Bilal
-- Ahmad), no note. The choice's effect: "The 1996 Rules are released with rules 1, 2 and 3(1) and the printed
-- syllabus fragments; the missing text is recorded as source incompleteness (migration 0054); pp3-4 (the 1995
-- notification) are set aside as a bound second instrument (flagged). What is lost: most of rule 3 onwards and both
-- Schedules."
--
-- Read from the renders on 2026-10-10 (agent CR): p1 (ae5fa1d7...) the notification of 18 April 1996 (No.
-- SO(VI)6-34/93), '1. SHORT TITLE & COMMENCEMENT' 1)-2), '2. DEFINITIONS.' a)-g) ('b) "Appointing Authority"' with
-- no definition printed), '3. EXAMINATION ITS SYLLABUS & TRAINING.' '(1) ... the papers in the subjects mentioned in
-- Schedule-I with the syllabus mentioned in Schedule-II and undergo such training as the Government may in
-- consultation with the Academy law down.' -- the page ends there. p2 (a237d85c...) begins '4. Municipal Committee
-- Street Rules, 1962.', '5. Duties & Functions of Local Councils Engineer.', '6. Local Government Ordinance, 1979
-- (Relevant Chapter).', then 'IV. SYLLABUS FOR MEDICAL/HEALTH BRANCH.' items 1-11, the authentication 'SECRETARY TO
-- GOVERNMENT OF SINDH', 'NO. SO(VI)6-34/93, Karachi, dated the 18th April, 1996.', the endorsement and distribution
-- list 1-5 and '(WASEEM HYDER KHAN) SECTION OFFICER-VI'. p3 (bfbda5c9...) a separate notification ('Karachi, dated,
-- 1995.', No. SO(VI)6-34/93) of the 'Sindh Councils Unified Grade Service (Departmental Examination & Training),
-- Rules, 1994': short title (1)-(2), 2 (a)-(g), 3 (1), '4. EXAMINATION & SECURITY' (1), a second '2. EXAMINATION'
-- (1)-(2); p4 (440b8a33...) jumps to 'V. SYLLABUS FOR MEDICAL/HEALTH BRANCH' 01-11, 'NO. SO(VI)G-34/93, Karachi,
-- dated 14th September 1995', endorsement, distribution list 1-5 and the signature. p5 (e53964e4...) is blank.
--
-- Prepared tree (claude/agCR/patch-2211.json, v4 + agent CR rule K `unlabelled_schedule_before_row`): rules 1, 2
-- (clauses a-g), 3 (sub-rule (1)); an unheaded SCHEDULE holding the printed fragment -- items 4-6 and the caption
-- 'IV. SYLLABUS FOR MEDICAL/HEALTH BRANCH.' over items 1-11; pp3-4 and the p2 apparatus set aside.
--
-- A dry run of tools/record_source_refetch.py --observation 4665 on 2026-10-10 returned HTTP 200, application/pdf,
-- 200657 bytes, SHA-256 9b68c550... = the held blob ('unchanged_copy'); it recorded nothing (prepare mode). No other
-- copy of the 1996 Rules (or of the 1994 Rules) is in the corpus (instrument titles searched 2026-10-10).
--
-- ORDER (see migration 0060):
--   1. python tools/record_source_refetch.py --observation 4665 --apply
--      If it reports a DIFFERENT valid PDF it records nothing: land and read that copy first -- this file then
--      refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   No contents reading follows: the copy prints no contents list (toc_found false).
--
-- Idempotent: a second run inserts nothing once a record stands for 4665.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4665 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4665 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4665, 2211, 'no_complete_copy_acquired', NULL,
       'Page 1 ends inside rule 3 after sub-rule (1) ("... undergo such training as the Government may in '
       'consultation with the Academy law down."); page 2 resumes at item "4. Municipal Committee Street Rules, '
       '1962." of a syllabus list. Nothing between is printed.',
       'The rest of rule 3 and any later rules of the 1996 Rules; Schedule-I (the subjects of the examination, named '
       'by rule 3(1)); Schedule-II (the syllabus, named by rule 3(1)) Parts I-III and items 1-3 of the part whose '
       'items 4-6 open page 2.',
       'All five rendered pages read. p1: the 18 April 1996 notification, rules 1, 2 (a)-(g) and 3(1). p2: syllabus '
       'items 4-6, "IV. SYLLABUS FOR MEDICAL/HEALTH BRANCH." items 1-11, the authentication, endorsement and '
       'distribution list. pp3-4: a separate 1995 notification of the "Sindh Councils Unified Grade Service '
       '(Departmental Examination & Training), Rules, 1994", itself breaking off after a second "2. EXAMINATION" '
       '(1)-(2) and resuming at "V. SYLLABUS FOR MEDICAL/HEALTH BRANCH"; set aside, not released (owner). p5: blank. '
       'Released at owner direction as printed: rules 1, 2 and 3(1) and the printed syllabus fragment, nothing '
       'supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same five-page PDF '
                 '(SHA-256 9b68c550...); no copy printing the rest of the 1996 Rules or its Schedules was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy of the 1996 Rules was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '9b68c550dbe5db43f43680ddf92bfe30ccdfd78c50baafc54bdd232fce602d7b',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc2211-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2211-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2211-p3.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2211-p4.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2211-p5.png'),
         'render_sha256', jsonb_build_array(
           'ae5fa1d770c96b82b2ff30a1a20a80358927eab647e353f2cf8e134d9c3cb03c',
           'a237d85c13e75a3ee19fcf1eff4ea3e89ffeae4f7861e97267b45db4f4cd1cec',
           'bfbda5c9f06801fd11b7fe73904d6caf8f8decfda511ab74518cafd683254c8d',
           '440b8a33866d1a9e1fcf4d509cb550cdd73d2189f7a17edeace14fd3ed9b6072',
           'e53964e458a15d12988dc356734f0cec174358716a545e76a4ac8ac61bd6570a'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', 'rule 3 after sub-rule (1), and any later rules',
                              'last_printed_block_id', 169909),
           jsonb_build_object('what', 'Schedule-I (subjects of the examination)', 'named_by', 'rule 3(1)'),
           jsonb_build_object('what', 'Schedule-II (syllabus) Parts I-III and items 1-3 of the part continued on p2',
                              'named_by', 'rule 3(1)', 'first_printed_block_id', 169910)),
         'bound_second_instrument', jsonb_build_object(
           'pages', jsonb_build_array(3, 4),
           'what', 'notification of 1995 (No. SO(VI)6-34/93; distribution dated 14 September 1995) of the Sindh '
                   'Councils Unified Grade Service (Departmental Examination & Training), Rules, 1994',
           'state', 'incomplete: breaks off after a second "2. EXAMINATION" (1)-(2) and resumes at Syllabus V',
           'treatment', 'set aside (source_apparatus_blocks), kept in the source, not citable, not released'),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-10-i.json',
           'document_id', 2211, 'question_id', 'q1',
           'choice', 'release-as-is', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction as printed: rules 1, 2 and 3(1) and the printed syllabus '
                         'fragment (an unheaded Schedule); the missing text is not reconstructed; pp3-4 are set aside.',
         'recovery_path', 'find the Sindh Government Gazette copy of the 18 April 1996 notification No. '
                          'SO(VI)6-34/93 with its Schedules, then recover_acquisition.py --alternate-for 4665 '
                          '--url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4665
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4665);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4665) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4665: run '
                        'tools/record_source_refetch.py --observation 4665 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 4665;
