-- Which model made the chunk embeddings (19 Nov 2026, DECISION-LOG D-098; docs/03 §3, INV-3).
--
-- docs/03 §3: "a new embedding model produces a differently-shaped space and mixing two generations in one index
-- would be silently wrong." A query must be encoded by the SAME model, revision, query template and quantisation as
-- the passages it is compared with, and a replay (INV-3) must be able to name them. This table records each
-- generation; exactly one is active (partial unique index), and tools/load_embeddings.py refuses to write vectors
-- under any other. The HNSW index follows in 0110, after the first load: built once over a full table instead of
-- row by row. chunk.embedding stays nullable -- a chunk is inserted by COPY before its vector exists -- and the rule
-- "while a generation is active, every chunk has a vector; with none active, none has" is audit criterion A21
-- (nizam.workers.chunk embeds a replay's new chunks in the same transaction).
-- REVERSAL: DROP TABLE embedding_generation.

BEGIN;

CREATE TABLE IF NOT EXISTS embedding_generation (
    id              smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model           text        NOT NULL,     -- hub id, e.g. BAAI/bge-m3
    revision        text        NOT NULL,     -- the exact commit of the weights used
    dims            integer     NOT NULL CHECK (dims = 1024),
    quantization    text        NOT NULL CHECK (quantization IN ('binary_sign')),
    pooling         text        NOT NULL CHECK (pooling IN ('cls', 'mean', 'lasttoken')),  -- the model's own config
    query_template  text        NOT NULL,     -- '{q}' or the instruct form the model card requires
    passage_source  text        NOT NULL,     -- what was embedded: 'context_prefix + newline + span text'
    max_tokens      integer     NOT NULL,
    chunker         text        NOT NULL,     -- the chunk table's splitting rule the vectors were made from
    chunk_count     integer     NOT NULL,
    selection       jsonb       NOT NULL,     -- the bake-off evidence that chose this model (dev split only)
    active          boolean     NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_embedding_generation_active ON embedding_generation (active) WHERE active;

COMMENT ON TABLE embedding_generation IS
  'The model, revision, query template and quantisation of chunk.embedding (D-098). One active generation: a '
  'query is encoded only by it, and a replay (INV-3) names it.';

COMMIT;
