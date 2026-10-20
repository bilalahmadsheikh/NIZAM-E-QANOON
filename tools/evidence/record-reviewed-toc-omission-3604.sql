-- Drafted by agent JC (12 Oct 2026); renamed and applied by builder BZ (entry ids passed as psql variables). Pattern: record-reviewed-toc-repeal-1846-2026-09-23.sql
-- with rule `body_evidenced_disposition` (the contents rows print NO lifecycle word; the body prints the omission).
--
-- Document 3604, Pakistan Medical and Dental Council Ordinance, 1962 (Pakistan Code copy, 28 pages), observation 417.
-- Owner decision: decision-review-2026-10-12-j.json, document 3604, q1 'omitted' (reviewer Bilal Ahmad): s.12 and s.14
-- (numbers from the contents, positions from the star lines) are recorded as omitted, citing the footnotes; contents
-- rows 12 and 14 link to those entries; no text is invented.
--
-- Read from the renders on 2026-10-12 (agent JC):
--   p1 (doc3604-p1.png 7abc58c4...) contents rows '12. Non-Pakistan qualifications in Schedule to be recognised.'
--      (block 423942) and '14. Recognition of medical qualification granted by a medical Institution outside
--      Pakistan.' (block 423944), no 'Omitted' (unlike rows 17, 24, 25, 32, which already carry assertions);
--   p9 (doc3604-p9.png 2acd980d...) after s.11A only '2* * * * * * *' (footnote 2 'Omitted and subs. by Act No. XIX
--      of 2012, ss.14 and 15.'), then s.13, then '3* * * * * * *' (footnote 3 'Omitted by Act No. XIX of 2012, s.16.').
--
-- ORDER: record claude/agJC/patch-3604.json (11 readings: soft-hyphen labels 16-A ... 36-B, the two star lines set
-- aside), replay, then FILL each reviewed_toc_entry_id below with the replayed instrument_toc_entry id of ordinal
-- 12 / 14 (label '12' / '14'), run this file, and replay again so the assertions materialise the omitted entries.
-- The stale 'absent_in_source' adjudication for row 14 (claude.absent-section-review/1) is then moot (the row links);
-- check ./nz toc-reattach reports it orphaned, not re-applied.

\set ON_ERROR_STOP on
BEGIN;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES
(417,0,12,:fill_entry_12,'12',E'Non­Pakistan qualifications in Schedule to be recognised.','omitted',
 423942,1,
 '.artifacts/release-work-2026-09-24/claude/renders/doc3604-p9.png',
 '2acd980d08decb2ae25b51364aff61064633af53a8c1bed3f532dc0e8451f03d',
 'Act No. XIX of 2012, ss.14 and 15',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc3604-p1.png',
  'contents_sha256','7abc58c46c9420accdf83c44979a5566b51b438671bf224c8c883442d935b902',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc3604-p9.png',
  'body_sha256','2acd980d08decb2ae25b51364aff61064633af53a8c1bed3f532dc0e8451f03d',
  'owner_decision',jsonb_build_object('export','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
                                      'document_id',3604,'question_id','q1','choice','omitted'),
  'finding','Contents page 1 lists s.12 with no Omitted mark. Body page 9 prints, after s.11A, only an unnumbered line of seven asterisks with footnote 2 ''Omitted and subs. by Act No. XIX of 2012, ss.14 and 15.''; no s.12 text is printed.'),
 'claude.disposition-review/2'),
(417,0,14,:fill_entry_14,'14',
 'Recognition of medical qualification granted by a medical Institution outside Pakistan.','omitted',
 423944,1,
 '.artifacts/release-work-2026-09-24/claude/renders/doc3604-p9.png',
 '2acd980d08decb2ae25b51364aff61064633af53a8c1bed3f532dc0e8451f03d',
 'Act No. XIX of 2012, s.16',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc3604-p1.png',
  'contents_sha256','7abc58c46c9420accdf83c44979a5566b51b438671bf224c8c883442d935b902',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc3604-p9.png',
  'body_sha256','2acd980d08decb2ae25b51364aff61064633af53a8c1bed3f532dc0e8451f03d',
  'owner_decision',jsonb_build_object('export','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
                                      'document_id',3604,'question_id','q1','choice','omitted'),
  'finding','Contents page 1 lists s.14 with no Omitted mark. Body page 9 prints, after s.13, only an unnumbered line of seven asterisks with footnote 3 ''Omitted by Act No. XIX of 2012, s.16.''; no s.14 text is printed.'),
 'claude.disposition-review/2');

COMMIT;
