-- A superseding disposition assertion could not survive an ordinal shift.
--
-- `toc_entry_ordinal` was already declared, in migration 0046's own comment,
-- to be "audit evidence, not revision-stable identity" -- the printed
-- contents entry is identified by its immutable source block, printed label
-- and printed heading, which an L2 segmentation replay preserves even when it
-- changes how many entries the same contents list yields (withdrawing a
-- phantom footnote row, or splitting one merged block's several printed lines
-- into their own entries, renumbers every ordinal after the change).
-- `check_toc_disposition_assertion()` was never updated to match that
-- declaration: its supersession rule (rule 2) still required
-- `previous.toc_entry_ordinal = NEW.toc_entry_ordinal`, so a corrective row
-- for an entry whose ordinal moved was refused -- correctly by rule 1 in
-- spirit (a replay recreates every `instrument_toc_entry` row, so the id an
-- assertion was written against no longer exists; the corrective row must,
-- and still must after this migration, re-identify a LIVE entry by its
-- CURRENT id/ordinal/label/heading/block/page) but wrongly by rule 2, which
-- compared the superseded row's ordinal to the new row's ordinal as though
-- ordinal were part of the printed entry's identity rather than a fact about
-- when it was reviewed.
--
-- Measured on document 3581 (assertion 71): printed_label "16", printed_
-- heading "1[Repealed]." and source_block_id 417057 are identical between
-- the stale assertion and the current live entry; only the ordinal moved,
-- from 15 to 16, because a replay withdrew a phantom entry earlier in the
-- same contents list. source_block_id is L1 extraction evidence -- immutable,
-- and untouched by an L2 segmentation replay -- which is the same law
-- `tools/reattach_orphaned_adjudications.py` already applies to
-- `segmentation_structural_adjudication`, keying re-attachment on
-- (document_id, source_block_id) rather than the regenerated candidate_id:
-- an identifier this pipeline regenerates cannot anchor evidence across a
-- regeneration it produced.
--
-- WHAT CHANGES. Only the supersession check (rule 2). A superseding row must
-- still, independently and exactly, identify a LIVE `instrument_toc_entry` --
-- rule 1 is untouched, so a repeal or omission can never attach to a node
-- that does not currently exist with exactly that label, heading, block and
-- page. What changes is what makes a superseding row "the same entry, judged
-- again": no longer `toc_entry_ordinal` equality between the two rows, but
-- source_block_id, printed_label and printed_heading equality (source_page is
-- required too, since it is what the reviewer looked at, though it is
-- redundant with block equality in every case measured so far). An entry
-- whose heading or block genuinely changed -- not merely moved -- still fails
-- this check and must be recorded as a fresh, unchained assertion for a human
-- to review; that refusal is deliberate and unchanged. This migration widens
-- what counts as "the same judgement, the entry moved", not what counts as
-- "the same entry".
--
-- This does not touch rule 1, the live-entry match, or the disposition CHECK
-- constraint restricting values to ('omitted','repealed'); a superseding row
-- for a repeal assertion must still name disposition='repealed' against a
-- live entry, or the insert is refused before rule 2 is ever reached. Nothing
-- here allows a disposition to be dropped by inserting a superseding row of a
-- different kind -- there is no path from this trigger to deleting or
-- silently reinterpreting a prior repeal.
--
-- Governing contract: docs/03b-legal-data-model, toc_disposition_assertion;
-- docs/03-data-and-storage on regenerated identifiers not anchoring evidence.

BEGIN;

CREATE OR REPLACE FUNCTION check_toc_disposition_assertion() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    current_instrument uuid;
    current_document bigint;
    previous toc_disposition_assertion%ROWTYPE;
BEGIN
    SELECT i.id,i.document_id INTO current_instrument,current_document
      FROM instrument i
     WHERE i.source_observation_id=NEW.source_observation_id
       AND i.expression_ordinal=NEW.expression_ordinal
       AND i.is_active AND i.duplicate_of IS NULL;
    IF current_instrument IS NULL THEN
        RAISE EXCEPTION 'no active canonical expression % for observation %',
                        NEW.expression_ordinal,NEW.source_observation_id;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM instrument_toc_entry e
         WHERE e.id=NEW.reviewed_toc_entry_id
           AND e.instrument_id=current_instrument
           AND e.ordinal=NEW.toc_entry_ordinal
           AND e.printed_label=NEW.printed_label
           AND e.printed_heading=NEW.printed_heading
           AND e.source_block_id=NEW.source_block_id
           AND e.source_page=NEW.source_page
    ) THEN
        RAISE EXCEPTION 'assertion does not exactly identify the current printed TOC entry';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM text_block b
         WHERE b.id=NEW.source_block_id
           AND b.document_id=current_document
           AND b.page_no=NEW.source_page
    ) THEN
        RAISE EXCEPTION 'assertion source block/page is outside the expression document';
    END IF;
    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT * INTO previous FROM toc_disposition_assertion
         WHERE id=NEW.supersedes_id;
        -- Ordinal is deliberately NOT compared here (migration 0052): it is
        -- audit evidence of when the row was reviewed, not identity of the
        -- printed entry, and a replay that changes how many entries a
        -- contents list yields moves it beneath every already-reviewed row
        -- after the change. The printed entry itself is identified by its
        -- source block, label and heading -- source_page is carried along
        -- too, though block already fixes it in every case measured -- and
        -- those must still agree exactly, or this is not a correction of the
        -- same judgement but a different entry, and must be refused.
        IF NOT FOUND
           OR previous.source_observation_id<>NEW.source_observation_id
           OR previous.expression_ordinal<>NEW.expression_ordinal
           OR previous.source_block_id<>NEW.source_block_id
           OR previous.printed_label<>NEW.printed_label
           OR previous.printed_heading<>NEW.printed_heading
           OR previous.source_page<>NEW.source_page THEN
            RAISE EXCEPTION 'superseded assertion identifies another TOC entry';
        END IF;
    END IF;
    RETURN NEW;
END $$;

COMMENT ON FUNCTION check_toc_disposition_assertion() IS
  'Guards toc_disposition_assertion: every row must exactly identify a live '
  'instrument_toc_entry (id, ordinal, label, heading, block, page); a '
  'superseding row must identify the SAME printed entry by source_block_id, '
  'printed_label and printed_heading (source_page carried along) -- not by '
  'toc_entry_ordinal, which a replay may move without the entry changing '
  '(migration 0052).';

COMMIT;
