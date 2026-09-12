-- Eight contents gaps, each read against its rendered source page by the
-- project owner, who reported what the page shows. Recorded here with the
-- provision the reading identifies, or with the defect class it exposes.
--
-- None of the eight is a section the official source omits. Three are the
-- contents numbered one ahead of the body; two are a year from a title line
-- read as a section label; one is a Preamble the parser never made a node; and
-- two -- documents 247 and 775 -- are sections printed plainly in the source
-- and absent from the tree, which is law the corpus does not currently hold.
--
-- `found_elsewhere` closes a gap and names the provision. `parser_defect`
-- classifies without closing: only a corrected parse resolves those, which is
-- exactly right for the five that remain.

BEGIN;

-- ── found_elsewhere: the contents is numbered one ahead of its body ─────────
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'found_elsewhere', g.source_page,
       jsonb_build_object(
         'found_provision_id', p.id::text,
         'body_label', p.label,
         'printed_heading', g.printed_heading,
         'method', 'owner read the rendered page and reported the heading '
                   'printed against the body number one below the promised one',
         'reviewer_type', 'human', 'human_page_review', true,
         'render_artifact', concat('.artifacts/toc-gap-review/doc',
                                   g.document_id, '-e', g.toc_entry_id,
                                   '-label', g.printed_label, '.png')),
       'Read against the rendered source page. The promised heading is printed '
       'in the margin beside the body section one number below, so this '
       'contents page is numbered one ahead of the body it describes -- the '
       'section is present and citable under the body''s own number. Nothing '
       'is absent from the source.',
       'bilalahmadsheikh'
  FROM v_toc_gap_pending g
  JOIN provision p ON p.instrument_id = g.instrument_id AND p.is_active
                  AND p.kind = 'section'
                  AND p.label = ((g.printed_label)::int - 1)::text
 WHERE (g.document_id, g.printed_label) IN ((169,'6'), (306,'3'), (732,'15'))
   AND g.toc_entry_id IS NOT NULL;

-- ── parser_defect: a section the source prints and the tree does not hold ───
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'printed_section_absent_from_tree',
         'observed', 'the page prints this section with this exact number; the '
                     'tree''s numbering stops one below it',
         'severity', 'law missing from the corpus',
         'reviewer_type', 'human', 'human_page_review', true),
       'Read against the rendered source page. The section is printed with the '
       'promised number and is not in the tree at all, so this is not a link '
       'failure and not an omission in the source: the parser did not open the '
       'section. The gap stays pending because only a corrected parse resolves '
       'it.',
       'bilalahmadsheikh'
  FROM v_toc_gap_pending g
 WHERE (g.document_id, g.printed_label) IN ((247,'10'), (775,'27'))
   AND g.toc_entry_id IS NOT NULL;

-- ── parser_defect: a year from a title line read as a section label ─────────
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'year_from_title_line_read_as_section_label',
         'observed', 'the "entry" is the long title or the regulation heading; '
                     'its trailing year became the label',
         'reviewer_type', 'human', 'human_page_review', true),
       'Read against the rendered source page. The contents row is not a row: '
       'it is the long title ("An Act to amend the Sind Wildlife Protection '
       'Ordinance, 1972.") or the regulation heading, whose trailing year the '
       'parser took for a section number. The source promises no such section, '
       'so a disposition would record a lifecycle fact it never stated.',
       'bilalahmadsheikh'
  FROM v_toc_gap_pending g
 WHERE (g.document_id, g.printed_label) IN ((523,'1972'), (559,'1987'))
   AND g.toc_entry_id IS NOT NULL;

-- ── parser_defect: the Preamble is printed but never became a node ──────────
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', g.source_page,
       jsonb_build_object(
         'defect_class', 'preamble_printed_but_not_materialised',
         'observed', 'the page prints "Preamble." in the margin before section '
                     '1; the contents counts it as entry 1; the tree has no '
                     'preamble provision',
         'reviewer_type', 'human', 'human_page_review', true),
       'Read against the rendered source page. The Preamble is printed and the '
       'contents numbers it as entry 1, but the tree holds no preamble node, so '
       'the entry links to nothing. The text is present in the corpus; what is '
       'missing is the provision that would make it citable.',
       'bilalahmadsheikh'
  FROM v_toc_gap_pending g
 WHERE (g.document_id, g.printed_label) IN ((362,'1'))
   AND g.toc_entry_id IS NOT NULL;

COMMIT;
