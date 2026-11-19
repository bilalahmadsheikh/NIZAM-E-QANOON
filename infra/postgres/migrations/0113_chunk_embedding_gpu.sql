-- The GPU embedding generation's own table (20 Nov 2026, DECISION-LOG D-099; docs/03 §3-§4, docs/04 §4.2).
--
-- Qwen3-Embedding-8B (its query encoder needs the GPU host, 0112) embedded all 1,132,245 chunks in 24 Kaggle shards.
-- Its vectors live here, beside the CPU generation's chunk.embedding (bge-m3, 0109-0111), which is untouched: two
-- spaces never share a column or an index (docs/03 §3).
--
-- Stored form: the sign of all 4,096 dimensions, bit(4096), 512 bytes a chunk, no halfvec rescoring column. Chosen on
-- the golden DEV split by the rule written before any 8B corpus vector existed
-- (evals/results/qwen8b-storage-rule-2026-11-19.json; scores in evals/results/qwen8b-dense-dev-2026-11-19.json):
-- bits4096 scored best (r50 .968, MRR@10 .626); bits2048 was within 1 point on r50 but not on MRR@10 (.614), and every
-- halfvec(1024)-rescored arm scored lower than the bits alone. tools/load_embeddings_gpu.py reads the width from this
-- column's type, so a different form is a new migration, never an edit.
--
--   chunk_id       the chunk, ON DELETE CASCADE: a replay that removes a chunk removes its vector with it, and
--                  nizam.workers.chunk counts the new chunks still lacking one (topped up by tools/embed_topup.py)
--   generation_id  the GPU generation that made it (embedding_generation, encoder_device 'gpu')
--   jurisdiction   copied from chunk.jurisdiction by trigger, never written by hand: the scope filter inside the HNSW
--                  scan (docs/04 §4.2), as chunk.jurisdiction is for the CPU space (0110)
--   bits           np.packbits(v > 0) order over the first 4,096 dimensions (all of them)
--
-- The HNSW index is created here on the empty table; the loader drops it, fills the table, and rebuilds it from this
-- definition (a graph built over a full table is better connected and far faster to make, as for ix_chunk_hnsw, 0111).
-- Audit A22 (tools/audit/criteria.sql) states the rule: with a GPU generation active, every chunk has exactly one
-- vector of it, of its width, in its own scope, and no vector belongs to any other generation.
-- REVERSAL: DROP TABLE chunk_embedding_gpu; DROP FUNCTION chunk_embedding_gpu_jurisdiction();
--           UPDATE embedding_generation SET active = false WHERE encoder_device = 'gpu'.

BEGIN;

CREATE TABLE IF NOT EXISTS chunk_embedding_gpu (
  chunk_id      bigint     PRIMARY KEY REFERENCES chunk (id) ON DELETE CASCADE,
  generation_id integer    NOT NULL REFERENCES embedding_generation (id),
  jurisdiction  text       NOT NULL,
  bits          bit(4096)  NOT NULL
);

CREATE OR REPLACE FUNCTION chunk_embedding_gpu_jurisdiction() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  SELECT c.jurisdiction INTO NEW.jurisdiction FROM chunk c WHERE c.id = NEW.chunk_id;
  IF NEW.jurisdiction IS NULL THEN
    RAISE EXCEPTION 'GPU vector for chunk %: no such chunk to take a jurisdiction from', NEW.chunk_id;
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS tr_chunk_embedding_gpu_jurisdiction ON chunk_embedding_gpu;
CREATE TRIGGER tr_chunk_embedding_gpu_jurisdiction BEFORE INSERT OR UPDATE OF chunk_id, jurisdiction
  ON chunk_embedding_gpu FOR EACH ROW EXECUTE FUNCTION chunk_embedding_gpu_jurisdiction();

CREATE INDEX IF NOT EXISTS ix_chunk_embedding_gpu_generation ON chunk_embedding_gpu (generation_id);

CREATE INDEX IF NOT EXISTS ix_chunk_embedding_gpu_hnsw ON chunk_embedding_gpu USING hnsw (bits bit_hamming_ops)
  WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE chunk_embedding_gpu IS
  'The GPU embedding generation (D-099): Qwen3-Embedding-8B sign bits, one row per chunk, beside the CPU generation in '
  'chunk.embedding. Written only by tools/load_embeddings_gpu.py (whole load or top-up); audit A22.';
COMMENT ON COLUMN chunk_embedding_gpu.jurisdiction IS
  'chunk.jurisdiction, set by trigger: the dense scope filter inside the HNSW scan (docs/04 §4.2). Not a serving '
  'filter: the INV-5 gate still decides what is operative.';
COMMENT ON INDEX ix_chunk_embedding_gpu_hnsw IS
  'Dense candidates of the GPU generation (D-099): HNSW over sign-binarised 4096-d vectors, Hamming distance (<~>). '
  'Rebuilt by the loader after a whole load.';

COMMIT;
