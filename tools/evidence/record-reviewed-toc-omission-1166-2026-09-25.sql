-- Balochistan Revenue Authority Act, 2015 (document 1166, observation 1368):
-- the official consolidation's contents page 1 prints rows '14. Section 14
-- omitted' and '15. Section 15 omitted'; body page 14 prints, under CHAPTER IV
-- ADMINISTRATION OF TAXES, only '[***] [Section 14 omitted]' and '[***]
-- [Section 15 omitted]' with footnotes 3-4 (sections 14 and 15 with marginal
-- headings omitted by the Balochistan Revenue Authority (Amendment) Act, 2019,
-- Act No. I of 2019). Record the exact current contents anchors; a bounded
-- replay applies them. Release agent D, 25 Sep 2026.
BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM instrument i
    JOIN instrument_toc_entry e ON e.instrument_id=i.id
    WHERE i.source_observation_id=1368 AND i.expression_ordinal=0
      AND i.is_active AND i.duplicate_of IS NULL
      AND e.id=1043537 AND e.ordinal=13
      AND e.printed_label='14'
      AND e.printed_heading='Section 14 omitted'
      AND e.source_block_id=57944 AND e.source_page=1
  ) OR NOT EXISTS (
    SELECT 1 FROM instrument i
    JOIN instrument_toc_entry e ON e.instrument_id=i.id
    WHERE i.source_observation_id=1368 AND i.expression_ordinal=0
      AND i.is_active AND i.duplicate_of IS NULL
      AND e.id=1043538 AND e.ordinal=14
      AND e.printed_label='15'
      AND e.printed_heading='Section 15 omitted'
      AND e.source_block_id=57945 AND e.source_page=1
  ) OR EXISTS (
    SELECT 1 FROM v_toc_disposition_assertion_latest a
    WHERE a.source_observation_id=1368 AND a.expression_ordinal=0
      AND a.reviewed_toc_entry_id IN (1043537,1043538)
  ) THEN
    RAISE EXCEPTION 'doc 1166 live anchor changed or already reviewed';
  END IF;
END $$;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES
(1368,0,13,1043537,'14','Section 14 omitted','omitted',
 57944,1,
 '.artifacts/release-work-2026-09-24/claude/renders/doc1166-p14.png',
 '482a961c0530c8548e402cede47339776183ab8b505ed893a8bf85f8f3400a14',
 'Balochistan Revenue Authority (Amendment) Act, 2019 (Act No. I of 2019)',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'review_batch','claude-agD-2026-09-25',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc1166-p1.png',
  'contents_sha256','f862d57c59eb15ddb4aabdcfe51720345674f9e7db1315bd06bef69e119314a0',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc1166-p14.png',
  'body_sha256','482a961c0530c8548e402cede47339776183ab8b505ed893a8bf85f8f3400a14',
  'finding','Contents page 1 lists 13. Advisory Council., 14. Section 14 omitted, 15. Section 15 omitted, 16. Fund. Body page 14 prints section 13(2)-(7), then CHAPTER IV ADMINISTRATION OF TAXES with only 2[***] 3[Section 14 omitted] and 3[***] 4[Section 15 omitted]; footnote 3 reads Section 14 with marginal heading omitted, by the Balochistan Revenue Authority (Amendment) Act, 2019 (Act No. I of 2019). No operative section-14 text remains.'),
 'claude.disposition-review/2'),
(1368,0,14,1043538,'15','Section 15 omitted','omitted',
 57945,1,
 '.artifacts/release-work-2026-09-24/claude/renders/doc1166-p14.png',
 '482a961c0530c8548e402cede47339776183ab8b505ed893a8bf85f8f3400a14',
 'Balochistan Revenue Authority (Amendment) Act, 2019 (Act No. I of 2019)',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'review_batch','claude-agD-2026-09-25',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc1166-p1.png',
  'contents_sha256','f862d57c59eb15ddb4aabdcfe51720345674f9e7db1315bd06bef69e119314a0',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc1166-p14.png',
  'body_sha256','482a961c0530c8548e402cede47339776183ab8b505ed893a8bf85f8f3400a14',
  'finding','Contents page 1 lists 15. Section 15 omitted. Body page 14 prints under CHAPTER IV only 3[***] 4[Section 15 omitted]; footnote 4 reads Section 15 with marginal heading omitted, ibid. (Balochistan Revenue Authority (Amendment) Act, 2019). No operative section-15 text remains.'),
 'claude.disposition-review/2');
COMMIT;
