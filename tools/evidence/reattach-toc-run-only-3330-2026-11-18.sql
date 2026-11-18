-- Doc 3330 (Dow University of Health Sciences Ordinance, 2003): its segmenter run reports label 45 missing although
-- the contents row '45. Faculties.' is linked (match 'statutes_order'). The reviewed decision closing that run-only
-- gap ('found_elsewhere', 14 Oct 2026) names the instrument the D-085 replay retired, and the post-replay re-attach
-- tool carries entry gaps only. Re-anchor the same decision to the active instrument, append-only, naming the row it
-- carries forward.
BEGIN;
INSERT INTO toc_gap_adjudication (instrument_id, document_id, printed_label, resolution, source_page, evidence,
                                  rationale, decided_by, toc_entry_id)
SELECT i.id, a.document_id, a.printed_label, a.resolution, a.source_page,
       a.evidence || jsonb_build_object('reattached_from', a.id, 'reattached_at', '2026-11-18'),
       a.rationale || ' (Re-anchored 18 Nov 2026 after the D-085 replay; decision unchanged.)',
       'claude.toc-run-only-reattach/1', NULL
  FROM toc_gap_adjudication a
  JOIN instrument i ON i.document_id = a.document_id AND i.is_active AND i.duplicate_of IS NULL
 WHERE a.id = 'fca8af01-3bdd-4c9b-a55a-be5b3908980d'
   AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication b WHERE b.instrument_id = i.id AND b.toc_entry_id IS NULL
                                                           AND b.printed_label = a.printed_label);
COMMIT;
