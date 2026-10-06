-- A file can land and still not be the statute.
--
-- 0047 gave the corpus a vocabulary for a catalogued item that never arrived,
-- and criterion C1 reads it: every catalogued item either landed or carries a
-- dated, evidence-backed exception.  That sentence is true and it is not the
-- whole truth, because `acquisition_exception` cannot describe the case found
-- by reading pages on 20-21 Sep 2026:
--
--   * Document 33, the Nawab Shaheed Ghous Bakhsh Raisani Memorial Hospital
--     Act, 2012.  Three pages from the Balochistan Code.  Its own contents
--     lists sixteen sections; the file stops inside section 5, mid-clause, at
--     "The administration and management of the affairs of the".
--   * Document 127, the Balochistan Witness Protection Act, 2016.  Seven pages
--     from the same portal.  Its contents lists twenty-nine sections; the body
--     stops inside section 2's definitions on page 4 and jumps to the Schedule.
--   * Document 2205, the Sind Public Conveyances Act, 1920.  Eight pages from
--     the Sindh Code.  Its contents lists thirty-nine sections; the text stops
--     inside section 20(3) at "...or passenger travelling in, the conveyance".
--
-- All three LANDED.  Their observations carry outcome 'landed', their bytes are
-- stored, and the trigger on acquisition_exception refuses -- correctly -- to
-- record an exception against an observation that landed.  So the corpus had
-- no way to say the one thing that is true of them: the acquisition succeeded
-- and the acquired file is a partial copy of the statute.
--
-- Left unsaid, the consequence is worse than a gap.  The contents gaps those
-- files generate are candidates for `absent_in_source`, which asserts that the
-- legislature never enacted the section.  On this evidence that claim would be
-- false: the sections exist, and for two of the three a complete official copy
-- is already in the corpus under a different observation.
--
-- WHAT THIS RECORDS, AND WHAT IT DOES NOT.  A row here says a named landed
-- source is incomplete, says where its body stops, and says either which
-- complete copy supersedes it or that repeated dated attempts could not obtain
-- one.  It deletes nothing and forecloses nothing: the truncated document, its
-- blocks and its tree all remain, because everything in the PDF stays in the
-- database.  What changes is which instrument the corpus publishes as the Act.
--
-- It does not record the instrument.  Re-segmentation retires instrument rows
-- and creates new ones, so an instrument id written here would be stale after
-- the next replay.  The durable fact is about the SOURCE; the instrument-level
-- `duplicate_of` flag is derived from it and re-applied by
-- tools/apply_source_incompleteness.py after every replay.
--
-- This is not instrument_identity_resolution (0036).  That table proves two
-- trees are IDENTICAL and carries a tree_sha256 to show it.  A truncated copy
-- is a strict subset, so no such proof exists or ever will.
--
-- Governing contract: docs/02-corpus-and-ingestion.html section 2.

BEGIN;

CREATE TABLE source_incompleteness (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- The landed observation and the document it produced.
    source_observation_id bigint NOT NULL REFERENCES source_observation(id)
                              ON DELETE RESTRICT,
    document_id           bigint NOT NULL REFERENCES document(id)
                              ON DELETE RESTRICT,
    -- What was done about it.
    resolution            text NOT NULL CHECK (resolution IN (
                              -- A complete official copy is in the corpus.
                              'superseded_by_complete_copy',
                              -- Repeated dated attempts could not obtain one.
                              'no_complete_copy_acquired')),
    complete_document_id  bigint REFERENCES document(id) ON DELETE RESTRICT,

    -- What reading the pages showed, in the reader's own words: where the body
    -- stops, and what the contents promised past it.
    body_stops_at         text NOT NULL CHECK (btrim(body_stops_at) <> ''),
    promised_top          text NOT NULL CHECK (btrim(promised_top) <> ''),
    observed              text NOT NULL CHECK (btrim(observed) <> ''),

    -- The attempts that justify the decision, and what they returned. Same
    -- shape as acquisition_exception: a decision is only as good as the dated
    -- record of what was tried.
    attempts_considered   integer NOT NULL CHECK (attempts_considered >= 1),
    first_attempt_at      timestamptz NOT NULL,
    last_attempt_at       timestamptz NOT NULL,
    observed_error        text NOT NULL CHECK (btrim(observed_error) <> ''),
    evidence              jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    asserted_by           text NOT NULL CHECK (btrim(asserted_by) <> ''),
    asserted_at           timestamptz NOT NULL DEFAULT now(),
    supersedes_id         bigint REFERENCES source_incompleteness(id)
                              ON DELETE RESTRICT,

    CHECK (last_attempt_at >= first_attempt_at),
    CHECK (document_id <> complete_document_id),
    -- A supersession names the copy that supersedes; an unrecovered one names
    -- nothing, and must not pretend otherwise.
    CHECK ((resolution = 'superseded_by_complete_copy')
           = (complete_document_id IS NOT NULL)),
    -- Who reviewed it and how, exactly as the OCR, contents-disposition and
    -- acquisition-exception assertions do.
    CHECK (evidence ? 'reviewer_type'),
    CHECK (evidence ? 'attempt_ids')
);

