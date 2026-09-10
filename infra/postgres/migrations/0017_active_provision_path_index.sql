-- Keep append-only provision history without forcing the descendant-path GiST
-- index to absorb every retired copy of the same legal tree.
--
-- Re-segmentation preserves old instruments and provisions. Their canonical
-- paths intentionally repeat across revisions, and the global ltree GiST became
-- pathological under that duplicate-heavy history: writes first exceeded
-- max_stack_depth and, when the stack ceiling was raised, wedged the database.
-- Exact historical lookup remains covered by uq_provision_instrument_path.
-- Descendant traversal only serves the active legal expression, so its GiST is
-- partial and bounded to active provisions.

BEGIN;

-- Drop first: even an UPDATE of a non-path column writes new tuples to every
-- non-HOT index. Updating revision flags while the pathological GiST exists
-- reproduces the same incomplete-split recursion this migration repairs.
DROP INDEX IF EXISTS provision_path_gist;

ALTER TABLE provision
    ADD COLUMN is_active boolean NOT NULL DEFAULT true;

UPDATE provision p
   SET is_active=i.is_active
  FROM instrument i
 WHERE i.id=p.instrument_id
   AND p.is_active IS DISTINCT FROM i.is_active;

CREATE INDEX provision_active_path_gist
    ON provision USING gist (path gist_ltree_ops(siglen=64))
    WHERE is_active;

CREATE INDEX provision_retired_instrument
    ON provision (instrument_id) WHERE NOT is_active;

COMMIT;
