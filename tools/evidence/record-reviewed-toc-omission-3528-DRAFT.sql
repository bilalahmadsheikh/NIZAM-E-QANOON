-- DRAFT by agent JC (13 Oct 2026, prepare mode; NOT RUN). Pattern: record-reviewed-toc-omission-3604-DRAFT.sql,
-- rule `body_evidenced_disposition` (the contents rows print NO lifecycle word; the body prints the omission).
--
-- Document 3528, The West Pakistan Finance Act, 1963 (W.P. Act No. IX of 1963; 15 pages), observation 1533.
-- Owner decision: decision-review-2026-10-12-j.json (export k is a superset), document 3528, q1 'omitted' (reviewer
-- Bilal Ahmad): ss.3, 11, 12, 13 and 16 are each recorded as omitted by the Khyber Pakhtunkhwa Adaptation of Laws
-- Order, 1975, on the evidence of the printed stubs and footnotes; the contents rows link to those entries; no text
-- is invented.
--
-- Read from the renders on 2026-10-13 (agent JC):
--   p1 (doc3528-p1.png 56b081b1...) contents rows '3. Surcharge on land revenue in certain districts.' (block 402364),
--      '1[11. Tolls on vessels plying in inland waters.' (402372), '12. Toll on fares and freights on inland traffic by
--      vessels.' (402373), '13. Surcharge on Betting Tax.]' (402374), '2[16. Capital gain tax.]' (402377); no
--      'Omitted' in any row; footnotes 1 and 2 'Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.'
--   p3 (doc3528-p3.png 19b7754f...) after s.2(b): '3[(c)............]' and '4[3. ..............]' with the margin note
--      'Surcharge on land revenue in certain districts.'; footnote 4 'Omitted vide Khyber Pakhtunkhwa Adaptation of
--      Laws Order, 1975.'
--   p7 (doc3528-p7.png 8a209c17...) '1[11,12,13 ............]' at the head of the page and '2[16..................].'
--      after s.15(5); footnotes 1 and 2 'Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.'
-- Proved in memory (agJC-disp.sh 3528 with $S/agJC-disp3528.json injected): five omitted entries created, 75 paths,
-- contents unlinked [] (was 3, 11, 12, 13, 16), S7 [].
--
-- ORDER: the document is NOT ready to release on this file alone -- see claude/agJC/card-3528-s7.json (s.7 items
-- (i)-(iii) are not printed) and agJC-log.md (engineering still open). When it proceeds: replay, then FILL each
-- reviewed_toc_entry_id below with the replayed instrument_toc_entry id of ordinal 2/10/11/12/15 (labels 3, 11, 12,
-- 13, 16), run this file, and replay again so the assertions materialise the omitted entries.

\set ON_ERROR_STOP on
BEGIN;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
SELECT 1533,0,v.ord,v.entry,v.label,v.heading,'omitted',v.block,1,
       v.body_render,v.body_sha,
       'Khyber Pakhtunkhwa Adaptation of Laws Order, 1975',
       jsonb_build_object(
        'visual_review',true,'reviewer_type','ai_assistant',
        'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc3528-p1.png',
        'contents_sha256','56b081b12a9b61e80314a72242df63cb63a7643c484582aa04b0c71646926393',
        'body_render',v.body_render,'body_sha256',v.body_sha,
        'owner_decision',jsonb_build_object('export','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
                                            'document_id',3528,'question_id','q1','choice','omitted'),
        'finding',v.finding),
       'claude.disposition-review/2'
  FROM (VALUES
   (2,:fill_entry_3,'3','Surcharge on land revenue in certain districts.',402364,
    '.artifacts/release-work-2026-09-24/claude/renders/doc3528-p3.png',
    '19b7754fe28384100e12d937e1301fe9f647b97505826302a56cb6f5d05291a4',
    'Contents page 1 lists s.3 with no Omitted mark. Body page 3 prints, after s.2(b), only the stub ''4[3. ..............]'' beside the margin note ''Surcharge on land revenue in certain districts.'', footnote 4 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.''; no s.3 text is printed.'),
   (10,:fill_entry_11,'11','Tolls on vessels plying in inland waters.',402372,
    '.artifacts/release-work-2026-09-24/claude/renders/doc3528-p7.png',
    '8a209c1727a9bf046ea139a38126d69eba832b238cc66de5617db625ab702108',
    'Contents page 1 lists s.11 inside the bracket ''1[11. ... 13. ...]'' with footnote 1 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.'' and no Omitted mark in the row. Body page 7 prints only the joint stub ''1[11,12,13 ............]'', footnote 1 the same; no s.11 text is printed.'),
   (11,:fill_entry_12,'12','Toll on fares and freights on inland traffic by vessels.',402373,
    '.artifacts/release-work-2026-09-24/claude/renders/doc3528-p7.png',
    '8a209c1727a9bf046ea139a38126d69eba832b238cc66de5617db625ab702108',
    'Contents page 1 lists s.12 inside the bracket ''1[11. ... 13. ...]'' with no Omitted mark in the row. Body page 7 prints only the joint stub ''1[11,12,13 ............]'', footnote 1 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.''; no s.12 text is printed.'),
   (12,:fill_entry_13,'13','Surcharge on Betting Tax.]',402374,
    '.artifacts/release-work-2026-09-24/claude/renders/doc3528-p7.png',
    '8a209c1727a9bf046ea139a38126d69eba832b238cc66de5617db625ab702108',
    'Contents page 1 lists s.13 closing the bracket ''1[11. ... 13. Surcharge on Betting Tax.]'' with no Omitted mark in the row. Body page 7 prints only the joint stub ''1[11,12,13 ............]'', footnote 1 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.''; no s.13 text is printed.'),
   (15,:fill_entry_16,'16','Capital gain tax.]',402377,
    '.artifacts/release-work-2026-09-24/claude/renders/doc3528-p7.png',
    '8a209c1727a9bf046ea139a38126d69eba832b238cc66de5617db625ab702108',
    'Contents page 1 lists ''2[16. Capital gain tax.]'' with footnote 2 ''Omitted vide Khyber Pakhtunkhwa Adaptation of Laws Order, 1975.'' and no Omitted mark in the row. Body page 7 prints after s.15(5) only the stub ''2[16..................].'', footnote 2 the same; no s.16 text is printed.')
  ) AS v(ord,entry,label,heading,block,body_render,body_sha,finding);

COMMIT;
