-- Contents gaps in documents 2205, 2557, 1856, 4428 and 4594, each read against
-- its rendered source page. None of these is a section the official source
-- omits, so none takes absent_in_source; each is classified with the defect it
-- exposes, which records the finding without closing the gap. That is correct:
-- in every one of them the promised law is in the PDF and is NOT citable in the
-- corpus, and only a corrected parse (or, for 2205, a complete PDF) fixes that.
BEGIN;

-- ── 2205 SIND PUBLIC CONVEYANCES ACT, 1920: the PDF is truncated ────────────
-- The contents on page 2 promises sections 21 to 39. The document has 8 pages
-- and page 8, the last, stops in the middle of section 20(3).
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'source_pdf_truncated',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', '.artifacts/catalogue/pages/doc2205-p8-8.png',
         'render_sha256', 'f45838e663fa8acdea3273c18b76e3d0ef91ce61b91802f0eb688c6e3210916c',
         'observed', 'Page 8 is the last page of an 8-page PDF. It prints sections 16A, 17, 18, 19 and 20 and stops inside section 20(3): "Every such driver shall on demand produce such list for the information of any hirer of, or passenger travelling in, the conveyance" - the sentence is cut and the page then carries only its footnotes. The tree ends at section 20. Sections 21 to 39, which the printed contents on page 2 lists by heading, are not printed anywhere in this copy.',
         'severity', 'law missing from the corpus',
         'remedy', 'reacquire a complete copy of the Act'),
       'The promised section is not absent from the official source: this copy of it '
       'is short. Page 8 of 8 breaks mid-sentence inside section 20(3) and the '
       'nineteen sections the contents page lists after section 20 are not printed. '
       'absent_in_source would be a false statement about the Act, so this is '
       'recorded as a source defect and the gap stays open until a complete PDF is '
       'acquired and re-extracted.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 2205 AND g.toc_entry_id IS NOT NULL;

-- ── 2557 SINDH INCUMBERED ESTATES ACT, 1896 ────────────────────────────────
-- (a) the seven real contents rows, whose sections the tree does not hold
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'printed_section_absent_from_tree',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', '.artifacts/catalogue/pages/doc2557-p5-05.png',
         'render_sha256', '42f21293d7e6e36688ab94f6899b6b4eeb3e8d035401b9a8ef14d48a2aba135d',
         'observed', 'The printed contents on page 1 lists "1. Title and commencement. 2. Definitions." under CHAPTER I and "3. Application for the benefits of this Act. 4. Order to inquire. 5. Interim order of protection. 6. Verified statement to be submitted. 7. Report of inquiry and proceedings thereon." under CHAPTER II. Page 5 prints sections 6 and 7 in full: "6. (1) When an inquiry has been directed under section 4, the applicant shall, within a period to be fixed by the 3[Collector] submit to the officer appointed to make such inquiry a statement duly verified by the said applicant..." and "7. (1) The officer so appointed, after making inquiry, shall submit a report of the proceedings to the 3[Collector]." The tree holds sections 8 to 39 and no sections 5, 6 or 7 at all; the nodes it labels 1, 2, 3 and 4 open on footnote lines on pages 8 and 12 ("1. The original section 22 was re-numbered as section 22(1) by the Sindh...", "3. The words Jagirdar or other omitted by Sind Ord. LIV of 1984, s.7.").',
         'severity', 'law missing from the corpus'),
       'The section is printed in the source with the promised number and is not in '
       'the tree: this is neither a link failure nor an omission in the source. '
       'Sections 1 to 7 of the Act are law the corpus holds as text and cannot cite. '
       'The tree''s top level for this document is chapters only - II, III, III read '
       'by OCR as 111, IV, V five times over, VI twice and VII twice - and the four '
       'nodes that carry the numbers 1 to 4 are footnote lines.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 2557 AND g.toc_entry_id IS NOT NULL AND g.ordinal <= 6;

-- (b) the fourteen entries the contents builder harvested from footnote lines
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'contents_row_is_not_a_section',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', '.artifacts/catalogue/pages/doc2557-p5-05.png',
         'render_sha256', '42f21293d7e6e36688ab94f6899b6b4eeb3e8d035401b9a8ef14d48a2aba135d',
         'observed', 'This contents entry is not a contents row. Its stored printed_heading is the text of a numbered FOOTNOTE at the foot of a body page, harvested by the contents builder because the footnotes on every page restart at 1: page 5 ends "1. Subs. by Central Laws (Statute Reforms) Ord. No.XXI of 1960., Sch. II, for the Provinces and the Capital of Federation...; 2. Sub-section (2) ins. By the Sindh Incumbered Estates (Amendment) Act, 1906 (2 of 1906) s. 3.; 3. Subs. by Sind Ordinance III of 1972, s. 2, Sch., for Revenue Commissioner.; 4. Subs. by Sind Laws (Adaption, Revision, Repeal and Declaration) Ordinance, 1955", and the entries stored at this ordinal read exactly like that. The document''s only printed contents is on page 1 and stops at ordinal 6.',
         'severity', 'phantom contents row; no law is promised by it'),
       'The entry promises nothing: it was built from a footnote line on a body page, '
       'not from the printed contents. It cannot be linked to a provision and it '
       'names no missing law. Only a corrected contents-region boundary removes it, '
       'so it is classified and left open rather than closed with a false finding.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 2557 AND g.toc_entry_id IS NOT NULL AND g.ordinal >= 39;

