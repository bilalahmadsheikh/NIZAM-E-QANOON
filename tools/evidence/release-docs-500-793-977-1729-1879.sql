\set ON_ERROR_STOP on

BEGIN;

-- Document 500: a fresh fetch on 2026-09-22 returned the exact one-page
-- source already held.  Rule 2 promises a Schedule, but the page moves
-- directly to signatures and the administrative forwarding list.
INSERT INTO acquisition_attempt (
    source_observation_id, requested_url, final_url, http_status, media_type,
    byte_length, response_sha256, object_key, outcome, error
)
SELECT 2850,
       'https://punjabcode.punjab.gov.pk/uploads/articles/home-deptt-direct-of-monitoring-2019-d-g-direct-dy-dir-pdf.pdf',
       'https://punjabcode.punjab.gov.pk/uploads/articles/home-deptt-direct-of-monitoring-2019-d-g-direct-dy-dir-pdf.pdf',
       200, 'application/pdf', 54331,
       '83cb30b6ed3d8e5aa0e8a9f6f38ae59b479d13fc3f51c8aef1eaaa7ab69d04bd',
       'raw/pk-punjab/83cb30b6ed3d8e5aa0e8a9f6f38ae59b479d13fc3f51c8aef1eaaa7ab69d04bd',
       'unchanged_copy',
       'Official endpoint still serves the byte-identical one-page copy; rule 2 refers to a Schedule that is absent.'
 WHERE NOT EXISTS (
       SELECT 1 FROM acquisition_attempt
        WHERE source_observation_id=2850
          AND outcome='unchanged_copy'
          AND response_sha256='83cb30b6ed3d8e5aa0e8a9f6f38ae59b479d13fc3f51c8aef1eaaa7ab69d04bd'
 );

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 2850, 500, 'no_complete_copy_acquired', NULL,
       'Page 1 ends after rule 2, the authorising signature and an administrative forwarding list.',
       'The Schedule appended to the rules, expressly incorporated by rule 2.',
       'The rendered official page contains rules 1 and 2. Rule 2 says recruitment details shall be as given in the Schedule appended to the rules, but no Schedule follows. The rest of the only page is distribution apparatus.',
       count(*), min(attempted_at), max(attempted_at),
       'A dated refetch of the official URL returned HTTP 200 and the exact same one-page PDF; no complete copy was obtained.',
       jsonb_build_object(
         'reviewer_type','assistant',
         'attempt_ids',jsonb_agg(id ORDER BY id),
         'source_sha256','83cb30b6ed3d8e5aa0e8a9f6f38ae59b479d13fc3f51c8aef1eaaa7ab69d04bd',
         'render_artifact','.artifacts/releases-six/source-pages/doc500-p1.png',
         'render_sha256','04ad0a70b6617c21a308c2bd3c584761c44e1ec8e87b11f2ef22f91b12f9fbda',
         'release_note','Released at user direction with a visible open source-incompleteness record; the missing Schedule is not fabricated.'
       ),
       'codex.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id=2850 AND outcome='unchanged_copy'
   AND response_sha256='83cb30b6ed3d8e5aa0e8a9f6f38ae59b479d13fc3f51c8aef1eaaa7ab69d04bd'
HAVING count(*) > 0
   AND NOT EXISTS (
       SELECT 1 FROM v_source_incompleteness_latest
        WHERE source_observation_id=2850
   );

-- Document 793: remove marginal-note prefixes from two blocks so their own
-- quoted labels are parsed, then the source-reviewed reparent operation moves
-- those quotations beneath amending sections 2 and 4.
INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,evidence,
     review_state,created_by)
VALUES
(3649,1,'Substitution ',
$before$Substitution 
of 
section 14 of Sind 
Ordinance 
XII 
of 
1979. 
 
 “$before$,' ',
 jsonb_build_object('reviewer_type','assistant','document_id',793,
   'source_block_id',35865,'purpose','remove fused marginal heading only',
   'render_artifact','.artifacts/releases-six/source-pages/doc793-1.png'),
 'source_verified','codex.release-six/1'),
(3649,2,'(10) No member shall be liable',
$before$Amendment 
of 
section 51 of Sind 
Ordinance 
XII 
of 
1979. 
 
 “$before$,' ',
 jsonb_build_object('reviewer_type','assistant','document_id',793,
   'source_block_id',35875,'purpose','remove fused marginal heading only',
   'render_artifact','.artifacts/releases-six/source-pages/doc793-2.png',
   'render_sha256','452ac4b4e5d1e54d0c510f2837a1b33b1b328e54baf9c8e29e656be716bb6b96'),
 'source_verified','codex.release-six/1')
ON CONFLICT DO NOTHING;

-- Document 1729: the source itself repeats rule 2 and then jumps to rule 4;
-- record the narrow derived-text correction to canonical rule 3. Parenthesised
-- bold labels 10-14 are visibly top-level rules, while (2) and (3) beneath 12
-- remain subrules and are not patched.
INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,evidence,
     review_state,created_by)
VALUES
(2168,1,'Appointment of Sub-Inspectors',
 '2. Appointment of Sub-Inspectors.-','3. Appointment of Sub-Inspectors.-',
 jsonb_build_object('reviewer_type','assistant','document_id',1729,
   'source_block_id',112428,'source_defect','printed 2, sequence and cross-references prove canonical rule 3',
   'render_artifact','.artifacts/s7-source/doc1729-p1-1.png',
   'render_sha256','64811bd8eab49cc2ee7c689dffdad4f9478dc6c4fb479b8f13cc51eff49db410'),
 'source_verified','codex.release-six/1'),
