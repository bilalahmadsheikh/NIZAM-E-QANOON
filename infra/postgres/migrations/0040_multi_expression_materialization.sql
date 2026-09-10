-- One official PDF can be a compilation containing several independently
-- citable legal instruments.  This migration separates the immutable source
-- observation from each legal expression materialised from it.  Blocks remain
-- stored once and one active assignment set still accounts for every block.

BEGIN;

ALTER TABLE instrument
    ADD COLUMN expression_ordinal smallint NOT NULL DEFAULT 0
        CHECK (expression_ordinal >= 0),
    ADD COLUMN source_start_block_id bigint REFERENCES text_block(id) ON DELETE RESTRICT,
    ADD COLUMN source_end_block_id bigint REFERENCES text_block(id) ON DELETE RESTRICT,
    ADD COLUMN expression_role text NOT NULL DEFAULT 'primary'
        CHECK (expression_role IN ('primary','embedded'));

UPDATE instrument i
   SET source_start_block_id=(SELECT min(t.id) FROM text_block t
                              WHERE t.document_id=i.document_id),
       source_end_block_id=(SELECT max(t.id) FROM text_block t
                            WHERE t.document_id=i.document_id)
 WHERE source_start_block_id IS NULL OR source_end_block_id IS NULL;

ALTER TABLE instrument
    ADD CONSTRAINT ck_instrument_source_span
    CHECK (source_start_block_id IS NULL OR source_end_block_id IS NULL
           OR source_start_block_id <= source_end_block_id);

CREATE FUNCTION check_instrument_source_span() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    start_doc bigint;
    end_doc bigint;
    start_order integer;
    end_order integer;
BEGIN
    IF NEW.source_start_block_id IS NULL OR NEW.source_end_block_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT document_id,reading_order INTO start_doc,start_order
      FROM text_block WHERE id=NEW.source_start_block_id;
    SELECT document_id,reading_order INTO end_doc,end_order
      FROM text_block WHERE id=NEW.source_end_block_id;
    IF start_doc IS DISTINCT FROM NEW.document_id
       OR end_doc IS DISTINCT FROM NEW.document_id
       OR start_order > end_order THEN
        RAISE EXCEPTION 'instrument source span does not belong to document % in reading order',
                        NEW.document_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER instrument_source_span_guard
BEFORE INSERT OR UPDATE OF document_id,source_start_block_id,source_end_block_id
ON instrument FOR EACH ROW EXECUTE FUNCTION check_instrument_source_span();

DROP INDEX uq_instrument_active_observation;
CREATE UNIQUE INDEX uq_instrument_active_expression
    ON instrument(source_observation_id,expression_ordinal) WHERE is_active;
CREATE INDEX instrument_source_span
    ON instrument(document_id,source_start_block_id,source_end_block_id)
    WHERE is_active;

CREATE TABLE instrument_expression_manifest (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_observation_id bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    document_id           bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    expression_ordinal    smallint NOT NULL CHECK (expression_ordinal >= 0),
    expression_role       text NOT NULL CHECK (expression_role IN ('primary','embedded')),
    start_block_id        bigint NOT NULL REFERENCES text_block(id) ON DELETE RESTRICT,
    end_block_id          bigint NOT NULL REFERENCES text_block(id) ON DELETE RESTRICT,
    detected_title        text NOT NULL,
    detected_kind         instrument_kind NOT NULL,
    detected_year         smallint NOT NULL CHECK (detected_year BETWEEN 1800 AND 2100),
    detected_number       text,
    review_basis          text NOT NULL CHECK (review_basis IN
                              ('machine_evidenced','source_verified','human_verified')),
    method                text NOT NULL,
    evidence              jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    materialized_instrument_id uuid REFERENCES instrument(id) ON DELETE RESTRICT,
    is_active             boolean NOT NULL DEFAULT true,
    supersedes_manifest_id uuid REFERENCES instrument_expression_manifest(id)
                              ON DELETE RESTRICT,
    retired_at            timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),
    CHECK (start_block_id <= end_block_id),
    CHECK (is_active OR retired_at IS NOT NULL)
);

CREATE FUNCTION check_expression_manifest_span() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    observation_sha char(64);
    document_sha char(64);
    start_doc bigint;
    end_doc bigint;
    start_order integer;
    end_order integer;
BEGIN
    SELECT sha256 INTO observation_sha FROM source_observation
     WHERE id=NEW.source_observation_id;
    SELECT sha256 INTO document_sha FROM document WHERE id=NEW.document_id;
    SELECT document_id,reading_order INTO start_doc,start_order
      FROM text_block WHERE id=NEW.start_block_id;
    SELECT document_id,reading_order INTO end_doc,end_order
      FROM text_block WHERE id=NEW.end_block_id;
    IF observation_sha IS DISTINCT FROM document_sha
       OR start_doc IS DISTINCT FROM NEW.document_id
       OR end_doc IS DISTINCT FROM NEW.document_id
       OR start_order > end_order THEN
        RAISE EXCEPTION 'expression manifest provenance/span mismatch for observation %, document %',
                        NEW.source_observation_id,NEW.document_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER expression_manifest_span_guard
BEFORE INSERT OR UPDATE OF source_observation_id,document_id,start_block_id,end_block_id
ON instrument_expression_manifest FOR EACH ROW
EXECUTE FUNCTION check_expression_manifest_span();

CREATE UNIQUE INDEX uq_expression_manifest_active_ordinal
    ON instrument_expression_manifest(source_observation_id,expression_ordinal)
    WHERE is_active;
CREATE INDEX expression_manifest_document_span
    ON instrument_expression_manifest(document_id,start_block_id,end_block_id)
    WHERE is_active;

COMMENT ON TABLE instrument_expression_manifest IS
  'Versioned, source-anchored legal-expression boundaries inside one official observation; source text is never copied or rewritten.';
COMMENT ON COLUMN instrument.expression_ordinal IS
  'Stable ordinal of one legal expression within its source observation; 0 is the ordinary single-expression case.';
COMMENT ON COLUMN instrument.source_start_block_id IS
  'First immutable source block owned by this legal expression.';
COMMENT ON COLUMN instrument.source_end_block_id IS
  'Last immutable source block owned by this legal expression.';

COMMIT;
