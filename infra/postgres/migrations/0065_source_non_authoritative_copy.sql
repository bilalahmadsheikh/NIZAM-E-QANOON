-- A landed file that is not the authoritative text of a law the corpus holds.
--
-- The corpus could already say three things about a second file of one law:
-- it is byte-identical (0036), a PARTIAL copy (0054), or the same text with
-- different page furniture (0062). Two landed files fit none of them, found
-- while releasing the last blocked documents on 20 Oct 2026:
--
--   * Document 4641 (observation 4130, Sindh Code PUB-16-000550), an Urdu
--     rendering of the Sindh Agricultural Income Tax (Amendment) Ordinance,
--     1997. Its closing note says it is a translation for public information
--     that cannot be used in a court. Its body matches the authoritative
--     English text, document 1522 (Ordinance XVI of 1997), section by section;
--     its own title and contents print 'Ordinance No. X' and an s.4 that no
--     Ordinance of that title has (the Sindh Judicial Academy index lists the
--     1997 amendment only as XVI). It is not partial, and it is not the same
--     text, so neither 0054 nor 0062 may hold it.
--   * Document 4642 (observation 1282, Balochistan Code docid 892), catalogued
--     as 'The Balochistan Motor Vehicles (Amendment) Act, 2020', prints 'A
--     BILL'. The enacted law is Act No. XIV of 2021 (passed 26 April 2021,
--     assented 4 May 2021), landed from the Provincial Assembly as document
--     4703, and its Twelfth Schedule rates differ from the Bill's. A Bill is
--     not law; publishing it would serve unenacted text as the Act.
--
-- docs/02 §4.1: English, Urdu and Sindhi publications are separate OFFICIAL
-- expressions linked by instrument identity, and docs/03b §'Bilingual
-- authenticity' puts authentic_language on the instrument. Neither covers an
-- unofficial translation or a Bill: they are not expressions of the law at all.
-- This record says so, names the authoritative document, and keeps the file out
-- of release. When the translation link of docs/03b is built, an unofficial
-- translation may be shown beside the authentic text as a labelled
-- translation; until then it is withheld.
--
-- WHAT THIS RECORDS. A row says: the document a landed observation produced is
-- not authoritative text -- an unofficial translation, or a Bill whose enacted
-- text is held -- and names the authoritative document, on a cited owner
-- decision. Like 0054 and 0062 it is about SOURCES, not instruments:
-- re-segmentation replaces instrument rows, so the instrument-level
-- `duplicate_of` flag is derived from this record and re-applied after every
-- replay by tools/apply_source_non_authoritative_copy.py
-- (tools/post_replay_sequence.sh step 2b2). Nothing is deleted: the file's
-- document, blocks and tree all remain.
--
-- GUARDS (trigger), as 0062's:
--   * append-only: UPDATE, DELETE and TRUNCATE are refused;
--   * one record per observation and one per document (UNIQUE), inserts
--     serialised on one advisory lock;
--   * the observation landed, and the document came from it;
--   * the two documents are different files, and the evidence's SHA-256 values
--     are theirs;
--   * the authoritative document is active and has an active, non-duplicate
--     instrument -- a file is never withheld in favour of nothing;
--   * no chains through this table: the authoritative document is not itself
--     recorded here as non-authoritative, and the recorded document is not
--     anyone's authoritative document;
--   * no instrument built from the observation is released: this route keeps
--     an unreleased file out of release, it never withdraws a released tree;
--   * the owner decision is about one of the two documents and reads
--     'keep-<authoritative_document_id>', so a record can never withhold the
--     document the owner chose to keep.
--
-- Until the link exists the file stays fail-closed by the ordinary release
-- gates; this migration does not touch the release views.
--
-- REVERSAL (explicitly irreversible once a row exists, per docs/03 §9): with
-- the table empty, drop the triggers, the function and the table.
--
-- Governing contract: docs/02 §2 and §4.1; docs/03b (bilingual authenticity);
-- docs/03 §9; docs/SCHEMA.md.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE source_non_authoritative_copy (
    id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- The landed observation of the NON-AUTHORITATIVE file, and its document.
    source_observation_id     bigint NOT NULL UNIQUE
                                  REFERENCES source_observation(id) ON DELETE RESTRICT,
    document_id               bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    -- What the file is.
    kind                      text NOT NULL CHECK (kind IN (
                                  -- a translation the file itself, or its
                                  -- publisher, says is not authoritative
                                  'unofficial_translation',
                                  -- a Bill, whose enacted text is the
                                  -- authoritative document
                                  'bill_superseded_by_enactment')),
    -- The document the corpus publishes as the law instead.
    authoritative_document_id bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    -- What reading both files found, in words.
    observed                  text NOT NULL CHECK (btrim(observed) <> ''),
    -- The owner decision-review answer (as 0062's).
    owner_decision            jsonb NOT NULL CHECK (coalesce(
                                  jsonb_typeof(owner_decision) = 'object'
                                  AND owner_decision ?& ARRAY['export','document_id',
                                                              'question_id','choice']
                                  AND jsonb_typeof(owner_decision->'export') = 'string'
                                  AND (owner_decision->>'export') LIKE '%.json'
                                  AND jsonb_typeof(owner_decision->'document_id') = 'number'
                                  AND (owner_decision->>'document_id') ~ '^[1-9][0-9]{0,17}$'
                                  AND jsonb_typeof(owner_decision->'question_id') = 'string'
                                  AND (owner_decision->>'question_id') ~ '^q[0-9]+$'
                                  AND jsonb_typeof(owner_decision->'choice') = 'string'
                                  AND btrim(owner_decision->>'choice') <> '',
                                  false)),
    -- Both files' SHA-256, the finding (which must equal kind), the basis the
    -- reviewer relied on, and the export's SHA-256.
    evidence                  jsonb NOT NULL CHECK (coalesce(
                                  jsonb_typeof(evidence) = 'object'
                                  AND (evidence->>'copy_sha256') ~ '^[0-9a-f]{64}$'
                                  AND (evidence->>'authoritative_sha256') ~ '^[0-9a-f]{64}$'
                                  AND btrim(evidence->>'basis') <> ''
                                  AND btrim(evidence->>'reviewer_type') <> ''
                                  AND (evidence->>'export_sha256') ~ '^[0-9a-f]{64}$',
                                  false)),
    recorded_by               text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at               timestamptz NOT NULL DEFAULT now(),

    CHECK (document_id <> authoritative_document_id),
    CHECK (evidence->>'finding' IS NOT DISTINCT FROM kind)
);

CREATE INDEX source_non_authoritative_copy_authoritative
    ON source_non_authoritative_copy(authoritative_document_id);
CREATE UNIQUE INDEX source_non_authoritative_copy_document
    ON source_non_authoritative_copy(document_id);

CREATE FUNCTION check_source_non_authoritative_copy() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    landed   text;
    copy_sha text;
    auth_sha text;
    cited    bigint;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'source_non_authoritative_copy is append-only';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext('source_non_authoritative_copy'));
    IF NEW.document_id = NEW.authoritative_document_id THEN
        RETURN NEW;   -- left for the CHECK (document_id <> authoritative_document_id)
    END IF;

    SELECT o.outcome::text INTO landed
      FROM source_observation o WHERE o.id = NEW.source_observation_id;
    IF landed IS DISTINCT FROM 'landed' THEN
        RAISE EXCEPTION 'observation % did not land', NEW.source_observation_id;
    END IF;

    SELECT d.sha256 INTO copy_sha
      FROM document d
      JOIN source_observation o ON o.sha256 = d.sha256
     WHERE d.id = NEW.document_id AND o.id = NEW.source_observation_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'document % did not come from observation %',
                        NEW.document_id, NEW.source_observation_id;
    END IF;

    SELECT d.sha256 INTO auth_sha
      FROM document d WHERE d.id = NEW.authoritative_document_id AND d.is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'authoritative document % is not an active document',
                        NEW.authoritative_document_id;
    END IF;
    IF copy_sha = auth_sha THEN
        RAISE EXCEPTION 'documents % and % are the same file',
                        NEW.document_id, NEW.authoritative_document_id;
    END IF;
    -- Malformed evidence is left for the evidence CHECK to refuse by name.
    IF NEW.evidence->>'copy_sha256' IS DISTINCT FROM copy_sha
       AND (NEW.evidence->>'copy_sha256') ~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'evidence copy_sha256 % is not document %''s file %',
          NEW.evidence->>'copy_sha256', NEW.document_id, copy_sha;
    END IF;
    IF NEW.evidence->>'authoritative_sha256' IS DISTINCT FROM auth_sha
       AND (NEW.evidence->>'authoritative_sha256') ~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'evidence authoritative_sha256 % is not document %''s file %',
          NEW.evidence->>'authoritative_sha256', NEW.authoritative_document_id, auth_sha;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM instrument i
                    WHERE i.document_id = NEW.authoritative_document_id
                      AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION
          'authoritative document % has no active canonical instrument; a file is '
          'never withheld in favour of nothing', NEW.authoritative_document_id;
    END IF;

    IF EXISTS (SELECT 1 FROM source_non_authoritative_copy s
                WHERE s.document_id = NEW.authoritative_document_id) THEN
        RAISE EXCEPTION 'authoritative document % is itself recorded as non-authoritative',
                        NEW.authoritative_document_id;
    END IF;
    IF EXISTS (SELECT 1 FROM source_non_authoritative_copy s
                WHERE s.authoritative_document_id = NEW.document_id) THEN
        RAISE EXCEPTION 'document % is the authoritative document of another record',
                        NEW.document_id;
    END IF;

    IF EXISTS (SELECT 1 FROM v_release_instrument r
                WHERE r.source_observation_id = NEW.source_observation_id) THEN
        RAISE EXCEPTION
          'observation % has a released instrument; this route never withdraws '
          'a released tree', NEW.source_observation_id;
    END IF;

    IF coalesce((NEW.owner_decision->>'document_id') ~ '^[1-9][0-9]{0,17}$',
                false) IS NOT TRUE THEN
        RETURN NEW;   -- left for the owner_decision CHECK to refuse by name
    END IF;
    cited := (NEW.owner_decision->>'document_id')::bigint;
    IF cited NOT IN (NEW.document_id, NEW.authoritative_document_id) THEN
        RAISE EXCEPTION 'owner_decision cites document %, not % or %',
          cited, NEW.document_id, NEW.authoritative_document_id;
    END IF;
    IF NEW.owner_decision->>'choice' IS DISTINCT FROM
       'keep-' || NEW.authoritative_document_id::text THEN
        RAISE EXCEPTION
          'owner_decision choice % does not keep document %; the answer must read keep-%',
          NEW.owner_decision->>'choice', NEW.authoritative_document_id,
          NEW.authoritative_document_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER source_non_authoritative_copy_guard
BEFORE INSERT OR UPDATE OR DELETE ON source_non_authoritative_copy
FOR EACH ROW EXECUTE FUNCTION check_source_non_authoritative_copy();

CREATE TRIGGER source_non_authoritative_copy_no_truncate
BEFORE TRUNCATE ON source_non_authoritative_copy
FOR EACH STATEMENT EXECUTE FUNCTION check_source_non_authoritative_copy();

COMMENT ON TABLE source_non_authoritative_copy IS
  'Append-only: a landed observation''s document is not authoritative text -- an '
  'unofficial translation, or a Bill whose enacted text is held -- and names the '
  'authoritative document, on a cited owner decision. One record per observation. '
  'instrument.duplicate_of is derived from it after every replay by '
  'tools/apply_source_non_authoritative_copy.py. Migration 0065.';

COMMIT;
