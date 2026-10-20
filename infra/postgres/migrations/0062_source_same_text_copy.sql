-- A landed file that prints the same text as another document, in a different
-- file.
--
-- The corpus could already say three things about two copies of one Act:
--
--   * instrument_identity_resolution (0036) -- two instrument revisions built
--     from the SAME source blob have byte-identical trees. It carries one
--     source_sha256 and a tree_sha256, and
--     tools/resolve_exact_instrument_duplicates.py groups only by one blob
--     within one document;
--   * source_incompleteness (0054) -- a landed file is a PARTIAL copy, and
--     names the complete copy that supersedes it;
--   * nothing at all about two different files carrying the same text.
--
-- The case that forced the decision: the Punjab Disabled Persons (Employment
-- and Rehabilitation) Rules, 1987 landed twice from the Punjab Code portal --
-- document 2191 (observation 2744, sha f60100a7...) and document 2673
-- (observation 2598, sha 18860c57...). A word-level diff over every text block
-- of both documents (4,640 vs 4,652 words, ratio 0.99677) finds every
-- difference in page furniture: 2673 prints page numbers 2-13 and its
-- "Cont...P/N" page-turn lines number two higher. The owner answered
-- (decision-review-2026-10-10-i.json, document 2191, q2 'keep-2191'): 2191 is
-- the canonical version and 2673 is linked as duplicate_of 2191, subject to
-- confirmation that the differences are limited to pagination and page
-- furniture -- which that diff confirms. The trees are not byte-identical (the
-- furniture moves blocks and pages), so 0036 cannot hold it; 2673 is not
-- partial, so 0054 must not.
--
-- WHAT THIS RECORDS. A row says: the document a landed observation produced
-- prints the same legal text as a canonical document, differing only in page
-- furniture, on a cited owner decision, with the diff that confirms it. Like
-- 0054 it is about SOURCES, not instruments: re-segmentation replaces
-- instrument rows, so the instrument-level `duplicate_of` flag is derived from
-- this record and re-applied after every replay by
-- tools/apply_source_same_text_copy.py (tools/post_replay_sequence.sh step 2b).
-- Nothing is deleted: the copy's document, blocks and tree all remain.
--
-- GUARDS (trigger):
--   * append-only: UPDATE, DELETE and TRUNCATE are refused;
--   * one record per observation and one per copy document (UNIQUE), and
--     inserts serialise on one advisory lock so two concurrent records cannot
--     both pass the chain checks;
--   * the observation landed, and the document came from it;
--   * the two documents are different files (same-blob copies are 0036's);
--   * the evidence's two SHA-256 values are those two documents' own;
--   * the canonical document is active and has an active, non-duplicate
--     instrument -- a copy is never retired in favour of nothing;
--   * no chains: the canonical document is not itself recorded as a copy, and
--     the copy is not anyone's canonical;
--   * no instrument built from the copy's observation is released: this route
--     keeps an unreleased copy out of release, it never withdraws a released
--     tree;
--   * the owner decision is about one of the two documents, and its choice
--     names the direction: it must read 'keep-<canonical_document_id>' (the
--     decision-review card's option naming convention, e.g. 'keep-2191'), so a
--     record can never retire the document the owner chose to keep.
--
-- Until the link exists the copy stays fail-closed by the ordinary release
-- gates; this migration does not touch the release views, and the canonical
-- document's release does not wait on it.
--
-- REVERSAL (explicitly irreversible once a row exists, per docs/03 §9): with
-- the table empty, drop the trigger, the function and the table.
--
-- Governing contract: docs/02 §2 (sources and acquisition: everything that
-- landed stays; which copy is published is a recorded decision);
-- docs/03 §9; docs/SCHEMA.md.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE source_same_text_copy (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- The landed observation of the COPY, and the document it produced.
    source_observation_id bigint NOT NULL UNIQUE
                              REFERENCES source_observation(id) ON DELETE RESTRICT,
    document_id           bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    -- The document the corpus publishes instead.
    canonical_document_id bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    -- What the comparison found, in words.
    observed              text NOT NULL CHECK (btrim(observed) <> ''),
    -- The owner decision-review answer, as
    -- nizam.workers.segment.owner_decision_answer cites one, plus the choice.
    -- Every test is wrapped in coalesce(..., false): a CHECK that evaluates to
    -- NULL passes.
    owner_decision        jsonb NOT NULL CHECK (coalesce(
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
    -- The diff: both files' SHA-256, both word counts, the finding, the tool
    -- that computed it and the tool's own SHA-256, and the export's and
    -- answered card's SHA-256 (the exports live under the git-ignored
    -- .artifacts/).
    evidence              jsonb NOT NULL CHECK (coalesce(
                              jsonb_typeof(evidence) = 'object'
                              AND (evidence->>'copy_sha256') ~ '^[0-9a-f]{64}$'
                              AND (evidence->>'canonical_sha256') ~ '^[0-9a-f]{64}$'
                              AND (evidence->>'copy_words') ~ '^[0-9]+$'
                              AND (evidence->>'canonical_words') ~ '^[0-9]+$'
                              AND evidence->>'finding' = 'page_furniture_only'
                              AND btrim(evidence->>'diff_tool') <> ''
                              AND (evidence->>'diff_tool_sha256') ~ '^[0-9a-f]{64}$'
                              AND (evidence->>'export_sha256') ~ '^[0-9a-f]{64}$'
                              AND (evidence->>'card_sha256') ~ '^[0-9a-f]{64}$',
                              false)),
    recorded_by           text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at           timestamptz NOT NULL DEFAULT now(),

    CHECK (document_id <> canonical_document_id)
);

CREATE INDEX source_same_text_copy_canonical
    ON source_same_text_copy(canonical_document_id);
-- A document is one landed file; it is a copy of at most one canonical.
CREATE UNIQUE INDEX source_same_text_copy_document
    ON source_same_text_copy(document_id);

CREATE FUNCTION check_source_same_text_copy() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    landed        text;
    copy_sha      text;
    canonical_sha text;
    cited         bigint;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'source_same_text_copy is append-only';
    END IF;
    -- Serialise inserts: the chain checks below read this table, and two
    -- concurrent inserts (A->B and B->A) would each pass them alone.
    PERFORM pg_advisory_xact_lock(hashtext('source_same_text_copy'));
    IF NEW.document_id = NEW.canonical_document_id THEN
        RETURN NEW;   -- left for the CHECK (document_id <> canonical_document_id)
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

    SELECT d.sha256 INTO canonical_sha
      FROM document d WHERE d.id = NEW.canonical_document_id AND d.is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'canonical document % is not an active document',
                        NEW.canonical_document_id;
    END IF;
    IF copy_sha = canonical_sha THEN
        RAISE EXCEPTION
          'documents % and % are the same file; a byte-identical copy is resolved '
          'by tools/resolve_exact_instrument_duplicates.py (0036), not here',
          NEW.document_id, NEW.canonical_document_id;
    END IF;
    -- BEFORE triggers run ahead of CHECK constraints: malformed evidence is
    -- left for the evidence CHECK to refuse by name.
    IF NEW.evidence->>'copy_sha256' IS DISTINCT FROM copy_sha
       AND (NEW.evidence->>'copy_sha256') ~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'evidence copy_sha256 % is not document %''s file %',
          NEW.evidence->>'copy_sha256', NEW.document_id, copy_sha;
    END IF;
    IF NEW.evidence->>'canonical_sha256' IS DISTINCT FROM canonical_sha
       AND (NEW.evidence->>'canonical_sha256') ~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'evidence canonical_sha256 % is not document %''s file %',
          NEW.evidence->>'canonical_sha256', NEW.canonical_document_id, canonical_sha;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM instrument i
                    WHERE i.document_id = NEW.canonical_document_id
                      AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION
          'canonical document % has no active canonical instrument; a copy is '
          'never retired in favour of nothing', NEW.canonical_document_id;
    END IF;

    IF EXISTS (SELECT 1 FROM source_same_text_copy s
                WHERE s.document_id = NEW.canonical_document_id) THEN
        RAISE EXCEPTION 'canonical document % is itself recorded as a copy',
                        NEW.canonical_document_id;
    END IF;
    IF EXISTS (SELECT 1 FROM source_same_text_copy s
                WHERE s.canonical_document_id = NEW.document_id) THEN
        RAISE EXCEPTION 'document % is the canonical of another copy',
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
    IF cited NOT IN (NEW.document_id, NEW.canonical_document_id) THEN
        RAISE EXCEPTION 'owner_decision cites document %, not % or %',
          cited, NEW.document_id, NEW.canonical_document_id;
    END IF;
    -- The answer must name the document it keeps: the link's direction is the
    -- owner's, never the recorder's.
    IF NEW.owner_decision->>'choice' IS DISTINCT FROM
       'keep-' || NEW.canonical_document_id::text THEN
        RAISE EXCEPTION
          'owner_decision choice % does not keep document %; the answer must read keep-%',
          NEW.owner_decision->>'choice', NEW.canonical_document_id,
          NEW.canonical_document_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER source_same_text_copy_guard
BEFORE INSERT OR UPDATE OR DELETE ON source_same_text_copy
FOR EACH ROW EXECUTE FUNCTION check_source_same_text_copy();

CREATE TRIGGER source_same_text_copy_no_truncate
BEFORE TRUNCATE ON source_same_text_copy
FOR EACH STATEMENT EXECUTE FUNCTION check_source_same_text_copy();

COMMENT ON TABLE source_same_text_copy IS
  'Append-only: a landed observation''s document prints the same legal text as '
  'a canonical document in a different file, differing only in page furniture, '
  'on a cited owner decision with the diff evidence. One record per '
  'observation. instrument.duplicate_of is derived from it after every replay '
  'by tools/apply_source_same_text_copy.py. Migration 0062.';

COMMIT;
