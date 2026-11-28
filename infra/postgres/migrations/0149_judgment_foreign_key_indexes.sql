-- 0149  Indexes under the judgment side's foreign keys (DECISION-LOG D-183).
--
-- Postgres indexes the referenced key of a foreign key, never the referencing columns. Seven referencing columns on
-- the judgment side had no index, so every delete of a judgment, opinion or paragraph made the foreign-key check scan
-- the referencing table whole. The first restore proof of the judgment prune (28 Nov 2026) spent 5 h 14 min in one
-- DELETE of 745k retired paragraphs, each checked against 437k statute and 205k case references, and was stopped.
--
-- Two of these also serve reads: a judgment's cited cases (judgment_case_reference by judgment_id) and the lineage
-- above a judgment (judgment_lineage by upper_judgment_id) scanned their tables on every judgment page.
--
-- judgment_paragraph is partitioned by decided_on: an index on the parent is created on every partition.

BEGIN;

CREATE INDEX IF NOT EXISTS ix_jsr_paragraph
  ON judgment_statute_reference (paragraph_id, decided_on);
CREATE INDEX IF NOT EXISTS ix_jcr_paragraph
  ON judgment_case_reference (paragraph_id, decided_on);
CREATE INDEX IF NOT EXISTS ix_jcr_judgment
  ON judgment_case_reference (judgment_id, decided_on);
CREATE INDEX IF NOT EXISTS ix_judgment_paragraph_opinion
  ON judgment_paragraph (opinion_id);
CREATE INDEX IF NOT EXISTS ix_judgment_lineage_upper
  ON judgment_lineage (upper_judgment_id, upper_decided_on);
CREATE INDEX IF NOT EXISTS ix_lineage_link_upper
  ON judgment_lineage_link (upper_judgment_id, upper_decided_on);
CREATE INDEX IF NOT EXISTS ix_invalidation_candidate_judgment
  ON judicial_invalidation_candidate (judgment_id, decided_on);

COMMIT;
