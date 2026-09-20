-- Per-entry source anchors for printed contents rows.
--
-- Migration 0024 gave every `instrument_toc_entry` a `source_block_id` and a
-- physical `source_page`, on the reasoning that "the immutable text_block
-- supplies text, page geometry and reading order". That holds only while one
-- block carries one printed row. PyMuPDF frequently merges several contents
-- lines into a single block, and then the anchor stops identifying anything: in
-- the Sind Landing and Wharfage Fees Act, 1882 (document 1918) block 134870
-- holds the printed rows for labels 5, 6, 7, 8, 9, 10, 11 and 12 at once, and
-- all eight rows of the ledger pointed at it with nothing to tell them apart.
--
-- A reviewer following such a row lands on 527 characters of text and has to
-- guess which line the row came from; two rows on one block cannot be
-- distinguished by their evidence at all; and the parser's own ordering of them
-- was whichever of its two readers -- the dotted-label reader or the
-- two-column-table reader -- happened to run first, not the order the page
-- prints. `ordinal` is meant to be the printed position (0011), and the
-- order-bounded match recovery in the segmenter reads adjacency out of it.
--
-- `source_char_offset` is the character index, inside that block's verbatim
-- text, of the first character of the row's printed label. It is a coordinate
-- into immutable evidence, exactly like `source_block_id`: nothing is copied out
-- of `text_block` and nothing is editable here. Two printed rows cannot begin at
-- the same character of the same block, so the anchor is unique per instrument
-- and the partial unique index says so. Measured over all 4,596 documents before
-- this landed: zero collisions.
--
-- NULL means "written before the parser recorded offsets". It is not backfilled,
-- because the offset is a parse output and inventing one would be evidence the
-- parser never produced; those rows acquire it when their instrument is
-- re-segmented, which appends a revision rather than editing this one (SCHEMA.md,
-- "Extraction and segmentation are revision chains").

BEGIN;

-- Idempotent by construction. This migration was first run while a 37-hour
-- read-only query held a lock on the table, so three queued backends attempted
-- the same ALTER; one completed the file while the others failed on "column
-- already exists", and the failure meant `schema_migration` never recorded the
-- version. The schema was then ahead of the ledger, which is the one state
-- doc 09a s7 does not permit -- "if the answer to 'how do I recreate this on
-- the server?' is anything other than 'run the migrations', the local
-- environment has stopped being production". Written this way the file can be
-- re-run to completion and record itself, whatever partial state it meets.
ALTER TABLE instrument_toc_entry
    ADD COLUMN IF NOT EXISTS source_char_offset integer;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'instrument_toc_entry'::regclass
           AND conname  = 'instrument_toc_entry_source_char_offset_check'
    ) THEN
        ALTER TABLE instrument_toc_entry
            ADD CONSTRAINT instrument_toc_entry_source_char_offset_check
            CHECK (source_char_offset IS NULL OR source_char_offset >= 0);
    END IF;
END $$;

-- The uniqueness of the anchor is the whole point of adding it, so it is a
-- constraint and not a convention. Scoped to the instrument: the same block can
-- legitimately anchor rows of two co-published expressions of one PDF (0040).
CREATE UNIQUE INDEX IF NOT EXISTS toc_entry_source_anchor
    ON instrument_toc_entry (instrument_id, source_block_id, source_char_offset)
    WHERE source_block_id IS NOT NULL AND source_char_offset IS NOT NULL;

COMMENT ON COLUMN instrument_toc_entry.source_char_offset IS
    'Character index, within source_block_id''s verbatim text, of the first '
    'character of this row''s printed label. Disambiguates several printed '
    'contents rows merged into one extracted block; NULL for rows parsed '
    'before offsets were recorded.';

DROP VIEW IF EXISTS v_toc;
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
       e.source_char_offset,
       -- The printed row as the PDF sets it, rendered from the immutable block
       -- rather than stored again. This is what a reviewer needs to see and the
       -- reason the offset exists; it is deliberately not truncated to the next
       -- row, because where the next row begins is the parser's claim and this
       -- column is the source.
       CASE WHEN e.source_char_offset IS NOT NULL
            THEN substring(t.text from e.source_char_offset + 1 for 200)
       END AS source_excerpt,
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
    'Printed contents in order, linked both backward to exact PDF '
    'block/offset/page evidence -- with the printed row itself rendered from the '
    'block -- and forward to the resolved provision.';

COMMIT;
