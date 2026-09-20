-- Re-anchor TOC disposition assertions whose entry ordinal moved in the replay.
--
-- WHY. A disposition assertion says "the contents entry at ordinal N, printed
-- label L, is omitted/repealed", and carries the rendered page and its SHA-256
-- as evidence. The 19 Sep corpus replay changed how many entries some contents
-- lists yield -- phantom footnote rows were withdrawn, merged blocks were split
-- per entry -- so ordinals shifted beneath assertions that were correct when
-- written. Document 3581 is the shape: its assertion says entry 15 label "16"
-- is repealed; label 16 now sits at ordinal 16, and its printed heading is
-- still exactly "1[Repealed].".
--
-- Three documents cannot be re-segmented at all until this is settled, because
-- `segment()` refuses to materialise a tree while an assertion it cannot match
-- is outstanding -- correctly, since silently dropping a repeal assertion would
-- let repealed text become citable again.
--
-- WHAT IS ASSERTED HERE. Only the anchor moves. The disposition, the printed
-- label, the printed heading, the source block, the source page, the render and
-- its SHA-256, and the amending instrument are all carried forward unchanged
-- from the row being superseded. The entry is identified by printed_label AND
-- printed_heading matching exactly -- not by ordinal, which is what moved, and
-- not by label alone, which cannot tell two entries apart.
--
-- This is the same repair as re-attaching an orphaned S7 reading by
-- (document_id, source_block_id): the evidence describes a printed page, the
-- page has not changed, and only the pointer into our own numbering broke.
--
-- Append-only: each new row supersedes its predecessor; nothing is deleted.
--
-- ============================================================================
-- BLOCKED, 20 Sep 2026. THIS FILE DOES NOT RUN, AND THE REASON IS A FINDING.
-- ============================================================================
--
-- `check_toc_disposition_assertion()` refuses it, twice over, and both refusals
-- are correct:
--
--   1. The row must identify a LIVE entry exactly -- `reviewed_toc_entry_id`,
--      ordinal, label, heading, source block and page. A replay recreates every
--      `instrument_toc_entry` row, so the id an assertion was written against no
--      longer exists. Taking the anchor fields from the current entry satisfies
--      this.
--
--   2. A superseding row must carry the SAME `toc_entry_ordinal` as the row it
--      supersedes. That is the blocker, and it is not an oversight: the model
--      treats the ordinal as part of the entry's identity, so supersession can
--      express "the same entry, judged again" and CANNOT express "the same
--      judgement, the entry moved".
--
-- So the disposition model has no append-only repair for ordinal drift. A
-- replay that changes how many entries a contents list yields -- which is
-- exactly what withdrawing phantom footnote rows and splitting merged blocks
-- per entry does -- strands every reviewed disposition below the change, and
-- nine are stranded now. Three documents (3581, 4441, 4608) cannot be
-- re-segmented at all until they are settled, because `segment()` refuses to
-- materialise a tree while an assertion it cannot match is outstanding.
-- That refusal is right: silently dropping a repeal assertion would let
-- repealed text become citable again.
--
-- The nine are listed by the query below and each is a genuine, already-reviewed
-- judgement whose evidence -- the rendered page and its sha256 -- is unchanged
-- and still correct. What they need is a decision about the model, not a patch:
-- either the assertion anchors on something a replay preserves (printed label
-- plus printed heading plus source page, as this file matches on), or the
-- supersession rule admits a moved ordinal when those three agree, or the
-- materialiser re-derives the ordinal at match time rather than storing it.
-- That is a schema question for the owner of migration 0043, not something to
-- force past a trigger that is doing its job.
--
-- One more assertion (id 179, document 4441, label 376B) is orphaned differently:
-- its observation has no active canonical expression at all, so the first check
-- rejects it before the second is reached. That one is a dedup artefact, not
-- ordinal drift.

\pset pager off
\set ON_ERROR_STOP on

BEGIN;

-- The anchor fields are taken from the CURRENT entry, because `instrument_toc_entry`
-- rows are recreated by a replay and `check_toc_disposition_assertion()` requires
-- the row to identify a live entry exactly -- its id, ordinal, label, heading,
-- source block and page. The entry is matched on printed label AND printed heading
-- AND source page: the page is what the reviewer looked at, so an entry that moved
-- to a different page is NOT the same entry and is deliberately not matched here.
CREATE TEMP TABLE reanchor AS
SELECT a.id                AS stale_id,
       i.document_id,
       a.toc_entry_ordinal AS asserted_ordinal,
       t.id                AS entry_id,
       t.ordinal           AS actual_ordinal,
       t.printed_label     AS entry_label,
       t.printed_heading   AS entry_heading,
       t.source_block_id   AS entry_block,
       t.source_page       AS entry_page,
       btrim(a.printed_label) AS label
  FROM toc_disposition_assertion a
  JOIN instrument i
    ON i.source_observation_id = a.source_observation_id
   AND i.expression_ordinal = a.expression_ordinal
   AND i.is_active AND i.duplicate_of IS NULL
  JOIN instrument_toc_entry t
    ON t.instrument_id = i.id
   AND btrim(t.printed_label) = btrim(a.printed_label)
   AND coalesce(t.printed_heading, '') = coalesce(a.printed_heading, '')
   AND t.source_page = a.source_page
 WHERE t.ordinal <> a.toc_entry_ordinal
   AND NOT EXISTS (SELECT 1 FROM toc_disposition_assertion s
                    WHERE s.supersedes_id = a.id);

\echo '-- assertions to re-anchor'
SELECT stale_id, document_id, asserted_ordinal, actual_ordinal, label
  FROM reanchor ORDER BY document_id;

-- Refuse the whole batch if any stale assertion matches more than one entry:
-- an ambiguous anchor must be read by a person, not guessed.
DO $$
DECLARE ambiguous int;
BEGIN
    SELECT count(*) INTO ambiguous
      FROM (SELECT stale_id FROM reanchor GROUP BY stale_id HAVING count(*) > 1) x;
    IF ambiguous > 0 THEN
        RAISE EXCEPTION 'ambiguous re-anchor for % assertion(s); read them', ambiguous;
    END IF;
END $$;

INSERT INTO toc_disposition_assertion (
    source_observation_id, expression_ordinal, toc_entry_ordinal,
    reviewed_toc_entry_id, printed_label, printed_heading, disposition,
    source_block_id, source_page, render_artifact, render_sha256,
    amending_instrument_id, amending_instrument_citation, evidence,
    reviewed_by, supersedes_id)
SELECT a.source_observation_id, a.expression_ordinal, r.actual_ordinal,
       r.entry_id, r.entry_label, r.entry_heading, a.disposition,
       r.entry_block, r.entry_page, a.render_artifact, a.render_sha256,
       a.amending_instrument_id, a.amending_instrument_citation,
       coalesce(a.evidence, '{}'::jsonb) || jsonb_build_object(
           'reanchored_from_ordinal', a.toc_entry_ordinal,
           'reanchored_on', '2026-09-20',
           'reanchor_basis',
           'printed_label and printed_heading matched exactly; only the entry '
           'ordinal moved, in the 19 Sep corpus replay. The rendered page and '
           'its sha256 are carried forward unchanged from the superseded row.'),
       'nizam.toc_disposition_reanchor/1',
       a.id
  FROM toc_disposition_assertion a
  JOIN reanchor r ON r.stale_id = a.id;

\echo '-- rows written'
SELECT count(*) AS reanchored
  FROM toc_disposition_assertion
 WHERE reviewed_by = 'nizam.toc_disposition_reanchor/1';

COMMIT;
