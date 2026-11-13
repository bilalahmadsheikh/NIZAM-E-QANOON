-- A1 (13 Nov 2026): released sections whose label is not the printed section number (INV-1), found by
-- tools/audit/label-disagrees-with-first-block.sql and separated from the correct-as-released classes by
-- tools/audit/label_triage.py. Each document below is taken out of the release while it is repaired from its page
-- image (procedure of P.O. 22, tools/evidence/hold-po22-1979-2026-11-12.sql), then the hold is lifted.
--
--   7527  Municipal Administration Ordinance, 1960 (Gazette Extraordinary, 11 Apr 1960). The running head
--         '414. THE GAZETTE ...' was released as section 4 holding s.77(3)-(6); '100. Education' (read '109') as
--         section 9; '111. Control over the activities of Municipal Committees' (read '411') as section 411; sections
--         108 and 123 were released as 8 and 3 behind them.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'released sections carry labels that are not their printed numbers (INV-1); '
                                    'taken out of the release while repaired from the page image and re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES (7527, 'running head 414 released as section 4 holding s.77(3)-(6); sections 100, 108, 111 and 123 '
                      'released as 9, 8, 411 and 3 (text-layer misreads 109 and 411)')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at >= '2026-11-13 00:00+00');
COMMIT;

-- REPAIR AND LIFT, 7527 (13 Nov 2026). Patches -a1 then -a2 from .artifacts/recrawl-queue/specs/blockfix-7527.json
-- (built by .artifacts/a1-labels/make_7527_a2.py; every page it touches rendered under
-- .artifacts/release-work-2026-09-24/claude/renders/doc7527-p*.png): running heads 414 and 422 set aside; sections 2,
-- 4(2) tail, 5 and 6 transcribed from pages 394 and 397; 36 section openers corrected (comma read for the full stop,
-- or a misread number: 109->100, 411->111, 166->106, 17->77, 24->94, $9->99, 6->116, 1->11, heads glued to 15, 23,
-- 129). Tree after replay: sections 1-130 in printed order, 907 provisions (815 before). Sections 18, 37, 54, 57, 62,
-- 69, 80, 95, 113, 114 and 118 are still not opened: the text layer did not read their numbers, and their text stays
-- inside the preceding section until the document is re-read (re-OCR queued: the text layer is garbled throughout).
-- Lift: nizam.workers.verify_text_quality re-run on the repaired document (statutory-language rate 0.420, passed),
-- which supersedes the hold row; released again.
