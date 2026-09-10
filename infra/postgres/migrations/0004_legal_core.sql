-- 0004  instrument, provision, provision_version -- Document 03 §2, the legal core
--
-- This is the rung of doc 02 §7's ladder where bytes become law:
--
--     document   a blob read as text          (0002)
--        |
--        v
--   instrument   the legal work: jurisdiction + kind + number + year
--        |
--        v
--    provision   THE CITABLE UNIT (INV-4) -- a tree, not a list
--        |
--        v
-- provision_version   that provision as at a date (INV-5)
--
-- Two invariants are enforced here by the database rather than by hope:
--
--   INV-4  Provisions are the citable unit. No chunk identifier appears above
--          L2, and re-chunking must never break a stored citation. Provision
--          identity is structural (instrument + lineage), never an offset into
--          a file, so it survives re-extraction and re-chunking.
--
--   INV-5  Law is answered as at a date. The EXCLUDE constraint on
--          provision_version makes two overlapping validity intervals for one
--          provision *impossible to insert*. Doc 03 §2.3 calls it "the single
--          most important line in this schema", and it is the reason SQLite was
--          rejected as the server engine.

BEGIN;

-- ---------------------------------------------------------------- enumerations
-- Doc 03 §1.1, verbatim. These are closed sets on purpose: a value that is not
-- listed is a modelling decision, not a data entry choice.
CREATE TYPE jurisdiction AS ENUM ('fed','punjab','sindh','kp','balochistan','ict','ajk','gb');

CREATE TYPE instrument_kind AS ENUM
    ('constitution','act','ordinance','order','regulation','rules','sro','notification');

CREATE TYPE provision_kind AS ENUM
    ('part','chapter','section','article','subsection','clause',
     'proviso','explanation','illustration','schedule','preamble');

CREATE TYPE lifecycle_state AS ENUM
    ('in_force','repealed','spent','lapsed','not_yet_commenced');

CREATE TYPE version_op AS ENUM ('original','inserted','substituted','omitted','amended');

-- ---------------------------------------------------------------- instrument
CREATE TABLE instrument (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction   jurisdiction    NOT NULL,
    kind           instrument_kind NOT NULL,

    -- "XLV", "12", "745(I)". Measured on this corpus: an act number is
    -- extractable from the first two pages of 76.4% of documents. Doc 03 §2.1
    -- writes UNIQUE (jurisdiction, kind, number, year) as a table constraint,
    -- which cannot hold when a quarter of the corpus has no printed number. It
    -- is implemented below as a PARTIAL unique index instead -- enforced exactly
    -- where the data supports it -- with source_sha256 carrying identity for the
    -- rest. Inventing a number to satisfy a constraint would be worse than
    -- admitting it is unknown.
    number         text,
    year           smallint        NOT NULL CHECK (year BETWEEN 1800 AND 2100),

    short_title    text            NOT NULL,
    long_title     text,
    preamble       text,

    enacted_on     date,
    commenced_on   date,
    gazette_ref    text,

    status         lifecycle_state NOT NULL DEFAULT 'in_force',
    repealed_on    date,
    repealed_by_id uuid REFERENCES instrument(id),

    -- ADR-1e: what a deployment is allowed to publish.
    scope          text            NOT NULL DEFAULT 'core',
    published      boolean         NOT NULL DEFAULT false,

    -- Provenance, straight down the ladder. §2.1: "source_sha256 is not
    -- decoration: it is how the duplicate documents are detected, and how a
    -- re-scrape proves a source has genuinely changed."
    source_sha256  char(64)        NOT NULL REFERENCES blob(sha256) ON DELETE RESTRICT,
    document_id    bigint          NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    source_url     text,

    extraction_conf real,
    created_at     timestamptz     NOT NULL DEFAULT now(),

    CONSTRAINT ck_repeal CHECK ((status = 'repealed') = (repealed_on IS NOT NULL))
);