-- ── 1856 SIND HIGHWAY ACT, 1883 ────────────────────────────────────────────
-- (a) the four real contents rows
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'printed_section_absent_from_tree',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', '.artifacts/catalogue/pages/doc1856-p3-3.png',
         'render_sha256', 'b08211771538fec9ff06069aca3ba371427bafc8019948a5452cf1f32064d8bf',
         'observed', 'The printed contents on page 1 lists sections 1 to 8 and the SCHEDULE. Pages 2 and 3 each print the whole preamble and sections 1 and 2 - the document sets the opening of the Act twice, page 2 misprinting the citation as "the 3[Sind] Highway Act, 1833" and page 3 printing "1883" - and page 4 prints "3. It shall be lawful for the 1[Provincial Government], after the publication of the notification referred to in the last proceeding section, to levy 2a tax on all carriages, coaches, vans, carts, hackeries, horses or ponies in accordance with the rates specified in the Schedule" and section 4. The tree''s top level begins at section 5; sections 1, 2, 3 and 4 are not in it under any label.',
         'severity', 'law missing from the corpus'),
       'The section is printed in the source - twice over, for sections 1 and 2 - and '
       'is not in the tree. Sections 5 to 8 and the Schedule are held and correctly '
       'headed; sections 1 to 4 are law the corpus holds as text and cannot cite. The '
       'duplicate setting of the Act''s opening on pages 2 and 3 is the likely cause '
       'and is itself a boundary the segmenter has to resolve.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 1856 AND g.toc_entry_id IS NOT NULL AND g.ordinal <= 3;

-- (b) the fourteen entries harvested from the body and its footnotes
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'contents_row_is_not_a_section',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', '.artifacts/catalogue/pages/doc1856-p2-2.png',
         'render_sha256', 'ea6e32be4468e3bfb1ef07fff831f579cbc96f0805737cbaa81e50ea7a5be5a1',
         'observed', 'This entry is not a contents row. The only printed contents is on page 1 and ends at "8. Saving provisions. SCHEDULE". The entries from ordinal 8 onward were harvested from the BODY: ordinals 8 and 9 are the text of sections 1 and 2 as set on page 2 ("This Act shall be cited as the 3[Sind] Highway Act, 1833, and it shall come into force in the manner provided in the next following section."), ordinals 10 to 17 are that page''s eight numbered footnotes ("1. For Statement of Objects and Reasons, see B. G. G., 1882, Pt. V. p. 53...", "6. Subs. by the A. O., 1937, for G. in C."), ordinals 18 and 19 are sections 1 and 2 again from the second setting on page 3, and ordinals 20 and 21 are sections 3 and 4 from page 4.',
         'severity', 'phantom contents row; no law is promised by it'),
       'The contents region was taken to run past page 1 into the body, so body '
       'sections and page footnotes became contents entries - and because the Act''s '
       'opening is set twice, sections 1 and 2 became entries twice. Nothing is '
       'promised and nothing can be linked. Only a corrected contents boundary '
       'removes these rows.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 1856 AND g.toc_entry_id IS NOT NULL AND g.ordinal >= 8;

