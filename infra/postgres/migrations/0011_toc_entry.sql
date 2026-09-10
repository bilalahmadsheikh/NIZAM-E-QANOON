-- 0011  instrument_toc_entry -- the printed contents list, as a relation
--
-- Every Pakistani statute prints its own table of contents, and until now the
-- corpus used it and then threw the structure away: the entries survived only as
-- text blocks with role 'contents' (166,456 blocks, 13.5M characters), and the
-- reconciliation against the body survived only as three integers on
-- segmentation_run. You could learn that 7,801 promised sections were not found.
-- You could not learn WHICH.
--
-- This table makes the contents list a first-class object, and it earns its keep
-- four times over:
--
--   1. NAVIGATION. The hierarchy a lawyer expects -- Act, Chapter, section --
--      taken from the statute's own printed list rather than one we inferred.
--   2. GROUND TRUTH. Contents agreement is already the acceptance test for
--      segmentation (doc 02 §5.1, "table-of-contents reconciliation"). Storing
--      it as a relation means the test can be joined to, not just counted.
--   3. A WORKLIST. `v_toc_gap` names every section a document promises and the
--      parser did not find -- with its heading and its instrument. A number
--      becomes a queue.
--   4. CITATION RESOLUTION. "Section 302 PPC" resolves through the printed label
--      the statute itself uses, which is what a citation actually names.
--
-- INV-4 is preserved exactly: this table does not become a citable unit. It
-- POINTS AT provisions. A ToC entry is evidence about the document, in the same
-- family as provision_block -- the printed page, kept.

BEGIN;

CREATE TABLE instrument_toc_entry (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instrument_id   uuid    NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
    ordinal         integer NOT NULL,          -- order as printed
    printed_label   text    NOT NULL,          -- "302", "XVI", "FIRST SCHEDULE"
    printed_heading text,                      -- "Punishment for qatl-i-amd"
    printed_page    integer,                   -- if the list prints one
    entry_kind      text    NOT NULL DEFAULT 'section'
                            CHECK (entry_kind IN ('section', 'schedule')),

    -- The provision this entry names, where the body walk found it. NULL is the
    -- interesting value: the document promises this section and the parser did
    -- not produce it. Deliberately no CHECK tying this to match_method -- a
    -- constraint that a SET NULL can violate breaks every later re-segmentation,
    -- which is the mistake migration 0008 had to undo.
    provision_id    uuid REFERENCES provision(id) ON DELETE SET NULL,
    match_method    text NOT NULL,             -- label | label_repaired | unmatched

    UNIQUE (instrument_id, ordinal)
);

CREATE INDEX toc_entry_instrument ON instrument_toc_entry (instrument_id, ordinal);
CREATE INDEX toc_entry_provision  ON instrument_toc_entry (provision_id)
    WHERE provision_id IS NOT NULL;
CREATE INDEX toc_entry_unmatched  ON instrument_toc_entry (instrument_id)
    WHERE provision_id IS NULL;
CREATE INDEX toc_entry_heading_trgm ON instrument_toc_entry
    USING gin (printed_heading gin_trgm_ops);

COMMENT ON TABLE instrument_toc_entry IS
    'The statute''s own printed contents list, entry by entry, linked to the '
    'provisions the body walk produced. A NULL provision_id is a gap the '
    'document itself proves exists -- see v_toc_gap.';
COMMENT ON COLUMN instrument_toc_entry.printed_label IS
    'The label exactly as the contents list prints it -- what a citation names.';
COMMENT ON COLUMN instrument_toc_entry.match_method IS
    'label: the body used the same label. label_repaired: a superscript '
    'amendment marker was fused to the number and the contents arbitrated it. '
    'unmatched: the body walk never produced this provision.';

-- ------------------------------------------------------------------ views
-- Reading a statute the way it is printed: its contents, in order, each entry
-- carrying a link if there is one.
CREATE VIEW v_toc AS
SELECT e.instrument_id,
       i.short_title,
       i.jurisdiction,
       e.ordinal,
       e.printed_label,
       e.printed_heading,
       e.entry_kind,
       e.provision_id,
       p.path,
       p.first_page,
       (e.provision_id IS NOT NULL) AS resolved
  FROM instrument_toc_entry e
  JOIN instrument i ON i.id = e.instrument_id
  LEFT JOIN provision p ON p.id = e.provision_id;

COMMENT ON VIEW v_toc IS
    'The printed contents of every instrument, in printed order, each entry '
    'resolved to its provision where one was found.';

-- The worklist. Every section a document promises and the parser did not find,
-- worst documents first.
CREATE VIEW v_toc_gap AS
SELECT e.instrument_id,
       i.document_id,
       i.short_title,
       i.jurisdiction,
       count(*)                                    AS gaps,
       (SELECT count(*) FROM instrument_toc_entry a
         WHERE a.instrument_id = e.instrument_id)  AS entries,
       round(100.0 * count(*) / (SELECT count(*) FROM instrument_toc_entry a
                                  WHERE a.instrument_id = e.instrument_id), 1)
                                                   AS pct_missing,
       array_agg(e.printed_label ORDER BY e.ordinal) FILTER (WHERE true) AS missing_labels
  FROM instrument_toc_entry e
  JOIN instrument i ON i.id = e.instrument_id
 WHERE e.provision_id IS NULL
 GROUP BY e.instrument_id, i.document_id, i.short_title, i.jurisdiction;

COMMENT ON VIEW v_toc_gap IS
    'Sections a statute promises in its own contents list and the parser did '
    'not produce. Not an estimate -- the document is the witness.';

COMMIT;
