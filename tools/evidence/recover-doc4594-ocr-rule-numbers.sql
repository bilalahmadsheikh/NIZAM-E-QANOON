-- Seven rules of the Sindh Prisons and Corrections Services Rules, 2019 that
-- an OCR'd rule number put beyond citation.
--
-- Document 4594 (source observation 4746) is the Sindh Government Gazette of
-- 14 May 2020, an image-only scan; it is the only lane-E4 document in this
-- batch and its text layer is poor throughout. Where the OCR misread a rule
-- NUMBER, the rule collided with a different rule bearing the misread number
-- and was demoted to a non-citable clause. Twenty such collisions are pending
-- S7 units on this document; in seven of them the number in the text layer is
-- not the number on the page, and those seven are corrected here.
--
-- Each printed number below was established by reading the rendered page, and
-- each is corroborated by its own neighbours: the page prints an unbroken run
-- of rule numbers and the rule in question sits in that run.
--
--   p13  blk 950081  OCR "43."  printed 39.  "Provision of funds, expenditure
--        and accounts" -- page 13 prints rules 37 to 42 in sequence: "37. Power
--        to certain temporary establishment.", "38. Supply of articles to
--        prisons and sale of manufactured articles and enter into contract.",
--        "39. Provision of funds, expenditure and accounts. (1) Subject to the
--        budget provision and allotment of funds to meet the expenditure of the
--        service, the entire control over all expenditure on the maintenance of
--        prisons ... shall vest in the Inspector General.", "40. Monthly audit
--        of expenditure by Inspector General".
--
--   p17  blk 950164  OCR "65."  printed 68.  page 17 prints rules 67 to 71 in
--        sequence: "67. Weekly inspection.", "68. Checking and counting
--        prisoners twice daily. The Officer Incharge shall cause all prisoners
--        to be checked and counted at least twice a daily, at unlocking in the
--        morning, at lock up in the evening.", "69. All business to be
--        transacted on prison premises.", "70. Officer in charge to enquire
--        into all prison offences and breach of discipline.", "71. Officer in
--        charge to visit prison when an unusual occurrence is reported."
--
--   p17  blk 950165  OCR "65."  printed 69.  the same run, the next rule:
--        "69. All business to be transacted on prison premises. The Officer
--        Incharge shall ordinarily transact all business connected with the
--        prison within its precincts and he shall not, except in cases of
--        necessity or emergency, require the attendance of the Deputy
--        Superintendent, Assistant Superintendent at any place outside the
--        prison premises." Two rules of page 17, 68 and 69, were both offered
--        against page 16's real rule 65 ("Visits to garden") and both accepted
--        as clauses of it -- one misread number cost two rules.
--
--   p18  blk 950187  OCR "27."  printed 77.  page 18 prints rules 72 to 77 in
--        sequence, ending "77. Reports and Statistics. (1) The Officer
--        In-charge shall regularly and punctually submit to the Inspector
--        General all such special or periodical - (a) returns of statistical
--        information; (b) statement of accounts in respect of receipts,
--        expenditure and property; (c) bills, vouchers and other original
--        documents; and (d) reports and other information; as he may at any
--        time prescribe by general or special order or as may be required by
--        these rules or regulations." The unit that kept the number 27 is a
--        different real rule, page 8's "27. Meetings. (1) There shall be held
--        ordinary meetings and special meetings."
--
--   p33  blk 950489  OCR "203."  printed 202.  page 33 prints rules 199 to 207
--        in sequence, among them "202. Strict attention to sanitary matters.
--        Strict attention shall be paid to all sanitary arrangements,
--        especially to conservancy, care being taken that the latrine pans are
--        cleaned immediately after use. The number of sweepers shall be
--        increased so as to cater for the proper needs." Rule 203 on the same
--        page is a different rule -- "203. Investigation as to the origin of
--        the first case" -- printed immediately after it and before "204.
--        Measures against small pox.", which is what makes 202 certain.
--
--   p45  blk 950716  OCR "273."  printed 279.  page 45 prints rules 278 to 285
--        in sequence: "278. Officers not to resign without Notice.", "279.
--        Prohibition against sleeping on duty or other irregularities. No
--        Junior Prison officer shall at any time - (a) be in a state of
--        intoxication; (b) sleep while on duty; (c) enter any enclosure
--        reserved for women prisoners unless he is authorized to do so under
--        the rules and is accompanied by a women junior prison officer; (d)
--        commit, or permit or abet the commission of any irregularity ...".
--        Rule 273 is on page 44 and is a different rule, "Officers not to leave
--        place of duty idle about or quarrel".
--
--   p46  blk 950760  OCR "283."  printed 289.  page 46 prints rules 286 to 289
--        in sequence: "286. Record and Character Roll.", "287. Pay and
--        Allowances.", "288. Pay of Officer reduced to lower grade.", "289.
--        Occurrence of Permanent Vacancy. Except as otherwise provided under
--        any other rules, appointments of all types on any permanent vacancy of
--        Junior Prison Officers or Junior Employees shall be made on the
--        recommendations of a committee of three Senior Prison Officers as
--        notified by the Administrative Department as provided in the
--        Schedule-I."
--
-- WHAT THIS DOES NOT FIX, and why it is not a curation patch.
--
-- The other thirteen pending units on this document carry the RIGHT number in
-- the text layer and still lose it. Their numbers all end in 3 -- 133, 143,
-- 153, 203, 223, 243, 253, 253, 273 and page 11's 33 -- and `_repair_label`
-- strips the leading digits because the remainder, "3", is promised by this
-- document's contents hypothesis. That hypothesis has three entries, parsed out
-- of pages 1 to 5, which are the Gazette's own CHAPTER index rendered by the
-- same failing OCR ("-CHAPTERNO. [CAPTION PAGE NO,", "CHAPTERS " PRELIMINARY
-- The", "~SHAPTER-II eLASSIFIGATION ANO ESTABLISHMENT OFS"). No substitution of
-- a number can repair those thirteen: the number is already correct, and a
-- patch whose before_text equals its after_text asserts nothing. They need the
-- contents hypothesis withdrawn -- the same family of defect as the post-walk
-- contents refutation -- which is a parser change, not a source correction, and
-- is deliberately left out of this file. Three more (rules 140, 182 and 195)
-- carry correct labels too and collide with a wrongly numbered unit that was
-- kept; those are S7 adjudications, already recorded.
--
-- Measured against the active segmenter with these seven patches supplied and
-- nothing else changed: citable labels 301 -> 308, gaining exactly 39, 68, 69,
-- 77, 202, 279 and 289 and losing none; pending S7 units on this document
-- 20 -> 13. Every locator resolves to exactly one block on its page and every
-- before_text occurs exactly once in that block, so the patch set fails closed
-- if a re-extraction changes any of these pages.
--
-- review_state is 'source_verified', which migration 0025 defines as directly
-- checked against the official PDF page; it does not imply human publication
-- approval. The rendered page each reading came from is named in the evidence,
-- with the sha256 of that render.

BEGIN;

INSERT INTO segmentation_curation_patch
    (source_observation_id, page_no, match_text, before_text, after_text,
     evidence, review_state, created_by)
VALUES
 (4746, 13, 'Provision of funds, expenditure and accounts',
  '43. Provision of funds', '39. Provision of funds',
  jsonb_build_object(
    'defect', 'rule number misread by OCR in the source text layer',
    'fixes', 'S7 repeated-label collision caused by the misread number',
    'document_id', 4594, 'extracted_number', '43', 'printed_number', '39',
    'source_block_id', 950081,
    'observed', 'Page 13 prints rules 37 to 42 in sequence and this rule as '
                '"39. Provision of funds, expenditure and accounts. (1) Subject '
                'to the budget provision and allotment of funds to meet the '
                'expenditure of the service, the entire control over all '
                'expenditure on the maintenance of prisons and on all matters '
                'in any way relating to, or connected with, the administration '
                'of prisons, shall vest in the Inspector General."',
    'render_artifact', '.artifacts/catalogue/pages/doc4594-p13-013.png',
    'render_sha256', 'f0dc826b101d73cbf77df974f1fa6cc346d6bfa93ff2c72aeea52e800a1b9dcd',
    'reviewer_type', 'assistant', 'assistant_page_review', true,
    'human_page_review', false),
  'source_verified', 'claude.ocr-digit-review/2'),

 (4746, 17, 'Checking and counting prisoners twice dally',
  '65. Checking and counting', '68. Checking and counting',
  jsonb_build_object(
    'defect', 'rule number misread by OCR in the source text layer',
    'fixes', 'S7 repeated-label collision caused by the misread number',
    'document_id', 4594, 'extracted_number', '65', 'printed_number', '68',
    'source_block_id', 950164,
    'observed', 'Page 17 prints rules 67 to 71 in sequence: "67. Weekly '
                'inspection.", "68. Checking and counting prisoners twice '
                'daily. The Officer Incharge shall cause all prisoners to be '
                'checked and counted at least twice a daily, at unlocking in '
                'the morning, at lock up in the evening.", "69. All business to '
                'be transacted on prison premises.", "70. Officer in charge to '
                'enquire into all prison offences and breach of discipline.", '
                '"71. Officer in charge to visit prison when an unusual '
                'occurrence is reported." The real rule 65 is on page 16, '
                '"Visits to garden".',
    'render_artifact', '.artifacts/catalogue/pages/doc4594-p17-017.png',
    'render_sha256', '01809e3562ee7645942bfcbce194852ba0bda04171fbbdd71e15569446be48be',
    'reviewer_type', 'assistant', 'assistant_page_review', true,
    'human_page_review', false),
  'source_verified', 'claude.ocr-digit-review/2'),

 (4746, 17, 'All business to be trangacted on prison premises',
  '65. All business', '69. All business',
  jsonb_build_object(
    'defect', 'rule number misread by OCR in the source text layer',
    'fixes', 'S7 repeated-label collision caused by the misread number',
    'document_id', 4594, 'extracted_number', '65', 'printed_number', '69',
    'source_block_id', 950165,
    'observed', 'Page 17 prints, immediately after rule 68 and before "70. '
                'Officer in charge to enquire into all prison offences and '
                'breach of discipline.": "69. All business to be transacted on '
                'prison premises. The Officer Incharge shall ordinarily '
                'transact all business connected with the prison within its '
                'precincts and he shall not, except in cases of necessity or '
                'emergency, require the attendance of the Deputy '
                'Superintendent, Assistant Superintendent at any place outside '
                'the prison premises."',
    'note', 'the same misread number 65 cost page 17 two rules, 68 and 69, '
            'both of which were accepted as clauses of page 16 rule 65',
    'render_artifact', '.artifacts/catalogue/pages/doc4594-p17-017.png',
    'render_sha256', '01809e3562ee7645942bfcbce194852ba0bda04171fbbdd71e15569446be48be',
    'reviewer_type', 'assistant', 'assistant_page_review', true,
    'human_page_review', false),
  'source_verified', 'claude.ocr-digit-review/2'),

 (4746, 18, 'Reports and Statistics. [1) The Officer In-charve',
  '27. Reports and Statistics', '77. Reports and Statistics',
  jsonb_build_object(
    'defect', 'rule number misread by OCR in the source text layer',
    'fixes', 'S7 repeated-label collision caused by the misread number',
    'document_id', 4594, 'extracted_number', '27', 'printed_number', '77',
    'source_block_id', 950187,
    'observed', 'Page 18 prints rules 72 to 77 in sequence: "72. Record of '
                'Award of Punishment.", "73. Appointment and punishment of '
                'staff under his control.", "74. Report of all importance '
                'occurrences.", "75. Officer in charge to accompany Inspector '
                'General, Deputy Inspector General or Official visitors.", '
                '"76. Control over receipt and expenditure.", "77. Reports and '
                'Statistics. (1) The Officer In-charge shall regularly and '
                'punctually submit to the Inspector General all such special or '
                'periodical - (a) returns of statistical information; (b) '
                'statement of accounts in respect of receipts, expenditure and '
                'property; (c) bills, vouchers and other original documents; '
                'and (d) reports and other information; as he may at any time '
                'prescribe by general or special order or as may be required by '
                'these rules or regulations." The unit that kept the number 27 '
                'is page 8 rule 27, "Meetings", a different real rule.',
    'render_artifact', '.artifacts/catalogue/pages/doc4594-p18-018.png',
    'render_sha256', '1d2b409bf3a788f5b1cf6c0640818cc5a91319a5979e88f9c1dedc9b29ef8e5e',
    'reviewer_type', 'assistant', 'assistant_page_review', true,
    'human_page_review', false),
  'source_verified', 'claude.ocr-digit-review/2'),

 (4746, 33, 'Strict attention to sanitary matters',
  '203. Strict attention', '202. Strict attention',
  jsonb_build_object(
    'defect', 'rule number misread by OCR in the source text layer',
    'fixes', 'S7 repeated-label collision caused by the misread number',
    'document_id', 4594, 'extracted_number', '203', 'printed_number', '202',
    'source_block_id', 950489,
    'observed', 'Page 33 prints rules 199 to 207 in sequence, among them "202. '
                'Strict attention to sanitary matters. Strict attention shall '
                'be paid to all sanitary arrangements, especially to '
                'conservancy, care being taken that the latrine pans are '
                'cleaned immediately after use. The number of sweepers shall be '
                'increased so as to cater for the proper needs." The next rule '
                'on the same page is a different one, "203. Investigation as to '
                'the origin of the first case", printed before "204. Measures '
                'against small pox."',
    'render_artifact', '.artifacts/catalogue/pages/doc4594-p33-033.png',
    'render_sha256', 'c8c0d795b4c80be4f237ad1de6746bd81b07af1e9dcd92ac8098074235eb9685',
    'reviewer_type', 'assistant', 'assistant_page_review', true,
    'human_page_review', false),
  'source_verified', 'claude.ocr-digit-review/2'),

 (4746, 45, 'Prohibition against sleeping on duty',
  '273. Prohibition against sleeping', '279. Prohibition against sleeping',
  jsonb_build_object(
    'defect', 'rule number misread by OCR in the source text layer',
    'fixes', 'S7 repeated-label collision caused by the misread number',
    'document_id', 4594, 'extracted_number', '273', 'printed_number', '279',
    'source_block_id', 950716,
    'observed', 'Page 45 prints rules 278 to 285 in sequence: "278. Officers '
                'not to resign without Notice.", "279. Prohibition against '
                'sleeping on duty or other irregularities. No Junior Prison '
                'officer shall at any time - (a) be in a state of intoxication; '
                '(b) sleep while on duty; (c) enter any enclosure reserved for '
                'women prisoners unless he is authorized to do so under the '
                'rules and is accompanied by a women junior prison officer; (d) '
                'commit, or permit or abet the commission of any irregularity '
                'in the prison." Rule 273 is on page 44 and is a different '
                'rule, "Officers not to leave place of duty idle about or '
                'quarrel".',
    'render_artifact', '.artifacts/catalogue/pages/doc4594-p45-045.png',
    'render_sha256', '7b8d5947a24e3a8ea2e4fc59fbe872d25ffb8db40dc5ecc03d025a3eebd8af0d',
    'reviewer_type', 'assistant', 'assistant_page_review', true,
    'human_page_review', false),
  'source_verified', 'claude.ocr-digit-review/2'),

 (4746, 46, 'Occurrence of Permanent Vacancy',
  '283. Occurrence of Permanent Vacancy', '289. Occurrence of Permanent Vacancy',
  jsonb_build_object(
    'defect', 'rule number misread by OCR in the source text layer',
    'fixes', 'S7 repeated-label collision caused by the misread number',
    'document_id', 4594, 'extracted_number', '283', 'printed_number', '289',
    'source_block_id', 950760,
    'observed', 'Page 46 prints rules 286 to 289 in sequence: "286. Record and '
                'Character Roll.", "287. Pay and Allowances.", "288. Pay of '
                'Officer reduced to lower grade.", "289. Occurrence of '
                'Permanent Vacancy. Except as otherwise provided under any '
                'other rules, appointments of all types on any permanent '
                'vacancy of Junior Prison Officers or Junior Employees shall be '
                'made on the recommendations of a committee of three Senior '
                'Prison Officers as notified by the Administrative Department '
                'as provided in the Schedule-I."',
    'render_artifact', '.artifacts/catalogue/pages/doc4594-p46-046.png',
    'render_sha256', '7272ef8e8f8bdeb4fd5583e749f1b2709cd9a96cd5513b78d1bfac5e7389d6b4',
    'reviewer_type', 'assistant', 'assistant_page_review', true,
    'human_page_review', false),
  'source_verified', 'claude.ocr-digit-review/2');

COMMIT;
