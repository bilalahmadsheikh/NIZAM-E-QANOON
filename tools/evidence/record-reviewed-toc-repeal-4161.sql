-- Drafted by agent JD (export j, 12 Oct 2026); renamed and applied by builder BZ on 13 Oct 2026. Doc 4161 The Canal and Drainage Act, 1873 (KP copy).
-- Owner decision decision-review-2026-10-12-j.json doc 4161 q1 'split': ss.40-43 each a repealed stub, all citing the one
-- printed note 'Rep. by the Punjab Tenancy Act, 1887 (XVI 1887), s. 3 and Sch.' (p23). Contents rows 40-43 print no
-- lifecycle word -> rule body_evidenced_disposition (evidence carries body_render/body_sha256). Apply AFTER recording
-- claude/agJD/patch-4161.json (sets the printed joint stub block 605332 aside). Re-check the entry ids after any replay.
BEGIN;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM instrument i JOIN instrument_toc_entry e ON e.instrument_id=i.id
     WHERE i.source_observation_id=1573 AND i.expression_ordinal=0 AND i.is_active AND i.duplicate_of IS NULL
       AND e.id=1025067 AND e.ordinal=39 AND e.printed_label='40'
       AND e.printed_heading='When occupier is to pay both owner''s rate and occupier''s rate.' AND e.source_block_id=605013 AND e.source_page=3)
  OR EXISTS (SELECT 1 FROM v_toc_disposition_assertion_latest a WHERE a.source_observation_id=1573
       AND a.expression_ordinal=0 AND a.reviewed_toc_entry_id=1025067)
  THEN RAISE EXCEPTION 'doc 4161 row 40: live anchor changed or already reviewed'; END IF;
END $$;
INSERT INTO toc_disposition_assertion (source_observation_id,expression_ordinal,toc_entry_ordinal,reviewed_toc_entry_id,
 printed_label,printed_heading,disposition,source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES (1573,0,39,1025067,'40','When occupier is to pay both owner''s rate and occupier''s rate.','repealed',
 605013,3,'.artifacts/release-work-2026-09-24/claude/renders/doc4161-p23.png','ceddd8d604394c271bc036e488f8894c22aa65fd4ff84ee53ae2a079a1284b5e',
 'Punjab Tenancy Act, 1887 (XVI 1887), s. 3 and Sch.','{"visual_review": true, "reviewer_type": "ai_assistant", "owner_decision": {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json", "document_id": 4161, "question_id": "q1"}, "contents_render": ".artifacts/release-work-2026-09-24/claude/renders/doc4161-p3.png", "contents_sha256": "c05327e30cf1c2caf841f76e5eb830b2c80a22adc923ff5314f9be9bae8a249d", "body_render": ".artifacts/release-work-2026-09-24/claude/renders/doc4161-p23.png", "body_sha256": "ceddd8d604394c271bc036e488f8894c22aa65fd4ff84ee53ae2a079a1284b5e", "finding": "Contents page 3 prints row ''40. When occupier is to pay both owner''s rate and occupier''s rate.'' with no lifecycle word. Body page 23 prints one joint stub ''40 to 43. [When occupier to pay both rates: apportionment of owner''s when owner to pay owner''s rate : effect of introduction of canal-irrigation on landlord''s right to enhance.] Rep. by the Punjab Tenancy Act, 1887 (XVI 1887), s. 3 and Sch.''; owner (export j q1 ''split'') holds each of ss.40-43 as a repealed stub citing that note."}'::jsonb,'claude.source_review.agJD/1');
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM instrument i JOIN instrument_toc_entry e ON e.instrument_id=i.id
     WHERE i.source_observation_id=1573 AND i.expression_ordinal=0 AND i.is_active AND i.duplicate_of IS NULL
       AND e.id=1025068 AND e.ordinal=40 AND e.printed_label='41'
       AND e.printed_heading='Power to make rules for apportioning owner''s rate.' AND e.source_block_id=605014 AND e.source_page=3)
  OR EXISTS (SELECT 1 FROM v_toc_disposition_assertion_latest a WHERE a.source_observation_id=1573
       AND a.expression_ordinal=0 AND a.reviewed_toc_entry_id=1025068)
  THEN RAISE EXCEPTION 'doc 4161 row 41: live anchor changed or already reviewed'; END IF;
END $$;
INSERT INTO toc_disposition_assertion (source_observation_id,expression_ordinal,toc_entry_ordinal,reviewed_toc_entry_id,
 printed_label,printed_heading,disposition,source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES (1573,0,40,1025068,'41','Power to make rules for apportioning owner''s rate.','repealed',
 605014,3,'.artifacts/release-work-2026-09-24/claude/renders/doc4161-p23.png','ceddd8d604394c271bc036e488f8894c22aa65fd4ff84ee53ae2a079a1284b5e',
 'Punjab Tenancy Act, 1887 (XVI 1887), s. 3 and Sch.','{"visual_review": true, "reviewer_type": "ai_assistant", "owner_decision": {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json", "document_id": 4161, "question_id": "q1"}, "contents_render": ".artifacts/release-work-2026-09-24/claude/renders/doc4161-p3.png", "contents_sha256": "c05327e30cf1c2caf841f76e5eb830b2c80a22adc923ff5314f9be9bae8a249d", "body_render": ".artifacts/release-work-2026-09-24/claude/renders/doc4161-p23.png", "body_sha256": "ceddd8d604394c271bc036e488f8894c22aa65fd4ff84ee53ae2a079a1284b5e", "finding": "Contents page 3 prints row ''41. Power to make rules for apportioning owner''s rate.'' with no lifecycle word. Body page 23 prints one joint stub ''40 to 43. [When occupier to pay both rates: apportionment of owner''s when owner to pay owner''s rate : effect of introduction of canal-irrigation on landlord''s right to enhance.] Rep. by the Punjab Tenancy Act, 1887 (XVI 1887), s. 3 and Sch.''; owner (export j q1 ''split'') holds each of ss.40-43 as a repealed stub citing that note."}'::jsonb,'claude.source_review.agJD/1');
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM instrument i JOIN instrument_toc_entry e ON e.instrument_id=i.id
     WHERE i.source_observation_id=1573 AND i.expression_ordinal=0 AND i.is_active AND i.duplicate_of IS NULL
       AND e.id=1025069 AND e.ordinal=41 AND e.printed_label='42'
       AND e.printed_heading='When owner is to pay owner''s rate.' AND e.source_block_id=605015 AND e.source_page=3)
  OR EXISTS (SELECT 1 FROM v_toc_disposition_assertion_latest a WHERE a.source_observation_id=1573
       AND a.expression_ordinal=0 AND a.reviewed_toc_entry_id=1025069)
  THEN RAISE EXCEPTION 'doc 4161 row 42: live anchor changed or already reviewed'; END IF;
