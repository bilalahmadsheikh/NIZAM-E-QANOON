-- Contents gaps, batch T1, 23 September 2026.
--
-- Twenty canonical expressions, each blocked by EXACTLY ONE pending contents
-- gap and no S7 or boundary unit (re-verified live before reading: quality
-- passed, segmented, 1 pending TOC row, 0 S7, 0 boundary). A closing decision
-- here therefore releases an expression with no tree write and no replay --
-- which is also why nothing downstream would catch a wrong one.
--
-- WHAT WAS READ. Every page of all twenty source PDFs, 166 pages, rendered with
-- the command tools/review_toc_gaps.py uses (pdftoppm -r 130 -png) into
-- .artifacts/toc-gap-review/ under that tool's naming convention; the shared
-- manifest.json there was NOT rewritten. Each PDF's sha256 was checked against
-- document.sha256 before rendering. Every decision names the pages it was read
-- from and their SHA-256. Decisions were made from the rendered pages; the text
-- layer was queried afterwards only to say where the page's words sit in the
-- tree, and those block ids are quoted in the evidence.
--
-- RESULT
--   found_elsewhere   1  doc 209 -- releases one expression.
--   parser_defect    16  classified; every one of these gaps stays pending.
--   absent_in_source  0
--   HELD              3  docs 294, 806, 876 -- the found_elsewhere reading is
--                        right, but applying it releases a tree the page
--                        contradicts. Written out at the foot, COMMENTED OUT.
--
-- WHY SO FEW CLOSE -- two findings.
--
-- 1. A found_elsewhere must not point at a provision that already carries its
--    own contents row: that is the owner's retraction of 169, 306 and 732
--    (tools/evidence/retract-toc-offset-misreading.sql). In 847, 1014, 1065 and
--    1225 the printed contents runs one off the body, the parser linked every
--    later contents row BY NUMBER, and so the later sections carry the NEXT (or
--    previous) section's name: 847 heads s.3, which the page names "Termination
--    of services.", "Appeals."; 1014 misnames five of its seven sections; 1065
--    heads s.1 "Preamble."; 1225 gives ss.5-8 each the previous name. The
--    unmatched row is only the visible end of that, and its target is already
--    linked by a wrong row. Closing it would publish the misnamed sections --
--    the A11 defect (right text, wrong name), which A11 cannot see in a
--    marginal-note statute. Classed contents_offset_linked_by_number.
--
-- 2. A closure is only as good as the tree it releases. 294 carries a phantom
--    "section 2014" (the year of "Rules 2014.") that holds rule 1(2); 806 names
--    ss.20-22 after one another; 876 gives s.11 "Chancellor." the Schedule's
--    "Functions of the Finance and Planning Committee.". Their readings are
--    correct and are kept, commented, for the owner.
--
-- NO absent_in_source. Two gaps are sections the source does not print -- 510
-- s.4 "Pass Book." and 1247 s.15 "Repeal." -- but absence from the LAW is not
-- established, and migration 0054 is explicit that absent_in_source asserts the
-- legislature never enacted the section. 510's predecessor Ordinance (doc 791)
-- prints a section 4 on pass-books; 1247 is the last contents row, so check 4
-- of tools/review_absent_sections.py cannot hold, and both headings are under
-- that tool's 12-character floor. Per the batch instruction, both stay open,
-- under a class that says plainly the section is NOT printed.
--
-- DISAGREEMENT RECORDED. Doc 1337 carries an orphaned row
-- eca7bad3-0caa-446e-b0b8-e61b01dada8d (codex.source_page_review/1,
-- absent_in_source, retired entry 458870). Page 2 prints the rule's heading and
-- text; only its numeral is missing. That is heading_only_no_number, as in doc
-- 2993, not an absence. The orphan is untouched (append-only); the reattacher
-- already refuses it (check 4).
--
-- ANCHOR. Each row is selected from v_toc_gap_pending by (document_id,
-- printed_label, source_block_id, source_page) -- migration 0052's identity for a
-- printed entry, less the heading -- so it binds the live entry or nothing. A
-- guard before COMMIT refuses the batch unless exactly 1 found_elsewhere and 16
-- parser_defect rows were written. found_elsewhere evidence carries the target's
-- kind, label, first_block and path so it can be re-resolved after a replay.

BEGIN;

-- ── found_elsewhere: doc 209, contents prints "21." twice ─────────────────────
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'found_elsewhere', g.source_page,
       jsonb_build_object(
         'found_provision_id', p.id::text,
         'body_label', p.label,
         'found_kind', p.kind::text,
         'found_label', p.label,
         'found_first_block', p.first_block,
         'found_path', p.path::text,
         'printed_heading', g.printed_heading,
         'method', 'assistant read every page of the document; the promised '
                   'heading is printed as the marginal note of body section 22, '
                   'and the contents gives that row a second "21."',
         'reviewer_type', 'assistant',
         'assistant_page_review', true,
         'human_page_review', false,
         'render_artifact', jsonb_build_array(
             '.artifacts/toc-gap-review/doc209-e976876-label21-p1.png',
             '.artifacts/toc-gap-review/doc209-e976876-label21-p2.png',
             '.artifacts/toc-gap-review/doc209-e976876-label21-p9.png',
             '.artifacts/toc-gap-review/doc209-e976876-label21-p10.png'),
         'render_sha256', jsonb_build_array(
             '3ff8b115cfcd997efb96a1653674eafa7337a416de27bf5e98b06dc6f58eec8f',
             '6a20077f07f558ee26f88cc77a2ef7eda25c6e6a499d978112649641c9c9abe3',
             '60112ff092ed6de42bfe36645c91a17d2a01bec0de6506d13a31be446d98b833',
             '948b446e940f4805924398915da9623d7d0b56d05efc0ad80225e73020cb939c'),
         'observed', 'The contents on page 1 ends "20. Power to make rules." / '
                     '"21. Regulations."; page 2 carries one more row, "21. '
                     'Repeal." -- the contents numbers two rows 21. Page 9 prints '
                     '"Regulations." beside "21. (1) The Board may, subject to the '
                     'approval of Government, frame regulations ...". Page 10 '
                     'prints "Repeal" in the margin beside "22. The Balochistan '
                     'Model Residential Secondary School Ordinance 1983 (XVII of '
                     '1983), is hereby repealed." No contents row links body '
                     'section 22.',
         'release_check', 'all body pages (3-10) read against the tree: sections '
                          '1-22 in printed order, every printed marginal name '
                          'agrees with the tree heading (s.5 carries the run-in '
                          'heading "Chairman and Vice Chairman of the Board" that '
                          'page 4 prints beside the margin note), section 22 has '
                          'no tree heading, no phantom or missing section',
         'toc_entry_id_at_review', g.toc_entry_id,
         'batch', 'T1-2026-09-23'),
       'Read against the rendered pages. The printed contents numbers the Repeal '
       'row "21." a second time; the body prints it as section 22 with the '
       'marginal note "Repeal". The section is present and citable under the '
       'body''s own number, and no other contents row already names it. Nothing '
       'is absent from the source.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
  JOIN provision p ON p.instrument_id = g.instrument_id AND p.is_active
                  AND p.kind = 'section' AND p.label = '22'
                  AND p.first_block = 8315
 WHERE g.document_id = 209 AND g.printed_label = '21'
   AND g.source_block_id = 8185 AND g.source_page = 2
   AND g.toc_entry_id IS NOT NULL;

