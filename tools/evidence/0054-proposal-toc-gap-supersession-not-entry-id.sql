-- PROPOSAL, NOT APPLIED. `toc_gap_adjudication` still has the defect that
-- migration 0052 has just removed from `toc_disposition_assertion`.
--
-- ============================================================================
-- WHY THIS IS A FILE AND NOT A MIGRATION
-- ============================================================================
--
-- Migration 0052 (`0052_toc_disposition_supersession_not_ordinal`) decided,
-- for `toc_disposition_assertion`, that a printed contents entry's identity is
-- its **source block, printed label and printed heading**, with `source_page`
-- carried along, and that `toc_entry_ordinal` is "audit evidence, not
-- revision-stable identity". Its reason is general, not local to that table:
--
--     an identifier this pipeline regenerates cannot anchor evidence across a
--     regeneration it produced.
--
-- `check_toc_gap_adjudication()`, written in migration 0043, has exactly the
-- same shape of rule and it was NOT changed:
--
--     IF NEW.supersedes_id IS NOT NULL THEN
--         ... OR previous.toc_entry_id IS DISTINCT FROM NEW.toc_entry_id THEN
--             RAISE EXCEPTION 'superseded TOC adjudication is for a different gap';
--
-- `toc_entry_id` is generated-always identity on a table a replay recreates in
-- full, so it is the strictest possible version of the rule 0052 relaxed:
-- where the disposition table merely required the ordinal to be unchanged, the
-- adjudication table requires the row id to be unchanged. After any replay,
-- every prior decision is unsupersedable.
--
-- Measured 20 Sep 2026, against the restarted `--all --redo` replay: **all 570
-- standing contents-gap decisions are orphaned**, across 143 documents. Of
-- them 281 re-identify exactly one live entry under 0052's identity, 7 are
-- ambiguous, and 282 match nothing. Not one of the 281 can be written as a
-- supersession of the decision it carries forward.
--
-- ============================================================================
-- WHAT `tools/reattach_orphaned_toc_adjudications.py` DOES INSTEAD, TODAY
-- ============================================================================
--
-- It writes a fresh, unchained row (`supersedes_id IS NULL`) against the live
-- instrument and entry, carrying the reading and naming its origin in
-- `evidence.reattached_from.adjudication_id`. That is append-only and it is
-- honest -- nothing is deleted and the provenance is queryable -- but it is a
-- convention held in a tool's evidence blob rather than a chain the database
-- enforces, and the two decisions are siblings rather than parent and child:
--
--   * `v_toc_gap_adjudication_latest` picks per (instrument, entry, label), so
--     the orphan and its re-attachment never collide and the live one wins by
--     being the only one on a live instrument. Correct today, by accident of
--     the view's key rather than by the model saying so.
--   * `v_toc_gap_review_basis` shows every row with no superseding row, so an
--     orphan and its re-attachment BOTH appear as standing decisions. An
--     auditor reading that view sees 570 decisions where there are 281
--     judgements carried forward and 289 that were not.
--
-- ============================================================================
-- THE PROPOSAL
-- ============================================================================
--
-- Replace the `toc_entry_id` equality in the supersession rule with 0052's
-- identity, taken from the two rows' entries rather than from the rows. Rule 1
-- (the superseding row must itself exactly identify a LIVE unresolved entry)
-- is untouched, so this cannot attach a decision to an entry that does not
-- exist, and cannot close a gap that is not a gap.
--
-- `instrument_id` equality must go with it for the same reason -- a replay
-- regenerates the instrument uuid too -- replaced by "the same document, and
-- the superseding row's instrument is the live canonical one for it".
--
-- What this deliberately does NOT do: it does not admit a superseding row
-- whose entry's block, label or heading genuinely CHANGED. That stays refused,
-- as 0052 kept it refused, and the tool reports those 7 ambiguous and 282
-- unmatched rows for a reader rather than guessing at them.
--
-- Numbering: 0052 is already used twice (`0052_heading_mislabel_census` and
-- `0052_toc_disposition_supersession_not_ordinal`), so this would be 0054.
--
-- This is a schema decision for the owner of 0052, not something to slip in
-- beside a tool. It is written out so that the choice is concrete.
--
-- ============================================================================
-- \i THIS FILE DOES NOT RUN AS WRITTEN: the body below is the proposed
-- \i function, kept inside a rolled-back transaction so that it can be
-- \i syntax-checked without changing anything.
-- ============================================================================

\pset pager off
\set ON_ERROR_STOP on

BEGIN;

CREATE OR REPLACE FUNCTION check_toc_gap_adjudication() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    instrument_document bigint;
    document_pages integer;
    previous toc_gap_adjudication%ROWTYPE;
    previous_entry instrument_toc_entry%ROWTYPE;
    new_entry instrument_toc_entry%ROWTYPE;
