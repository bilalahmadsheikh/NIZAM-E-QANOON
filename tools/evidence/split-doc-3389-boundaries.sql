-- Drafted (renamed and applied by builder BZ, 14 Oct 2026); DRAFT by agent JB (13 Oct 2026, prepare mode; not applied). Source-verified boundary evidence anchoring expression 1
-- of document 3389 at its printed title, for the reviewed plan tools/evidence/multi-instrument-plans/doc-3389.json
-- (to be adopted as doc-3389.json; 3389 to leave PRIMARY_DOCUMENTS in tools/materialize_multi_instrument.py).
--
-- Why it is needed: expression 1 does not open the document, so the materializer requires a confirmed_split candidate
-- at its first span start (evidence.boundary_anchor_required; doc 977 precedent). Observation 4610 has NO live
-- boundary candidate. Its only candidate ever recorded -- d0aadd2e-5c10-4de1-806d-bd89c2dd03af
-- (nizam.multi_instrument_detector/1, confidence 0.85, rules enactment_formula + section_one_self_names_instrument,
-- start block 366444 = the notification number line 'NO: SLGB/CAO/2001/7483. In exercise of the powers ...', p12,
-- detected title 'Sindh Local Government (Local Fund Budget) Rules 2001') -- was keyed to instrument 929f0ee4 and
-- archived with it by the prune (instrument_revision_archive_manifest batch 45fea3b9-16a6-42ac-b3bc-fcb521a0c294);
-- it was never adjudicated. It is cited here, not revived: its start block is one block after the printed title.
--
-- Span starts checked against the printed titles (page renders, agent JB 13 Oct):
--   E0 starts at block 366318 ('The Sindh Government Gazette', p1 masthead) -- the document's first block; its printed
--      title 'Sindh Councils (Conduct of Business) Rules, 2001' is block 366326 on the same page, after the masthead,
--      'PAERT I', the department, 'NOTIFICATION' and the date. Released instrument e31f5940 has the same span
--      (366318-366442). No anchor is required for E0.
--   E1 starts at block 366443 ('SINDH, LOCAL GOVERNMENT (LOCAL FUND BUDGET) / Rules 2001', p12) = its printed title.
--      render .artifacts/release-work-2026-09-24/claude/renders/doc3389-p12.png
--      sha256 c3da97ae542571031d5ed4fea6ad2350a5a38f622ea4add7c5522694460fc072
--      Page 12 opens a second Gazette issue: 'The Sindh Government Gazette' (366435), 'Published by Authority', the
--      rule, 'KARACHI WEDNESDAY DECEMBER 5, 2001', 'PAERT I', 'GOVERNMENT OF SINDH LOCAL GOVERNMENT, RURAL DEVELOPMENT AND
--      KATCHI ABADIES DEPARTMENT (Sindh Local Government Board)' (366440), 'NOTIFICATION' (366441), 'Karachi the 5th
--      December, 2001' (366442), then the title (366443), 'NO: SLGB/CAO/2001/7483. In exercise of the powers conferred
--      under Section 191 ... the Government of Sindh are pleased to make the following Rules-' (366444), 'CHAPTER I',
--      'PRELIMINARY & DEFINITIONS', '1. Short title and commencement', '1. These rules may be called Sindh Local
--      Government (Local Fund Budget) Rules 2001.'
--   No released boundary moves under this plan: E0 keeps 366318-366442 and rebuilds as stored (in-memory build,
--   default profile + agJB rule F: 59 provisions, S7 0; $S/agJB-tree-3389-defF.txt).
--   LEAD OPTION (RELEASED-CHANGE, not drafted here): blocks 366435-366442 (p12's masthead and notification header of
--   the Budget Rules' Gazette issue) are stored today as body text of RELEASED rule 39 of E0 (provision_block role body,
--   path sindh.rules.y2001_o4610.s_39). Starting E1 at its masthead (366435) instead, as E0 starts at its own, would move
--   E0's released end 366442 -> 366434: r.39 loses those 8 blocks of masthead text (E0 body roles 115 -> 107, no
--   provision added or removed, every other E0 line identical) and E1 gains them as preface (4 -> 12; its 10 provisions
--   identical) -- in-memory, $S/agJB-tree-3389-altF.txt vs -defF.txt. The candidate below would then start at 366435.
--
-- The candidate is keyed to the active UNRELEASED expression-1 instrument (8fdcbd3d-7519-4511-83a6-8b97b12905dc,
-- span 366443-366576), whose tree spans the boundary; no released instrument is touched.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id, i.source_observation_id
    FROM instrument i
   WHERE i.document_id=3389 AND i.expression_ordinal=1
     AND i.id='8fdcbd3d-7519-4511-83a6-8b97b12905dc'
     AND i.is_active AND i.duplicate_of IS NULL
     AND i.source_observation_id=4610
     AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,a.source_observation_id,3389,366443,12,
       'Sindh Local Government (Local Fund Budget) Rules, 2001','rules',2001,NULL,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-3389.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'question_id','q1',
         'archived_candidate_id','d0aadd2e-5c10-4de1-806d-bd89c2dd03af',
         'archived_candidate_note','nizam.multi_instrument_detector/1 at block 366444 (the notification number line, one block after the printed title), keyed to archived instrument 929f0ee4-0819-4ba9-8c4f-5eeb686727bd (archive batch 45fea3b9-16a6-42ac-b3bc-fcb521a0c294); never adjudicated',
         'source_facts',jsonb_build_array(
           'page 12 opens a second Sindh Government Gazette issue (masthead, KARACHI WEDNESDAY DECEMBER 5, 2001, PAERT I, the Local Government department, NOTIFICATION, Karachi the 5th December, 2001)',
           'block 366443 prints the title SINDH, LOCAL GOVERNMENT (LOCAL FUND BUDGET) Rules 2001, followed by the enacting notification NO: SLGB/CAO/2001/7483 under Section 191 of the Sindh Local Government Ordinance, 2001',
           'its rule 1 names it the Sindh Local Government (Local Fund Budget) Rules 2001; page 11 before it ends the Conduct of Business Rules at rule 39'),
         'reviewed_pages',jsonb_build_array(11,12),
         'render_artifact','.artifacts/release-work-2026-09-24/claude/renders/doc3389-p12.png',
         'render_sha256','c3da97ae542571031d5ed4fea6ad2350a5a38f622ea4add7c5522694460fc072')
  FROM active_instrument a
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       'Block 366443 prints the title of the Sindh Local Government (Local Fund Budget) Rules, 2001, a separate set of rules notified in a second Gazette issue after the Sindh Councils (Conduct of Business) Rules, 2001 (owner decision 2026-10-12 export j q1 release-with-gap). Supersedes, by citation, the unadjudicated archived detector candidate d0aadd2e-5c10-4de1-806d-bd89c2dd03af at block 366444.',
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'archived_candidate_id','d0aadd2e-5c10-4de1-806d-bd89c2dd03af',
                          'plan','tools/evidence/multi-instrument-plans/doc-3389.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=3389
   AND c.start_block_id=366443
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
