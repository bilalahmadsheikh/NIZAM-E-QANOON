-- Parser improvements can discover a previously missed contents row and shift
-- every later ordinal.  A review assertion must follow the immutable printed
-- source block and label, not a parser-generated list position.

BEGIN;

DROP VIEW v_toc_disposition_assertion_latest;

CREATE INDEX toc_disposition_assertion_source_identity
    ON toc_disposition_assertion
       (source_observation_id,expression_ordinal,source_block_id,printed_label,
        reviewed_at DESC,id DESC);

CREATE VIEW v_toc_disposition_assertion_latest AS
SELECT DISTINCT ON
       (source_observation_id,expression_ordinal,source_block_id,printed_label) a.*
  FROM toc_disposition_assertion a
 ORDER BY source_observation_id,expression_ordinal,source_block_id,printed_label,
          reviewed_at DESC,id DESC;

COMMENT ON COLUMN toc_disposition_assertion.toc_entry_ordinal IS
  'Ordinal at review time (audit evidence, not revision-stable identity); application matches immutable source block + printed label + heading.';

COMMIT;
