-- Lead, 20 Oct 2026. Document 4703/4704 (blob 05a966e6..., the Balochistan Motor Vehicles (Amendment) Act, Act No. XIV
-- of 2021, Provincial Assembly notification of 5 May 2021): an OCR table document, as assertion 12 records for the
-- Bill's copy (blob b85b2553..., document 4524/4642). verify_ocr/4 put 4704 in review on 'legal-token rate 0.230'; the
-- rate reflects the substituted Twelfth Schedule's penalty-rate vocabulary (63 + 11 table rows). Idempotent.
\set ON_ERROR_STOP on
INSERT INTO extraction_assertion (sha256, page_no, kind, evidence, detail, asserted_by)
SELECT '05a966e64e8f07abb91b6ea09595d9ee5cc85f60826abab8f208416b0d0e23b6', NULL, 'source_content_confirmed',
       'The owner reviewed all four page images against the Surya reading and accepted 4/4 (ocr-review-doc-4703.json, '
       'reviewed_source_image true on every page); the lead read p1 on its render and every block of the promoted '
       'revision 4704: one page of the Assembly notification, preamble and ss.1-2, then the substituted Twelfth Schedule''s '
       'penalty-rate tables (moving violation rows 1-63, parking violation rows 1.-11.) and notes. The 0.230 legal-token '
       'rate reflects table vocabulary; Surya mean confidence 0.9925 over 1,106 words.',
       '{"method": "owner-page-review+lead-render-read", "purpose": "ocr-table-document", "pages_reviewed": [1, 2, 3, 4], '
       '"owner_export": ".artifacts/ocr-review-exports/ocr-review-doc-4703.json", '
       '"owner_export_sha256": "d9de4d97122413ad1af04b41fd0597f0e60e2839415d89905aba8371cc7a4204", '
       '"precedent_assertion_id": 12}'::jsonb,
       'claude.lead-table-document-review/1'
 WHERE NOT EXISTS (SELECT 1 FROM extraction_assertion WHERE sha256 = '05a966e64e8f07abb91b6ea09595d9ee5cc85f60826abab8f208416b0d0e23b6'
                     AND kind = 'source_content_confirmed' AND is_active AND detail->>'purpose' = 'ocr-table-document');
SELECT id, kind, detail->>'purpose' FROM extraction_assertion WHERE sha256 = '05a966e64e8f07abb91b6ea09595d9ee5cc85f60826abab8f208416b0d0e23b6';
