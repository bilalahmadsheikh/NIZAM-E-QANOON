-- 0120  Judgment search storage: BM25 over judgment paragraphs; judgment chunks with the CPU generation's vectors
--       (DECISION-LOG D-121, D-123; docs/PRECEDENT-MODEL.md §6.1).
--
-- * BM25 (pg_search, pinned 0.25.6 by 0108) is declared on the partitioned judgment_paragraph: an index declared on
--   the parent propagates to every partition, existing and future (docs/03 §7; checked on this build 22 Nov 2026).
-- * judgment_chunk holds offsets into one judgment_paragraph's text, never a copy of it (docs/03 §3). Each chunk
--   carries the sign bits of the active CPU embedding generation (bge-m3, the statutes' own generation, D-098), so
--   one query vector searches statutes and judgments. HNSW over Hamming distance, as ix_chunk_hnsw (0111).
--   As built: one unpartitioned table. docs/03 §7 partitions a table that is large AND read by date ranges; one
--   court's chunks are neither yet. Partition when a second court lands.
-- * The statute chunk table and its audits (A20-A22) are untouched: a judgment span can never pass the statute gate.
--
-- REVERSAL: DROP TABLE judgment_chunk; DROP INDEX ix_judgment_paragraph_bm25.

BEGIN;

CREATE INDEX ix_judgment_paragraph_bm25 ON judgment_paragraph
    USING bm25 (id, text) WITH (key_field = 'id');

CREATE TABLE judgment_chunk (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    paragraph_id   uuid NOT NULL,
    decided_on     date NOT NULL,
    judgment_id    uuid NOT NULL,
    seq            integer NOT NULL CHECK (seq >= 0),
    char_start     integer NOT NULL,
    char_end       integer NOT NULL,
    context_prefix text NOT NULL CHECK (length(context_prefix) <= 240),
    embedding      bit(1024),
    generation_id  bigint REFERENCES embedding_generation (id),
    chunker        text NOT NULL,
    FOREIGN KEY (paragraph_id, decided_on) REFERENCES judgment_paragraph (id, decided_on),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on),
    UNIQUE (paragraph_id, seq),
    CONSTRAINT ck_judgment_chunk_span CHECK (0 <= char_start AND char_start < char_end),
    CONSTRAINT ck_judgment_chunk_vector CHECK ((embedding IS NULL) = (generation_id IS NULL))
);
CREATE INDEX ix_judgment_chunk_judgment ON judgment_chunk (judgment_id);
CREATE INDEX ix_judgment_chunk_hnsw ON judgment_chunk USING hnsw (embedding bit_hamming_ops)
    WITH (m = 16, ef_construction = 64);

-- A chunk's end never passes its paragraph's text (the statutes' trigger rule, 0108).
CREATE FUNCTION judgment_chunk_within_paragraph() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
    SELECT length(text) INTO n FROM judgment_paragraph WHERE id = NEW.paragraph_id AND decided_on = NEW.decided_on;
    IF n IS NULL OR NEW.char_end > n THEN
        RAISE EXCEPTION 'judgment_chunk: span [%, %) passes paragraph % (length %)', NEW.char_start, NEW.char_end,
            NEW.paragraph_id, n;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER judgment_chunk_within_paragraph BEFORE INSERT OR UPDATE ON judgment_chunk
    FOR EACH ROW EXECUTE FUNCTION judgment_chunk_within_paragraph();

COMMIT;
