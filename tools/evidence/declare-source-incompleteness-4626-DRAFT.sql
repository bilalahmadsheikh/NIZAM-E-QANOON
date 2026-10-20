-- DRAFT by agent K6 (18 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-ocr-4626.sh (step 6). Pattern: declare-source-incompleteness-4575-DRAFT.sql
-- (record 28, the 4575 network_error ruling) and -4646.sql.
--
-- Observation 4548: the Sindh Government Gazette of Thursday 12 March 2020 (No. 12), twelve pages, catalogued as 'CONSTITUTION
-- AND REGULATION OF THE SINDH COUNCILS UNIFIED GRADES (SERVICE) RULES, 2020'. The row names the ACTIVE OCR-PROMOTED REVISION
-- that supersedes document 4626 (same blob, so the 0054 guard accepts it); the file refuses unless that revision exists.
--
-- PDF page 1 is gazette page 298: the issue's cover and the S&GAD (Regulation Wing) notification No. SORI(SGA&CD)3-76/2019 of
-- 3 March 2020 amending the Sindh Civil Servants (Appointment, Promotion & Transfer) Rules, 1974 -- 'AMENDMENTS / 1. In rule
-- 2- / i. for clauses (d) and (e), the following shall be substituted :- "(d) ... (e) ... Basic Pay Scale 15 and below";' --
-- and the page ends there. PDF page 2 is gazette page 302: it opens inside another notification (an officers' list 1-12, its
-- para 2 and the signature LAEEQ AHMED) before the SCUG (Service) Rules begin. Gazette pages 299-301 are not in the copy.
--
-- Owner decisions: export m (decision-review-2026-10-16-m.json) 4626 q1 'split' -- the APT amendment notification is its own
-- instrument (E1 of the plan); decision-review-2026-10-18-4598-4626.json 4626 q2 'release-with-gap' -- it is released as far
-- as printed, gazette pp.299-301 recorded here. Nothing is supplied.
--
-- Read from the renders (agent K6, 18 Oct 2026): .artifacts/ocr-review-pack-owner-2026-10-17/doc-4626/images/
--   page-001.png d4f32ae9... cover, CONTENTS, PART-I, the S&GAD notification to the substituted clause (e), foot line '(298)';
--   page-002.png 3a32ab87... head '302', the officers' list 1-12, para 2, signature, then the Local Government Department
--                notification making the SCUG (Service) Rules 2020.
--
-- ORDER (the lead script's step 6, after the promotion, the first segmentation and the pin):
--   1. python tools/record_source_refetch.py --observation 4548 (dry run; --apply only if it is unchanged_copy or, by the
--      lead's ruling of 17 Oct 2026 for 4575, network_error while the portal is unreachable -- the gap is proven by the copy
--      itself, gazette page run 298|302; a refetch is then owed. Never on a changed copy.)
--   2. this file (refuses unless step 1's attempt exists and the promoted revision exists).
-- Idempotent: a second run inserts nothing once a record stands for 4548.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4548 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4548 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM document WHERE supersedes_document_id = 4626 AND is_active) THEN
        RAISE EXCEPTION '4626 has no active promoted revision: promote it first (lead-ocr-4626.sh step 2)';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4548,
       (SELECT id FROM document WHERE supersedes_document_id = 4626 AND is_active ORDER BY id DESC LIMIT 1),
       'no_complete_copy_acquired', NULL,
       'PDF page 1 (gazette page 298) ends the S&GAD notification of 3 March 2020 with the substituted clause "(e) '
       '"Departmental Selection Committee" means a Committee constituted for the purpose of making selection for initial '
       'appointment to the posts under a Department or Office of Government in Basic Pay Scale 15 and below";" and the '
       'foot line "(298)"; PDF page 2 is gazette page 302, opening inside another notification. Gazette pages 299-301 are '
       'not in the copy.',
       'Gazette pages 299-301: the rest of the S&GAD (Regulation Wing) notification No. SORI(SGA&CD)3-76/2019 of 3 March '
       '2020 amending the Sindh Civil Servants (Appointment, Promotion & Transfer) Rules, 1974 (any further amendments and '
       'its authentication), and the opening of the notification whose officers'' list 1-12 continues on gazette page 302.',
       'PDF pages 1-12 read on their renders (agent K6, 18 Oct 2026). p1 (gazette 298): the cover (KARACHI THURSDAY MARCH '
       '12, 2020, No. 12, CONTENTS: PART I pages 298-321), PART-I, NOTIFICATIONS BY THE GOVERNMENT OF SINDH, the S&GAD '
       'notification, AMENDMENTS, item 1 with i. and the substituted clauses (d) and (e), the foot line "L.iv 182  I - 28  '
       '(298)  Price Rs. 126.09"; p2 (gazette 302): the officers'' list 1-12, para 2, the signature LAEEQ AHMED, then the '
       'Local Government Department notification of 20 February 2020 and the SCUG (Service) Rules 2020 to p12. The APT '
       'amendment notification (E1) releases as far as printed; the officers'' list is set aside (outside every span).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same twelve-page PDF (SHA-256 4c6bc708...); no copy '
                 'printing gazette pages 299-301 was obtained.'
            WHEN NOT bool_or(outcome = 'unchanged_copy') AND bool_or(outcome = 'network_error')
            THEN 'The official URL could not be reached (dated refetch: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '). The gap rests on the copy itself (gazette page run 298|302 on PDF pp1-2); whether a complete copy '
                    'is now served is unverified -- a refetch is owed.'
            ELSE 'Dated refetches returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing gazette pages 299-301 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'render_artifact', jsonb_build_array(
           '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4626/images/page-001.png',
           '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4626/images/page-002.png'),
         'render_sha256', jsonb_build_array(
           'd4f32ae9c9abef3dc6373b106cba000e822af5ca35e6556713b0ea4144e2973b',
           '3a32ab874861a3fe105c30b3121aabaf82d37b74296b19b23978431c07103f0f'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', 'gazette pages 299-301: the rest of the S&GAD notification of 3 March 2020 (plan '
                                      'expression 1) and the opening of the officers'' list notification',
                              'between', 'the substituted clause (e) (PDF p1) and the officers'' list item 1 (PDF p2)')),
         'expression', jsonb_build_object('ordinal', 1, 'title', 'Services, General Administration & Coordination '
           'Department (Regulation Wing) Notification No. SORI(SGA&CD)3-76/2019 dated 3 March 2020 (amendments in the '
           'Sindh Civil Servants (Appointment, Promotion & Transfer) Rules, 1974)'),
         'gap_proof', jsonb_build_object(
           'basis', 'the copy itself: gazette page run 298|302 on PDF pp1-2; p1 ends at the substituted clause (e) and p2 '
                    'opens inside another notification',
           'renders', jsonb_build_array('page-001.png', 'page-002.png')),
         'refetch', jsonb_build_object(
           'outcomes', jsonb_agg(DISTINCT outcome),
           'complete_copy_checked', bool_or(outcome = 'unchanged_copy'),
           'owed', NOT bool_or(outcome = 'unchanged_copy'),
           'note', CASE WHEN bool_or(outcome = 'unchanged_copy')
                        THEN 'the portal served the same PDF'
                        ELSE 'the portal was unreachable when the refetch was attempted; it is owed: rerun '
                             'tools/record_source_refetch.py --observation 4548 when the portal answers, and supersede '
                             'this record if it serves a different copy'
                   END,
           'lead_ruling', 'lead, 17 Oct 2026 (4575): a failed refetch is recorded as a dated network_error attempt and '
                          'the gap proceeds; the gap is proven by the copy'),
         'owner_decision', jsonb_build_object(
           'split', jsonb_build_object('source', '.artifacts/decision-review/exports/decision-review-2026-10-16-m.json',
                                       'document_id', 4626, 'question_id', 'q1', 'choice', 'split'),
           'gap', jsonb_build_object('source', '.artifacts/decision-review/exports/decision-review-2026-10-18-4598-4626.json',
                                     'document_id', 4626, 'question_id', 'q2', 'choice', 'release-with-gap'),
           'pattern', jsonb_build_array(510, 2205, 4565, 4646, 4575))),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4548
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4548);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4548) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4548: run tools/record_source_refetch.py '
                        '--observation 4548 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, document_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 4548;
