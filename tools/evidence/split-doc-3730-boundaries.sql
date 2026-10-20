-- Builder BZ (16 Oct 2026; applied by the owner-run batch, agBZ-plan.sh). Source-verified boundary evidence for the
-- reviewed split of document 3730 (tools/evidence/multi-instrument-plans/doc-3730.json; owner decision
-- decision-review-2026-10-12-j.json doc 3730 q1 'split'; delegated answers decision-review-2026-10-15-delegated.json q2
-- 'rows-by-group').
--
-- Why it is needed: batch 14 stopped at the materializer's guard "expressions [0, 2] need a recorded confirmed_split
-- boundary candidate at their first span start". The plan orders the gazette as printed: E1 (the completion-dates
-- notification, p1) opens the document at block 459453 and needs no anchor; E0 (the Rules, p2) and E2 (the rates
-- notification with Annexures A-E, pp3-37) do not open it.
--
-- Existing candidates: observation 4676 has NO boundary candidate, live or archived. Its ten archived instruments
-- (instrument_revision_archive_manifest, batches 7c94484b, 058e4e9f, a82824b0) carry either no 'boundary_candidates' key
-- or an empty list, so there is nothing to cite.
--
-- Span starts checked against the printed pages (renders, builder BZ 16 Oct):
--   E0 starts at block 459462 'NOTIFICATION', the first printed line of page 2. The Rules print no title line of their
--      own: page 2 is 'NOTIFICATION', the enabling formula 'In exercise of the powers conferred by Section 70 read with
--      Section 15-A of the Sind Irrigation Act, 1879 the Government of Sind are pleased to make the following rules:-'
--      (459463), then '1. (1) These rules may be called the Sind Drainage Rates Rules, 1983.' (459464) -- the title is
--      printed in rule 1(1). Page 1 ends with the completion table's row 5 'Larkana Shikarpur Surface Drainage Scarp
--      30-6-1982 Rabi, 83-84.' (459461) and the signature A.N.G. ABBASI.
--      render .artifacts/release-work-2026-09-24/claude/renders/doc3730-p2.png
--      sha256 1a68309ced33fb38794daf75cbd2db5342045fda65dc6a9593f4709cd4031f29
--   E2 starts at block 459480 'NOTIFICATION / Karachi the 8th September, 1983. / No. 2/67-S.O.(R&S)/82.- In exercise of
--      the powers conferred by clause (d) of Section 70 of the Sind Irrigation Act 1879 read with Section 15-A ...', the
--      first printed line of page 3; page 2 ends with rule 6(2) (459479) and the signature A.N.G. ABBASI.
--      render .artifacts/release-work-2026-09-24/claude/renders/doc3730-p3.png
--      sha256 5d0ce4e72f4c09b276cde7f81d8252f99945f78423f3813fddf565f5b7521fc2
--   (E1, p1: 'THE SIND GOVERNMENT GAZETTE ... KARACHI, WEDNESDAY, SEPTEMBER 14, 1983 / PART I / ... NOTIFICATION / No.
--    2/67-S.O.(R&S)/82- In pursuance of the proviso to sub-section (1) of Section 15-A ...' -- the document's first block.)
--
-- The candidates are keyed to the active UNRELEASED instrument of 3730 (86e27938..., one expression spanning every
-- block); no released instrument is touched. The guarded materialisation follows in the same batch item.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=3730 AND i.source_observation_id=4676
     AND i.is_active AND i.duplicate_of IS NULL
     AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (459462::bigint,2,
     'The Sind Drainage Rates Rules, 1983',
     'rules',1983,NULL::text,
     jsonb_build_array(
       'page 1 ends the completion-dates notification with its table row 5 and the signature A.N.G. ABBASI, Secretary to Government of Sindh',
       'page 2 opens ''NOTIFICATION'' and ''In exercise of the powers conferred by Section 70 read with Section 15-A of the Sind Irrigation Act, 1879 the Government of Sind are pleased to make the following rules:-'', then ''1. (1) These rules may be called the Sind Drainage Rates Rules, 1983.''',
       'page 2 holds rules 1-6 and ends with the signature A.N.G. ABBASI, Secretary to Govt. of Sindh'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3730-p2.png',
     '1a68309ced33fb38794daf75cbd2db5342045fda65dc6a9593f4709cd4031f29'),
    (459480::bigint,3,
     'Irrigation and Power Department Notification No. 2/67-S.O.(R&S)/82 dated 8 September 1983 (drainage rate per cropped acre for Salinity Control and Reclamation Projects, with Annexures A-E)',
     'notification',1983,'2/67-S.O.(R&S)/82',
     jsonb_build_array(
       'page 2 ends the Rules with rule 6(2) and the signature',
       'page 3 opens ''NOTIFICATION / Karachi the 8th September, 1983. / No. 2/67-S.O.(R&S)/82.- In exercise of the powers conferred by clause (d) of Section 70 of the Sind Irrigation Act 1879 read with Section 15-A, thereof, the Government of Sind are pleased to direct that the Drainage Rate ... shall be leviable at the rate mentioned in column 3:-'', then the five-row TABLE and ANNEXURE ''A'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3730-p3.png',
     '5d0ce4e72f4c09b276cde7f81d8252f99945f78423f3813fddf565f5b7521fc2')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,4676,3730,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-3730.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3),
         'archived_candidates','none: observation 4676 never had a boundary candidate (live or archived)',
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 459462 THEN 'Block 459462 (''NOTIFICATION'', p2) begins the Sind Drainage Rates Rules, 1983, a separate instrument after the completion-dates notification of p1 (owner decision 2026-10-12, export j q1 split).'
         WHEN 459480 THEN 'Block 459480 (''NOTIFICATION / Karachi the 8th September, 1983. / No. 2/67-S.O.(R&S)/82.-'', p3) begins the drainage-rate notification with its Annexures A-E, a separate instrument after the Rules (owner decision 2026-10-12, export j q1 split).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-3730.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=3730 AND c.source_observation_id=4676
   AND c.start_block_id IN (459462,459480)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

DO $$
BEGIN
  IF (SELECT count(*) FROM segmentation_boundary_candidate c
        JOIN v_boundary_adjudication_latest a ON a.candidate_id=c.id AND a.resolution='confirmed_split'
       WHERE c.document_id=3730 AND c.source_observation_id=4676 AND c.start_block_id IN (459462,459480)) <> 2 THEN
    RAISE EXCEPTION 'document 3730: expected 2 confirmed_split candidates at blocks 459462 and 459480';
  END IF;
END $$;

COMMIT;
