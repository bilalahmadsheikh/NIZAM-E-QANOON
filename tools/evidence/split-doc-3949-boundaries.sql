-- Drafted by agent JF (17 Oct 2026); adopted by builder BZ 17 Oct 2026 (applied by the owner-run batch). Source-verified boundary evidence for the reviewed split
-- of document 3949 (plan claude/agJF/doc-3949-DRAFT.json -> tools/evidence/multi-instrument-plans/doc-3949.json when
-- adopted; owner decisions decision-review-2026-10-16-m.json doc 3949 q1 'keep-both', q2 'keep-printed').
-- Pattern: split-doc-3730-boundaries.sql (builder BZ).
--
-- Why it is needed: 3949 is on COMPILATION_DOCUMENTS with legacy manifests whose span-start candidates
-- (470bb425, 3c4a555c, f4950597, d0cb9fd9, 1c033f85 -- nizam.multi_instrument_detector/1, never adjudicated) were
-- archived and deleted by prune_retired_instruments (lead 13 Oct: the same dangling-anchor state as 4434). None of the
-- five expressions opens the document (pp1-5, blocks 530167-530271, are the compilation's front matter, outside every
-- span), so all five need a recorded confirmed_split at their first span start before --apply.
--
-- Span starts checked against the printed pages (renders, agent JF 17 Oct; listed per candidate below). E3's printed
-- title ('SERVICE RULES 2006', 530501-530503) sits at the END of the released E2's span; moving E3's start there would
-- change the released E2, so the span is kept and E3 starts at its enacting formula (530504) -- reported to the lead.
--
-- The candidates are keyed to the active UNRELEASED instrument of expression 0 (f078a8d1...); no released instrument
-- (E1 ac8eed3e, E2 a4fe74d6) is touched.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=3949 AND i.source_observation_id=2876 AND i.expression_ordinal=0
     AND i.is_active AND i.duplicate_of IS NULL
     AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,archived_candidate,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (530272::bigint,6,
     'Punjab Education Foundation (Conduct of Business) Rules, 2005',
     'rules',2005,NULL::text,'470bb425-4c27-45ab-86ef-7e7c4c6a271e',
     jsonb_build_array(
       'page 6 opens ''TEXT'', then the title ''THE PUNJAB EDUCATION FOUNDATION (CONDUCT OF BUSINESS) RULES, 2005'', ''[26th October, 2005]'', ''NOTIFICATION'' and ''No.S.O.(S-VII)l-33/2004. In exercise of the powers conferred under Section 13 of the Punjab Education Foundation Act, 2004, the Government of the Punjab is pleased to make the following rules:-''',
       'page 6 then prints ''1. Short Title and Commencement:- (1) These rules may be called the Punjab Education Foundation (Conduct of Business) Rules, 2005.'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3949-p6.png',
     '832755802ce300d732400f12bc831ef69b88b35a0b7d85e1ca669f800f8202cd'),
    (530345::bigint,10,
     'Punjab Education Foundation (Finance and Audit) Rules, 2005',
     'rules',2005,NULL::text,'3c4a555c-507e-44d9-a5c1-bd752847b536',
     jsonb_build_array(
       'page 10 opens with the title ''THE PUNJAB EDUCATION FOUNDATION (FINANCE AND AUDIT) RULES, 2005'' (blocks 530345-530346); page 9 ends the Conduct of Business Rules with the distribution list and ''UNDER SECRETARY(S-VII)'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3949-p10.png',
     '1c40094bb4a728011eac2421614caef87e09dc1e274e1ec88c86a92a546da88c'),
    (530427::bigint,13,
     'CONTRACT APPOINTMENT RULES, 2005',
     'rules',2005,NULL::text,'f4950597-7a02-4851-975d-b3af4d657c27',
     jsonb_build_array(
       'page 13 opens with the title ''CONTRACT APPOINTMENT RULES, 2005'' and ''[Dated Lahore the 26th October, 2005]'' (blocks 530427-530428)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3949-p13.png',
     '30705c5f9d9dfaaeae24e85a2cba08af6450de9de752212f1880a94480542a68'),
    (530504::bigint,16,
     'The Punjab Education Foundation Service Rules 2006',
     'rules',2006,NULL::text,'d0cb9fd9-4b6d-41f3-8654-3c6e64b82b3f',
     jsonb_build_array(
       'page 16 prints ''SERVICE RULES 2006'', ''[Dated Lahore the 18th May, 2006].'' and ''NOTIFICATION'' (blocks 530501-530503), then ''No. S.O.(S-VII)l-33/2004. In exercise of the powers conferred upon him under Section-13 of the Punjab Education Foundation Act 2004, the Governor of the Punjab is pleased to direct that the following rules shall be made:-'' (block 530504) and ''1. Short title, Commencement and Application (1) These rules may be called The Punjab Education Foundation Service Rules 2006.''',
       'the title blocks 530501-530503 lie inside the RELEASED expression E2''s span (530427-530503, the active manifest''s) and are not moved: the span starts at the enacting formula, block 530504'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3949-p16.png',
     'd02c876e02984a99d0679d702e13b0b3c3bd9d16a2e255e028b2b2f9ec145036'),
    (530684::bigint,24,
     'THE PUNJAB EDUCATION FOUNDATION REGULATIONS 2006',
     'regulation',2006,NULL::text,'1c033f85-f5e6-4de3-bc05-a12dd856dd64',
     jsonb_build_array(
       'page 24 opens with the title ''THE PUNJAB EDUCATION FOUNDATION REGULATIONS 2006'' and ''[Lahore, the 13th February, 2006]'' (blocks 530684-530685), then ''NOTIFICATION'' and ''NO. PEF(ADMN)l-3/2004/929A. In exercise of the powers conferred under Section-14 of Punjab Education Foundation Act, 2004 ...'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3949-p24.png',
     '8bb11175202f8db0a66825e942e55a43560a846161c32f239cd93dcd2d2d7d2a')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2876,3949,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-3949.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-16-m.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(6,9,10,13,16,17,24),
         'archived_candidate',p.archived_candidate,
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 530272 THEN 'Block 530272 begins the Punjab Education Foundation (Conduct of Business) Rules, 2005 at its printed title (p6) (owner decisions 2026-10-16, export m q1 keep-both, q2 keep-printed; the five-instrument split of the copy).'
         WHEN 530345 THEN 'Block 530345 begins the Punjab Education Foundation (Finance and Audit) Rules, 2005 at its printed title (p10) (owner decisions 2026-10-16, export m q1 keep-both, q2 keep-printed; the five-instrument split of the copy).'
         WHEN 530427 THEN 'Block 530427 begins the Contract Appointment Rules, 2005 at its printed title (p13) (owner decisions 2026-10-16, export m q1 keep-both, q2 keep-printed; the five-instrument split of the copy).'
         WHEN 530504 THEN 'Block 530504 begins the Punjab Education Foundation Service Rules 2006 at its enacting formula (p16); its title blocks 530501-530503 stay in released E2''s span (owner decisions 2026-10-16, export m q1 keep-both, q2 keep-printed; the five-instrument split of the copy).'
         WHEN 530684 THEN 'Block 530684 begins the Punjab Education Foundation Regulations 2006 at its printed title (p24) (owner decisions 2026-10-16, export m q1 keep-both, q2 keep-printed; the five-instrument split of the copy).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-3949.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-16-m.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=3949 AND c.source_observation_id=2876
   AND c.start_block_id IN (530272,530345,530427,530504,530684)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

DO $$
BEGIN
  IF (SELECT count(*) FROM segmentation_boundary_candidate c
        JOIN v_boundary_adjudication_latest a ON a.candidate_id=c.id AND a.resolution='confirmed_split'
       WHERE c.document_id=3949 AND c.source_observation_id=2876
         AND c.start_block_id IN (530272,530345,530427,530504,530684)) <> 5 THEN
    RAISE EXCEPTION 'document 3949: expected 5 confirmed_split candidates at their first span starts';
  END IF;
END $$;

COMMIT;