-- ── parser_defect: sixteen readings that close nothing ───────────────────────
CREATE TEMP TABLE _t1_defect (
    document_id     bigint,
    printed_label   text,
    source_block_id bigint,
    source_page     integer,
    defect_class    text,
    render_artifact text[],
    render_sha256   text[],
    observed        text,
    where_it_is     text,
    severity        text,
    rationale       text
) ON COMMIT DROP;

INSERT INTO _t1_defect VALUES
-- 510 SIND LOANS FOR AGRICULTURAL PURPOSES ACT, 1974
(510, '4', 19681, 1, 'promised_section_not_printed_absence_unproven',
 ARRAY['.artifacts/toc-gap-review/doc510-e992956-label4-p1.png',
       '.artifacts/toc-gap-review/doc510-e992956-label4-p2.png',
       '.artifacts/toc-gap-review/doc510-e992956-label4-p3.png',
       '.artifacts/toc-gap-review/doc510-e992956-label4-p4.png'],
 ARRAY['81725e1e150e5d0aec0f5729b9d052a12fab142811676218305da39913470a85',
       '511792345f7b78182d0172ea6d471b84aa2d55ee5248de534a6fcf7dd316cc00',
       '97264579783951b0306b7576d45c866189b39009abf4967e07d64f34434b37cb',
       '7945518d3d7c5d807c555211d74f1457658f97adc03928663db44fc2c0990784'],
 'All four pages read. The contents on page 1 lists "4. Pass Book." between '
 '"3. Act to Override Laws." and "5. Delivery of agricultural produce.". Page 3 '
 'prints "3. The provisions of this Act shall have effect notwithstanding '
 'anything contained in any other law for the time being in force." and then '
 'directly "5. (1) The borrower may deliver agricultural produce ..."; page 4 '
 'prints 8, 9 and 10 and ends the Act. No section 4, no omission marker and no '
 'footnote appear on any page.',
 'Evidence against absence: s.2(g) defines "pass-book" and s.6 requires '
 'payments to be "entered in the pass-book of the borrower". The Sind Loans for '
 'Agricultural Purposes Ordinance, 1974 (doc 791), which s.10 of this Act '
 'repeals, prints on its page 3 "4. (1) A borrower applying to any bank or '
 'society for a loan or advance on the security of land, may produce before '
 'such bank or society a pass-book in proof of ...". Remedy: check an official '
 'Gazette copy of Sind Act XXII of 1974; if s.4 is printed there, this is a '
 'source_incompleteness case (migration 0054), not an absence.',
 'law probably missing from this copy; no parser change can create it',
 'The promised section is not printed in this copy, but absent_in_source -- '
 'that the Act never had it -- is contradicted by the Act''s own definitions '
 'and by the Ordinance it replaced, which prints a section 4 on pass-books. '
 'Recorded so the reading is kept and the gap stays open; it needs a source '
 'check, not a parser fix.'),

-- 1003 SIND REVENUE JURISDICTION ACT, 1876
(1003, '6', 47258, 1, 'bare_repealed_section_number_not_opened',
 ARRAY['.artifacts/toc-gap-review/doc1003-e987743-label6-p1.png',
       '.artifacts/toc-gap-review/doc1003-e987743-label6-p3.png'],
 ARRAY['ce2691df37aa041ab4d4f1decfb87bd5487705754b9cd574cff2b6b1e8126c47',
       'f266566e9fa27edb345045578de5419998d208360b88953f180d95b4c8fc3446'],
 'The contents on page 1 lists "4. (Repealed).", "5. (Repealed).", "6. '
 '(Repealed).". Page 3 prints, after section 3: "4. Repealed by the West '
 'Pakistan Land Revenue Act, 1967." / "5. (Act. (XVII of 1967), Schedule, '
 'Part-2." / "6." -- one repeal note split across three list numbers, with the '
 'number 6 printed alone and nothing after it. Page 4 opens with section 7.',
 'All three numbers sit in one text block, 47271, which the tree holds as '
 'section 4; section 5 exists with the heading "(Act"; there is no section 6. '
 'Remedy: a repealed toc_disposition_assertion for entry 6 citing page 3, as '
 'was recorded for entry 17 (assertion 13).',
 'repealed section not represented; no operative text lost',
 'The page prints the number 6, so the source does not omit section 6: it is '
 'repealed and printed as an empty number. A disposition, not an absence, is '
 'what closes it, and that is the owner''s decision. Left open.'),