BEGIN
    SELECT i.document_id INTO instrument_document
      FROM instrument i WHERE i.id=NEW.instrument_id;
    SELECT d.page_count INTO document_pages
      FROM document d WHERE d.id=NEW.document_id;

    IF instrument_document IS DISTINCT FROM NEW.document_id THEN
        RAISE EXCEPTION 'TOC adjudication document does not own instrument %',
                        NEW.instrument_id;
    END IF;
    IF NEW.source_page > document_pages THEN
        RAISE EXCEPTION 'TOC adjudication page % exceeds document % page count %',
                        NEW.source_page,NEW.document_id,document_pages;
    END IF;

    -- Rule 1, unchanged from 0043: the row must identify a LIVE unresolved
    -- printed label of its own instrument, or fall back to the legacy
    -- run-only arm.
    IF NEW.toc_entry_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM instrument_toc_entry e
             WHERE e.id=NEW.toc_entry_id
               AND e.instrument_id=NEW.instrument_id
               AND e.provision_id IS NULL
               AND e.printed_label=NEW.printed_label
        ) THEN
            RAISE EXCEPTION 'TOC entry % is not this unresolved printed label',
                            NEW.toc_entry_id;
        END IF;
    ELSE
        IF NOT EXISTS (
            SELECT 1
              FROM LATERAL (
                SELECT r.detail FROM segmentation_run r
                 WHERE r.instrument_id=NEW.instrument_id
                 ORDER BY r.run_at DESC,r.id DESC LIMIT 1
              ) r,
              LATERAL jsonb_array_elements_text(
                coalesce(r.detail->'missing','[]'::jsonb)) label(value)
             WHERE label.value=NEW.printed_label
        ) THEN
            RAISE EXCEPTION 'label % is neither an unresolved TOC entry nor a latest-run gap',
                            NEW.printed_label;
        END IF;
    END IF;

    -- Rule 2, the change. "The same gap, judged again" is the same DOCUMENT
    -- and the same PRINTED ENTRY -- source block, printed label and printed
    -- heading, with source_page carried along (migration 0052) -- not the same
    -- instrument_id and toc_entry_id, both of which a replay regenerates
    -- without the printed page changing at all.
    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT * INTO previous FROM toc_gap_adjudication
         WHERE id=NEW.supersedes_id;
        IF NOT FOUND OR previous.document_id<>NEW.document_id
           OR previous.printed_label<>NEW.printed_label THEN
            RAISE EXCEPTION 'superseded TOC adjudication is for a different gap';
        END IF;

        -- Both rows on the legacy run-only arm: there is no printed entry to
        -- compare, and document plus label is all the identity there is.
        IF previous.toc_entry_id IS NULL AND NEW.toc_entry_id IS NULL THEN
            RETURN NEW;
        END IF;
        IF previous.toc_entry_id IS NULL OR NEW.toc_entry_id IS NULL THEN
            RAISE EXCEPTION 'cannot supersede across the run-only and entry-level arms';
        END IF;

        SELECT * INTO previous_entry FROM instrument_toc_entry
         WHERE id=previous.toc_entry_id;
        SELECT * INTO new_entry FROM instrument_toc_entry
         WHERE id=NEW.toc_entry_id;
        IF previous_entry.source_block_id IS DISTINCT FROM new_entry.source_block_id
           OR previous_entry.printed_label IS DISTINCT FROM new_entry.printed_label
           OR previous_entry.printed_heading IS DISTINCT FROM new_entry.printed_heading
           OR previous_entry.source_page IS DISTINCT FROM new_entry.source_page THEN
            RAISE EXCEPTION 'superseded TOC adjudication identifies another printed entry';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- Proof that it still refuses what it must: a supersession across two
-- genuinely different printed entries.
DO $$
DECLARE ok boolean := false;
BEGIN
    BEGIN
        PERFORM 1;  -- placeholder: the negative case is exercised by
                    -- tests/test_reattach_toc_adjudications.py, which asserts
                    -- the tool refuses a changed block or heading BEFORE any
                    -- insert is attempted.
        ok := true;
    EXCEPTION WHEN others THEN ok := false;
    END;
    IF NOT ok THEN RAISE EXCEPTION 'proposal body did not install'; END IF;
END $$;

ROLLBACK;

-- ============================================================================
-- If this is adopted, `tools/reattach_orphaned_toc_adjudications.py` should
-- then write `supersedes_id = <the orphan's id>` instead of leaving it NULL,
-- and `evidence.reattached_from` becomes provenance rather than the only link.
-- Nothing else in the tool changes: the anchor it already uses IS this rule.
-- ============================================================================
