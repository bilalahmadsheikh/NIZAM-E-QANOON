-- 17 Nov 2026, after the second PPC replay (hold-ppc-structure-2026-11-17.sql): both twin instruments of document 4441
-- were rebuilt, so the page-26 contents reading -- the printed contents misnumber section 462N as '362N'
-- (found_elsewhere, decision d60c3702) -- is recorded again for every pending '362N' entry of the document. The page
-- has not changed; reattach_orphaned_toc_adjudications.py refuses because the label names an entry in each twin.
BEGIN;
INSERT INTO toc_gap_adjudication (instrument_id, document_id, printed_label, resolution, source_page, evidence,
                                  rationale, decided_by, toc_entry_id)
SELECT g.instrument_id, a.document_id, a.printed_label, a.resolution, a.source_page,
       a.evidence || jsonb_build_object('repeats_decision', a.id::text,
                                        'why', 'replayed twin instruments over the same source; same printed contents entry'),
       a.rationale, a.decided_by, g.toc_entry_id
  FROM toc_gap_adjudication a
  JOIN v_toc_gap_pending g ON g.document_id = a.document_id AND g.printed_label = a.printed_label AND g.source_page = 26
 WHERE a.id = 'd60c3702-623e-41a1-9015-573fcad309ec';
COMMIT;
