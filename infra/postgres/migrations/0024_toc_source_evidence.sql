-- Preserve the source anchor for every parsed table-of-contents entry.
--
-- A label/heading dictionary is useful during parsing but is not evidence: it
-- collapses repeated labels and cannot take a reviewer back to the printed PDF.
-- The immutable text_block supplies text, page geometry and reading order; the
-- denormalised source_page makes page-level audit/worklist queries inexpensive.

BEGIN;

ALTER TABLE instrument_toc_entry
    ADD COLUMN source_block_id bigint REFERENCES text_block(id) ON DELETE RESTRICT,
    ADD COLUMN source_page integer CHECK (source_page IS NULL OR source_page > 0);

CREATE INDEX toc_entry_source_block ON instrument_toc_entry (source_block_id)
    WHERE source_block_id IS NOT NULL;
CREATE INDEX toc_entry_source_page ON instrument_toc_entry
    (instrument_id, source_page, ordinal);

COMMENT ON COLUMN instrument_toc_entry.source_block_id IS
    'Immutable extracted block containing this parsed printed entry; join to '
    'text_block for verbatim text, bbox, script and reading order.';
COMMENT ON COLUMN instrument_toc_entry.source_page IS
    'One-based physical PDF page containing this entry, not a printed page '
    'number appearing in the contents list.';

DROP VIEW v_toc;
CREATE VIEW v_toc AS
SELECT e.instrument_id,
       i.short_title,
       i.jurisdiction,
       e.ordinal,
       e.printed_label,
       e.printed_heading,
       e.printed_page,
       e.source_page,
       e.source_block_id,
       t.reading_order AS source_reading_order,
       t.x0 AS source_x0,
       t.y0 AS source_y0,
       t.x1 AS source_x1,
       t.y1 AS source_y1,
       e.entry_kind,
       e.match_method,
       e.provision_id,
       p.path,
       p.first_page,
       (e.provision_id IS NOT NULL) AS resolved
  FROM instrument_toc_entry e
  JOIN instrument i ON i.id = e.instrument_id
  LEFT JOIN text_block t ON t.id = e.source_block_id
  LEFT JOIN provision p ON p.id = e.provision_id;

COMMENT ON VIEW v_toc IS
    'Printed contents in order, linked both backward to exact PDF block/page '
    'evidence and forward to the resolved provision.';

COMMIT;
