-- WITHDRAWN -- DO NOT RE-RUN. The disposition lane applies only to a contents row
-- that itself prints [Omitted]/[Repealed]; this one does not, and the replay
-- refused it as stale. Removed by withdraw-stale-toc-omission-2783-2026-09-24.sql.
-- Revenue Recovery Act, 1890 (document 2783, observation 12): the
-- official copy prints section 11 only as an omission stub. Record the exact
-- current contents anchor; the exact-tree overlay
-- (tools/materialize_toc_dispositions.py) is a separate bounded step.
BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM instrument i
    JOIN instrument_toc_entry e ON e.instrument_id=i.id
    WHERE i.source_observation_id=12 AND i.expression_ordinal=0
      AND i.is_active AND i.duplicate_of IS NULL
      AND e.id=1073277 AND e.ordinal=10
      AND e.printed_label='11'
      AND e.printed_heading='Recovery in the Provinces of land-revenue, etc., accruing in an Acceding State.'
      AND e.source_block_id=248231 AND e.source_page=1
  ) OR EXISTS (
    SELECT 1 FROM v_toc_disposition_assertion_latest a
    WHERE a.source_observation_id=12 AND a.expression_ordinal=0
      AND a.reviewed_toc_entry_id=1073277
  ) THEN
    RAISE EXCEPTION 'doc 2783 live anchor changed or already reviewed';
  END IF;
END $$;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES (
 12,0,10,1073277,'11','Recovery in the Provinces of land-revenue, etc., accruing in an Acceding State.','omitted',
 248231,1,
 '.artifacts/release-work-2026-09-24/claude/renders/doc2783-p5.png',
 '20b5187b26619b97943fd3eecec87fb482be8445947d79d949708b8a1f5e81e1',
 'Federal Laws (Revision and Declaration) Ordinance, 1981 (XXVII of 1981), s. 3 and Sch. II',
 jsonb_build_object(
  'visual_review',true,'reviewer_type','ai_assistant',
  'review_batch','claude-2026-09-24',
  'contents_render','.artifacts/release-work-2026-09-24/claude/renders/doc2783-p1.png',
  'contents_sha256','506d47bc4d8ccf03779fa0cba8f9aef46307a15e70963b416e5a5a6ae241af8d',
  'body_render','.artifacts/release-work-2026-09-24/claude/renders/doc2783-p5.png',
  'body_sha256','20b5187b26619b97943fd3eecec87fb482be8445947d79d949708b8a1f5e81e1',
  'finding','Contents page 1 lists sections 1-11, row 11 Recovery in the Provinces of land-revenue, etc., accruing in an Acceding State. Body page 5 prints 11. [Recovery in the Provinces of land-revenue, etc., accruing in an Acceding State.] Omitted by the Federal Laws (Revision and Declaration) Ordinance, 1981 (XXVII of 1981), s. 3 and Sch. II., its number carrying footnote 4 (Sec. 11 added by the Revenue Recovery (Amdt.) Act, 1950); no operative section-11 text remains.'),
 'claude.disposition-review/2');
COMMIT;
