--
-- By Codex (10 Nov 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9305, Finance (Revised) Ordinance1988 and21separately issued embedded instruments/notices.
-- Observation 12283, https://drs.molaw.gov.pk/pdf/XXII-%20The%20Finance%20%28Revised%29%20Ordinance%2C%201988.pdf, SHA-256 550d25d5c895989ba68a2f7e402ebeea1a83b55662e088dcaee7c699818ae94e.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9305, q3
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 12283 --apply (done 10 Nov 2026, acquisition_attempt226); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 12283 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 12283 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 12283, 9305, 'no_complete_copy_acquired', NULL,
       'The acquiredFinanceOrdinance includes CustomsFirstSchedule interpretationRules1-6 on physical28-29; physical30 contains only reference chapter contents. Physical31 begins a separateTaxLaws(Repeal)OrdinanceXXIII.',
       'ActualCustomsTariff chapter bodies referenced by contents1-16, printedpage references1026onward, and any remainder of that separately referenced tariff publication are not acquired in this76pagePDF.',
       'Root individually read all76original page images; independent source slices1-22,23-46and47-76 were audited. Page29 expressly refers to theGazette26.10.1988. Page30lists tariffchapter headings, not tariffentries/body. No such chapter bodies occur among the22issued source identities. Refetch226of the officialURLon10November2026 returned HTTP200and the identical53637074byte source ( SHA550d25d5c895989ba68a2f7e402ebeea1a83b55662e088dcaee7c699818ae94e). No complete tariff copy was acquired by this attempt. The actual interpretationRules are retained; missing chapter words are not synthesized.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 550d25d5...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '550d25d5c895989ba68a2f7e402ebeea1a83b55662e088dcaee7c699818ae94e',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc9305-p27.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9305-p28.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9305-p29.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9305-p30.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9305-p31.png'),
         'render_sha256', jsonb_build_array('244d320f59e21245cd50fe7dba48287d23eb811a84ab552be631662e1bb6b333', 'e0de5659de25147af3212c21f7b9708fdd8ffdee26664569f38972333b104f50', '07188d74fb778b1348a3dcc8dfa40dda27c8aaac34ab2e41c5968827dccd7f87', '819df651b6790784c92d6fb9524e938f149d4fb6344be3b55e1fa330180defc7', '52e2fd5d9709f58cc1a8ae6308762365960702ac6440ea57109accc8bf031eb6'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Actualtariffchapter bodies/pages referenced at physical30, beyond interpretationRules1-6. The acquired publication switches to independentOrdinanceXXIII after the referencecontents.', 'last_printed_block_id', 2450630, 'resumes_block_id', 2450631)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9305, 'question_id', 'q3', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'Acquire and individually read the referencedGazetteofPakistanExtraordinaryPartI26October1988CustomsTariff pages1026onward, then add a new source observation and reviewed expressions; retain the present immutablePDF and declared limitation.'),
       'codex.source-incompleteness-review-9305/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 12283
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 12283);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 12283) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 12283: run tools/record_source_refetch.py --observation 12283 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 12283;
