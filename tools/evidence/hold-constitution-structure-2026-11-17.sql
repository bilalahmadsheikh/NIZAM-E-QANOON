-- 17 Nov 2026, the Constitution of 1973 as consolidated in the Pakistan Code (document 4419), DECISION-LOG D-069.
-- The released tree starts at Article 1: the Preamble (pp17-18) and 'PART I / INTRODUCTORY' (p19) were read as
-- contents, and the Annex's recital (the Objectives Resolution, p145) became the instrument's Preamble. Two
-- page-read readings (tools/evidence/constitution-4419-2026-11-17/readings.json) set the body start at the PREAMBLE
-- head and open the Annex. Held while the replay runs, then re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('preamble and Part I read as contents; the Annex served as the preamble'),
       '[]'::jsonb,
       jsonb_build_object('reason', 'the Preamble is not served, Articles 1-6 stand outside Part I and the Annex is '
                                    'labelled Preamble; taken out of the release while the tree is rebuilt from the '
                                    'page-read body start and Annex opener',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the replay')
  FROM unnest(ARRAY[4419]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
