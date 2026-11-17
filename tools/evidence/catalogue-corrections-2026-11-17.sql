-- Catalogue corrections for five released laws, each read from the law's own printed text (migration 0101).
--
--   6688   kind act -> ordinance, year 1942 -> 1943, and the display title: the short-title clause is OCR-fused with
--          its side note 'Short title and commencement' ('Civil Pioneer ene and mmencs- Force'); the clause names
--          the Civil Pioneer Force (Amendment) Ordinance, 1943, made under s.72 of the Government of India Act.
--   8846   year 1883 -> 1896, number I. The Gazette heading prints 'Act No, | OF 1896,'; the '|' is the numeral I
--          as the page render shows ('Act No. I of 1896', the reviewed display title already recorded).
--   9067   year 1860 -> 1870, number XXVII ('Acr No. XXVII or 1870.' -- OCR for 'Act No. XXVII of 1870.').
--   11382  year 2016 -> 2014 ('This Act may be called the ... Environmental Protection Act, 2014.').
--   11379  kind act -> rules ('These rules may be called the ... Finance Committee Rules-2010.').
-- Append-only; a later reading supersedes by a newer row. tools/apply_instrument_metadata.py --apply writes them.

BEGIN;

WITH d(doc, field, value, block, quote, basis) AS (VALUES
  (6688,  'kind', 'ordinance', 1582605,
   '1. (1) This Ordinance may be called the Civil Pioneer ene and mmencs- Force (Amendment) Ordinance, 1943.',
   'printed_short_title_clause'),
  (6688,  'year', '1943', 1582605,
   '1. (1) This Ordinance may be called the Civil Pioneer ene and mmencs- Force (Amendment) Ordinance, 1943.',
   'printed_short_title_clause'),
  (8846,  'year', '1896', 2348018, 'Act No, | OF 1896,', 'printed_act_heading'),
  (8846,  'number', 'I', 2348018, 'Act No, | OF 1896,', 'printed_act_heading'),
  (9067,  'year', '1870', 2367060, 'Acr No. XXVII or 1870.', 'printed_act_heading'),
  (9067,  'number', 'XXVII', 2367060, 'Acr No. XXVII or 1870.', 'printed_act_heading'),
  (11382, 'year', '2014', 2851045,
   '(1) This Act may be called the G ilg it- Balt ist an Environmental Protection Act, 2014.',
   'printed_short_title_clause'),
  (11379, 'kind', 'rules', 2850823,
   '(1) These rules may be called the Gilgit –Baltistan Legislative Assembly Finance Committee Rules-2010.',
   'printed_short_title_clause')
)
INSERT INTO instrument_metadata_assertion
       (source_observation_id, expression_ordinal, field, value, assertion, basis, source_block_id, source_page,
        quote, method, evidence, recorded_by)
SELECT i.source_observation_id, i.expression_ordinal, d.field, d.value, 'asserted', d.basis, d.block, b.page_no,
       d.quote, 'nizam.catalogue_correction_page_read/1',
       jsonb_build_object('reviewer_type', 'claude', 'page_read', true,
                          'corrected_from', CASE d.field WHEN 'year' THEN i.year::text
                                                         WHEN 'kind' THEN i.kind::text
                                                         ELSE i.number END,
                          'reviewed_file', 'tools/evidence/catalogue-corrections-2026-11-17.sql'),
       'claude'
  FROM d
  JOIN v_release_instrument i ON i.document_id = d.doc
  JOIN text_block b ON b.id = d.block
 WHERE NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                    WHERE c.instrument_id = i.id AND c.field = d.field AND c.value = d.value);

-- 6688's display title, without the fused side note
INSERT INTO instrument_metadata_assertion
       (source_observation_id, expression_ordinal, field, value, assertion, basis, method, evidence, recorded_by)
SELECT i.source_observation_id, i.expression_ordinal, 'display_title',
       'The Civil Pioneer Force (Amendment) Ordinance, 1943', 'asserted', 'reviewed_corrected_name',
       'nizam.display_title_from_printed_text/1',
       jsonb_build_object('reviewer_type', 'claude', 'page_read', true,
                          'review_evidence', 'This Ordinance may be called the Civil Pioneer ene and mmencs- Force (Amendment) Ordinance, 1943.',
                          'note', 'side note ''Short title and commencement'' fused into the name by OCR',
                          'corrected_from', i.display_title,
                          'reviewed_file', 'tools/evidence/catalogue-corrections-2026-11-17.sql'),
       'claude'
  FROM v_release_instrument i
 WHERE i.document_id = 6688
   AND NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                    WHERE c.instrument_id = i.id AND c.field = 'display_title'
                      AND c.value = 'The Civil Pioneer Force (Amendment) Ordinance, 1943');

COMMIT;
