-- Lead, 20 Oct 2026. Migration 0065: document 4642 (observation 1282, Balochistan Code docid 892, catalogued 'The
-- Balochistan Motor Vehicles (Amendment) Act, 2020') is a BILL, superseded by its enactment: document 4704, Act No. XIV
-- of 2021 (Provincial Assembly notification No.PAB/Legis:V(06)/2021 of 5 May 2021; passed 26 April 2021, assented 4 May
-- 2021), released as instrument 2c2ffcaa. Run with -v export_sha=<sha256 of the owner's export>.
--
-- 4642 (OCR revision of 4524) p1 prints 'A / BILL' and s.1(1) '... Act, 2020'; its parking table is headed 'Proposed
-- Rates'; p4 ends with the Bill's notes and 'Statement of object and reasons.'. The enacted text differs: e.g. moving
-- row 1 LTV/HTV 1000 (Bill) against 1500 (Act). Owner: decision-review-2026-10-20-4642-4704.json, 4642 q2 'keep-4704'.
\set ON_ERROR_STOP on
BEGIN;
INSERT INTO source_non_authoritative_copy
    (source_observation_id, document_id, kind, authoritative_document_id, observed,
     owner_decision, evidence, recorded_by)
SELECT 1282, 4642, 'bill_superseded_by_enactment', 4704,
       'The Balochistan Code copy prints "A BILL further to amend the Balochistan Motor Vehicles Ordinance, 1965" with '
       's.1(1) "... (Amendment) Act, 2020", a parking table headed "Proposed Rates", and the Bill''s notes and Statement '
       'of object and reasons. The enacted law is Act No. XIV of 2021 (document 4704, the Provincial Assembly''s '
       'publication), whose Twelfth Schedule rates differ (e.g. moving row 1 LTV/HTV: Bill 1000, Act 1500).',
       jsonb_build_object('export', '.artifacts/decision-review/exports/decision-review-2026-10-20-4642-4704.json',
                          'document_id', 4642, 'question_id', 'q2', 'choice', 'keep-4704'),
       jsonb_build_object(
         'copy_sha256', (SELECT sha256 FROM document WHERE id = 4642),
         'authoritative_sha256', (SELECT sha256 FROM document WHERE id = 4704),
         'finding', 'bill_superseded_by_enactment',
         'reviewer_type', 'assistant',
         'basis', '4642 p1 "A BILL" (claude/renders/doc4524-p1.png); the Provincial Assembly Acts list: The Balochistan '
                  'Motor Vehicle (Amendment) Act XIV of 2021, passed 26/04/2021, assented 04/05/2021; 4704 p1 '
                  'notification No.PAB/Legis:V(06)/2021 (owner-reviewed OCR); row 1 LTV/HTV 1000 vs 1500',
         'enactment_url', 'https://pabalochistan.gov.pk/storage/4228/2021-07-19_11_22_31_8c6cc.pdf',
         'acts_list_url', 'https://pabalochistan.gov.pk/acts',
         'export_sha256', :'export_sha'),
       'claude.non-authoritative-review/1'
 WHERE NOT EXISTS (SELECT 1 FROM source_non_authoritative_copy WHERE source_observation_id = 1282);
COMMIT;
SELECT id, document_id, kind, authoritative_document_id FROM source_non_authoritative_copy WHERE source_observation_id = 1282;