-- 1004 THE PAKISTAN DAY MEMORIAL CESS (WEST PAKISTAN) ACT, 1964
(1004, '4-A', 47314, 1, 'printed_section_held_as_a_non_section',
 ARRAY['.artifacts/toc-gap-review/doc1004-e989218-label4-A-p3.png',
       '.artifacts/toc-gap-review/doc1004-e989218-label4-A-p4.png'],
 ARRAY['0ae6ec4ddd499fb722d2cc39392e0b413f4312ee99e8e75146acda62eb9d86da',
       'cd242705ad767c617f96836564a03504a2570c32e78b343230f5831449bc8d1e'],
 'Page 3 prints, after section 4, "3[“4-A (1) Government shall, as soon as may '
 'be, constitute a Committee, to be known as the Pakistan Day Memorial (West '
 'Pakistan) Committee ..." with the marginal note "Constitution and composition '
 'of the committee and its function." and footnote 3 "Inserted vide West '
 'Pakistan Ord. No. V of 1966."; page 4 continues 4-A(3)(a)-(b) and then prints '
 '4-B and 4-C.',
 'Blocks 47351-47354 are held inside section 4 (paths s_4.ss_2, s_4.ss_2_n1_1, '
 's_4.ss_3). The opener 3[“4-A, with no full stop after the label, was not '
 'opened as a section.',
 'law present in the corpus but cited as section 4(2)',
 'The section is printed with the promised label and its text is in the tree '
 'under the wrong citation. Only a corrected parse resolves it.'),

-- 1034 SINDH REPRODUCTIVE HEALTH ORDINANCE 2014 (instrument short_title)
(1034, '5', 48663, 1, 'section_opener_lost_at_page_foot',
 ARRAY['.artifacts/toc-gap-review/doc1034-e978016-label5-p3.png',
       '.artifacts/toc-gap-review/doc1034-e978016-label5-p4.png',
       '.artifacts/toc-gap-review/doc1034-e978016-label5-p5.png',
       '.artifacts/toc-gap-review/doc1034-e978016-label5-p6.png'],
 ARRAY['dac86ff31f1ef516d54ff3207d4b9bbef06b78463b359b279152f75390581991',
       'd2b9a44087cc6db8664fb19f56923dea843c47ba67f4387d798f00fcbe2e233d',
       '76c7a6e18c40ffff746ac927a628342f3a60f9ce5a54b404729f65fd35029652',
       'b9a2e35029c742335031b0e9a93d1be4fa6c81d3b282acfc7dedb8c1be57ed93'],
 'Page 4 ends with section 4(2)(h), "cause performance audit and internal '
 'financial audit to be conducted ...". Page 5 opens mid-sentence, "powers, '
 'perform all functions and do all acts and things which may be exercised, '
 'performed or done by the Authority.", beside the tail of a marginal note, '
 '"Board.", then prints "(2) The Board shall comprise of the following:-" with '
 'its Chairperson / Vice Chairperson / Member table, "(2) The Director General '
 'shall also act as Secretary of the Board." and (3) to (5); page 6 prints (6) '
 'to (8) and then "6. (1) No person shall be or shall continue to be a member '
 'who –". The line that would carry "5. (1)" and the start of the marginal note '
 'is printed on neither page: the page 4 render ends at (h), and page 4 has no '
 'text block outside its crop box.',
 'The body of section 5 (blocks 48751-48781) is held as sub-sections of section '
 '4 (paths s_4.ss_2.cl_h, s_4.ss_2_n2_1, s_4.ss_2_n3_1, s_4.ss_3 to s_4.ss_8).',
 'law present in the corpus but cited as section 4; the section''s opening '
 'words are missing from this copy',
 'Section 5 is printed -- all of it but its first line -- and is not in the '
 'tree as section 5: its text is filed under section 4, so a citation of '
 'section 4 returns the Board''s constitution. Neither absent nor elsewhere. '
 'Left open.'),

-- 1051 THE HAZARA SETTLEMENT RULES REPEAL REGULATION, 1901
(1051, '1901', 49757, 2, 'year_from_title_line_read_as_section_label',
 ARRAY['.artifacts/toc-gap-review/doc1051-e995431-label1901-p1.png',
       '.artifacts/toc-gap-review/doc1051-e995431-label1901-p2.png'],
 ARRAY['58e92238d1bd6aeb42db635d42b2cec11e0f051ae9613130d196ed4577607d83',
       '7f32d008f81baf88bd8baa2c78fee07d04d3c36be331681726bede87b15a6b51'],
 'The contents on page 1 lists three sections only: "1. Short title, extent and '
 'commencement.", "2. Repeal of Regulations 1872 and 11, 1874.", "3. Provision '
 'as to entries in record of rights of first Hazara Settlement.". The "entry" '
 'labelled 1901 is the assent line under the title on page 2: "1[Received the '
 'assent of the Governor-General on the 25th October, 1901, published in the '
 'Gazette of India on the 26th Idem, and in the Punjab Gazette on the 31st '
 'idem]." Its year became the label.',
 'Contents row built from the assent line (block 49757).',
 'phantom contents row; no law is promised by it',
 'The contents row is not a row: it is the assent line, whose year the parser '
 'took for a section number. The source promises no such section, so no '
 'disposition applies. Only a corrected contents boundary removes it.'),

-- 1079 THE KHYBER PAKHTUNKHWA (PROVINCIAL URBAN DEVELOPMENT BOARD VALIDATION OF ACTIONS) ORDINANCE, 1980
(1079, '1980', 51085, 2, 'year_from_title_line_read_as_section_label',
 ARRAY['.artifacts/toc-gap-review/doc1079-e989467-label1980-p1.png',
       '.artifacts/toc-gap-review/doc1079-e989467-label1980-p2.png'],
 ARRAY['fbd33f39572ba71e11d610db0835082772c926fe30e167e280ebdac6874aa348',
       'b23dae8e0602819a1ca5154f7a694a63995ee6984960045c9ea1dc51d2b91f7a'],
 'The contents on page 1 lists "1. Short title and commencement." and "2. '
 'Validation." only. The "entry" labelled 1980 is the title line "2[KHYBER '
 'PAKHTUNKHWA] ORDINANCE No. VIII OF 1980" printed at the head of page 2.',
 'Contents row built from the title block (block 51085).',
 'phantom contents row; no law is promised by it',
 'The contents row is not a row: it is the Ordinance''s number line, whose '
 'year the parser took for a section number. The source promises no such '
 'section. Only a corrected contents boundary removes it.'),