END $$;
INSERT INTO toc_disposition_assertion (source_observation_id,expression_ordinal,toc_entry_ordinal,reviewed_toc_entry_id,
 printed_label,printed_heading,disposition,source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES (1573,0,41,1025069,'42','When owner is to pay owner''s rate.','repealed',
 605015,3,'.artifacts/release-work-2026-09-24/claude/renders/doc4161-p23.png','ceddd8d604394c271bc036e488f8894c22aa65fd4ff84ee53ae2a079a1284b5e',
 'Punjab Tenancy Act, 1887 (XVI 1887), s. 3 and Sch.','{"visual_review": true, "reviewer_type": "ai_assistant", "owner_decision": {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json", "document_id": 4161, "question_id": "q1"}, "contents_render": ".artifacts/release-work-2026-09-24/claude/renders/doc4161-p3.png", "contents_sha256": "c05327e30cf1c2caf841f76e5eb830b2c80a22adc923ff5314f9be9bae8a249d", "body_render": ".artifacts/release-work-2026-09-24/claude/renders/doc4161-p23.png", "body_sha256": "ceddd8d604394c271bc036e488f8894c22aa65fd4ff84ee53ae2a079a1284b5e", "finding": "Contents page 3 prints row ''42. When owner is to pay owner''s rate.'' with no lifecycle word. Body page 23 prints one joint stub ''40 to 43. [When occupier to pay both rates: apportionment of owner''s when owner to pay owner''s rate : effect of introduction of canal-irrigation on landlord''s right to enhance.] Rep. by the Punjab Tenancy Act, 1887 (XVI 1887), s. 3 and Sch.''; owner (export j q1 ''split'') holds each of ss.40-43 as a repealed stub citing that note."}'::jsonb,'claude.source_review.agJD/1');
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM instrument i JOIN instrument_toc_entry e ON e.instrument_id=i.id
     WHERE i.source_observation_id=1573 AND i.expression_ordinal=0 AND i.is_active AND i.duplicate_of IS NULL
       AND e.id=1025070 AND e.ordinal=42 AND e.printed_label='43'
       AND e.printed_heading='Effect of introduction of canal irrigation on landlord''s right to enhance.' AND e.source_block_id=605018 AND e.source_page=4)
  OR EXISTS (SELECT 1 FROM v_toc_disposition_assertion_latest a WHERE a.source_observation_id=1573
       AND a.expression_ordinal=0 AND a.reviewed_toc_entry_id=1025070)
  THEN RAISE EXCEPTION 'doc 4161 row 43: live anchor changed or already reviewed'; END IF;
END $$;
INSERT INTO toc_disposition_assertion (source_observation_id,expression_ordinal,toc_entry_ordinal,reviewed_toc_entry_id,
 printed_label,printed_heading,disposition,source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES (1573,0,42,1025070,'43','Effect of introduction of canal irrigation on landlord''s right to enhance.','repealed',
 605018,4,'.artifacts/release-work-2026-09-24/claude/renders/doc4161-p23.png','ceddd8d604394c271bc036e488f8894c22aa65fd4ff84ee53ae2a079a1284b5e',
 'Punjab Tenancy Act, 1887 (XVI 1887), s. 3 and Sch.','{"visual_review": true, "reviewer_type": "ai_assistant", "owner_decision": {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json", "document_id": 4161, "question_id": "q1"}, "contents_render": ".artifacts/release-work-2026-09-24/claude/renders/doc4161-p4.png", "contents_sha256": "2262f7c510ba24ab093c554a25d02aa3d9c413d433acb6d2c8187cef4415f1f3", "body_render": ".artifacts/release-work-2026-09-24/claude/renders/doc4161-p23.png", "body_sha256": "ceddd8d604394c271bc036e488f8894c22aa65fd4ff84ee53ae2a079a1284b5e", "finding": "Contents page 4 prints row ''43. Effect of introduction of canal irrigation on landlord''s right to enhance.'' with no lifecycle word. Body page 23 prints one joint stub ''40 to 43. [When occupier to pay both rates: apportionment of owner''s when owner to pay owner''s rate : effect of introduction of canal-irrigation on landlord''s right to enhance.] Rep. by the Punjab Tenancy Act, 1887 (XVI 1887), s. 3 and Sch.''; owner (export j q1 ''split'') holds each of ss.40-43 as a repealed stub citing that note."}'::jsonb,'claude.source_review.agJD/1');
COMMIT;
