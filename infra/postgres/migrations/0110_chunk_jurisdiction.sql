-- The jurisdiction on the chunk row, so the dense search filters INSIDE the index scan (19 Nov 2026, D-098).
--
-- docs/04 §4.2 ("Required L2 correction"): "ANN predicates hidden behind joins may be applied after index traversal.
-- Materialize a denormalized search_projection carrying ... jurisdiction ... and embedding on the indexed row."
-- AS BUILT, the part of that projection the dense generator needs now: chunk.jurisdiction, the top label of the
-- chunk's provision path (fed, punjab, sindh, kp, balochistan, ajk, gb -- the jurisdiction every other L2 query
-- reads the same way, subltree(path, 0, 1)). With it, HNSW's iterative scan (pgvector 0.8, docs/04 §9.1) keeps
-- reading the graph until enough chunks IN SCOPE are found, and a small scope can be scanned exactly. Validity,
-- status and territory stay with the INV-5 gate (operative_units over operative_provision), which every candidate
-- passes whichever generator found it -- so they are not copied here.
--
-- The value is never written by hand: a BEFORE INSERT trigger derives it from the version's provision, the backfill
-- below fills today's rows the same way, and NOT NULL follows the backfill (add / backfill / constrain). A
-- provision's path does not move once released (D-090), and a replay retires versions, whose chunks are removed.
-- REVERSAL: DROP TRIGGER tr_chunk_jurisdiction ON chunk; DROP FUNCTION chunk_jurisdiction();
--           DROP INDEX ix_chunk_jurisdiction; ALTER TABLE chunk DROP COLUMN jurisdiction.

BEGIN;

ALTER TABLE chunk ADD COLUMN IF NOT EXISTS jurisdiction text;

CREATE OR REPLACE FUNCTION chunk_jurisdiction() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  SELECT subltree(p.path, 0, 1)::text INTO NEW.jurisdiction
    FROM provision_version v JOIN provision p ON p.id = v.provision_id
   WHERE v.id = NEW.version_id;
  IF NEW.jurisdiction IS NULL THEN
    RAISE EXCEPTION 'chunk % of version %: no provision path to take a jurisdiction from', NEW.seq, NEW.version_id;
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS tr_chunk_jurisdiction ON chunk;
CREATE TRIGGER tr_chunk_jurisdiction BEFORE INSERT OR UPDATE OF version_id, jurisdiction ON chunk
  FOR EACH ROW EXECUTE FUNCTION chunk_jurisdiction();

-- the backfill fires the trigger (UPDATE OF jurisdiction), so today's rows take their value exactly as new rows will
UPDATE chunk SET jurisdiction = '' WHERE jurisdiction IS NULL;

ALTER TABLE chunk ALTER COLUMN jurisdiction SET NOT NULL;
CREATE INDEX IF NOT EXISTS ix_chunk_jurisdiction ON chunk (jurisdiction);

COMMENT ON COLUMN chunk.jurisdiction IS
  'subltree(provision.path, 0, 1) of the chunk''s version, set by trigger (D-098): the dense search''s scope filter '
  'runs inside the HNSW scan (docs/04 §4.2). Not a serving filter: the INV-5 gate still decides what is operative.';

COMMIT;
