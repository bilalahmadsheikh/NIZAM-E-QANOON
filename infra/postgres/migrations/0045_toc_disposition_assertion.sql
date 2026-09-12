-- A printed contents row may preserve the number of a section whose operative
-- text has been omitted or repealed.  That is a lifecycle fact, not a parser
-- failure and not permission to invent text.  Store the source-reviewed fact
-- independently of any replaceable instrument/tree revision, then let a
-- bounded replay materialise an empty, citable provision_version with
-- operation='omitted'.  Governing contract: docs/02 section 5 and section 8.

BEGIN;

CREATE TABLE toc_disposition_assertion (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_observation_id    bigint NOT NULL REFERENCES source_observation(id)
                                  ON DELETE RESTRICT,
    expression_ordinal       smallint NOT NULL DEFAULT 0
                                  CHECK (expression_ordinal >= 0),
    toc_entry_ordinal        integer NOT NULL CHECK (toc_entry_ordinal >= 0),
    reviewed_toc_entry_id    bigint NOT NULL REFERENCES instrument_toc_entry(id)
                                  ON DELETE RESTRICT,
    printed_label            text NOT NULL CHECK (btrim(printed_label) <> ''),
    printed_heading          text NOT NULL CHECK (btrim(printed_heading) <> ''),
    disposition              text NOT NULL
                                  CHECK (disposition IN ('omitted','repealed')),
    source_block_id          bigint NOT NULL REFERENCES text_block(id)
                                  ON DELETE RESTRICT,
    source_page              integer NOT NULL CHECK (source_page > 0),
    render_artifact          text NOT NULL CHECK (btrim(render_artifact) <> ''),
    render_sha256            character(64) NOT NULL
                                  CHECK (render_sha256 ~ '^[0-9a-f]{64}$'),
    amending_instrument_id    uuid REFERENCES instrument(id) ON DELETE RESTRICT,
    amending_instrument_citation text,
    evidence                 jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    reviewed_by              text NOT NULL CHECK (btrim(reviewed_by) <> ''),
    reviewed_at              timestamptz NOT NULL DEFAULT now(),
    supersedes_id            bigint REFERENCES toc_disposition_assertion(id)
                                  ON DELETE RESTRICT,

    CHECK (evidence @> '{"visual_review":true}'::jsonb),
    CHECK (evidence ? 'reviewer_type'),
    CHECK (amending_instrument_id IS NULL
           OR amending_instrument_citation IS NOT NULL)
);

CREATE INDEX toc_disposition_assertion_key
    ON toc_disposition_assertion
       (source_observation_id,expression_ordinal,toc_entry_ordinal,
        reviewed_at DESC,id DESC);
CREATE INDEX toc_disposition_assertion_entry
    ON toc_disposition_assertion(reviewed_toc_entry_id);

CREATE FUNCTION check_toc_disposition_assertion() RETURNS trigger
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
        IF NOT FOUND
           OR previous.source_observation_id<>NEW.source_observation_id
           OR previous.expression_ordinal<>NEW.expression_ordinal
           OR previous.toc_entry_ordinal<>NEW.toc_entry_ordinal THEN
            RAISE EXCEPTION 'superseded assertion identifies another TOC entry';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER toc_disposition_assertion_guard
BEFORE INSERT ON toc_disposition_assertion
FOR EACH ROW EXECUTE FUNCTION check_toc_disposition_assertion();

CREATE VIEW v_toc_disposition_assertion_latest AS
SELECT DISTINCT ON
       (source_observation_id,expression_ordinal,toc_entry_ordinal) a.*
  FROM toc_disposition_assertion a
 ORDER BY source_observation_id,expression_ordinal,toc_entry_ordinal,
          reviewed_at DESC,id DESC;

ALTER TABLE provision_version
    ADD COLUMN source_toc_disposition_assertion_id bigint
        REFERENCES toc_disposition_assertion(id) ON DELETE RESTRICT;
ALTER TABLE provision_version
    ADD CONSTRAINT provision_version_toc_disposition_is_omitted
    CHECK (source_toc_disposition_assertion_id IS NULL OR operation='omitted');
CREATE INDEX provision_version_toc_disposition
    ON provision_version(source_toc_disposition_assertion_id)
    WHERE source_toc_disposition_assertion_id IS NOT NULL;

COMMENT ON TABLE toc_disposition_assertion IS
  'Append-only rendered-source proof that a printed TOC entry denotes an omitted/repealed section; it survives tree revisions.';
COMMENT ON COLUMN provision_version.source_toc_disposition_assertion_id IS
  'Rendered-source assertion supporting an empty operation=omitted version; never synthesized from a label gap.';

COMMIT;
