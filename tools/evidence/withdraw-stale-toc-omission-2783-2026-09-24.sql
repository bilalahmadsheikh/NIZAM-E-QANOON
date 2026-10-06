-- WITHDRAWN 24 Sep 2026 ~17:40 UTC, minutes after insert, by the same reviewer
-- (claude.disposition-review/2). The assertion recorded by
-- record-reviewed-toc-omission-2783-2026-09-24.sql was invalid for this table:
-- the segmenter applies an omission only to a contents row that itself prints
-- the disposition ([Omitted]/[Repealed]); doc 2783's contents row 11 prints the
-- section's heading and only the BODY prints the omission. The replay raised
-- "stale TOC disposition assertion for ordinal 10 label 11", so the row made
-- the document unreplayable. It was never applied to any tree (no
-- provision_version references it) and nothing supersedes it. There is no
-- append-only withdrawal path for this table, so the single row is removed
-- under an exact guard. The source finding stands: page 5 prints
-- "11. [...] Omitted by the Federal Laws (Revision and Declaration) Ordinance,
-- 1981" -- that belongs to a different lane (the body's own omission stub).
BEGIN;
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM toc_disposition_assertion a
   WHERE a.source_observation_id=12 AND a.expression_ordinal=0
     AND a.reviewed_toc_entry_id=1073277 AND a.printed_label='11'
     AND a.reviewed_by='claude.disposition-review/2'
     AND a.reviewed_at > now() - interval '2 hours'
     AND NOT EXISTS (SELECT 1 FROM provision_version v WHERE v.source_toc_disposition_assertion_id=a.id)
     AND NOT EXISTS (SELECT 1 FROM toc_disposition_assertion b WHERE b.supersedes_id=a.id);
  IF n <> 1 THEN RAISE EXCEPTION 'expected exactly one unreferenced fresh 2783 assertion, found %', n; END IF;
  IF (SELECT count(*) FROM toc_disposition_assertion WHERE source_observation_id=12) <> 1 THEN
    RAISE EXCEPTION 'observation 12 carries other disposition assertions';
  END IF;
END $$;
DELETE FROM toc_disposition_assertion
 WHERE source_observation_id=12 AND expression_ordinal=0
   AND reviewed_toc_entry_id=1073277 AND reviewed_by='claude.disposition-review/2';
COMMIT;
