-- 17 Nov 2026: after the PPC footnote repair (hold-ppc-footnotes-2026-11-17.sql) document 4441 replays as two active
-- instruments (twins over one source). The contents-gap reading of page 26 -- the printed contents misnumber section
-- 462N as '362N' (found_elsewhere) -- carried to instrument e9383564 but not to its twin 0e73eed1: the label names an
-- entry in each twin, so reattach_orphaned_toc_adjudications.py finds no single live entry and refuses. The page has
-- not changed; this records the same reading for the twin's entry, citing the decision it repeats.
BEGIN;
INSERT INTO toc_gap_adjudication (instrument_id, document_id, printed_label, resolution, source_page, evidence,
                                  rationale, decided_by, toc_entry_id)
SELECT e.instrument_id, a.document_id, a.printed_label, a.resolution, a.source_page,
       a.evidence || jsonb_build_object('repeats_decision', a.id::text,
                                        'why', 'twin instrument over the same source; same printed contents entry'),
       a.rationale, a.decided_by, e.id
  FROM toc_gap_adjudication a
  JOIN instrument_toc_entry e ON e.id = 1252834 AND e.printed_label = a.printed_label
 WHERE a.id = 'd60c3702-623e-41a1-9015-573fcad309ec'
   AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication x WHERE x.toc_entry_id = 1252834);
COMMIT;