-- Doc 03 §2.1's constraint, enforced where a number exists.
CREATE UNIQUE INDEX uq_instrument_cited
    ON instrument (jurisdiction, kind, number, year) WHERE number IS NOT NULL;

-- One instrument per extracted document: re-running segmentation replaces, it
-- does not accumulate.
CREATE UNIQUE INDEX uq_instrument_document ON instrument (document_id);

CREATE INDEX instrument_title_trgm ON instrument USING gin (short_title gin_trgm_ops);
CREATE INDEX instrument_year       ON instrument (jurisdiction, year);

COMMENT ON TABLE instrument IS
    'The legal work. Doc 02 §7: identity is jurisdiction+type+number+year; title changes become aliases.';

-- ---------------------------------------------------------------- provision
-- The citable unit (INV-4). A tree: chapters contain sections, sections contain
-- subsections, subsections contain clauses, and provisos/explanations hang off
-- whatever they qualify.
CREATE TABLE provision (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id uuid NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
    parent_id     uuid REFERENCES provision(id) ON DELETE CASCADE,

    -- fed.act.1860_XLV.ch_XVI.s_302.cl_c
    -- ltree gives subtree and ancestor queries without recursive joins (doc 03 §1).
    path          ltree NOT NULL,

    kind          provision_kind NOT NULL,
    label         text  NOT NULL,      -- "302", "337A", "(c)", "Proviso" -- verbatim
    heading       text,                -- the marginal note / section heading
    marginal_note text,
    ordinal       integer NOT NULL,    -- sort order within the parent

    -- Page anchors back to the immutable source (doc 02 §4.1). A citation must
    -- be checkable against the printed page, whichever lane read it.
    first_page    integer,
    last_page     integer,
    first_block   bigint REFERENCES text_block(id) ON DELETE SET NULL,

    CONSTRAINT uq_provision_path UNIQUE (path),
    -- A provision cannot be its own parent, and the tree cannot cross instruments.
    CONSTRAINT ck_not_self_parent CHECK (parent_id IS NULL OR parent_id <> id)
);

CREATE INDEX provision_path_gist   ON provision USING gist (path);
CREATE INDEX provision_instrument  ON provision (instrument_id, ordinal);
CREATE INDEX provision_parent      ON provision (parent_id);
CREATE INDEX provision_label       ON provision (instrument_id, kind, label);

COMMENT ON TABLE provision IS
    'INV-4: the citable unit. Identity is structural, so re-chunking never breaks a citation.';
COMMENT ON COLUMN provision.path IS
    'ltree lineage. Subtree queries (ancestors, descendants) without recursive CTEs.';

-- ------------------------------------------------------- provision_version
-- Where temporal correctness is enforced (INV-5).
CREATE TABLE provision_version (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provision_id   uuid NOT NULL REFERENCES provision(id) ON DELETE CASCADE,

    -- '[1860-10-06,2005-01-01)' ; upper NULL means still in force.
    --
    -- The corpus currently holds CONSOLIDATED text from the code portals: the
    -- law as it stood when the portal was scraped. We do not yet have the
    -- amendment history that would let us say what section 302 said in 2004.
    -- So the lower bound is the date the source was observed -- which is true
    -- and traceable -- rather than the year of enactment, which would assert
    -- that today's amended text was in force in 1860.
    --
    -- A query for an earlier date therefore matches nothing, and INV-2 turns
    -- that into an abstention. That is the correct behaviour: we would rather
    -- say "not known as at that date" than serve today's text as if it were
    -- historic.
    validity       daterange NOT NULL,

    text_en        text,
    text_ur        text,
    text_normalised text NOT NULL,

    operation      version_op NOT NULL DEFAULT 'original',
    amended_by_id  uuid REFERENCES instrument(id),
    amendment_note text,                -- "Subs. by Act XLIII of 2016, s.3" -- verbatim

    extraction_conf real,
    verified_by    text,
    verified_at    timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),

    -- The four lines that carry INV-5. Two overlapping validity intervals for
    -- the same provision are impossible to insert; a buggy amendment resolver
    -- fails loudly at commit instead of quietly producing a corpus where
    -- section 302 has two simultaneous texts.
    CONSTRAINT no_overlap EXCLUDE USING gist (
        provision_id WITH =,
        validity     WITH &&
    )
);

