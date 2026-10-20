-- Drafted by agent JA (12 Oct 2026); renamed and applied by builder BZ on 13 Oct 2026 (entry ids passed as psql variables). Pattern: record-reviewed-toc-omission-3604-DRAFT.sql
-- (agent JC) with rule `body_evidenced_disposition` (the contents rows print NO lifecycle word; the body prints the omission).
--
-- Document 2370, The West Pakistan Finance Act, 1965 (KP copy, 14 pages), observation 1593.
-- Owner decision: decision-review-2026-10-12-j.json, document 2370, q1 'omitted' (reviewer Bilal Ahmad): sections 4, 7 and
-- 8 are recorded as omitted by the Khyber Pakhtunkhwa Adaptation of Laws Order 1975, with no text; contents rows 4, 7, 8
-- link to those omitted entries; the footnote is cited as the evidence.
--
-- Read from the renders on 2026-10-12 (agent JA):
--   p1 (doc2370-p1.png 9876023d...) contents rows '1[4. ……………]' (block 191276), '2[7. …………..' (191279) and
--      '8. ……………]' (191280); footnotes 1-2 'Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.'; no 'Omitted' word;
--   p4 (doc2370-p4.png 4034a355...) after s.3(2) '4[4 . . . . . . . . . . . .]' (footnote 4) and after s.6(ii)
--      '5[7-8 ………………..]' (footnote 5), both 'Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.'.
--
-- ORDER: record claude/agJA/patch-2370.json (9 readings; the two body dot stubs are set aside), replay, then FILL each
-- reviewed_toc_entry_id below with the replayed instrument_toc_entry id of ordinal 3 / 6 / 7 (label '4' / '7' / '8'), run
-- this file, and replay again so the assertions materialise the omitted entries ss.4, 7, 8.

\set ON_ERROR_STOP on
BEGIN;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES
(1593,0,3,:fill_entry_4,'4',E'……………]','omitted',
 191276,1,
 '.artifacts/release-work-2026-09-24/claude/renders/doc2370-p4.png',
 '4034a35563bfd2afe810b80be2d2e0110fb2c67e52ec2288562f51e4dbfa60ef',
 'Khyber Pakhtunkhwa Adaptation of Laws Order, 1975',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc2370-p1.png',
  'contents_sha256','9876023d698c4dd893110d95ed4a92d05de01ca5a9c79a5358519b26f83bb94e',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc2370-p4.png',
  'body_sha256','4034a35563bfd2afe810b80be2d2e0110fb2c67e52ec2288562f51e4dbfa60ef',
  'owner_decision',jsonb_build_object('export','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
                                      'document_id',2370,'question_id','q1','choice','omitted'),
  'finding','Contents page 1 prints row 4 as ''[4. ……………]'' (footnote 1 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.''), no Omitted word. Body page 4 prints, after s.3(2), only ''4[4 . . . . . . . . . . . .]'' with footnote 4 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.''; no s.4 text is printed.'),
 'claude.disposition-review/2'),
(1593,0,6,:fill_entry_7,'7',E'…………..','omitted',
 191279,1,
 '.artifacts/release-work-2026-09-24/claude/renders/doc2370-p4.png',
 '4034a35563bfd2afe810b80be2d2e0110fb2c67e52ec2288562f51e4dbfa60ef',
 'Khyber Pakhtunkhwa Adaptation of Laws Order, 1975',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc2370-p1.png',
  'contents_sha256','9876023d698c4dd893110d95ed4a92d05de01ca5a9c79a5358519b26f83bb94e',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc2370-p4.png',
  'body_sha256','4034a35563bfd2afe810b80be2d2e0110fb2c67e52ec2288562f51e4dbfa60ef',
  'owner_decision',jsonb_build_object('export','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
                                      'document_id',2370,'question_id','q1','choice','omitted'),
  'finding','Contents page 1 prints row 7 as ''[7. …………..'' (footnote 2 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.''), no Omitted word. Body page 4 prints, after s.6(ii), only ''5[7-8 ………………..]'' with footnote 5 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.''; no s.7 text is printed.'),
 'claude.disposition-review/2'),
(1593,0,7,:fill_entry_8,'8',E'……………]','omitted',
 191280,1,
 '.artifacts/release-work-2026-09-24/claude/renders/doc2370-p4.png',
 '4034a35563bfd2afe810b80be2d2e0110fb2c67e52ec2288562f51e4dbfa60ef',
 'Khyber Pakhtunkhwa Adaptation of Laws Order, 1975',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc2370-p1.png',
  'contents_sha256','9876023d698c4dd893110d95ed4a92d05de01ca5a9c79a5358519b26f83bb94e',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc2370-p4.png',
  'body_sha256','4034a35563bfd2afe810b80be2d2e0110fb2c67e52ec2288562f51e4dbfa60ef',
  'owner_decision',jsonb_build_object('export','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
                                      'document_id',2370,'question_id','q1','choice','omitted'),
  'finding','Contents page 1 prints row 8 as ''8. ……………]'' (closing the bracket opened at row 7, footnote 2), no Omitted word. Body page 4 prints, after s.6(ii), only ''5[7-8 ………………..]'' with footnote 5 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.''; no s.8 text is printed.'),
 'claude.disposition-review/2');

COMMIT;
