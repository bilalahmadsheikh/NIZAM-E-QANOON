-- Three released historical Gazette scans whose catalogue title names a DIFFERENT law (lead, 16 Nov 2026). Their
-- display title is the law each page prints. Their stored year (from the catalogue) is also wrong and is NOT changed
-- here: instrument.year has no evidence field yet; recorded as an open defect in docs/SCHEMA.md. Append-only.
--   9067 catalogue 'NA-The Pakistan Penal Code Act, 1860'; page 1 prints 'Acr No. XXVII or 1870. An Act to amend
--        the Indian Penal Code' (Gazette of India, 26 November 1870; assented 25 November 1870)
--   8846 catalogue 'NA-The Indian Emigration Act, 1883'; page 1 prints 'Act No, | OF 1896 ... to amend the Indian
--        E[migration] Act, 1883' (Gazette of India, 11 January 1896)
--   6688 catalogue 'NA- X of 1942'; prints 'This Ordinance may be called the Civil Pioneer [Force] (Amendment)
--        Ordinance, 1943' (ORDINANCE No. VII of 1943)

BEGIN;

WITH d(doc, name, quote) AS (VALUES
  (9067, 'Act No. XXVII of 1870 — An Act to amend the Indian Penal Code',
         'Acr No. XXVII or 1870. An Act to amend the Indian Penal Code.'),
  (8846, 'Act No. I of 1896 — An Act to amend the Indian Emigration Act, 1883',
         'Act No, | OF 1896, ty 10 amend the lndian E e ° Act, 1883'),
  (6688, 'The Civil Pioneer Force (Amendment) Ordinance, 1943',
         'This Ordinance may be called the Civil Pioneer ene and mmencs- Force (Amendment) Ordinance, 1943.')
)
INSERT INTO instrument_metadata_assertion
       (source_observation_id, expression_ordinal, field, value, assertion, basis, method, evidence, recorded_by)
SELECT i.source_observation_id, i.expression_ordinal, 'display_title', d.name, 'asserted', 'reviewed_corrected_name',
       'nizam.display_title_from_printed_text/1',
       jsonb_build_object('reviewer_type', 'claude', 'page_read', true, 'review_evidence', d.quote,
                          'corrected_from', i.short_title, 'identity_defect',
                          'the catalogue title and year name a different law than the file prints',
                          'reviewed_file', 'tools/evidence/display-titles-misidentified-2026-11-16.sql'),
       'claude'
  FROM d JOIN v_release_instrument i ON i.document_id = d.doc
 WHERE NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                    WHERE c.instrument_id = i.id AND c.field = 'display_title');

COMMIT;
