-- 0141  The GPU embedding generation for judgment chunks (DECISION-LOG D-158; docs/PRECEDENT-MODEL.md §6.1; the 0113
--       pattern). The judgment chunks (0120) carry the CPU generation's bge-m3 bits in judgment_chunk.embedding, the
--       statutes' own space (D-121). This adds the GPU generation's Qwen3-Embedding-8B sign bits beside them, in the
--       statutes' GPU space (chunk_embedding_gpu, 0113, D-099): one generation per device, shared by laws and
--       judgments, so one question vector searches both.
--
-- One row per judgment chunk, keyed by its id. A re-read retires a judgment and its chunks are rebuilt with new ids
-- (nizam.workers.judgment_chunk), so the old rows go with them (ON DELETE CASCADE) and the new chunks are a top-up,
-- as for the statutes. Written only by tools/load_judgment_embeddings_gpu.py; audit A33.
-- The HNSW index is built by the loader after the rows are in (a graph grown row by row over 760k inserts is slow
-- and worse connected; 0113's loader does the same).

BEGIN;

CREATE TABLE IF NOT EXISTS judgment_chunk_embedding_gpu (
  chunk_id      bigint     PRIMARY KEY REFERENCES judgment_chunk (id) ON DELETE CASCADE,
  generation_id integer    NOT NULL REFERENCES embedding_generation (id),
  bits          bit(4096)  NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_judgment_chunk_embedding_gpu_generation
  ON judgment_chunk_embedding_gpu (generation_id);

COMMENT ON TABLE judgment_chunk_embedding_gpu IS
  'The GPU embedding generation (D-099) for judgment chunks (D-158): Qwen3-Embedding-8B sign bits, one row per '
  'judgment_chunk, in the same space as chunk_embedding_gpu. Written only by tools/load_judgment_embeddings_gpu.py '
  '(whole load or top-up); audit A33. Its HNSW index (ix_judgment_chunk_embedding_gpu_hnsw) is built by the loader.';

COMMIT;
