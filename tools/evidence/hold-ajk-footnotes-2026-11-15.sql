-- AJK landing 14 Nov 2026: in released AJK documents the page footnotes printed below the footnote rule -- amendment
-- notes, and the superseded text a revised volume reproduces in them ('The original extract of the Sec. 6 is reproduced
-- as under:- "6. Aims and Objectives ..."', doc 10092 p6) -- were read into the law as provision text. Found by
-- tools/recrawl/footnote_zone.py (the rule read from the PDF's drawings; blocks below it whose every span is set at
-- least 1pt smaller than the law; the zone opening with a note marker or continuing the previous page's notes); pages
-- read: 9940 p1, 9958 p4, 10063 p4, 10092 pp4 6, 10927 p9, 10959 p2, 11153 p13 (and 11262 p2, whose fused law-and-note
-- block is excluded by the every-span test). Held while those blocks are set aside as footnotes (patch-DOCf.json, rule
-- reviewed_apparatus_block, no law text edited), then re-verified and released. __DOCS__ is filled by the apply script.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('page footnotes read into released provision text'), '[]'::jsonb,
       jsonb_build_object('reason', 'page footnotes (amendment notes and reproduced superseded text) read into released '
                                    'provision text; taken out of the release while they are set aside as footnotes and '
                                    'the text re-verified',
                          'reverify', 'verify_text_quality is re-run after the repair')
  FROM unnest(ARRAY[__DOCS__]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
