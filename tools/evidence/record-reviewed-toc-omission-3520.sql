-- Drafted by agent JC (12 Oct 2026); renamed and applied by builder BZ (entry ids passed as psql variables). Pattern: record-reviewed-toc-repeal-1846-2026-09-23.sql
-- with rule `body_evidenced_disposition` (the contents rows print NO lifecycle word; the body prints the omission).
--
-- Document 3520, The Khyber Pakhtunkhwa Highways Ordinance, 1959 (24 pages), observation 1519.
-- Owner decision: decision-review-2026-10-12-j.json, document 3520, q1 'omitted' (reviewer Bilal Ahmad): sections 9
-- and 10 are recorded as omitted by Ordinance No. X of 1984, on the evidence of the body's stub and footnote; contents
-- rows 9 and 10 link to those omitted entries; no text is invented.
--
-- Read from the renders on 2026-10-12 (agent JC):
--   p1 (doc3520-p1.png c4c7849d...) contents rows '9. Adoption of restrictions of section 8 in respect of other
--      highways.' and '10. Compensation.' (both in block 399619), no 'Omitted';
--   p10 (doc3520-p10.png db7e6e97...) between s.8 (p9) and s.11 only '1[9, 10 * * *]', footnote 1 '. Section 9 and 10
--      omitted Ordinance ibid vide No.X of 1984.'
--
-- ORDER: record claude/agJC/patch-3520.json (14 readings) with agJC rule C `apparatus_contents_rows` ported, replay,
-- FILL each reviewed_toc_entry_id with the replayed instrument_toc_entry id of ordinal 8 / 9 (label '9' / '10'), run
-- this file, replay again.

\set ON_ERROR_STOP on
BEGIN;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
SELECT 1519,0,v.ord,v.entry,v.label,v.heading,'omitted',399619,1,
 '.artifacts/release-work-2026-09-24/claude/renders/doc3520-p10.png',
 'db7e6e97feaaa9c08f43b6cb8b02ffc26322f0f684f616553f2e933a43fc9c54',
 'Khyber Pakhtunkhwa Ordinance No. X of 1984',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc3520-p1.png',
  'contents_sha256','c4c7849dbc13b54bb0b69014ba58e278c6ebe07de1e6b95cba8fd667e335b795',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc3520-p10.png',
  'body_sha256','db7e6e97feaaa9c08f43b6cb8b02ffc26322f0f684f616553f2e933a43fc9c54',
  'owner_decision',jsonb_build_object('export','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
                                      'document_id',3520,'question_id','q1','choice','omitted'),
  'finding','Contents page 1 lists s.'||v.label||' with no Omitted mark. Body page 10 prints between s.8 and s.11 only the stub ''1[9, 10 * * *]'' with footnote 1 ''Section 9 and 10 omitted Ordinance ibid vide No.X of 1984.''; no text of s.'||v.label||' is printed.'),
 'claude.disposition-review/2'
FROM (VALUES (8,:fill_entry_9::bigint,'9','Adoption of restrictions of section 8 in respect of other highways.'),
             (9,:fill_entry_10::bigint,'10','Compensation.')) AS v(ord,entry,label,heading);

COMMIT;