-- 1105 PUNJAB COMMUNICATION AND WORKS DEPARTMENT (ENGINEERING POSTS ...) RULES, 1985
(1105, '2', 52802, 1, 'printed_section_held_as_a_non_section',
 ARRAY['.artifacts/toc-gap-review/doc1105-e987174-label2-p1.png',
       '.artifacts/toc-gap-review/doc1105-e987174-label2-p2.png'],
 ARRAY['97d472ec7355bc438fd2075ce0cc64e3047b2179a633ee4babf2a8248a0087a9',
       '14d6a6fefdc9bc2f1d5474d93976910edfba88e62bd03c03efebca2efdf12636'],
 'The contents on page 1 prints "1. ******", "2. ******", "3. ******", "4 ******" '
 'and "Schedule". Page 2 prints "1. These rules may be called the Punjab '
 'Communication & Works Department (Engineering Posts Qualifications and '
 'Conditions for Recruitment) Rules, 1985." / "2. They shall come into force at '
 'once." / "3. The method of recruitment ..." / "4. The following rules are '
 'hereby repealed:-".',
 'Rule 2 (block 52815) is held as sub-rule (2) of rule 1 (path s_1.ss_2).',
 'law present in the corpus but cited as rule 1(2)',
 'The rule is printed with the promised number and its text is in the tree '
 'under the wrong citation. Only a corrected parse resolves it.'),

-- 1247 SINDH SOLID WASTE MANAGEMENT BOARD ORDINANCE, 2014
(1247, '15', 65550, 2, 'promised_section_not_printed_absence_unproven',
 ARRAY['.artifacts/toc-gap-review/doc1247-e961048-label15-p2.png',
       '.artifacts/toc-gap-review/doc1247-e961048-label15-p17.png',
       '.artifacts/toc-gap-review/doc1247-e961048-label15-p18.png'],
 ARRAY['60f40769a7dead17513bcabd3439d581d01802b5da5220242c08017e32d5b8f8',
       '1219ca36f26800dcae6c991f0b0877acc819fd1a11cf8eb0e1c03c450a9f77ca',
       '5dea51259591c696fa5139eb2792fbb4ca0d1b72b7955c8f7c444c077981a9c5'],
 'The contents on page 2 lists "14. Decisions." and "15. Repeal." under CHAPTER '
 'VIII. Page 17 prints "CHAPTER-VIII MISCELLANEOUS" and section 14(1) to (3); '
 'page 18, the last page of the file, prints 14(4) and 14(5), "Any action taken '
 'by the employee of the Board in good faith shall not be questioned in any '
 'court of law.", and nothing after it: no section 15, no omission marker, no '
 'signature block.',
 'The Sindh Solid Waste Management Board Act, 2014 (doc 1233) lists "14.Decisions. '
 '15.Repeal." in its contents and prints on page 16 "15. The Sindh Solid Waste '
 'Management Board Ordinance is hereby repealed." -- so this Ordinance''s '
 'contents may have been copied from the Act, in which case the Ordinance never '
 'had a section 15. Plausible, not proven. absent_in_source is refused because '
 'this is the last contents row, so check 4 of tools/review_absent_sections.py '
 '(a resolved entry on both sides) cannot hold, and "Repeal." is below that '
 'tool''s 12-character heading floor.',
 'unresolved: a contents row with no section, or a copy missing its last section',
 'The promised section is not printed, and nothing on the page says why. The '
 'row is the tail of the contents, which is exactly the truncated-copy shape '
 'the absence checks refuse. Kept open for a source check rather than closed '
 'on a guess.'),

-- 1287 SINDH HIGHER EDUCATION COMMISSION ACT, 2013
(1287, '1', 69804, 1, 'printed_section_absent_from_tree',
 ARRAY['.artifacts/toc-gap-review/doc1287-e977924-label1-p1.png',
       '.artifacts/toc-gap-review/doc1287-e977924-label1-p2.png'],
 ARRAY['debb345bd914f58d61700bf3d429e2716e00d627e479f5a4da3282b3f5ce2ebf',
       '6023bc67325ca81df7f7d4f9223f283d52705325ffafc2383f2046df35945d03'],
 'Page 2 prints, under "CHAPTER-I PRELIMINARY", "1 (1) This Act may be called '
 'the Sindh Higher Education Commission Act, 2013." / "(2) It extends to the '
 'whole Province of Sindh." / "(3) It shall come into force at once." with the '
 'marginal note "Short title and commencement.". The label is printed "1" with '
 'no full stop.',
 'Block 69838, which holds all of section 1, and its marginal note (69837) carry '
 'role contents, as do the long title, preamble and enacting formula on the '
 'same page: the contents region ran into the body and took section 1 with it, '
 'so the tree begins at section 2.',
 'law not citable; the commencement section is held as contents apparatus',
 'The section is printed with the promised number and is not in the tree at '
 'all. Only a corrected contents boundary and parse resolve it.'),

