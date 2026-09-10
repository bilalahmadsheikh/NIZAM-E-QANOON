-- PostgreSQL does not automatically index the referencing side of foreign
-- keys. These two source-anchor references are queried for every text-block
-- deletion; without indexes, revision archival degenerates into a full scan per
-- block. They also accelerate block-to-provision provenance lookups.
BEGIN;

CREATE INDEX provision_first_block
    ON provision(first_block) WHERE first_block IS NOT NULL;
CREATE INDEX provision_block_block
    ON provision_block(block_id);

COMMIT;
