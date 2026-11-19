-- One active embedding generation per encoder device (19 Nov 2026, DECISION-LOG D-099; docs/03 §3, docs/04 §4.2).
--
-- 0109 allowed exactly one active generation. The owner's ruling (D-099) keeps bge-m3 (generation 1, its query
-- encoder int8 ONNX on any CPU) AND adds Qwen3-Embedding-8B, whose query encoder needs the GPU host that serves the
-- answer model. Both spaces are kept, each complete over the chunks, each with its own vectors and index:
--
--   encoder_device  'cpu' | 'gpu'  -- where the QUERY encoder runs; at most one active generation per device
--   storage         'chunk.embedding'      the CPU generation's sign bits (0109-0111, unchanged)
--                   'chunk_embedding_gpu'  the GPU generation's table (0113)
--   dims            the stored sign-bit width (1024 for chunk.embedding; 1024/2048/4096 for the GPU table)
--   rescore_dims    the GPU table's halfvec prefix that re-ranks the Hamming window, or NULL
--   vector_dims     the model's full output width (bge-m3 1024, Qwen3-Embedding-8B 4096)
--
-- "Two generations in one index is silently wrong" (docs/03 §3) still holds: they never share a column or an index,
-- and a query reaches only the generation whose model, commit, pooling and template made it
-- (nizam.storage.unit_search.generation_for). Audit A21 keeps chunk.embedding's rule for the CPU generation; A22
-- (tools/audit/criteria.sql) states the GPU table's.
-- REVERSAL: drop the four columns and their checks; recreate uq_embedding_generation_active ON (active) WHERE active.

BEGIN;

ALTER TABLE embedding_generation
  ADD COLUMN IF NOT EXISTS encoder_device text NOT NULL DEFAULT 'cpu',
  ADD COLUMN IF NOT EXISTS storage        text NOT NULL DEFAULT 'chunk.embedding',
  ADD COLUMN IF NOT EXISTS rescore_dims   integer,
  ADD COLUMN IF NOT EXISTS vector_dims    integer;

UPDATE embedding_generation SET vector_dims = dims WHERE vector_dims IS NULL;     -- bge-m3: 1024 out, 1024 stored
ALTER TABLE embedding_generation ALTER COLUMN vector_dims SET NOT NULL;

ALTER TABLE embedding_generation
  DROP CONSTRAINT IF EXISTS embedding_generation_dims_check,
  ADD CONSTRAINT ck_embedding_generation_device CHECK (encoder_device IN ('cpu', 'gpu')),
  ADD CONSTRAINT ck_embedding_generation_storage CHECK (
        (encoder_device = 'cpu' AND storage = 'chunk.embedding')
     OR (encoder_device = 'gpu' AND storage = 'chunk_embedding_gpu')),
  ADD CONSTRAINT ck_embedding_generation_dims CHECK (
        dims IN (1024, 2048, 4096) AND dims <= vector_dims
    AND (storage <> 'chunk.embedding' OR dims = 1024)),
  ADD CONSTRAINT ck_embedding_generation_rescore CHECK (
        rescore_dims IS NULL
     OR (storage = 'chunk_embedding_gpu' AND rescore_dims IN (512, 1024, 2048) AND rescore_dims <= vector_dims));

DROP INDEX IF EXISTS uq_embedding_generation_active;
CREATE UNIQUE INDEX uq_embedding_generation_active ON embedding_generation (encoder_device) WHERE active;

COMMENT ON TABLE embedding_generation IS
  'The model, revision, query template and quantisation of each embedding space (D-098, D-099). At most one active '
  'generation per encoder device: cpu (chunk.embedding) and gpu (chunk_embedding_gpu). A query is compared only with '
  'the generation its own encoder made, and a replay (INV-3) names it.';

COMMIT;
