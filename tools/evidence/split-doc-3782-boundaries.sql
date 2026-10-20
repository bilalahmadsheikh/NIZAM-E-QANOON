-- adopted by builder BZ 16 Oct 2026 (renamed from -DRAFT; applied by the owner-run batch).
-- DRAFT by agent K4 (15 Oct 2026, prepare mode; the builder renames and applies it). Source-verified boundary evidence
-- for the reviewed split of document 3782 (tools/evidence/multi-instrument-plans/doc-3782.json, which the builder
-- renames to doc-3782.json after filling E1's owner_decision from the answer to claude/agK4/card-3782-q4.json).
--
-- The PDF (observation 3929, 'The K.D.A. (Disposal of Land) Rules, 1971', 25 pages) prints the contents (p1), the Rules
-- of 19 July 1971 with Appendices A-F-III (pp2-18), then five amending notifications: an undated one inserting rule
-- 11-A, amending rule 12 and adding Appendix 'G' (pp19-21); that of 26-7-1973 adding rule 14 (p22); that of 14 November
-- 1973 amending rule 2 and adding rule 15 (pp22-23); a second print dated 26-7-1973 of the same amendments, numbered on
-- (pp23-24); and that of 27 December 1973 substituting rule 12 (pp24-25).  The owner decided (decision-review-2026-10-12-j
-- .json doc 3782 q1 'split') that each amending notification is its own instrument, and (decision-review-2026-10-14-l
-- .json q3 'separate') that the pp23-24 repeat is its own instrument too.  The Rules open the document at block 474952
-- (contents), so they need no boundary row.
--
-- Materialisation is the separate, dry-run-gated `tools/materialize_multi_instrument.py --document 3782`, after the
-- readings claude/agK4/patch-3782.json are recorded.  Report-mode build (claude/agK4/tools/agK4-mat.py, rules D and F
-- installed): E0 201 provisions, E1 39, E2 1, E3 6, E4 6, E5 1; S7 0 in every expression; contents rows 14-25 left for
-- the TOC readings claude/agK4/toc-3782-DRAFT.json after the replay.
--
-- E1 has no printed date: its detected_year is NULL here (migration 0063), on the answer decision-review-2026-10-15-delegated.json doc 3782 q4 'undated'
-- (lead's delegated answer, card claude/agK4/card-3782-q4.json).

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=3782 AND i.source_observation_id=3929
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (475162::bigint,19,
     'Notification No. SO(KDA)-10/2-70 amending the K.D.A. (Disposal of Land) Rules, 1971 (rule 11-A, rule 12, Appendix ''G'')',
     'notification',NULL::integer,'SO(KDA)-10/2-70',
     jsonb_build_array(
       'page 18 ends the Rules'' Appendix ''F-III'' (mosque sites) with its item 9',
       'page 19 opens ''NOTIFICATION / NO. SO(KDA)-10/2-70-- In Exercise of the powers conferred by Article 14 read with Article 111 of the Karachi Development Authority Order, 1957 ... the Governor of Sind is pleased to make the following amendments to the K.D.A. (Disposal of Land)Rules, 1971:-'' with no date line, then AMENDMENTS 1 (rule 11-A (1)-(8))',
       'page 20: amendments 2 (rule 12) and 3 (Appendix ''G''); page 21: APPENDIX ''G'' and the signature ''(M.J.R. KHAN) CSP Secretary to Government of Sind'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3782-p19.png',
     '7ff7206349e8588ba0781d082bae860562da46dce48efdaca9fb8254d6e4076e'),
    (475197::bigint,22,
     'Notification No. SOI(KDA)-10-2/70 of 26 July 1973 amending the K.D.A. (Disposal of Land) Rules, 1971 (rule 14)',
     'notification',1973,'SOI(KDA)-10-2/70',
     jsonb_build_array(
       'page 21 ends the first notification with its signature',
       'page 22 opens (under the page head) ''HOUSING TOWN PLANNING AND LOCAL GOVERNMENT DEPARTMENT. / NOTIFICATION / Karachi, 26-7- 1973. / NO. SOI(KDA)-10-2/70-- ... the following amendments to the KDA (Disposal of Land)Rules, 1971. AMENDMENTS 1. The following New rule shall be added after rule 13..'' and the quoted rule 14, ending ''BY ORDER OF GOVERNOR OF SIND'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3782-p22.png',
     '9d97fdba2b35c451fd0d6c30e0d14ec7b45be5509f71e5b99d2fb7289c01c38a'),
    (475203::bigint,22,
     'Notification No. SO(KDA)-10-2/70 of 14 November 1973 amending the K.D.A. (Disposal of Land) Rules, 1971 (rules 2 and 15)',
     'notification',1973,'SO(KDA)-10-2/70',
     jsonb_build_array(
       'page 22, below ''BY ORDER OF GOVERNOR OF SIND'': ''HOUSING TOWN PLANNING AND LOCAL GOVERNMENT DEPARTMENT. / NOTIFICATION / Karachi, 14th November, 1973. / NO. SO(KDA)-10-2/70-- ... further amendments shall be made in Karachi Development Authority (Disposal of Land)Rules, 1971 namely:- AMENDMENTS 2. In rule 2.''',
       'page 23: (a) with (i)-(ii), (b), amendment 3 (rule 15 added) and the signature ''MAZHAR RAFI, SECRETARY TO THE GOVT; OF SINDH H.T.P.& L.G. DEPTT.'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3782-p22.png',
     '9d97fdba2b35c451fd0d6c30e0d14ec7b45be5509f71e5b99d2fb7289c01c38a'),
    (475217::bigint,23,
     'Notification No. SO(KDA)-10-2/70 dated 26 July 1973 (Part IV-A) amending the K.D.A. (Disposal of Land) Rules, 1971 (rules 2 and 15)',
     'notification',1973,'SO(KDA)-10-2/70',
     jsonb_build_array(
       'page 23, below MAZHAR RAFI''s signature: ''PART IV-A / GOVERNMENT OF SIND / HOUSING TOWN PLANNING AND LOCAL GOVERNMENT DEPARTMENT. / NOTIFICATION / Karachi, dated 26-7-1973 / NO. SO(KDA)-10-2/70-- ... the following amendments to the K.D.A. (Disposal of Land)Rules, 1971:- AMENDMENTS 4. In rule 2.''',
       'page 24: (c) with (iii)-(iv), (d), amendment 5 (rule 15 added), no signature; owner export l q3 ''separate'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3782-p23.png',
     'a5c4f0a3f46263f9c2d485de9e0b08089a4190cdaec6da30d887e996ab9a8a7b'),
    (475231::bigint,24,
     'Notification No. SO(KDA)-10-60/71 of 27 December 1973 amending the K.D.A. (Disposal of Land) Rules, 1971 (rule 12)',
     'notification',1973,'SO(KDA)-10-60/71',
     jsonb_build_array(
       'page 24, below amendment 5: ''PART IV-A / GOVERNMENT OF SIND / HOUSING, TOWN PLANNING & LOCAL GOVERNMENT & RURAL DEPARTMENT. / Karachi, the 27th Dec ember, 1973. / NOTIFICATION / NO. SO(KDA)-10-60/71-- In Exercise of the powers ... the Government of Sind are pleased to make the following''',
       'page 25: ''amendment in the KDA (Disposal of Land) Rules, 1971:-- AMENDMENTS For Rule 12, the following shall be substituted:- “12. ...”'' and the signature ''M.SALMAN FARUQUI, Secretary to Government of Sind.'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3782-p24.png',
     'e1aaeafbd45c69ca809669cc1693df64b61dc73d433f3e56b7b820a2a54fcb47')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,3929,3782,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-3782.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(18,19,20,21,22,23,24,25),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 475162 THEN 'Block 475162 begins the first amending notification (No. SO(KDA)-10/2-70, undated: rule 11-A, rule 12, Appendix ''G''), a separate instrument after the Rules'' Appendix F-III (owner decision 2026-10-12, export j q1 split).'
         WHEN 475197 THEN 'Block 475197 begins the notification of 26-7-1973 (No. SOI(KDA)-10-2/70) adding rule 14, a separate instrument (owner decision 2026-10-12, export j q1 split).'
         WHEN 475203 THEN 'Block 475203 begins the notification of 14 November 1973 (No. SO(KDA)-10-2/70) amending rule 2 and adding rule 15, a separate instrument (owner decision 2026-10-12, export j q1 split).'
         WHEN 475217 THEN 'Block 475217 begins the Part IV-A notification dated 26-7-1973 (No. SO(KDA)-10-2/70) repeating the 14 November amendments numbered on, its own instrument (owner decisions export j q1 split and export l q3 separate).'
         WHEN 475231 THEN 'Block 475231 begins the Part IV-A notification of 27 December 1973 (No. SO(KDA)-10-60/71) substituting rule 12, a separate instrument (owner decision 2026-10-12, export j q1 split).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-3782.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=3782 AND c.source_observation_id=3929
   AND c.start_block_id IN (475162,475197,475203,475217,475231)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
