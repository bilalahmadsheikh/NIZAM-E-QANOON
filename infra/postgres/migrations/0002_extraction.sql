-- 0002  blob, document, page, text_block -- Document 02 §4 and §7
--
-- The identity ladder, one rung at a time. Doc 02 §7 is explicit that these are
-- different things and conflating them is the mistake that cannot be undone
-- later:
--
--   source_observation  what a portal exposed at a time      (0001)
--   blob                bytes, identified by SHA-256         (here)
--   document            a blob read as text, in a language   (here)
--   instrument          the legal work: jurisdiction+type+number+year   (later)
--   provision           a citable unit within an instrument             (later)
--   provision_version   that provision as at a date                     (later)
--
-- Two facts from the corpus show why this matters. The Pakistan Penal Code sits
-- at two different paths in the federal archive with one identical SHA-256 --
-- one blob, two observations. Punjab publishes its own copy of the same Code
-- with a different SHA-256 -- two blobs, two documents, and eventually one
-- instrument. A schema that keyed law on the file would get both wrong.
--
-- Extraction stores evidence, not just text. Doc 02 §4.1: "The canonical output
-- is not a plain text file. Each block carries {page, bbox, reading_order,
-- script, extractor, confidence}; every provision stores page anchors back to
-- the immutable source." Segmentation (§5) reads these blocks; it never re-opens
-- the PDF.

BEGIN;

CREATE TYPE extraction_lane AS ENUM ('E1','E2','E3','E4','E5');
COMMENT ON TYPE extraction_lane IS
  'Doc 02 §4: E1 official HTML, E2 born-digital PDF, E3 mixed, E4 scanned/OCR, E5 image or table schedule.';

-- ---------------------------------------------------------------- blob
-- One row per distinct byte sequence. Deduplicates across sources and paths
-- without losing the separate observations that found it (§7).
CREATE TABLE blob (
    sha256       char(64) PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    source_id    text        NOT NULL,
    object_key   text        NOT NULL,
    byte_length  bigint      NOT NULL CHECK (byte_length > 0),
    media_type   text        NOT NULL DEFAULT 'application/pdf',
    first_seen   timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE blob IS 'Byte identity. Doc 02 §7: "Byte identity is the SHA-256 hash."';

-- ---------------------------------------------------------------- document
-- An expression: a blob read as text in one language and publication role.
-- Doc 02 §4.1 forbids translation during ingestion -- English, Urdu and Sindhi
-- publications are separate official expressions linked by instrument identity,
-- so language belongs here and never becomes a column on the law itself.
CREATE TABLE document (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sha256           char(64) NOT NULL REFERENCES blob(sha256) ON DELETE RESTRICT,
    language         text     NOT NULL DEFAULT 'en' CHECK (language IN ('en','ur','sd','mixed')),
    publication_role text     NOT NULL DEFAULT 'code_portal'
                              CHECK (publication_role IN ('code_portal','gazette','other')),

    page_count       integer  NOT NULL CHECK (page_count > 0),
    char_count       bigint   NOT NULL DEFAULT 0,
    -- Doc 02 §4 acceptance for lane E2: ">=95% printable characters".
    printable_ratio  numeric(6,4) CHECK (printable_ratio BETWEEN 0 AND 1),
    empty_pages      integer  NOT NULL DEFAULT 0,

    lane             extraction_lane NOT NULL,
    extractor        text     NOT NULL,          -- library and version, e.g. pymupdf-1.26.7
    extractor_config jsonb    NOT NULL DEFAULT '{}'::jsonb,
    pdf_metadata     jsonb    NOT NULL DEFAULT '{}'::jsonb,
    extracted_at     timestamptz NOT NULL DEFAULT now(),

    -- Re-extracting the same bytes with the same extractor must be an update,
    -- not a second document.
    UNIQUE (sha256, language, publication_role, extractor)
);
COMMENT ON TABLE document IS 'An expression: doc 02 §7 "blob + language + publication role".';

-- ---------------------------------------------------------------- page
CREATE TABLE page (
    document_id  bigint  NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    page_no      integer NOT NULL CHECK (page_no >= 1),
    width        numeric(9,3),
    height       numeric(9,3),
    char_count   integer NOT NULL DEFAULT 0,
    -- Routing is per page, not per document: §4 "one bad page does not force OCR
    -- across an entire Act".
    lane         extraction_lane NOT NULL,
    PRIMARY KEY (document_id, page_no)
);

-- ---------------------------------------------------------------- text_block
-- The evidence layer. Never rewritten in place: hyphen repair, ligature
-- expansion and whitespace normalisation produce derived text elsewhere, "while
-- the exact extracted form remains available for audit" (§4.1).
CREATE TABLE text_block (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id   bigint  NOT NULL,
    page_no       integer NOT NULL,
    block_no      integer NOT NULL,          -- index within the page, as extracted
    reading_order integer NOT NULL,          -- monotonic across the whole document
    x0 numeric(9,3) NOT NULL, y0 numeric(9,3) NOT NULL,
    x1 numeric(9,3) NOT NULL, y1 numeric(9,3) NOT NULL,
    text          text    NOT NULL,
    script        text,                      -- 'latin' | 'arabic' | 'mixed' | NULL
    confidence    numeric(4,3) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    FOREIGN KEY (document_id, page_no) REFERENCES page(document_id, page_no) ON DELETE CASCADE,
    UNIQUE (document_id, reading_order)
);

CREATE INDEX text_block_doc_page ON text_block (document_id, page_no, block_no);
CREATE INDEX document_sha256     ON document (sha256);
CREATE INDEX blob_source         ON blob (source_id);

COMMIT;
