-- The dense index over chunk.embedding (19 Nov 2026, DECISION-LOG D-098; docs/03 §3-§4, docs/04 §4.2).
--
-- HNSW on the stored sign bits with Hamming distance (pgvector bit_hamming_ops; the query operator is <~>). Built
-- once, after tools/load_embeddings.py filled every chunk (audit A21): a graph built over a full table is better
-- connected and far faster to make than one grown row by row. Parameters are pgvector's defaults (m = 16,
-- ef_construction = 64); search-time breadth is hnsw.ef_search, set per query by nizam.storage.unit_search
-- (pgvector caps it at 1000).
--
-- Memory: the build keeps its graph in maintenance_work_mem (1 GB on this server, docs/09a); two parallel workers
-- so the build does not take every core of a 6-core, 5 GB host. Measured on the first load: see D-098.
-- REVERSAL: DROP INDEX ix_chunk_hnsw.

SET max_parallel_maintenance_workers = 2;

CREATE INDEX IF NOT EXISTS ix_chunk_hnsw ON chunk USING hnsw (embedding bit_hamming_ops)
  WITH (m = 16, ef_construction = 64);

COMMENT ON INDEX ix_chunk_hnsw IS
  'Dense candidates (D-098): HNSW over sign-binarised 1024-d vectors, Hamming distance (<~>). One embedding '
  'generation at a time (embedding_generation, A21); re-embedding rebuilds it.';

ANALYZE chunk;
