-- Page-read metadata for the Constitution 25th, 26th and 27th Amendment Acts (docs 11385, 11384, 11383; D-076).
--
-- WHY. These three laws are Gazette scans whose text layer is poor OCR. Their provisions are served from a page reading
-- (curation patches), but the title-region recorders (record_instrument_numbers, record_long_titles,
-- record_enacted_dates) and the short-title pass read the raw text_block layer. On 18 Nov they recorded the 27th's long
-- title as 'An Act further to amend lhe Ctm.stitution ... WIIEREAS.', and nothing for the 26th's and 27th's names
-- ('This Act shall be called ...'), the 25th's and 26th's assent dates, or any of the three numbers.
-- Each value below was read from the page image (renders doc{N}-p1.png) and agrees with the page reading recorded for
-- that block. The quote is the printed words; the block is the text_block the reading replaced. Append-only.
-- Commencement then follows from 'This Act shall come into force at once' (record_commencement.py, 0066 convention).
BEGIN;
WITH d(doc, field, value, basis, method, block, quote) AS (VALUES
  (11384, 'display_title', 'The Constitution (Twenty-sixth Amendment) Act, 2024', 'reviewed_printed_name',
   'nizam.display_title_from_printed_text/1', 2851809,
   'This Act shall be called the Constitution (Twenty-sixth Amendment) Act, 2024.'),
  (11383, 'display_title', 'The Constitution (Twenty-seventh Amendment) Act, 2025', 'reviewed_printed_name',
   'nizam.display_title_from_printed_text/1', 2851349,
   'This Act shall be called the Constitution (Twenty-seventh Amendment) Act, 2025.'),
  (11385, 'number', 'XXXVII', 'printed_act_heading', 'nizam.page_read_metadata/1', 2852266, 'ACT NO. XXXVII OF 2018'),
  (11384, 'number', 'XXVI', 'printed_act_heading', 'nizam.page_read_metadata/1', 2851797, 'ACT NO. XXVI OF 2024'),
  (11383, 'number', 'XXXII', 'printed_act_heading', 'nizam.page_read_metadata/1', 2851345, 'ACT NO. XXXII OF 2025'),
  (11385, 'enacted_on', '2018-05-31', 'printed_assent_statement', 'nizam.page_read_metadata/1', 2852264,
   'The following Act of Majlis-e-Shoora (Parliament) received the assent of the President on 31st May, 2018'),
  (11384, 'enacted_on', '2024-10-21', 'printed_assent_statement', 'nizam.page_read_metadata/1', 2851794,
   'The following Act of Majlis-e-Shoora (Parliament) received the assent of the President on the 21st October, 2024'),
  (11385, 'long_title', 'An Act further to amend the Constitution of the Islamic Republic of Pakistan',
   'printed_long_title', 'nizam.page_read_metadata/1', 2852267,
   'An Act further to amend the Constitution of the Islamic Republic of Pakistan'),
  (11383, 'long_title', 'An Act further to amend the Constitution of the Islamic Republic of Pakistan',
   'printed_long_title', 'nizam.page_read_metadata/1', 2851346,
   'An Act further to amend the Constitution of the Islamic Republic of Pakistan')
)
INSERT INTO instrument_metadata_assertion
       (source_observation_id, expression_ordinal, field, value, assertion, basis, source_block_id, source_page,
        quote, method, evidence, recorded_by)
SELECT i.source_observation_id, i.expression_ordinal, d.field, d.value, 'asserted', d.basis, d.block, b.page_no,
       d.quote, d.method,
       jsonb_build_object('reviewer_type', 'claude', 'page_read', true,
                          'read_from', 'page image and the recorded page reading of the block (D-076)',
                          'corrected_from', (SELECT c.value FROM v_instrument_metadata_current c
                                              WHERE c.instrument_id = i.id AND c.field = d.field),
                          'reviewed_file', 'tools/evidence/amendment-acts-metadata-2026-11-18.sql'),
       'claude'
  FROM d
  JOIN v_release_instrument i ON i.document_id = d.doc
  JOIN text_block b ON b.id = d.block AND b.document_id = d.doc
 WHERE NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                    WHERE c.instrument_id = i.id AND c.field = d.field AND c.value = d.value);
COMMIT;
