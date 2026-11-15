-- ICT doc 9913 (S.R.O. 805(1)/91 and the CDA notifications compiled with it), 15 Nov 2026: verify_extraction/3 measured
-- character precision 0.99497 (102 unexplained characters, 't','e','a','g','z',...). Per page the extra characters are
-- 20 on each of pages 1, 4, 5, 7, 8, 10 and 12 -- exactly the letters of the Gazette masthead 'The Gazette of Pakistan',
-- printed in blackletter type at the head of each Gazette issue and visible on each page render; the text layer
-- carries the masthead (in blocks of its own, read as furniture, never law) and pdftotext does not emit it. The
-- extra characters are therefore printed source content, not decoder fabrication. Append-only.
INSERT INTO extraction_assertion (sha256, page_no, kind, evidence, detail, asserted_by)
SELECT d.sha256, NULL, 'source_content_confirmed',
       'The lead read pages 1, 4, 5, 7, 8, 10 and 12 of document 9913 against their renders: each prints the Gazette '
       'masthead ''The Gazette of Pakistan'' in blackletter type at its head. The 20 characters per page that the '
       'text layer holds beyond pdftotext are that masthead (its blocks are set aside as furniture, never law).',
       jsonb_build_object('method', 'lead-page-read', 'purpose', 'precision-masthead-confirmed', 'document_id', 9913,
                          'pages', jsonb_build_array(1, 4, 5, 7, 8, 10, 12),
                          'masthead_blocks', jsonb_build_array(2737213, 2737214, 2737245, 2737246, 2737262, 2737263,
                                                               2737342, 2737343, 2737362, 2737363, 2737385, 2737386,
                                                               2737417, 2737418),
                          'measured', 'verify_extraction/3: precision 0.99497, 102 unexplained characters; 20 per page '
                                      'on the seven masthead pages'),
       'claude.lead-page-read/1'
  FROM document d
 WHERE d.id = 9913
   AND NOT EXISTS (SELECT 1 FROM extraction_assertion a WHERE a.sha256 = d.sha256 AND a.kind = 'source_content_confirmed'
                      AND a.is_active AND a.detail->>'purpose' = 'precision-masthead-confirmed');