-- 1306 WEST PAKISTAN BUILDINGS AND ROADS DEPARTMENT (CIRCLE) MINISTERIAL SERVICE RULES, 1963
(1306, '14', 71658, 1, 'printed_section_held_as_a_non_section',
 ARRAY['.artifacts/toc-gap-review/doc1306-e981998-label14-p1.png',
       '.artifacts/toc-gap-review/doc1306-e981998-label14-p7.png'],
 ARRAY['0f7f89c945d4a8a7c2ecf34bc59fbed5545cb0c6f6e34059a82c583200210d38',
       '9af6621d70339bce2e9e723e1836f51b4446e21b2c36b1b91f6771b84f8717b8'],
 'The contents on page 1 lists "14. *******". Page 7 prints, after "13. '
 'Delegation.- Government may delegate ...", "14 Powers of Governor to '
 'safeguard rights of Government servants.- Whenever in the application of '
 'these rules, the terms and conditions of service of any person serving in '
 'connection with the affairs of the Province of West Pakistan ... are likely '
 'to be adversely affected, the Governor of West Pakistan, shall make '
 'appropriate orders to safeguard the constitutional and legal rights of such '
 'persons." The label is printed "14" with no full stop.',
 'Block 71745 is held inside rule 13 (path pt_III.s_13).',
 'law present in the corpus but cited as rule 13',
 'The rule is printed with the promised number and its text is in the tree '
 'under the wrong citation. Only a corrected parse resolves it.'),

-- 1337 SINDH HOSPITAL WASTE MANAGEMENT RULES, 2014
(1337, '1', 74343, 1, 'heading_only_no_number',
 ARRAY['.artifacts/toc-gap-review/doc1337-e978156-label1-p1.png',
       '.artifacts/toc-gap-review/doc1337-e978156-label1-p2.png'],
 ARRAY['88dd6ad3e92e28c5ee3b06d5b52e77a7baa0e78657eafb8d32380f60d7664737',
       '55423c23b7fc39066c49bc8aac18424ddad4012e575f58d807328c978044b599'],
 'The contents on page 1 lists "1. Short title and Commencement.". Page 2 '
 'prints, after the notification and before "2. Definitions.-", "Short title '
 'and commencement.- (1) These rules may be called the Sindh Hospital Waste '
 'Management Rules, 2014." and "(2) They shall come into force at once." -- the '
 'rule''s heading and text, with no numeral 1.',
 'Blocks 74364 and 74365 carry role contents, so rule 1 is neither in the tree '
 'nor citable. Disagrees with the orphaned absent_in_source row '
 'eca7bad3-0caa-446e-b0b8-e61b01dada8d (codex.source_page_review/1, retired '
 'entry 458870): the rule is printed, only its numeral is not -- the shape of '
 'doc 2993 regulations 21-23.',
 'law not citable; the commencement rule is held as contents apparatus',
 'The contents promises rule 1 and the page prints it, heading and text, '
 'without its number. The law is not absent from the source; there is no '
 'numbered node to link. Only a parse that opens a provision on the heading '
 'resolves it.'),

-- 1348 LAND IMPROVEMENT LOANS ACT, 1883
(1348, '12', 75584, 1, 'printed_section_held_as_a_non_section',
 ARRAY['.artifacts/toc-gap-review/doc1348-e984240-label12-p1.png',
       '.artifacts/toc-gap-review/doc1348-e984240-label12-p7.png'],
 ARRAY['754fd5f31e1baf3897155917df46571437a4d7b53327298346b087938fd4e5d3',
       '38a3d5f01bc39eaee3d17a502bf2cf58f56ee36a3bd5ba3fb797e48de8162a39'],
 'The contents on page 1 lists "12. Certain powers of Provincial Government to '
 'be exercisable by Board of Revenue or Financial Commissioner.". Page 7 prints, '
 'after section 11(2), "3[12]. The Powers conferred on a 4[Provincial '
 'Government] by Section 4(1), 5 (1) and 10 may, in a province for which there '
 'is a Board of Revenue or a Financial Commissioner, be exercised in the like '
 'manner ..." with that marginal note, and footnote 3 "S.12 was ins. by the '
 'Decentralization Act, 1914 (IV of 1914) s. 2 and Sch. Pt. I. The original s. '
 '12 was rep. by the Registration Act, 1908 (XVI of 1908)."',
 'Block 75689 is held as section 11(2) (path s_11.ss_2) and its marginal note '
 'as a proviso of it. The bracketed opener "[12]." was not opened.',
 'law present in the corpus but cited as section 11(2)',
 'The section is printed with the promised number and its text is in the tree '
 'under the wrong citation. Only a corrected parse resolves it.'),

-- 847 KHYBER PAKHTUNKHWA ROAD TRANSPORT BOARD REMOVAL OF UNDESIRABLE EMPLOYEES ORDINANCE, 1965
(847, '2', 38081, 1, 'contents_offset_linked_by_number',
 ARRAY['.artifacts/toc-gap-review/doc847-e991966-label2-p1.png',
       '.artifacts/toc-gap-review/doc847-e991966-label2-p3.png',
       '.artifacts/toc-gap-review/doc847-e991966-label2-p4.png'],
 ARRAY['df02099db924e57b354031ad186b2982ad9d0b1c567a12e578c4dbc9310c3f4f',
       'a7783b20538187c120115f98a6fe69be326f3a07421951bfc01edb5d7c44378b',
       'a056a99de159f8a37f41b31af86135b651f3c24c2695b046ed8799eda9ff782e'],
 'The contents on page 1 lists "1. Short title and Commencement.", "3[2. '
 'Definitions.]", "2. Termination of Services.", "3. Appeals.", "4. Protection '
 'taken under the Ordinance." -- after the substituted Definitions row it was '
 'not renumbered. The body prints "Termination of services." beside section 3 '
 '(page 3), "Appeal." beside section 4 and "Protection taken under the '
 'Ordinance." beside section 5 (page 4).',
 'Linked by number, "3. Appeals." points at section 3 and "4. Protection ..." '
 'at section 4, so the tree heads section 3 "Appeals." and section 4 '
 '"Protection taken under the Ordinance.", and section 5 has no heading. The '
 'promised section is body section 3, which already carries contents row 3; '
 'pointing this row at it too would make one provision two contents rows (see '
 'tools/evidence/retract-toc-offset-misreading.sql). Remedy: link contents rows '
 'by printed heading where the numbering disagrees with the body.',
 'two provisions carry another section''s name; the promised section is '
 'present as section 3',
 'The promised section is in the tree, but the contents runs one behind the '
 'body and the parser paired it by number, misnaming the sections after it. '
 'Closing this row would release those names. Only a heading-aware relink '
 'resolves it.'),