CREATE INDEX provision_version_current ON provision_version (provision_id)
    WHERE upper_inf(validity);

COMMENT ON TABLE provision_version IS
    'INV-5. The EXCLUDE constraint makes overlapping validity intervals impossible.';

-- --------------------------------------------------------- segmentation_run
-- Doc 02 §8: nothing reaches retrieval because a script finished. Every
-- segmentation attempt records what it produced and how well it reconciled
-- against the document's own printed table of contents.
CREATE TABLE segmentation_run (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id     bigint NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    instrument_id   uuid REFERENCES instrument(id) ON DELETE SET NULL,
    segmenter       text   NOT NULL,

    outcome         text   NOT NULL,     -- segmented | rejected | error
    reason          text,

    provisions      integer NOT NULL DEFAULT 0,
    sections        integer NOT NULL DEFAULT 0,
    max_depth       integer NOT NULL DEFAULT 0,
    body_starts_page integer,

    -- Table-of-contents reconciliation, the acceptance test doc 02 §5 names.
    toc_found       boolean NOT NULL DEFAULT false,
    toc_entries     integer,
    toc_matched     integer,
    toc_missing     integer,             -- in the contents, absent from the body
    toc_extra       integer,             -- in the body, absent from the contents
    toc_agreement   numeric(6,4),

    detail          jsonb NOT NULL DEFAULT '{}'::jsonb,
    duration_ms     integer,
    run_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX segmentation_run_doc      ON segmentation_run (document_id, run_at DESC);
CREATE INDEX segmentation_run_bad      ON segmentation_run (outcome, toc_agreement)
    WHERE outcome <> 'segmented' OR toc_agreement < 0.95;

COMMENT ON TABLE segmentation_run IS
    'Doc 02 §5/§8. Table-of-contents agreement is the acceptance test for segmentation.';

-- ---------------------------------------------------------------- views
CREATE VIEW v_provision AS
SELECT p.id                AS provision_id,
       i.id                AS instrument_id,
       i.jurisdiction,
       i.kind              AS instrument_kind,
       i.short_title,
       i.year,
       p.path,
       nlevel(p.path)      AS depth,
       p.kind,
       p.label,
       p.heading,
       p.ordinal,
       p.first_page,
       p.last_page,
       v.text_normalised   AS text,
       v.validity,
       i.document_id
  FROM provision p
  JOIN instrument i ON i.id = p.instrument_id
  LEFT JOIN LATERAL (
       SELECT pv.* FROM provision_version pv
        WHERE pv.provision_id = p.id AND upper_inf(pv.validity)
        ORDER BY lower(pv.validity) DESC LIMIT 1
  ) v ON true;

COMMENT ON VIEW v_provision IS
    'Every provision with its currently-operative text. Read this, never the base table (INV-5).';

CREATE VIEW v_segmentation_health AS
SELECT i.jurisdiction,
       count(DISTINCT i.id)                              AS instruments,
       count(p.id)                                       AS provisions,
       count(p.id) FILTER (WHERE p.kind = 'section')     AS sections,
       round(avg(r.toc_agreement) FILTER (WHERE r.toc_found), 4) AS mean_toc_agreement,
       count(DISTINCT i.id) FILTER (WHERE r.toc_found)   AS with_contents
  FROM instrument i
  LEFT JOIN provision p ON p.instrument_id = i.id
  LEFT JOIN LATERAL (
       SELECT * FROM segmentation_run s
        WHERE s.instrument_id = i.id ORDER BY s.run_at DESC LIMIT 1
  ) r ON true
 GROUP BY i.jurisdiction;

COMMIT;