-- ── 4428 SINDH PUBLIC PROCUREMENT ACT, 2009 + RULES, 2010 in one file ───────
-- (a) the three real contents rows
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'printed_section_absent_from_tree',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', '.artifacts/catalogue/pages/doc4428-p17-17.png',
         'render_sha256', '8e81499e0bec15703f33763a1b3e35988a1ad4156aec015c4c8b965793427914',
         'observed', 'The file holds TWO instruments. Pages 1 to 2 are the contents of THE SINDH PUBLIC PROCUREMENT ACT, 2009 ("25. WINDING UP. 15 / 26. POWER OF GOVERNMENT TO MAKE RULES. 15 / 27. POWERS OF THE AUTHORITY TO MAKE REGULATION. 15"), pages 3 to 16 are that Act''s body, and page 17 opens THE SINDH PUBLIC PROCUREMENT RULES, 2010 with its own "TABLE OF CONTENTS / Rule no. PAGE NO. / 1. Short Title and Commencement 23 / PART-I GENERAL PROVISIONS / 2. Definitions 23 / 3. Scope and Applicability 29". The tree''s sections 1 to 43 all carry first_page 17 to 19 and their text is that Rules table of contents - section 1 holds "1. Short Title and Commencement PART-I GENERAL PROVISIONS 23" and section 10 holds "10. Transparency PART II-PROCUREMENT OF GOODS, WORKS AND RELATED SERVICES" - while the headings on them are the ACT''s contents headings (SHORT TITLE EXTENT AND COMMENCMENT, DEFINATIONS, ESTABLISHMENT OF THE AUTHORITY). The Act''s own sections, printed on pages 3 to 16, are not in the tree.',
         'severity', 'law missing from the corpus; and 43 active provisions are mis-headed',
         'also_found', 'the Act''s contents headings were paired positionally onto provisions built from the Rules contents list, so 43 active provisions of this instrument carry a heading that does not belong to their text - wider than the gap asked about, and it must be fixed before this document is released'),
       'The promised section is printed on page 15 of the Act and is not in the tree. '
       'The document binds the Act and the Rules, and the segmenter built its whole '
       'section list from the Rules'' table of contents on pages 17 to 19 while '
       'pairing the Act''s contents headings onto it. Neither instrument is citable. '
       'This needs a boundary split and a re-parse, not a contents-gap decision.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 4428 AND g.toc_entry_id IS NOT NULL AND g.ordinal <= 26;

-- (b) the sixteen entries harvested from the Act's body pages
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'contents_row_is_not_a_section',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', '.artifacts/catalogue/pages/doc4428-p15-15.png',
         'render_sha256', 'dc0ceb4e212d52581056009b4e5e82d5e90afc5b06257e4893d03b119fe3e555',
         'observed', 'This entry is not a contents row: it was harvested from the ACT''s body on pages 3 to 15, whose printed contents ends on page 2. Its stored printed_heading is operative text - page 15 prints "22. No act or proceedings of the Authority or the Board shall be invalid by reason only of the existence of a vacancy in, or defect in the constitution of, the Authority or the Board." and "23. No suit, prosecution, or other legal proceedings shall lie against the Authority, the Board, the Chairman or any member, officer, servants, adviser or consultant of the Authority in respect of anything in good faith done or intended to be done under this Act", and the entries stored at these ordinals are those sentences verbatim.',
         'severity', 'phantom contents row, and the law it quotes is not citable'),
       'The contents region was taken to run from page 2 into the Act''s body, so the '
       'Act''s sections became contents entries instead of provisions. The text is in '
       'the corpus and is not citable. The repair is the same boundary split and '
       're-parse the three real contents rows need.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 4428 AND g.toc_entry_id IS NOT NULL AND g.ordinal >= 27;

-- ── 4594 SINDH PRISONS AND CORRECTIONS SERVICES RULES, 2019 ────────────────
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'contents_row_is_not_a_section',
         'reviewer_type', 'assistant', 'assistant_page_review', true,
         'render_artifact', '.artifacts/catalogue/pages/doc4594-p4-004.png',
         'render_sha256', '866f12adb71c45220e9a8bda61a4b74fa1a7cb3d2ba680b525c55762491df86d',
         'observed', 'Pages 4 and 5 are body pages of this Gazette scan, not contents pages, and the two entries were harvested from them. The second entry stores as its heading the OCR of a rule''s operative text - "Prisoner to be kept in 8 separate cell on evellable capacity of Cell. (1: Subsect to the available cangcicy of cells-and the Instructions of the Offic" - which is a rule, not a contents row; the first stores "Construction and administration of High Security Prison." from page 4. The tree holds no rule 3 or rule 10 at those pages: its node labelled 3 first appears on page 11 and is rule 33, because this scan''s OCR loses the leading digits of rule numbers, which is the same defect that produced the document''s twenty structural collisions.',
         'severity', 'phantom contents row; the rule it quotes is not citable under its printed number'),
       'Neither entry came from a printed contents list. Both were taken from body '
       'pages of a scan whose OCR truncates rule numbers, so the label they carry is '
       'not the rule''s printed number. They cannot be linked and they name no '
       'missing law that a contents decision could settle: the repair is the source '
       'correction of the OCR''d rule numbers and a re-parse.',
       'claude.toc-source-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 4594 AND g.toc_entry_id IS NOT NULL;

SELECT document_id, evidence->>'defect_class' AS defect_class, count(*)
  FROM toc_gap_adjudication
 WHERE decided_by = 'claude.toc-source-review/1'
 GROUP BY 1, 2 ORDER BY 1, 2;
COMMIT;