CREATE INDEX source_incompleteness_observation
    ON source_incompleteness(source_observation_id, asserted_at DESC, id DESC);
CREATE INDEX source_incompleteness_document
    ON source_incompleteness(document_id, asserted_at DESC, id DESC);
CREATE INDEX source_incompleteness_complete
    ON source_incompleteness(complete_document_id)
    WHERE complete_document_id IS NOT NULL;
CREATE INDEX source_incompleteness_chain
    ON source_incompleteness(supersedes_id) WHERE supersedes_id IS NOT NULL;

-- The mirror of acquisition_exception's guard. That one refuses a row for an
-- observation that LANDED; this one refuses a row for an observation that did
-- NOT. The two tables partition the ledger between them, and neither can be
-- used to say what the other says.
CREATE FUNCTION check_source_incompleteness() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    landed text;
    same_blob boolean;
BEGIN
    SELECT o.outcome::text INTO landed
      FROM source_observation o WHERE o.id = NEW.source_observation_id;
    IF landed IS DISTINCT FROM 'landed' THEN
        RAISE EXCEPTION
            'observation % did not land; that is an acquisition_exception, '
            'not an incomplete source', NEW.source_observation_id;
    END IF;

    PERFORM 1 FROM document d
      JOIN source_observation o ON o.sha256 = d.sha256
     WHERE d.id = NEW.document_id AND o.id = NEW.source_observation_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION
            'document % did not come from observation %',
            NEW.document_id, NEW.source_observation_id;
    END IF;

    IF NEW.complete_document_id IS NOT NULL THEN
        SELECT d.sha256 = c.sha256 INTO same_blob
          FROM document d, document c
         WHERE d.id = NEW.document_id AND c.id = NEW.complete_document_id;
        IF same_blob THEN
            RAISE EXCEPTION
                'documents % and % are the same blob; one cannot complete the '
                'other', NEW.document_id, NEW.complete_document_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER source_incompleteness_guard
    BEFORE INSERT ON source_incompleteness
    FOR EACH ROW EXECUTE FUNCTION check_source_incompleteness();

-- The current decision for each incomplete source: latest wins, superseded
-- rows stay.
CREATE VIEW v_source_incompleteness_latest AS
SELECT DISTINCT ON (s.source_observation_id) s.*
  FROM source_incompleteness s
 ORDER BY s.source_observation_id, s.asserted_at DESC, s.id DESC;

-- Landed sources known to be partial copies for which no complete copy has
-- been obtained. This is the honest open queue: law the corpus knows it is
-- missing and cannot yet serve.
CREATE VIEW v_source_incompleteness_open AS
SELECT s.*, o.source_id, o.canonical_url,
       o.source_metadata ->> 'title' AS title
  FROM v_source_incompleteness_latest s
  JOIN source_observation o ON o.id = s.source_observation_id
 WHERE s.resolution = 'no_complete_copy_acquired';

COMMENT ON TABLE source_incompleteness IS
  'Append-only record that a LANDED source is a partial copy of its statute, '
  'with the complete copy that supersedes it or the dated attempts that failed '
  'to obtain one. Nothing is deleted: the truncated document, its blocks and '
  'its tree all remain.';

COMMIT;
