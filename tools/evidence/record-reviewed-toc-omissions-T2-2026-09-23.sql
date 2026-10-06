-- Three source-reviewed omissions in the bounded T2 batch. Contents and body
-- page renders are preserved under .artifacts/release-batches/T2/omitted/.
-- This records evidence only; materialize_toc_dispositions applies the tree
-- overlays separately after a dry run.
BEGIN;

CREATE TEMP TABLE _t2_omission (
  observation_id bigint, entry_id bigint, entry_ordinal integer,
  label text, heading text, toc_block bigint, toc_page integer,
  body_render text, body_sha text, contents_render text, contents_sha text,
  citation text, finding text
) ON COMMIT DROP;

INSERT INTO _t2_omission VALUES
(1486,1066692,3,'4','Bar on alienation of Project Land.',75767,1,
 '.artifacts/release-batches/T2/omitted/doc1351-e1066692-label4-p3.png',
 'f60263a368ac1e1c1eb28e3e411786267ad9b3c54073de7a0495c1bf49f4a9cf',
 '.artifacts/release-batches/T2/omitted/doc1351-e1066692-label4-p1.png',
 '892ea9c15cfe2e75747c643b797deed02d800f8e6216a7d6f3606d19d4b9c6ef',
 'W. P. Ord. IV of 1969, s. 2',
 'Contents page 1 promises section 4. Body page 3 prints an omission marker between sections 3 and 5; the footnote expressly says section 4 was omitted.'),
(1465,1071864,11,'12','Repeal of Act No. LXVI of 1950.]',77069,1,
 '.artifacts/release-batches/T2/omitted/doc1366-e1071864-label12-p6.png',
 '9d1cd002105fed67dd282485dc75d0f03a1dad042864ddacaa0fba6314ff5682',
 '.artifacts/release-batches/T2/omitted/doc1366-e1071864-label12-p1.png',
 '29fac075b623c43fc6f0409ad020e93e426318889c7824f72441eb1c5f3d212f',
 'Khyber Pakhtunkhwa Adaptation of Laws Order, 1975',
 'Contents page 1 promises section 12. Body page 6 prints section 12 as dots after section 11; the footnote expressly says it was omitted.'),
(1445,1071826,3,'4','Bar on Alienation of Project Land.',99562,1,
 '.artifacts/release-batches/T2/omitted/doc1609-e1071826-label4-p3.png',
 '506de927df4a918662334a2f3a0dbd3239d08b2fe3c7dfb08dedfe67ff1a48a6',
 '.artifacts/release-batches/T2/omitted/doc1609-e1071826-label4-p1.png',
 '65a5d86fc286779164959e4f3a85a177d35ccda9e1900a7b72f630d3787eeaa7',
 'W.P. Act IV of 1969',
 'Contents page 1 promises section 4. Body page 3 prints section 4 as stars between sections 3 and 5; the footnote expressly says it was omitted.');

DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM _t2_omission x
  JOIN instrument i ON i.source_observation_id=x.observation_id
                   AND i.expression_ordinal=0 AND i.is_active
                   AND i.duplicate_of IS NULL
  JOIN instrument_toc_entry e ON e.id=x.entry_id AND e.instrument_id=i.id
         AND e.ordinal=x.entry_ordinal AND e.printed_label=x.label
         AND e.printed_heading=x.heading AND e.source_block_id=x.toc_block
         AND e.source_page=x.toc_page
  WHERE NOT EXISTS (SELECT 1 FROM v_toc_disposition_assertion_latest a
                    WHERE a.source_observation_id=x.observation_id
                      AND a.expression_ordinal=0
                      AND a.reviewed_toc_entry_id=x.entry_id);
  IF n <> 3 THEN
    RAISE EXCEPTION 'T2 exact live anchor/unreviewed gate: expected 3, got %', n;
  END IF;
END $$;

INSERT INTO toc_disposition_assertion (
 source_observation_id,expression_ordinal,toc_entry_ordinal,
 reviewed_toc_entry_id,printed_label,printed_heading,disposition,
 source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
SELECT observation_id,0,entry_ordinal,entry_id,label,heading,'omitted',
       toc_block,toc_page,body_render,body_sha,citation,
       jsonb_build_object('visual_review',true,
                          'reviewer_type','ai_assistant',
                          'review_batch','T2-2026-09-23',
                          'contents_render',contents_render,
                          'contents_sha256',contents_sha,
                          'body_render',body_render,
                          'body_sha256',body_sha,
                          'finding',finding),
       'codex.source_review.T2/1'
FROM _t2_omission;

SELECT count(*) AS t2_assertions_written
FROM toc_disposition_assertion WHERE reviewed_by='codex.source_review.T2/1';
COMMIT;
