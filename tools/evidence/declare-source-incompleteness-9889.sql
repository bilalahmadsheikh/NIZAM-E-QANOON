--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9889, Historical Gazette source8364:8acquiredtexts, missing692andlocalreadingloss.
-- Observation 13202, https://drs.molaw.gov.pk/pdf/VIII-%20The%20Income%20Tax%20Act%2C%201872.pdf, SHA-256 09bae40ad602a738520fa1154c957fcdf0289de071778e81f2419d1b7849de01.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9889, q3
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 13202 --apply (done9Nov2026,attempt225); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 13202 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 13202 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 13202, 9889, 'no_complete_copy_acquired', NULL,
       'IncomeTax46andSchedule complete;Rules2887through32andforms/registers/returns;Police1088ends22;Contract117stops45mid-sentence and partial126resumes46,through266andSchedule59.',
       'IncomeTax46sections;Rules2887/32rules/templates;Contract266sectioncontents, including unavailable118-125and126head.',
       'All59acquiredimages individually source-reviewed. Printed692absent between691/693(original45/46), omitting117tail,118-125and126head. Local defocus/tear/gutter losses are explicitly[illegible] in audited source readings, including unknown templatecaption21 andPolice1088two village referents22. Rawsource conserved. This is no_complete_copy_acquired, not a claim no better copy exists.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 09bae40a...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '09bae40ad602a738520fa1154c957fcdf0289de071778e81f2419d1b7849de01',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p1.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p3.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p4.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p5.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p7.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p8.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p10.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p12.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p13.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p14.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p16.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p17.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p18.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p20.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p21.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p22.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p34.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p36.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p38.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p40.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p42.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p43.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p44.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p45.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p46.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p51.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p53.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p57.png', '.artifacts/release-work-2026-09-24/codex-8364-2026-11-09/doc9889-p59.png'),
         'render_sha256', jsonb_build_array('4102559bf97be1d06a968a114bcefef4c6586a1f0853485d3a72c868a572e42f', '8af0fce7c46561ca592f10baec014d1240b3abda583d6076f1ed334386477732', 'a38a140fb572e207ee1f9e235f88f5d9816a38078123b81b15da4d40393c02d7', '0cc8c6bca030febcf261813b5d9133249d6444ce4f1fa95b68996131ade2a922', '253c0e61520d7c93bdd1e59175488b48a9c9962534a7c07adad63018006793a3', '4dde2860434c9551848140b506bd3cdf792623f2c351cfd9c9d3a8b832716431', '065024126b236651ecca01a2527e5092f6513c6c143ce16c24fe13f8a539888e', '496c6648f7e09d1e25c3251351b7ed488fa528f9d0935211d841277660887b53', '6fe65785ffb9de8680f9ec269f8e8d7fc58cf9847dcc538d2371ce081249db9f', '0f0bf03ccd8cc02598c1c8668fb041d068d9d73d4fa7c5504dab8924f04c1834', 'd18a833185e45b638f07bd9c2a9f7b8531c88716e6e59bd33549ac03408fd225', '3e4bd832c7d8ee34f2172237ef477f0adbf2781e4adeb621de496c7c5c27d6db', '4c286cb7894032ff2834d5acaab21e7a32b1fe7c0c41d99122fabd7ceb035d41', 'f91f44eefcad46c41c96d91438a9bcc24c68fa032958780ee0f47648eb207746', '63864a998499330005b321f86baecc76cb48b93de4e43d005f394139c2a55aad', 'd432229c91b5240ee5cbd2a718441f9bdb24f7c7ea9e66520ecec6ac03a2b687', '4c629cac1dff83a5460b146192e8487f277e1be557ffb6c63bbfb1f1ce910cd6', 'b37148773a3814ff33f8cfa24c0a5fee4cce5a71a965804acee114be585f3874', '1d17c91e8d85f38bbc793932f49607adcbf1ad3157bd8967148dfe2cdc245dc3', 'ddccdb7de68f0fa50ce361a0ce706d26f20c70841846ddb34f163e9a32a067f3', '189a72f4dc968e2ef9883dae693e404a423fc580b41eaaeb8382039da2e553c3', 'f397cb355fa1b0a44f71c1d81d3e534a9369911660b4ee88ee09c285939461f5', 'c8e4923193de986b77f67463678eb3f7cbbafb65e548fbdf6d52bad86a6d9e0a', 'f49088eb9b12091b231bde40c4ee335ec9d84f89ae1598c7f573d70d786263df', '6a24f8dc2b8af24e86a2b06edbc9681254eb41aefcfdb39ac775cf2146932f21', '90b64f4a507f431f77caab256a6416710adf2f6e890c44947b7e95a0f9530acd', 'bcf273de1a9e00f87d7e15b28e4bc3fc263d72fa159d09ee361083e0acd75b5b', 'a60c92b91afd7836f9c464c5cb7ab49f6f2682a90e7468835622f8f6095a6607', 'a2d6b3c255a1f84bd598b0efe6bca1e2d8cd8ff40e341269f95d6fc2c7d02f5b'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Printedfolio692:117tail,118-125entire,126head', 'last_printed_block_id', 2721814, 'resumes_block_id', 2721928), jsonb_build_object('what', 'Local unreadable words/numbers in individuallyread acquiredimages; exactlocations are[illegible] in hashbound source proposals and candidate map', 'last_printed_block_id', NULL, 'resumes_block_id', NULL)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9889, 'question_id', 'q3', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'parser_partial_openers', '[{"cited_label": "126", "source_block_id": 2721928, "source_prefix": "respect of whose default the guarantee is given, is called the principal debtor", "missing_before": ["118", "119", "120", "121", "122", "123", "124", "125"]}]'::jsonb,
         'recovery_path', 'Acquisition_attempt225 refetched officialURL: HTTP200 unchangedcopy4843465bytes, sameSHA09bae40a... No complete substitute acquired. Revisit only on actual better authoritative source; no modern-word completion.'),
       'codex.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 13202
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13202);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13202) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 13202: run tools/record_source_refetch.py --observation 13202 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 13202;