-- 1014 SIND (TEACHING, PROMOTION AND USE OF SINDHI LANGUAGE) ACT, 1972
(1014, '8', 47679, 1, 'contents_offset_linked_by_number',
 ARRAY['.artifacts/toc-gap-review/doc1014-e994931-label8-p1.png',
       '.artifacts/toc-gap-review/doc1014-e994931-label8-p2.png',
       '.artifacts/toc-gap-review/doc1014-e994931-label8-p3.png'],
 ARRAY['b2fac8efaa42b29c4df84be57ea865566ef8221260aaa746d76fd08bb841bea2',
       '4a582a61b82853bf8a313cb13e0cf8b911d7ac399051da3880dc8e46fbd1fa47',
       'd50adb5e20836b3a015af069fb8e92a2ded901398f877925dd7fd9906e4fa984'],
 'The contents on page 1 lists 1 "Short title, commencement and extent.", 2 '
 '"Definition.", 3 "Constitution of Governing Body.", 4 "Provincial '
 'Language.", 5 "Teaching of Sindhi.", 6 "Sindhi Promotion of.", 7 "Use of '
 'Sindhi.", 8 "Power to make rules.". The body prints no section on a '
 'governing body: page 3 prints "3. Sindhi shall be used as the Provincial '
 'Language of the Province of Sind." beside "Provincial Language.", 4 beside '
 '"Teaching of Sindhi.", 5 beside "Promotion of Sindhi.", 6 beside "Use of '
 'Sindhi.", and "7. (1) Government may make rules for carrying out the purposes '
 'of this Act." beside "Power to make rules.". The Act ends at 7.',
 'Linked by number, sections 3 to 7 each carry the contents name of the next '
 'section: section 3 is headed "Constitution of Governing Body.", section 7 '
 '"Use of Sindhi.". The promised section is body section 7, which already '
 'carries contents row 7. Contents row 3 promises a section the body does not '
 'print. Remedy: link contents rows by printed heading.',
 'five of seven provisions misnamed; the promised section is present as '
 'section 7',
 'The promised section is in the tree, but the contents runs one ahead of the '
 'body from row 3 and the parser paired it by number, misnaming five sections. '
 'Closing this row would release those names. Only a heading-aware relink '
 'resolves it.'),

-- 1065 THE KHYBER PAKHTUNKHWA FINANCE ACT, 1985
(1065, '5', 50228, 1, 'contents_offset_linked_by_number',
 ARRAY['.artifacts/toc-gap-review/doc1065-e994232-label5-p1.png',
       '.artifacts/toc-gap-review/doc1065-e994232-label5-p2.png',
       '.artifacts/toc-gap-review/doc1065-e994232-label5-p3.png'],
 ARRAY['07767bc0388fa5206cd65c77662da40fb67195387cff4eaa68bcf6958498ee16',
       '54119893db2a54a52310f8347c224af4cf0b7d5e5457d43c23f8ed6ce28bb7b7',
       '4bda8ea1afdca47331c6f1b2a9333a0409032e2b8ab32f67d220cc9f6ac0b6df'],
 'The contents on page 1 numbers "1. Preamble." as a section, so it runs one '
 'ahead: its 2 "Short title, extent and commencement." is body 1, its 3 "Repeal '
 'of Act XIV of 1963." is body 2, its 4 is body 3, and its 5 "Deletion of '
 'section 8 of 5[Khyber Pakhtunkhwa] Act II of 1975." is body 4, which page 3 '
 'prints as "4. In the 1[Khyber Pakhtunkhwa] Finance Act, 1975 (... Act II of '
 '1975), section 8 shall be deleted." beside that marginal note.',
 'Linked by number, the tree heads section 1 "Preamble.", section 3 "Repeal of '
 'Act XIV of 1963." and section 4 "Amendment of section 12 of West Pakistan Act '
 'I of 1965."; section 2 is headed with operative text. Block 50244 holds 1(2), '
 '1(3) and section 2 ("The Gift Tax Act, 1963 (XIV of 1963), is hereby '
 'repealed.") together as sub-section 1(2). The promised section is body '
 'section 4, which already carries contents row 4.',
 'every section misnamed, and section 2''s text cited as 1(2)',
 'The promised section is in the tree, but the contents counts the Preamble '
 'as section 1 and the parser paired it by number, misnaming every section. '
 'Closing this row would release those names. Only a corrected parse resolves '
 'it.'),

-- 1225 SINDH FINANCE ACT, 2006
(1225, '9', 63193, 1, 'contents_offset_linked_by_number',
 ARRAY['.artifacts/toc-gap-review/doc1225-e982919-label9-p1.png',
       '.artifacts/toc-gap-review/doc1225-e982919-label9-p6.png',
       '.artifacts/toc-gap-review/doc1225-e982919-label9-p7.png',
       '.artifacts/toc-gap-review/doc1225-e982919-label9-p8.png'],
 ARRAY['b2f4e2bc229f9dab26bd75e13bbf0d25f9934c3ee7add7e1fadc50b20a382236',
       '0f0247205dfd7794b4a4cb2bc823316e0cecb3e53197bc58ea1faeb2647d2047',
       '5cef081e7e82a651d763a51525a887821c4baf7fadec42594af66c2cd4f95681',
       '7657762282eb98ec8f0baf49398b256a0d60ab45e105672ff2ae248a7e99f225'],
 'The contents on page 1 lists nine sections; its 3 "Duties payable by whom as '
 'per Articles of the Schedule." is not printed as a section in the body, so '
 'from 3 the contents runs one ahead. The body prints, with these marginal '
 'notes: 3 "Amendment of West Pakistan Act XXXII of 1958" (page 6); 4 '
 '"Amendment of Sindh Act XXVI of 1974" and 5 "Amendment of Sindh Act VIII of '
 '1975" (page 7); 6 "Amendment of Schedule to Sindh Ordinance VIII of 2000", 7 '
 '"Amendment of Sindh Act I of 2005" and 8 "Repeal of Sindh Ordinance XVII of '
 '2006." -- "8. The Sindh Assembly Members, Ministers and Special Assistants to '
 'the Chief Minister (Salaries, Allowances and Privileges) Amending Ordinance, '
 '2006 is hereby repealed." (page 8).',
 'Linked by number, sections 5 to 8 each carry the previous section''s name '
 '(section 8 is headed "Amendment of Sindh Act I of 2005."); sections 3 and 4 '
 'have no heading. The promised section is body section 8, which already '
 'carries contents row 8.',
 'four provisions misnamed; the promised section is present as section 8',
 'The promised section is in the tree, but the contents carries an extra row '
 'at 3 and the parser paired it by number, misnaming four sections. Closing '
 'this row would release those names. Only a heading-aware relink resolves '
 'it.');

INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', d.defect_class,
         'reviewer_type', 'assistant',
         'assistant_page_review', true,
         'human_page_review', false,
         'render_artifact', to_jsonb(d.render_artifact),
         'render_sha256', to_jsonb(d.render_sha256),
         'observed', d.observed,
         'where_it_is', d.where_it_is,
         'severity', d.severity,
         'printed_heading', g.printed_heading,
         'toc_entry_id_at_review', g.toc_entry_id,
         'batch', 'T1-2026-09-23'),
       d.rationale,
       'claude.toc-source-review/1'
  FROM _t1_defect d
  JOIN v_toc_gap_pending g
    ON g.document_id = d.document_id AND g.printed_label = d.printed_label
   AND g.source_block_id = d.source_block_id AND g.source_page = d.source_page
   AND g.toc_entry_id IS NOT NULL;

-- ── guard: the batch lands whole or not at all ───────────────────────────────
DO $$
DECLARE fe integer; pd integer;
BEGIN
    SELECT count(*) FILTER (WHERE resolution = 'found_elsewhere'),
           count(*) FILTER (WHERE resolution = 'parser_defect')
      INTO fe, pd
      FROM toc_gap_adjudication
     WHERE decided_at = now() AND evidence->>'batch' = 'T1-2026-09-23';
    IF fe <> 1 OR pd <> 16 THEN
        RAISE EXCEPTION 'T1 batch expected 1 found_elsewhere and 16 parser_defect, '
                        'wrote % and %; a live entry no longer matches its anchor',
                        fe, pd;
    END IF;
END $$;

SELECT a.document_id, a.printed_label, a.resolution,
       a.evidence->>'defect_class' AS defect_class,
       (SELECT count(*) FROM v_toc_gap_pending v
         WHERE v.instrument_id = a.instrument_id) AS still_pending,
       EXISTS (SELECT 1 FROM v_release_instrument r
                WHERE r.id = a.instrument_id) AS released
  FROM toc_gap_adjudication a
 WHERE a.decided_at = now() AND a.evidence->>'batch' = 'T1-2026-09-23'
 ORDER BY a.resolution, a.document_id;

COMMIT;

