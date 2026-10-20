-- Drafted by agent JD (claude/agJD/disp-3901-DRAFT.json, 13 Oct 2026); written as SQL and applied by builder BZ on
-- 14 Oct 2026 with the replayed contents entry id. Doc 3901 (Town Improvement Act 1922), observation 3389: contents row
-- '8 to 11' (read by rule range_to_contents_row) is 'omitted' -- W.P. Ord. XVIII of 1962, s.5 substituted Chapter II.
\set ON_ERROR_STOP on
BEGIN;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM v_toc_disposition_assertion_latest a WHERE a.source_observation_id=3389 AND a.expression_ordinal=0 AND a.reviewed_toc_entry_id=1140445) THEN RAISE EXCEPTION 'already reviewed'; END IF; END $$;
INSERT INTO toc_disposition_assertion (source_observation_id,expression_ordinal,toc_entry_ordinal,reviewed_toc_entry_id,
 printed_label,printed_heading,disposition,source_block_id,source_page,render_artifact,render_sha256,
 amending_instrument_citation,evidence,reviewed_by)
VALUES (3389,0,7,1140445,'8 to 11','Omitted.','omitted',516032,1,'.artifacts/release-work-2026-09-24/claude/renders/doc3901-p1.png','29dd4f744c42b215ca71f95de2070f0f56a6220c86a3ee50a97b5267e9c14f5e','W.P. Ord. XVIII of 1962, s.5 (Chapter II, sections 3 to 11, substituted)','{"visual_review": true, "reviewer_type": "ai_assistant", "owner_decision": {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json", "document_id": 3901, "question_id": "q1"}, "contents_render": ".artifacts/release-work-2026-09-24/claude/renders/doc3901-p1.png", "contents_sha256": "29dd4f744c42b215ca71f95de2070f0f56a6220c86a3ee50a97b5267e9c14f5e", "body_render": ".artifacts/release-work-2026-09-24/claude/renders/doc3901-p11.png", "body_sha256": "21e48ee65673d6cb208f3a03d7097dc77f7bff6be4ab09e4cec41bd3d6a858f0", "finding": "Contents p1 prints one range row ''8. / to / 11. Omitted.'' under Chapter II (footnote 1 ''Chapter II (Sections 3 to 11), Subs. By W.P. Ord. XVIII of 1962, s.5.''); body p11 prints ss.3-7 of the substituted Chapter II then CHAPTER III and s.12. Owner (export j q1 ''one-entry''): one omitted entry labelled ''8 to 11''."}'::jsonb,'claude.source_review.agJD/1');
COMMIT;