(2168,4,'Appointment of Inspectors', '(10)', '10.',
 jsonb_build_object('reviewer_type','assistant','document_id',1729,'source_block_id',112460,
   'purpose','top-level rule typography','render_artifact','.artifacts/releases-six/source-pages/doc1729-p4.png','render_sha256','5b7628055b153db73c052692b20e165cf34e32508db56aa9082621a55ef6dc04'),
 'source_verified','codex.release-six/1'),
(2168,4,'Probation of Inspectors', '(11)', '11.',
 jsonb_build_object('reviewer_type','assistant','document_id',1729,'source_block_id',112461,
   'purpose','top-level rule typography and express reference to rule 10','render_artifact','.artifacts/releases-six/source-pages/doc1729-p4.png','render_sha256','5b7628055b153db73c052692b20e165cf34e32508db56aa9082621a55ef6dc04'),
 'source_verified','codex.release-six/1'),
(2168,4,'Seniority of Inspectors.- (1)', '(12)', '12.',
 jsonb_build_object('reviewer_type','assistant','document_id',1729,'source_block_id',112462,
   'purpose','top-level rule typography','render_artifact','.artifacts/releases-six/source-pages/doc1729-p4.png','render_sha256','5b7628055b153db73c052692b20e165cf34e32508db56aa9082621a55ef6dc04'),
 'source_verified','codex.release-six/1'),
(2168,4,'Method of recruitment, appointment', '(13)', '13.',
 jsonb_build_object('reviewer_type','assistant','document_id',1729,'source_block_id',112465,
   'purpose','top-level rule typography','render_artifact','.artifacts/releases-six/source-pages/doc1729-p4.png','render_sha256','5b7628055b153db73c052692b20e165cf34e32508db56aa9082621a55ef6dc04'),
 'source_verified','codex.release-six/1'),
(2168,4,'Overriding effect', '(14)', '14.',
 jsonb_build_object('reviewer_type','assistant','document_id',1729,'source_block_id',112466,
   'purpose','top-level rule typography','render_artifact','.artifacts/releases-six/source-pages/doc1729-p4.png','render_sha256','5b7628055b153db73c052692b20e165cf34e32508db56aa9082621a55ef6dc04'),
 'source_verified','codex.release-six/1')
ON CONFLICT DO NOTHING;

-- Document 1879: remove a running header before section 9 and the superscript
-- footnote number following section 14. Footnote-only blocks are separately
-- excluded through the source-reviewed S7 evidence.
INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,evidence,
     review_state,created_by)
VALUES
(3027,3,'1838: Act XIX',
$before$1838: Act XIX  
 
 
Coasting-vessels. 
 
$before$,' ',
 jsonb_build_object('reviewer_type','assistant','document_id',1879,
   'source_block_id',130467,'purpose','remove repeated running header before section 9',
   'render_artifact','.artifacts/releases-six/source-pages/doc1879-p3.png',
   'render_sha256','8833c104bf6c419cb396bcd6ca470e829534e1da48f2dc253ecdcbe4ef8d99fc'),
 'source_verified','codex.release-six/1'),
(3027,4,'Federal Government] may direct',
$before$14. 
3  *$before$,$after$14. 
*$after$,
 jsonb_build_object('reviewer_type','assistant','document_id',1879,
   'source_block_id',130488,'purpose','remove superscript footnote 3 from the section label',
   'render_artifact','.artifacts/releases-six/source-pages/doc1879-4.png',
   'render_sha256','eb3e3c13f903f8b31f5675f15babf3e5df1b334b9ec96d9b596d32ce259cca18'),
 'source_verified','codex.release-six/1')
ON CONFLICT DO NOTHING;

-- Document 977 contains a second independent legal formula beginning at the
-- Home Department notification.  The primary and embedded spans are disjoint.
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT i.id,3890,977,45939,1,
       'Home Department Notification No. 6/110-H(Spl-II)/72, 1972',
       'notification',1972,'6/110-H(Spl-II)/72',1.0,
       'codex.source-page-review/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'source_facts',jsonb_build_array(
           'new department heading',
           'new notification date and number',
           'independent enabling formula under section 11 of the West Pakistan Arms Ordinance 1965',
           'amends the Arms Rules 1924 rather than the medical-charges Rules'),
         'reviewed_pages',jsonb_build_array(1,2),
         'render_artifact','.artifacts/s7-source/doc977-p2-2.png',
         'render_sha256','d8f996444c53d63a2bc244ddb31665fb889dab9b1d925bcdad7a908fa6a965a8'
       )
  FROM instrument i
 WHERE i.document_id=977 AND i.source_observation_id=3890
   AND i.is_active AND i.duplicate_of IS NULL
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','codex.source-page-review/1',
       'Block 45939 begins a separately headed and numbered Home Department notification with its own enabling formula and an amendments section concerning the Arms Rules, 1924; it is not part of the Sind Re-imbursement of Medical Charges Rules, 1972.',
       jsonb_build_object('reviewer_type','assistant','reviewed_pages',jsonb_build_array(1,2),
                          'source_start_block_id',45939),
       'codex.source-page-review/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=977 AND c.source_observation_id=3890
   AND c.start_block_id=45939 AND c.method='codex.source-page-review/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split'
   );

COMMIT;
