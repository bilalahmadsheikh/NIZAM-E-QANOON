-- One legal expression can occupy several disjoint ranges in an official PDF.
-- A Finance Act may insert the full text of a new Act and then resume its own
-- appendices; the inserted Act's contents row can likewise appear on the
-- package contents page.  The original start/end columns remain the bounding
-- envelope for compatibility.  This child table is the exact source ownership.

BEGIN;

CREATE TABLE instrument_expression_span (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manifest_id    uuid NOT NULL REFERENCES instrument_expression_manifest(id)
                       ON DELETE RESTRICT,
    span_ordinal   smallint NOT NULL CHECK (span_ordinal >= 0),
    start_block_id bigint NOT NULL REFERENCES text_block(id) ON DELETE RESTRICT,
    end_block_id   bigint NOT NULL REFERENCES text_block(id) ON DELETE RESTRICT,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (manifest_id,span_ordinal),
    CHECK (start_block_id <= end_block_id)
);

CREATE FUNCTION check_expression_source_span() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    manifest_document bigint;
    start_document bigint;
    end_document bigint;
    start_order integer;
    end_order integer;
BEGIN
    SELECT document_id INTO manifest_document
      FROM instrument_expression_manifest WHERE id=NEW.manifest_id;
    SELECT document_id,reading_order INTO start_document,start_order
      FROM text_block WHERE id=NEW.start_block_id;
    SELECT document_id,reading_order INTO end_document,end_order
      FROM text_block WHERE id=NEW.end_block_id;
    IF manifest_document IS NULL
       OR start_document IS DISTINCT FROM manifest_document
       OR end_document IS DISTINCT FROM manifest_document
       OR start_order > end_order THEN
        RAISE EXCEPTION 'expression source span does not belong to manifest document';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER expression_source_span_guard
BEFORE INSERT OR UPDATE OF manifest_id,start_block_id,end_block_id
ON instrument_expression_span FOR EACH ROW
EXECUTE FUNCTION check_expression_source_span();

-- Existing manifests asserted one contiguous range. Preserve that historical
-- assertion as span zero; a later append-only manifest can supersede it with
-- the exact multi-span ownership.
INSERT INTO instrument_expression_span
    (manifest_id,span_ordinal,start_block_id,end_block_id)
SELECT id,0,start_block_id,end_block_id
  FROM instrument_expression_manifest;

CREATE VIEW v_active_instrument_expression_span AS
SELECT s.*,m.source_observation_id,m.document_id,m.expression_ordinal,
       m.expression_role,m.materialized_instrument_id
  FROM instrument_expression_span s
  JOIN instrument_expression_manifest m ON m.id=s.manifest_id
 WHERE m.is_active;

COMMENT ON TABLE instrument_expression_span IS
  'Exact ordered immutable block ranges owned by one versioned legal-expression manifest; multiple rows represent a discontiguous expression.';
COMMENT ON VIEW v_active_instrument_expression_span IS
  'Current exact source spans for materialized legal expressions.';

COMMIT;
