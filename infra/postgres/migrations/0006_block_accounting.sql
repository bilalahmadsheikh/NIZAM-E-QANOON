-- 0006  provision_block -- every text block has a home
--
-- The rule this enforces, from docs/CORPUS-CRITERIA.md:
--
--     If it is in the PDF, it is in the database, and it is reachable.
--
-- Before this table, 18.6% of extracted characters were in no provision. Some of
-- that was correct -- a contents list and a running header are not enacted text --
-- but the corpus could not tell the difference between "classified as not body"
-- and "silently dropped". Both looked identical: absent.
--
-- Akoma Ntoso (OASIS, the international standard for legal documents) solves this
-- by giving every part of an instrument a place: cover, preface, preamble, body,
-- conclusions, attachments. Nothing is discarded because nothing needs to be --
-- there is an element for it. This table is that idea applied to a corpus that
-- arrives as PDF rather than as XML: every block is assigned a role, and body
-- blocks additionally carry the provision they became.
--
-- The role `unassigned` is deliberately available and must always be zero. It is
-- the defect counter: text the parser could not place stays visible and countable
-- instead of vanishing.

BEGIN;

CREATE TYPE block_role AS ENUM (
    'body',            -- enacted text; carries a provision_id
    'contents',        -- the printed table of contents
    'preface',         -- title page, gazette line, enacting formula
    'preamble',        -- WHEREAS...
    'heading',         -- part / chapter / schedule heading with no text of its own
    'footnote',        -- amendment footnotes in the bottom margin
    'running_header',  -- "Page 90 of 179"
    'schedule_row',    -- a row of a schedule table
    'unassigned'       -- the parser could not place it -- MUST be 0
);

CREATE TABLE provision_block (
    block_id     bigint PRIMARY KEY REFERENCES text_block(id) ON DELETE CASCADE,
    document_id  bigint NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    -- NULL for every role except 'body': a contents entry is reachable through
    -- the instrument, not through a provision.
    provision_id uuid REFERENCES provision(id) ON DELETE SET NULL,
    role         block_role NOT NULL,
    chars        integer NOT NULL DEFAULT 0,

    CONSTRAINT ck_body_has_provision
        CHECK ((role = 'body') = (provision_id IS NOT NULL))
);

CREATE INDEX provision_block_document  ON provision_block (document_id, role);
CREATE INDEX provision_block_provision ON provision_block (provision_id)
    WHERE provision_id IS NOT NULL;
CREATE INDEX provision_block_unplaced  ON provision_block (document_id)
    WHERE role = 'unassigned';

COMMENT ON TABLE provision_block IS
    'Every text block, accounted for. C4/C5 in docs/CORPUS-CRITERIA.md: role '
    '''unassigned'' must be 0, or text has been silently lost.';

-- ------------------------------------------------------------------ views
-- The completeness answer, per document and for the corpus.
CREATE VIEW v_block_accounting AS
SELECT d.id                                   AS document_id,
       d.char_count                           AS chars_extracted,
       count(t.id)                            AS blocks,
       count(pb.block_id)                     AS blocks_accounted,
       count(t.id) - count(pb.block_id)       AS blocks_unaccounted,
       coalesce(sum(pb.chars) FILTER (WHERE pb.role = 'body'), 0)        AS chars_body,
       coalesce(sum(pb.chars) FILTER (WHERE pb.role <> 'body'), 0)       AS chars_other,
       coalesce(sum(pb.chars) FILTER (WHERE pb.role = 'unassigned'), 0)  AS chars_unassigned
  FROM document d
  JOIN text_block t ON t.document_id = d.id
  LEFT JOIN provision_block pb ON pb.block_id = t.id
 GROUP BY d.id, d.char_count;

COMMENT ON VIEW v_block_accounting IS
    'Per document: is every block placed, and where did its characters go?';

-- What a provision is made of, straight back to the printed page.
CREATE VIEW v_provision_source AS
SELECT pb.provision_id,
       count(*)                          AS blocks,
       min(t.page_no)                     AS first_page,
       max(t.page_no)                     AS last_page,
       sum(pb.chars)                      AS chars,
       array_agg(t.id ORDER BY t.reading_order) AS block_ids
  FROM provision_block pb
  JOIN text_block t ON t.id = pb.block_id
 WHERE pb.provision_id IS NOT NULL
 GROUP BY pb.provision_id;

COMMENT ON VIEW v_provision_source IS
    'The blocks a provision was built from -- its evidence trail to the page.';

COMMIT;
