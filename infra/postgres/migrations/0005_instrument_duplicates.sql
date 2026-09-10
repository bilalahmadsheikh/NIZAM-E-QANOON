-- 0005  the same Act appears more than once, and that is a fact about the corpus
--
-- Migration 0004 implemented doc 03 §2.1's identity constraint as a partial
-- unique index:
--
--     UNIQUE (jurisdiction, kind, number, year) WHERE number IS NOT NULL
--
-- Segmenting the whole corpus rejected 1,142 documents on it. Those are not bad
-- data. Doc 02 §7 already describes exactly this situation: the same legal work
-- is published on more than one portal, and byte-identical copies were already
-- deduplicated at the blob rung (118 of them). What remains is the same Act
-- published twice with DIFFERENT bytes -- a federal Act reproduced in a
-- provincial code, a consolidated copy beside a Gazette copy -- which is one
-- instrument reached by two documents.
--
-- Resolving that is `instrument` identity resolution, and doc 02 §7 makes it a
-- deliberate step with its own change classification, not something to infer
-- while parsing. Until it exists, enforcing the constraint would mean silently
-- dropping a quarter of the corpus to protect an invariant we cannot yet
-- satisfy -- losing more than it protects.
--
-- So the uniqueness becomes an index, and the duplication becomes visible and
-- queryable instead of fatal.

BEGIN;

DROP INDEX IF EXISTS uq_instrument_cited;

-- Same columns, no longer unique: the lookup stays fast, the duplicates stay.
CREATE INDEX instrument_citation ON instrument (jurisdiction, kind, number, year)
    WHERE number IS NOT NULL;

-- Where identity resolution has run, this points a duplicate at the instrument
-- it duplicates. Null means "not yet assessed", which is different from "not a
-- duplicate" and is why the column is nullable rather than defaulted.
ALTER TABLE instrument
    ADD COLUMN duplicate_of uuid REFERENCES instrument(id) ON DELETE SET NULL;

CREATE INDEX instrument_duplicate_of ON instrument (duplicate_of)
    WHERE duplicate_of IS NOT NULL;

COMMENT ON COLUMN instrument.duplicate_of IS
    'Set by instrument identity resolution (doc 02 §7). NULL means not yet assessed.';

-- The work list for that resolution: citations reached by more than one document.
CREATE VIEW v_instrument_duplicates AS
SELECT jurisdiction, kind, number, year,
       count(*)                                   AS documents,
       array_agg(id ORDER BY created_at)          AS instrument_ids,
       array_agg(document_id ORDER BY created_at) AS document_ids,
       min(short_title)                           AS a_title
  FROM instrument
 WHERE number IS NOT NULL
 GROUP BY jurisdiction, kind, number, year
HAVING count(*) > 1;

COMMENT ON VIEW v_instrument_duplicates IS
    'Citations claimed by more than one document. The queue for identity resolution.';

COMMIT;
