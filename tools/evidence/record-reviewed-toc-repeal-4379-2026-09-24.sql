-- Succession Act, 1925 (document 4379, observation 187): the official copy
-- prints section 392 only as a repeal stub. Record the exact current contents
-- anchor; the exact-tree overlay (tools/materialize_toc_dispositions.py) is a
-- separate bounded step.
BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM instrument i
    JOIN instrument_toc_entry e ON e.instrument_id=i.id
    WHERE i.source_observation_id=187 AND i.expression_ordinal=0
      AND i.is_active AND i.duplicate_of IS NULL
      AND e.id=1004953 AND e.ordinal=385
      AND e.printed_label='392' AND e.printed_heading='Repeal'
      AND e.source_block_id=711431 AND e.source_page=19
  ) OR EXISTS (
    SELECT 1 FROM v_toc_disposition_assertion_latest a
    WHERE a.source_observation_id=187 AND a.expression_ordinal=0
      AND a.reviewed_toc_entry_id=1004953
  ) THEN
    RAISE EXCEPTION 'doc 4379 live anchor changed or already reviewed';
  END IF;
END $$;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES (
 187,0,385,1004953,'392','Repeal','repealed',
 711431,19,
 '.artifacts/release-work-2026-09-24/claude/renders/doc4379-p127.png',
 'ef7a74ec1e168cd0c3e8436593ba2cf0a02a9248dc1e8fe6233f140533da0de2',
 'Repealing Act, 1927 (XII of 1927), s. 2 and Sch.',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'review_batch','claude-2026-09-24',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc4379-p19.png',
  'contents_sha256','74a26c00b711d5804f440d7088a0744b633f8daf104e38125b6a89a4987353ff',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc4379-p127.png',
  'body_sha256','ef7a74ec1e168cd0c3e8436593ba2cf0a02a9248dc1e8fe6233f140533da0de2',
  'finding','Contents page 19 (Part XI Miscellaneous) promises 391 Saving and 392 Repeal. Body page 127 prints section 391 with clauses (i) to (iv) and then 392. [Repeals.] Rep. by the Repealing Act, 1927 (XII of 1927), s. 2 and Sch.; no operative section-392 text remains.'),
 'claude.disposition-review/2');
COMMIT;
