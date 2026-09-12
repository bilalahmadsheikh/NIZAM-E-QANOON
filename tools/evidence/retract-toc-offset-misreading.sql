-- Retract three `found_elsewhere` decisions that were wrong.
--
-- I recorded documents 169, 306 and 732 as "the contents is numbered one ahead
-- of the body", pointing each unmatched entry at the section one number below.
-- The owner challenged it from the source pages, and the challenge is right.
--
-- In all three the contents aligns with the body exactly: entry 5 links to
-- section 5, entry 2 to section 2, entry 14 to section 14. Pointing the NEXT
-- entry at that same section asserts one provision is two different contents
-- rows, which is false and would put a wrong citation target in the record.
--
-- What the pages actually show is the opposite reading: the section the
-- contents promises is NOT in the body, and its marginal heading is printed
-- beside the preceding section's text. Document 732 is unambiguous -- the body
-- runs 14, 16, 17 with no 15, while the contents lists 15 "Registration and
-- renewal fee", and that heading appears in the margin next to section 14.
--
-- These are superseded rather than deleted, so the mistake stays visible. The
-- gaps return to pending, which is the correct state: whether the source omits
-- the section or the parser lost it is exactly what a page reading must settle,
-- and my reading of it was wrong.

BEGIN;

INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by, supersedes_id)
SELECT prev.instrument_id, prev.document_id, prev.toc_entry_id,
       prev.printed_label, 'parser_defect', prev.source_page,
       jsonb_build_object(
         'defect_class', 'retracted_incorrect_found_elsewhere',
         'retracts', prev.id::text,
         'why_wrong', 'the section named as the target already carries its own '
                      'contents entry, so the contents is not numbered one '
                      'ahead; the promised section is simply not in the body',
         'observed', 'document 732 runs 14, 16, 17 with no 15, and the heading '
                     'for 15 is printed in the margin beside section 14',
         'raised_by', 'project owner, from the rendered source pages',
         'reviewer_type', 'assistant', 'human_page_review', false),
       'Retracts an earlier found_elsewhere decision of mine. I read a marginal '
       'heading printed beside section N and concluded the contents was '
       'numbered one ahead. It is not: entry N links to section N already. The '
       'promised section is absent from the body and its heading sits beside '
       'the section before it. Returning this gap to pending, because what it '
       'needs is a reading that settles whether the source omits the section or '
       'the parser lost it -- and mine did not.',
       'claude.toc-retraction/1', prev.id
  FROM toc_gap_adjudication prev
 WHERE prev.decided_by = 'bilalahmadsheikh'
   AND prev.resolution = 'found_elsewhere'
   AND (prev.document_id, prev.printed_label) IN
       ((169,'6'), (306,'3'), (732,'15'))
   AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication later
                    WHERE later.supersedes_id = prev.id);

COMMIT;
