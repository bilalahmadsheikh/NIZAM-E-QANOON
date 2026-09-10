-- 0010  teach ck_role_provision about 'unstructured', and name the queue
--
-- An unstructured block belongs to no provision -- there are no provisions --
-- so it joins the arm of the CHECK that requires provision_id IS NULL.

BEGIN;

ALTER TABLE provision_block DROP CONSTRAINT ck_role_provision;

ALTER TABLE provision_block ADD CONSTRAINT ck_role_provision CHECK (
    CASE
        -- text that became part of the enacted tree
        WHEN role IN ('body', 'heading', 'schedule_row', 'preamble')
            THEN provision_id IS NOT NULL
        -- text that is reachable through the document rather than a provision
        WHEN role IN ('contents', 'preface', 'running_header',
                      'unstructured', 'unassigned')
            THEN provision_id IS NULL
        -- a footnote may be bound to the provision it annotates, or not yet
        ELSE true
    END
);

CREATE INDEX provision_block_unstructured ON provision_block (document_id)
    WHERE role = 'unstructured';

-- ------------------------------------------------------------------ the queue
-- Documents whose text is in the database but not in the provision tree, with
-- the reason the segmenter gave. This is the review list -- and it is a view,
-- not a spreadsheet, so it can never go stale.
CREATE VIEW v_unstructured_document AS
SELECT d.id                                   AS document_id,
       d.lane,
       d.page_count,
       d.char_count,
       count(pb.block_id)                     AS blocks,
       sum(pb.chars)                          AS chars,
       r.reason,
       r.run_at,
       (SELECT o.canonical_url FROM source_observation o
         WHERE o.sha256 = d.sha256 AND o.outcome = 'landed'
         ORDER BY o.fetched_at DESC LIMIT 1)   AS source_url
  FROM document d
  JOIN provision_block pb ON pb.document_id = d.id AND pb.role = 'unstructured'
  LEFT JOIN LATERAL (
        SELECT reason, run_at FROM segmentation_run s
         WHERE s.document_id = d.id ORDER BY s.run_at DESC LIMIT 1) r ON true
 GROUP BY d.id, d.lane, d.page_count, d.char_count, r.reason, r.run_at;

COMMENT ON VIEW v_unstructured_document IS
    'Documents with text but no provision structure. Their characters are '
    'accounted for (C4/C5) but are not answerable through the provision tree; '
    'each row is a document that needs a table model, a better lane, or nothing.';

COMMIT;
