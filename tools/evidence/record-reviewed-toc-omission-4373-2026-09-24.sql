-- Sind Co-operative Societies Act, 1925 (document 4373, observation 133): the
-- official copy prints section 72 only as an omission stub. Record the exact
-- current contents anchor; the exact-tree overlay
-- (tools/materialize_toc_dispositions.py) is a separate bounded step.
BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM instrument i
    JOIN instrument_toc_entry e ON e.instrument_id=i.id
    WHERE i.source_observation_id=133 AND i.expression_ordinal=0
      AND i.is_active AND i.duplicate_of IS NULL
      AND e.id=1018599 AND e.ordinal=112
      AND e.printed_label='72'
      AND e.printed_heading='Saving of existing Societies.[Omitted.]'
      AND e.source_block_id=707828 AND e.source_page=5
  ) OR EXISTS (
    SELECT 1 FROM v_toc_disposition_assertion_latest a
    WHERE a.source_observation_id=133 AND a.expression_ordinal=0
      AND a.reviewed_toc_entry_id=1018599
  ) THEN
    RAISE EXCEPTION 'doc 4373 live anchor changed or already reviewed';
  END IF;
END $$;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES (
 133,0,112,1018599,'72','Saving of existing Societies.[Omitted.]','omitted',
 707828,5,
 '.artifacts/release-work-2026-09-24/claude/renders/doc4373-p45.png',
 'a941e3bc7e27b0d32af6b3a3350991881603b54b27ebc372dbd0202d554e46aa',
 'Sind Act XVII of 1975',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'review_batch','claude-2026-09-24',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc4373-p5.png',
  'contents_sha256','04f7eb2b4fada7b2562d38aecd8c6a350c220b5f66a6ff5e5042f3e8e94a09de',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc4373-p45.png',
  'body_sha256','a941e3bc7e27b0d32af6b3a3350991881603b54b27ebc372dbd0202d554e46aa',
  'finding','Contents page 5 lists 71 Rules., 72 Saving of existing Societies.[Omitted.], 72A Construction of references ..., 72B [Repealed]., 73 [Repealed]. Body page 45 prints section 71(3)-(5), then 72. [Saving of existing societies]. Omitted by Sind Act XVII of 1975., then 72A, 72B and 73; no operative section-72 text remains.'),
 'claude.disposition-review/2');
COMMIT;
