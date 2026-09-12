-- Contents gaps classified by reading the rendered source page.
--
-- These four were rendered by tools/review_toc_gaps.py and read. Each is
-- recorded as `parser_defect`, which requires a defect_class and nothing else:
-- it says the gap is the parser's fault and names how, which is a claim the
-- reading supports. None is recorded as `absent_in_source`, because migration
-- 0042 reserves that for a human page review and an assistant reading a render
-- is not one -- the evidence column would be false if it said otherwise.
--
-- A parser_defect deliberately does NOT close the gap: v_toc_gap_pending keeps
-- it, because only a corrected parse resolves it. What this buys is a queue
-- that says what is wrong rather than only that something is.

BEGIN;

-- Document 306, Sindh Disposal of Urban Land (Repeal) Act 2005. The page prints
-- an unnumbered Preamble in the margin, then sections 1 and 2. The tree has
-- section 1 = "Preamble." and section 2 = "Short title and commencement.", so
-- every marginal heading sits one provision late and the repeal section -- the
-- entire operative purpose of the Act -- carries no heading at all.
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', 2,
       jsonb_build_object(
           'defect_class', 'preamble_marginal_note_consumed_by_first_section',
           'observed', 'tree has section 1 "Preamble." and section 2 "Short '
                       'title and commencement."; the page prints Preamble '
                       'unnumbered, then 1. Short title, then 2. Repeal',
           'render_artifact', '.artifacts/toc-gap-review/doc306-e271902-label3-p2.png',
           'reviewer_type', 'assistant',
           'human_page_review', false),
       'Read against the rendered page. The marginal headings are shifted one '
       'provision late because the unnumbered Preamble''s marginal note was '
       'attached to section 1. The promised "Repeal of Sindh Ordinance X of '
       '2002." is printed as section 2 and exists in the tree, but headingless, '
       'so no heading match can find it. Fixing the shift resolves this gap.',
       'claude.toc-page-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 306 AND g.printed_label = '3'
   AND g.toc_entry_id IS NOT NULL;

-- Document 4483, a scanned Sindh gazette. Its "contents list" is not one: the
-- running header "THE SINDH GOVT. GAZETTE MAY 20, 2021 PART-I" was parsed as a
-- contents row under label 341, and the rule's own opening line as another.
-- Every gap in this document is downstream of that.
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
SELECT g.instrument_id, g.document_id, g.toc_entry_id, g.printed_label,
       'parser_defect', 2,
       jsonb_build_object(
           'defect_class', 'running_header_and_body_text_parsed_as_contents',
           'observed', 'entry 341 is the page running header; entry 1 is the '
                       'rule''s own first line on page 2',
           'render_artifact', '.artifacts/toc-gap-review/doc4483-e470310-label1-p2.png',
           'reviewer_type', 'assistant',
           'human_page_review', false),
       'Read against the rendered page. This document prints no contents list. '
       'The parser built one from a running header and from body text, so its '
       'entries promise sections that were never promised. The gap is the '
       'contents list itself, and a disposition would record a lifecycle fact '
       'that the source never stated.',
       'claude.toc-page-review/1'
  FROM v_toc_gap_pending g
 WHERE g.document_id = 4483 AND g.toc_entry_id IS NOT NULL;

COMMIT;