-- ═════════════════════════════════════════════════════════════════════════════
-- HELD -- NOT APPLIED. Three found_elsewhere readings that are correct about the
-- gap, each pointing at a provision no other contents row names, but whose
-- release would publish a tree the page contradicts. Apply only after the tree
-- is repaired, or by the owner's explicit decision; the anchors bind the live
-- entry and the target by first_block, so they survive a replay only if both
-- still match. Dry-run 23 Sep 2026: closes 3 gaps, releases 3 expressions.
--
--   294  contents "10. Schedule (Polyethylene, Polypropylene or Polystyrene
--        products.)." (page 1) = "THE SCHEDULE (See rule 2 (j)) Polyethylene,
--        Polypropylene or Polystyrene products" (page 5), tree SCHEDULE, block
--        13940. HOLD: the tree carries a phantom "section 2014" -- the year of
--        "Rules 2014." in rule 1(1) on page 2 -- that holds rule 1(2) "These
--        rules come in to force at once."; rule 1 lacks its (2). (The body's
--        missing rule 4 is genuine: page 3 prints 3 then 5, and the contents
--        lists no 4.)
--   806  contents "25. Accounts." (page 2, the second "25.") = "Accounts. 26.
--        The Authority shall maintain proper accounts ..." (page 11), tree s.26,
--        block 36511. HOLD: the contents orders 20 "Water and Sanitation
--        Authority Fund.", 21 "Delegation.", 22 "Committees ." while page 10
--        prints 20 "Delegation.", 21 "Committees ." and 22 "Water and
--        Sanitation Authority Fund."; linked by number, each of ss.20-22
--        carries another section's name.
--   876  contents (Schedule items, page 2) "10. Finance and Planning
--        Committee." = Schedule item "10. (1) The Finance and Planning
--        Committee shall consist of—" (page 22), tree SCHEDULE clause 10, block
--        39794; unmatched only because label 10 resolved to main s.10
--        "Visitation.". HOLD: page 1 prints "11 Chancellor." without a full
--        stop, so no row was built for it, and the Schedule's row "11.
--        Functions of the Finance and Planning Committee." was linked to main
--        s.11 instead; the tree heads s.11 -- page 9, "Chancellor. 11. (1) The
--        President of society shall be the Chancellor of the University" --
--        "Functions of the Finance and Planning Committee.".
--
-- BEGIN;
-- CREATE TEMP TABLE _t1_held (document_id bigint, printed_label text,
--     source_block_id bigint, source_page integer, found_kind text,
--     found_label text, found_first_block bigint, render_artifact text[],
--     render_sha256 text[], observed text, hold_reason text) ON COMMIT DROP;
-- INSERT INTO _t1_held VALUES
-- (294, '10', 13893, 1, 'schedule', 'SCHEDULE', 13940,
--  ARRAY['.artifacts/toc-gap-review/doc294-e990737-label10-p1.png',
--        '.artifacts/toc-gap-review/doc294-e990737-label10-p2.png',
--        '.artifacts/toc-gap-review/doc294-e990737-label10-p5.png'],
--  ARRAY['e5c1bb502fe371669068bf7a679b9ef2618575e71edf314a15e719ad214cca15',
--        'ae9e89f2c32c6569785745d9334a43fd31116faa7c35d8db3da5b7c14ce20cbe',
--        'ec12efe4cfd5ebdf727663b794a1e2a6e9e85786a43c1912eabde0dc42a86283'],
--  'The contents on page 1 lists "10. Schedule (Polyethylene, Polypropylene or '
--  'Polystyrene products.)." after rule 9. Page 5 prints "THE SCHEDULE (See rule '
--  '2 (j)) Polyethylene, Polypropylene or Polystyrene products" and items 1 to '
--  '9. The contents numbers the Schedule as item 10; the tree holds it as '
--  'SCHEDULE, which no contents row links.',
--  'phantom section 2014 holding rule 1(2)'),
-- (806, '25', 36338, 2, 'section', '26', 36511,
--  ARRAY['.artifacts/toc-gap-review/doc806-e961828-label25-p1.png',
--        '.artifacts/toc-gap-review/doc806-e961828-label25-p2.png',
--        '.artifacts/toc-gap-review/doc806-e961828-label25-p10.png',
--        '.artifacts/toc-gap-review/doc806-e961828-label25-p11.png'],
--  ARRAY['b019476eda3d7f8dfd4a02ad69b49368a501273df1e61726c15c72722c3b1025',
--        'fad13a49183ba947ce2c489e552d758afe789ae51d150360dc93736be339345d',
--        'fa0079e6f903dc4f17a3f1476e3eeea734e1e61b9bb041c47a0dea56d3d2ec7d',
--        '7ecaa92200133080bba7ab584b9bdd2f8957ad220b09fda029581ce4410718af'],
--  'The contents on page 2 prints "25. Powers to Borrow money." and then "25. '
--  'Accounts." -- 25 twice -- and then "27. Audit.". Page 11 prints "Accounts." '
--  'beside "26. The Authority shall maintain proper accounts and other relevant '
--  'records in such form as may be prescribed by the Board and approved by the '
--  'Provincial Government."; no contents row links section 26.',
--  'ss.20-22 misnamed by number against a contents that orders them differently'),
-- (876, '10', 39500, 2, 'clause', '10', 39794,
--  ARRAY['.artifacts/toc-gap-review/doc876-e950287-label10-p1.png',
--        '.artifacts/toc-gap-review/doc876-e950287-label10-p2.png',
--        '.artifacts/toc-gap-review/doc876-e950287-label10-p9.png',
--        '.artifacts/toc-gap-review/doc876-e950287-label10-p22.png',
--        '.artifacts/toc-gap-review/doc876-e950287-label10-p23.png'],
--  ARRAY['748756aefdca2765c35087f7c91e2d6d9f7178d91437e10a849e6335bb87768e',
--        '33f33a9ca784d717c1b45198d19debeb63a4082bc8e5da3c2f7a2d233b79d59b',
--        '9e685bb7b63e91ac98a84e6621dcd24e57fbc4a324bc93e0a7ff3e702dcf27a2',
--        'c172de514c99f5723372ce6f56d505547e6db9a793d03cac1ced97e6f853ac95',
--        '7696520628fee07989f3441ab0d79d69159c447f1ff368b1ef147178ecdeb00f'],
--  'The contents on page 2 lists the Schedule''s items under "ITEMS Schedule", '
--  'among them "10. Finance and Planning Committee.". Page 22 prints the '
--  'Schedule''s item "10. (1) The Finance and Planning Committee shall consist '
--  'of—" with that marginal note, continued on page 23; the tree holds it as '
--  'SCHEDULE clause 10, which no contents row links. The row is unmatched '
--  'because label 10 already resolved to main-body section 10 "Visitation.".',
--  'main s.11 (Chancellor) carries the Schedule''s item-11 name');
-- INSERT INTO toc_gap_adjudication
--     (instrument_id, document_id, toc_entry_id, printed_label, resolution,
--      source_page, evidence, rationale, decided_by)
-- SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
--        'found_elsewhere', g.source_page,
--        jsonb_build_object(
--          'found_provision_id', p.id::text, 'body_label', p.label,
--          'found_kind', p.kind::text, 'found_label', p.label,
--          'found_first_block', p.first_block, 'found_path', p.path::text,
--          'printed_heading', g.printed_heading,
--          'method', 'assistant read the rendered contents and body pages and '
--                    'matched the promised heading to the provision that '
--                    'prints it',
--          'reviewer_type', 'assistant', 'assistant_page_review', true,
--          'human_page_review', false,
--          'render_artifact', to_jsonb(h.render_artifact),
--          'render_sha256', to_jsonb(h.render_sha256),
--          'observed', h.observed,
--          'held_on_23_sep_because', h.hold_reason,
--          'toc_entry_id_at_review', g.toc_entry_id,
--          'batch', 'T1-2026-09-23-held'),
--        'Read against the rendered pages. The promised item is printed and '
--        'held in the tree under a different label, and no other contents row '
--        'names that provision; nothing is absent from the source. '
--        || h.observed,
--        'claude.toc-source-review/1'
--   FROM _t1_held h
--   JOIN v_toc_gap_pending g
--     ON g.document_id = h.document_id AND g.printed_label = h.printed_label
--    AND g.source_block_id = h.source_block_id AND g.source_page = h.source_page
--    AND g.toc_entry_id IS NOT NULL
--   JOIN provision p ON p.instrument_id = g.instrument_id AND p.is_active
--                   AND p.kind::text = h.found_kind AND p.label = h.found_label
--                   AND p.first_block = h.found_first_block;
-- COMMIT;
