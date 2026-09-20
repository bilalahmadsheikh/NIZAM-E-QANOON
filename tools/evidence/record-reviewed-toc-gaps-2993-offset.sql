-- Document 2993, SINDH FARMERS ORGANIZATIONS FINANCIAL REGULATIONS, 2004.
-- Twenty-one contents gaps, one shape: the printed contents on page 1 and the
-- printed body are numbered differently, and the offset grows because the body
-- prints an extra regulation the contents does not list (body 4, "The FO Fund
-- shall consist of:-") and then skips a number (the body runs ... 15, 17 ...).
-- Matched by HEADING against the rendered body pages, not by number.
BEGIN;

CREATE TEMP TABLE _m(toc_label text, body_label text, body_page int, sha text, quote text) ON COMMIT DROP;
INSERT INTO _m VALUES
 ('3','3',4,'ebc0d2383675d9a7ecaceb7fc57bcae8c803e007580cccacf6fdf9426d08b5c0','Page 4 prints "3. There shall be a fund to be known as the FO Fund vested in the concerned FO."'),
 ('4','5',4,'ebc0d2383675d9a7ecaceb7fc57bcae8c803e007580cccacf6fdf9426d08b5c0','Page 4 prints "5. Banks 5.1 The FO will open its own bank account in one of the Scheduled banks notified by the Government of Pakistan."'),
 ('5','6',5,'999c8943d8f1c971602cc830130c64335f1d988af5cff094aae06cc844049dc4','Page 5 prints "6. Budget and Business Plan 6.1 A business plan for the FO will be compiled by the Board of Management for five years."'),
 ('6','7',5,'999c8943d8f1c971602cc830130c64335f1d988af5cff094aae06cc844049dc4','Page 5 prints "7. Vouchers 7.1 All vouchers will be serially numbered and dated."'),
 ('7','8',5,'999c8943d8f1c971602cc830130c64335f1d988af5cff094aae06cc844049dc4','Page 5 prints "8. Receipts 1.1 A receipt must be given to the payer by the Treasurer authorized by the Board of Management for all money received on behalf of the FO."'),
 ('8','9',5,'999c8943d8f1c971602cc830130c64335f1d988af5cff094aae06cc844049dc4','Page 5 prints "9. Payments 9.1 All payments must be made by crossed cheque, except for petty cash replenishment."'),
 ('9','10',6,'7918a2e8874a3e7d88c58ddcd5004f384e5e406d196a6217b0d4ffcca072b568','Page 6 prints "10. Income Tax Deductions: Deduction from bills on account of income tax shall be made strictly in accordance with the relevant provisions of the Income Tax Ordinance 2001."'),
 ('10','11',7,'74d0d5949cc4935cfe9f874caa28ccb18c47cfb189013a479ed5283330de43f8','Page 7 prints "11. Accounting Convention Accounts will be prepared under the historical cost convention and in conformity with applicable International Accounting Standards."'),
 ('11','12',7,'74d0d5949cc4935cfe9f874caa28ccb18c47cfb189013a479ed5283330de43f8','Page 7 prints "12. Double - Entry Accounting System The double entry accounting system will be used for recording all transactions."'),
 ('12','13',7,'74d0d5949cc4935cfe9f874caa28ccb18c47cfb189013a479ed5283330de43f8','Page 7 prints "13. Accounting Year The accounting year of the FO will be from 1 July to 30 June of the following year."'),
 ('13','14',7,'74d0d5949cc4935cfe9f874caa28ccb18c47cfb189013a479ed5283330de43f8','Page 7 prints "14. Taxation No provisions for taxation will be made in the financial statements of the project accounts as the FO operates as an organization which is not-for-profit."'),
 ('14','15',7,'74d0d5949cc4935cfe9f874caa28ccb18c47cfb189013a479ed5283330de43f8','Page 7 prints "15. Fixed Assets and Depreciation 16.1 Fixed assets will be shown at historical cost." The contents calls it "Fixed Assets and description"; the body sub-items are misprinted 16.1 to 16.4 under regulation 15.'),
 ('15','17',8,'ebd33851161f90fea6e910a234a5bb01ee5dc0edcb9163629f6090cca9ab675f','Page 8 prints "17. Development Expenditure / Capital Work in progress Development expenditure / Capital work in progress includes all costs including material, labour and overheads." The body has no regulation 16: it runs 15 then 17, which is why the offset widens from one to two.'),
 ('16','18',8,'ebd33851161f90fea6e910a234a5bb01ee5dc0edcb9163629f6090cca9ab675f','Page 8 prints "18. Books of account The FO will maintain the following books of account 1- Cash book 2- Petty cash book."'),
 ('17','19',8,'ebd33851161f90fea6e910a234a5bb01ee5dc0edcb9163629f6090cca9ab675f','Page 8 prints "19. Annual Accounts Every FO will produce annual accounts not later than three months of close of the financial year."'),
 ('18','20',9,'a9fb179b871f1884817f27d507b34877cda4a04806f4ac64fc4a9e9036e5778c','Page 9 prints "20. Audit of Account Annual accounts will be audited by a Chartered Accountants Within six months of the close of financial year."'),
 ('19','21',9,'a9fb179b871f1884817f27d507b34877cda4a04806f4ac64fc4a9e9036e5778c','Page 9 prints "21. Members Share Subscription Fund A membership fee of Rs. 1000/- or an amount specified by the FO General Body will be collected by FO from its members."'),
 ('20','22',9,'a9fb179b871f1884817f27d507b34877cda4a04806f4ac64fc4a9e9036e5778c','Page 9 prints "22. Revenue 22.1 The Board of Management is responsible for the preparation of schedule of rates of abiana / other charges for each crop."');

INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'found_elsewhere', g.source_page,
       jsonb_build_object(
         'found_provision_id', p.id::text,
         'body_label', p.label,
         'printed_heading', g.printed_heading,
         'method', 'assistant read the rendered body pages and matched the promised heading to the regulation that prints it, by heading and not by number',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', '.artifacts/catalogue/pages/doc2993-p' || m.body_page || '-' || lpad(m.body_page::text, 2, '0') || '.png',
         'render_sha256', m.sha,
         'observed', m.quote),
       'The printed contents on page 1 of the SINDH FARMERS ORGANIZATIONS FINANCIAL '
       'REGULATIONS, 2004 lists regulations 1 to 23. The body numbers them differently: '
       'it prints an extra regulation the contents omits (body 4, "The FO Fund shall '
       'consist of:-") and then skips a number (15 is followed by 17), so the contents '
       'runs one behind the body from label 4 and two behind from label 15. '
       || m.quote || ' The regulation is present and citable under the body''s own '
       'number; nothing is absent from the source. Contents entries 1 and 2 linked '
       'correctly and every later entry was left unlinked, so no provision was '
       'mis-headed by the offset.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
  JOIN _m m ON m.toc_label = g.printed_label
  JOIN provision p ON p.instrument_id = g.instrument_id AND p.is_active
                  AND p.kind = 'section' AND p.label = m.body_label
 WHERE g.document_id = 2993 AND g.toc_entry_id IS NOT NULL;

INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'heading_only_no_number',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', CASE g.printed_label
             WHEN '21' THEN '.artifacts/catalogue/pages/doc2993-p10-10.png'
             WHEN '22' THEN '.artifacts/catalogue/pages/doc2993-p11-11.png'
             ELSE '.artifacts/catalogue/pages/doc2993-p12-12.png' END,
         'render_sha256', CASE g.printed_label
             WHEN '21' THEN '0b1d07295713ce868891540bed5fa963b557d1b3b519ae0287f2b52b78540c2d'
             WHEN '22' THEN 'b2bc293482625eea93cc008eb6053f0320fdda89e25518b2c1003a5fa5af6f5a'
             ELSE '39b8850c08b829936d0b25fec4929fc04f90af571f523e8d5326218376536c69' END,
         'observed', CASE g.printed_label
             WHEN '21' THEN 'Page 10 prints, in place of a numbered regulation 21, the centred heading "SECTION V POWERS FOR RE-ALLOCATION OF FUNDS WITHIN THE APPROVED BUDGET ALLOCATION" followed by unnumbered text: "The General Body will have the full power, for re-allocation of funds between various head of accounts, sub-heads, minor heads and sub-major heads within the approved business plan and budget."'
             WHEN '22' THEN 'Page 11 prints, in place of a numbered regulation 22, the centred heading "SECTION VI AUTHORIZATION OF CAPITAL EXPENDITURE" followed by an unnumbered table of NATURE OF POWER / COMPETENT AUTHORITY / MONETARY LIMITS.'
             ELSE 'Page 12 prints, in place of a numbered regulation 23, the centred heading "SECTION VII POWERS FOR REVENUE EXPENDITURE" followed by "Definition: Revenue expenditure comprises those charges which are incidental to the management of an office as an office" and an unnumbered table of powers.' END,
         'severity', 'law present in the corpus but not citable by the promised number'),
       'The contents promises this as a numbered regulation. The body prints it as an '
       'unnumbered centred SECTION heading with its text or table beneath, so there is '
       'no numbered node to link and the text is not absent from the source. Only a '
       'corrected parse, which opens a provision on the SECTION heading, resolves it.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 2993 AND g.printed_label IN ('21', '22', '23')
   AND g.toc_entry_id IS NOT NULL;

SELECT resolution, count(*) FROM toc_gap_adjudication
 WHERE document_id = 2993 AND decided_by = 'claude.toc-source-review/1' GROUP BY 1;
COMMIT;
