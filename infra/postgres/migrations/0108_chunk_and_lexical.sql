-- The retrieval index's storage (L2): the chunk table, and the lexical indexes (18 Nov 2026, DECISION-LOG D-095).
--
-- docs/03 §3 (chunks store offsets, not text), §4 (indexes), §5 (the lexical port: BM25 with a portable fallback);
-- docs/04 §4.1 (BM25 fields: title, heading, provision label, body; pinned extension); docs/02 §5.3 (chunking).
--
-- 1. chunk: ordered character offsets into ONE provision_version.text_normalised -- never a copy of the text.
--    AS BUILT, two departures from docs/03 §3's DDL, both recorded in D-095:
--      * embedding is NULLABLE until the dense slice fills it; that slice adds NOT NULL after its backfill (the
--        add-column / backfill / add-constraint order of the migration rules). A NULL embedding is invisible to
--        the dense candidate query, which orders by it.
--      * chunker names the splitting rule that produced the row (nizam.chunking/N), so a corpus version can be
--        replayed (INV-3) and a rule change is a full rebuild, like a model change.
--    Rows exist only for released versions (v_release_provision_version); tools/build_chunks.py keeps that
--    boundary and audit A20 asserts it. The bounds trigger makes a span past its version's text impossible to
--    insert, so a bad chunker run fails at commit rather than indexing garbage.
-- 2. Lexical indexes, ParadeDB pg_search pinned at 0.25.6 (docs/04 §4.1: its SQL is version-sensitive):
--      provision_version body  -- stemmed English, the BM25 the lexical port reads (docs/03 §5 implementation A)
--      provision heading, marginal note, label (space-folded literal: '462I' finds the printed '462 I', D-094)
--      instrument titles       -- short, display and long title
--    and the portable fallback (docs/03 §5 implementation B): a GIN over the to_tsvector('english', body)
--    EXPRESSION, never a stored column (docs/03: the tsvector is not materialised).
--    Every index covers all rows; reads start from the release and operative views (docs/03 as built), so a
--    retired or unreleased version can be matched by the index but never returned by the port.
-- REVERSAL: DROP TABLE chunk; DROP INDEX ix_provision_version_bm25, ix_provision_bm25, ix_instrument_bm25,
--           ix_provision_version_fts; DROP FUNCTION chunk_span_in_bounds().

BEGIN;

DO $$
DECLARE v text := (SELECT extversion FROM pg_extension WHERE extname = 'pg_search');
BEGIN
  IF v IS DISTINCT FROM '0.25.6' THEN
    RAISE EXCEPTION 'pg_search % installed; this migration''s index and query syntax is verified on 0.25.6', v;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS chunk (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id     uuid     NOT NULL REFERENCES provision_version(id) ON DELETE CASCADE,
    seq            smallint NOT NULL,
    char_start     integer  NOT NULL,     -- offsets into provision_version.text_normalised
    char_end       integer  NOT NULL,
    context_prefix text     NOT NULL,     -- title | chapter heading | unit + section heading | qualifies: ...
    embedding      bit(1024),             -- the dense slice fills it, then makes it NOT NULL (D-095)
    chunker        text     NOT NULL,     -- the splitting rule, e.g. nizam.chunking/1
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_span CHECK (char_start >= 0 AND char_end > char_start),
    CONSTRAINT ck_seq CHECK (seq >= 0),
    CONSTRAINT uq_chunk UNIQUE (version_id, seq)
);

COMMENT ON TABLE chunk IS
  'Retrieval index artefact (docs/03 §3): offsets into one provision_version.text_normalised, never its text. '
  'Released versions only (A20). No chunk id leaves L2 (INV-4): retrieval returns provisions. A chunker or model '
  'change is TRUNCATE plus rebuild (tools/build_chunks.py), never an update (D-095).';

CREATE OR REPLACE FUNCTION chunk_span_in_bounds() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  SELECT length(text_normalised) INTO n FROM provision_version WHERE id = NEW.version_id;
  IF n IS NULL OR NEW.char_end > n THEN
    RAISE EXCEPTION 'chunk % of version % ends at % beyond its text (% chars)',
      NEW.seq, NEW.version_id, NEW.char_end, coalesce(n, -1);
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS tr_chunk_span_in_bounds ON chunk;
CREATE TRIGGER tr_chunk_span_in_bounds BEFORE INSERT OR UPDATE OF version_id, char_start, char_end ON chunk
  FOR EACH ROW EXECUTE FUNCTION chunk_span_in_bounds();

-- the lexical port, implementation A (docs/03 §5): BM25 over the body, stemmed English
CREATE INDEX IF NOT EXISTS ix_provision_version_bm25 ON provision_version
  USING bm25 (id, (text_normalised::pdb.simple('stemmer=english')))
  WITH (key_field = 'id');

-- headings, marginal notes and the label (space-folded, matched lowercased) -- docs/04 §4.1's field boosts
CREATE INDEX IF NOT EXISTS ix_provision_bm25 ON provision
  USING bm25 (id, (heading::pdb.simple('stemmer=english')), (marginal_note::pdb.simple('stemmer=english')),
              ((replace(label, ' ', ''))::pdb.literal_normalized))
  WITH (key_field = 'id');

CREATE INDEX IF NOT EXISTS ix_instrument_bm25 ON instrument
  USING bm25 (id, (short_title::pdb.simple('stemmer=english')), (display_title::pdb.simple('stemmer=english')),
              (long_title::pdb.simple('stemmer=english')))
  WITH (key_field = 'id');

-- implementation B, portable (docs/03 §5): ts_rank_cd over an expression index
CREATE INDEX IF NOT EXISTS ix_provision_version_fts ON provision_version
  USING gin (to_tsvector('english', text_normalised));

COMMIT;
