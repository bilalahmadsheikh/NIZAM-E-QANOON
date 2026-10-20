-- DRAFT by agent K6 (17 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-ocr-4575.sh (step 3). Pattern: declare-source-incompleteness-4565.sql
-- and -4646.sql.
--
-- Document 4575, THE INSTITUTE OF OPHTHALMOLOGY AND VISUAL SCIENCES EMPLOYEES PAY SCALES RULES, 2021 (Sindh Govt.
-- Gazette Ext., 27 September 2021, gazette pages 1065-1076), observation 4734
-- (https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-21-000041.pdf,
-- SHA-256 ef85a28c8bfb02fc694c16a2b4a6e777c244d721a0163ec5fb50e1a7c95350a1, twelve pages, scanned: lane E4). The row names
-- the ACTIVE OCR-PROMOTED REVISION of 4575 (same blob, so the 0054 guard accepts it), which is the revision that releases;
-- the file refuses unless that revision exists.
--
-- The copy scans gazette page 1069 TWICE (PDF pp5 and 6; p6 carries a handwritten corner mark '62') and never prints gazette
-- page 1070. PDF p7 (gazette 1071) opens with '(3) The expression "scale of pay" ...', the last sub-rule of rule 12, then
-- '13. Fixation of Pay on Reversion ...'. So rules 9, 10, 11 and rule 12(1)-(2) are not in this copy.
--
-- Owner decision: .artifacts/decision-review/exports/decision-review-2026-10-17-4575.json, document 4575, q2
-- 'release-with-gap' (the owner in chat, 17 Oct 2026: "Release now with gap (Recommended)"); it supersedes, for now, the
-- route of q1 'use-4565-page' (the page-supplement feature, draft migration 0065, is deferred after its schema review).
-- The rules release as printed; the duplicate scan is set aside; rules 9-12(2) are recorded here; the orphan 12(3) at the
-- top of PDF p7 is set aside as non-citable (it cannot be cited as rule 12(3) without rule 12, and must not join rule 8).
-- Nothing is supplied.
--
-- The missing page IS on file elsewhere: document 4565 (observation 4721) carries gazette pages 1069-1076 of these Rules as
-- its own pp5-12, and its p6 = gazette 1070 was re-OCR'd (Surya candidate 1656) and owner-accepted on 17 Oct 2026. It is
-- named below as the recovery path for when the supplement feature is built; this record does not use it.
--
-- Read from the renders (agent K6, 17 Oct 2026): .artifacts/ocr-review-pack-owner-2026-10-17/doc-4575/images/
--   page-005.png 09fb3d0b... folio 1069, running head, rule 4(5)(viii) to rule 8 (i)-(vi) '... lower grade pay shall not be
--                protected.', a handwritten corner mark '(2)';
--   page-006.png 48b65047... folio 1069 again, the same text word for word, the corner mark '62';
--   page-007.png 70ab66cf... folio 1071, running head, '(3) The expression "scale of pay" represents the maximum of the scale
--                which is to be taken into consideration for determining the authority competent to sanction increments
--                rather that the stage to which the advance increment has been given.', then rule 13.
--
-- ORDER (the lead script's step 6, after the promotion, segmentation and pin):
--   1. python tools/record_source_refetch.py --observation 4734 (dry run; --apply only if it is unchanged_copy or,
--      by the lead's decision of 17 Oct 2026, network_error -- sindhlaws.gov.pk was unreachable all day: the gap is
--      proven by the copy itself, the refetch only asks whether a complete copy is now served, so a failed one is
--      recorded as a dated attempt and the evidence says a refetch is owed. Never on a changed copy.)
--   2. this file (refuses unless step 1's attempt exists and the promoted revision exists).
-- Migration 0054 accepts this: its trigger checks only that the observation landed and that the document is of its
-- blob; neither the table nor v_source_incompleteness_* reads attempt outcomes (record 12, observation 3341, already
-- rests partly on a network_error attempt). The audit reports v_source_incompleteness_open and never fails on it.
-- Idempotent: a second run inserts nothing once a record stands for 4734.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4734 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4734 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM document WHERE supersedes_document_id = 4575 AND is_active) THEN
        RAISE EXCEPTION '4575 has no active promoted revision: promote it first (lead-ocr-4575.sh step 2)';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4734,
       (SELECT id FROM document WHERE supersedes_document_id = 4575 AND is_active ORDER BY id DESC LIMIT 1),
       'no_complete_copy_acquired', NULL,
       'PDF page 5 (gazette page 1069) ends with rule 8 (vi) "That in case of regular appointment in lower grade pay shall '
       'not be protected." (and a handwritten corner mark "(2)"); PDF page 6 is a second scan of gazette page 1069; PDF page 7 (gazette '
       'page 1071) opens with "(3) The expression "scale of pay" represents ..." (the last sub-rule of rule 12) and then '
       'rule 13. Gazette page 1070 is not in the copy.',
       'Gazette page 1070: rule 9 (Withdrawal of increment), rule 10 (Conditions of Service for Increments) (i)-(iv), rule 11 '
       '(Calculation of increments) (1)-(4) and rule 12 (Grant of Advance Increments) (1)-(2), whose sub-rule (3) is '
       'printed at the top of gazette page 1071 -- as gazette page 1070 is printed in document 4565''s PDF page 6.',
       'PDF pages 5, 6, 7 and 9 read on their renders (agent K6, 17 Oct 2026); all twelve through the owner-reviewed '
       'OCR (ocr-review-doc-4575.json, candidates 861-872 accepted). pp1-4 (gazette pages 1065-1068): the notification '
       'and rules 1 to 4(5)(vii); p5 (1069): rule 4(5)(viii) to rule 8 (vi) and a handwritten corner mark "(2)"; p6: '
       'folio 1069 again, rule 4(5)(viii) to rule 8 word for word, and a handwritten corner mark "62" (the owner: "Page '
       'image is a duplicate scan of page 5 (Gazette p.1069)"); p7 (1071): rule 12 (3), rules 13-16; pp8-12 '
       '(1072-1076): rules 17-39, the signature "EXECUTIVE DIRECTOR" and the imprint. Rules 1-8 and 13-39 release as '
       'printed; the duplicate scan and the orphan rule 12 (3) are set aside, not citable.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same twelve-page PDF (SHA-256 ef85a28c...); no copy '
                 'printing gazette page 1070 was obtained.'
            WHEN NOT bool_or(outcome = 'unchanged_copy') AND bool_or(outcome = 'network_error')
            THEN 'The official URL could not be reached (dated refetch: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '); sindhlaws.gov.pk was unreachable on 17 Oct 2026. The gap rests on the copy itself (gazette folio '
                    'run 1069|1069|1071 on PDF pp5-7); whether a complete copy is now served is unverified -- a refetch '
                    'is owed.'
            ELSE 'Dated refetches returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing gazette page 1070 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'render_artifact', jsonb_build_array(
           '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4575/images/page-005.png',
           '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4575/images/page-006.png',
           '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4575/images/page-007.png'),
         'render_sha256', jsonb_build_array(
           '09fb3d0b3012634d8ebef57c3cbe93f064528e3ef181dc0b5d1fc7cc22c545ee',
           '48b650477587fc00c713a56570ab1bf1e9b3eb17f31aca8f16afff5e9d892695',
           '70ab66cfb7b15788238214d805d2fb651ef3fa5db80e132cf7e909eb03500263'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', 'gazette page 1070: rules 9, 10, 11 and rule 12 (1)-(2)',
                              'between', 'rule 8 (vi) (PDF p5) and rule 12 (3) (PDF p7)')),
         'set_aside', jsonb_build_array(
           jsonb_build_object('what', 'PDF page 6, a second scan of gazette page 1069 (corner mark ''62'')',
                              'how', 'source_apparatus_blocks (K6 reading on p5)'),
           jsonb_build_object('what', 'the orphan rule 12 (3) at the top of PDF p7 and the p7 folio ''1071''',
                              'how', 'source_apparatus_blocks (K6 reading on p7): non-citable; not attached to rule 8'),
           jsonb_build_object('what', 'the handwritten corner marks ''(2)'' (PDF p5) and ''(3)'' (PDF p9)',
                              'how', 'source_apparatus_blocks'),
           jsonb_build_object('what', 'the Gazette folios, p1''s masthead foot, the signature and the imprint',
                              'how', 'source_apparatus_blocks (page furniture; authentication)')),
         'gap_proof', jsonb_build_object(
           'basis', 'the copy itself: gazette folio run 1069|1069|1071 on PDF pp5-7 (p6 a duplicate scan of p.1069); '
                    'p7 opens mid-rule 12 with sub-rule (3)',
           'renders', jsonb_build_array('page-005.png', 'page-006.png', 'page-007.png')),
         'refetch', jsonb_build_object(
           'outcomes', jsonb_agg(DISTINCT outcome),
           'complete_copy_checked', bool_or(outcome = 'unchanged_copy'),
           'owed', NOT bool_or(outcome = 'unchanged_copy'),
           'note', CASE WHEN bool_or(outcome = 'unchanged_copy')
                        THEN 'the portal served the same PDF'
                        ELSE 'the portal (sindhlaws.gov.pk) was unreachable on 17 Oct 2026; the refetch only checks '
                             'whether a complete copy is now available, so it is owed: rerun tools/record_source_refetch.py '
                             '--observation 4734 when the portal answers, and supersede this record if it serves a '
                             'different copy'
                   END,
           'lead_decision', 'lead, 17 Oct 2026: record the failed refetch as a dated network_error attempt and proceed '
                            'with the gap; the gap is proven by the copy'),
         'readings', '.artifacts/release-work-2026-09-24/claude/agK6/patch-<promoted id>.json (work/agK6-mk_4575.py; simulated: patch-4575-sim.json)',
         'recovery_path', jsonb_build_object(
           'document_id', 4565, 'source_observation_id', 4721, 'page', 6, 'gazette_page', 1070,
           'ocr_candidate_id', 1656, 'owner_adjudication', 'accepted 2026-10-17',
           'feature', 'source_page_supplement (draft migration 0065; schema review '
                      'claude/review-0065-source-page-supplement.md: APPROVE WITH CHANGES; deferred)'),
         'owner_decision', jsonb_build_object(
           'source', '.artifacts/decision-review/exports/decision-review-2026-10-17-4575.json',
           'date', '2026-10-17', 'document_id', 4575, 'question_id', 'q2', 'choice', 'release-with-gap',
           'supersedes_route', 'q1 use-4565-page (deferred)',
           'pattern', jsonb_build_array(510, 2205, 4565, 4646))),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4734
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4734);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4734) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4734: run tools/record_source_refetch.py '
                        '--observation 4734 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, document_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 4734;
