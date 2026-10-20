-- An append-only withdrawal of a recorded contents disposition.
--
-- `toc_disposition_assertion` (0045, 0046, 0052) records that a printed
-- contents row denotes an omitted or repealed section, and the segmenter
-- materialises an empty operation='omitted' provision_version from the latest
-- assertion per printed entry (`v_toc_disposition_assertion_latest`). There was
-- no way to say "this disposition no longer applies": a superseding row must
-- itself name 'omitted' or 'repealed' (0052's header says so in terms), the
-- table has no immutability guard but is evidence and must not be edited, and
-- the one prior withdrawal (doc 2783, 24 Sep) was a guarded DELETE of a row no
-- tree had yet referenced -- a path that is closed once provision_version
-- points at the assertion (FK ON DELETE RESTRICT).
--
-- The case that forced the decision: document 1457, the Sind Speaker's and
-- Deputy Speaker's (Salaries, Allowances and Privileges) Act 1975 (observation
-- 3253). Assertion 17 (openai.codex, 11 Sep) reads contents row "15
-- Repealed." as a repealed section 15; seven provision_version rows, one in the
-- active tree, cite it. The contents predates the 1995 renumbering the body
-- carries, and the owner answered (decision-review-2026-10-08-f.json, document
-- 1457, q1 'body') that the body numbering governs: contents row 15 is section
-- 19, the repeal section, which stays in force -- no repeal disposition is
-- applied. Left standing, the assertion would make s.19 an empty stub. The
-- owner decided on 8 Oct (CLAUDE-CLAIMS.md) to withdraw it append-only.
--
-- WHAT THIS ADDS
--
--   * `toc_disposition_withdrawal`: one row per withdrawn assertion (UNIQUE),
--     naming the owner decision it rests on and the evidence. Append-only:
--     UPDATE, DELETE and TRUNCATE are refused. The assertion row is untouched
--     and stays on record; the FK (RESTRICT) also closes the DELETE path for a
--     withdrawn assertion.
--   * `v_toc_disposition_assertion_latest` keeps its exact columns and its
--     0046 identity (observation, expression, source block, printed label) but
--     drops a key whose LATEST assertion is withdrawn. It does not fall back to
--     an older assertion in the same chain: a withdrawal removes the standing
--     judgement, it does not resurrect the one that judgement superseded. Every
--     consumer (nizam.storage.legal_write.toc_dispositions_for -> the segment
--     worker and the probes, tools/materialize_toc_dispositions.py,
--     tools/review_toc_dispositions.py) reads this view, so no Python reader
--     changes.
--   * A guard on new assertions: once the latest assertion for a printed entry
--     is withdrawn, a new assertion for that entry is admitted only as an
--     explicit supersession of the withdrawn row (supersedes_id = it). A bulk
--     re-run of the detector cannot silently re-assert what the owner withdrew.
--
-- WHAT A WITHDRAWAL MAY TOUCH. Only the governing (latest) assertion of its
-- printed entry, and only while NO instrument built from the assertion's
-- source observation is released (v_release_instrument) -- the same rule 0056
-- applies to profile pins. A released tree is never changed by this route;
-- withdrawing a disposition under a released instrument is a correction that
-- needs its own review and its own migration.
--
-- RELEASED REPLAY IS UNAFFECTED. The table is created empty, so the view
-- returns exactly the rows it returned before; no assertion is withdrawn
-- except by an explicit recorded row (tools/withdraw_toc_disposition.py).
--
-- A withdrawal changes no tree by itself. The active tree of an affected
-- document keeps its omitted version (and its reference to the assertion)
-- until the document is replayed; the replay then builds without the
-- disposition. Superseded trees keep their references -- they are history.
--
-- REVERSAL (explicitly irreversible once a withdrawal row exists, per docs/03
-- §9): with the table empty, restore 0046's view definition, then drop the
-- triggers, the functions and the table.
--
-- Governing contract: docs/02 §5 and §8 (the contents list is source evidence;
-- a lifecycle fact is materialised only from a standing reviewed record);
-- docs/03 §9 (migrations, append-only evidence); docs/SCHEMA.md.

BEGIN;

CREATE TABLE toc_disposition_withdrawal (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assertion_id    bigint NOT NULL UNIQUE
                        REFERENCES toc_disposition_assertion(id)
                        ON DELETE RESTRICT,
    reason          text NOT NULL CHECK (btrim(reason) <> ''),
    -- The owner decision-review answer the withdrawal rests on, as
    -- nizam.workers.segment.owner_decision_answer cites one, plus the choice
    -- so the record reads on its own (the exports live under the git-ignored
    -- .artifacts/).
    -- Every test is wrapped in coalesce(..., false): a CHECK that evaluates to
    -- NULL passes, and ->> of an absent or JSON-null key is NULL.
    owner_decision  jsonb NOT NULL CHECK (coalesce(
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
    -- What the export held when the withdrawal was recorded: its SHA-256 and
    -- the answered card's SHA-256, so the citation is checkable after the
    -- export file is gone.
    evidence        jsonb NOT NULL CHECK (coalesce(
                        jsonb_typeof(evidence) = 'object'
                        AND (evidence->>'export_sha256') ~ '^[0-9a-f]{64}$'
                        AND (evidence->>'card_sha256') ~ '^[0-9a-f]{64}$',
                        false)),
    withdrawn_by    text NOT NULL CHECK (btrim(withdrawn_by) <> ''),
    withdrawn_at    timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION toc_disposition_withdrawal_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    target    toc_disposition_assertion%ROWTYPE;
    governing bigint;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'toc_disposition_withdrawal is append-only';
    END IF;

    SELECT * INTO target FROM toc_disposition_assertion
     WHERE id = NEW.assertion_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'toc_disposition_assertion % does not exist',
                        NEW.assertion_id;
    END IF;

    -- Only the standing judgement for its printed entry may be withdrawn;
    -- withdrawing a superseded row would change nothing and read as if it had.
    SELECT a.id INTO governing
      FROM toc_disposition_assertion a
     WHERE a.source_observation_id = target.source_observation_id
       AND a.expression_ordinal    = target.expression_ordinal
       AND a.source_block_id       = target.source_block_id
       AND a.printed_label         = target.printed_label
     ORDER BY a.reviewed_at DESC, a.id DESC
     LIMIT 1;
    IF governing IS DISTINCT FROM target.id THEN
        RAISE EXCEPTION
          'toc_disposition_assertion % is superseded by %; withdraw the governing assertion',
          target.id, governing;
    END IF;

    -- The released boundary is never moved by this route (as 0056).
    IF EXISTS (SELECT 1 FROM v_release_instrument r
                WHERE r.source_observation_id = target.source_observation_id) THEN
        RAISE EXCEPTION
          'observation % has a released instrument; a withdrawal cannot change a released tree',
          target.source_observation_id;
    END IF;

    -- The owner decision must be about this assertion's document. BEFORE
    -- triggers run ahead of CHECK constraints: a malformed citation is left
    -- for the owner_decision CHECK to refuse by name, not failed here on a cast.
    IF coalesce((NEW.owner_decision->>'document_id') ~ '^[1-9][0-9]{0,17}$',
                false) IS NOT TRUE THEN
        RETURN NEW;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM instrument i
         WHERE i.source_observation_id = target.source_observation_id
           AND i.document_id = (NEW.owner_decision->>'document_id')::bigint
    ) THEN
        RAISE EXCEPTION
          'owner_decision cites document %, which observation % was never built from',
          NEW.owner_decision->>'document_id', target.source_observation_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER toc_disposition_withdrawal_guard
BEFORE INSERT OR UPDATE OR DELETE ON toc_disposition_withdrawal
FOR EACH ROW EXECUTE FUNCTION toc_disposition_withdrawal_guard();

CREATE TRIGGER toc_disposition_withdrawal_no_truncate
BEFORE TRUNCATE ON toc_disposition_withdrawal
FOR EACH STATEMENT EXECUTE FUNCTION toc_disposition_withdrawal_guard();

-- A withdrawn entry is re-asserted only deliberately: as a supersession of the
-- withdrawn row. A separate function and trigger, so 0052's
-- check_toc_disposition_assertion() -- which every assertion passes through --
-- is not redefined here.
CREATE FUNCTION check_toc_disposition_not_withdrawn() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    governing bigint;
BEGIN
    SELECT a.id INTO governing
      FROM toc_disposition_assertion a
     WHERE a.source_observation_id = NEW.source_observation_id
       AND a.expression_ordinal    = NEW.expression_ordinal
       AND a.source_block_id       = NEW.source_block_id
       AND a.printed_label         = NEW.printed_label
     ORDER BY a.reviewed_at DESC, a.id DESC
     LIMIT 1;
    IF governing IS NOT NULL
       AND EXISTS (SELECT 1 FROM toc_disposition_withdrawal w
                    WHERE w.assertion_id = governing)
       AND NEW.supersedes_id IS DISTINCT FROM governing THEN
        RAISE EXCEPTION
          'the disposition for this contents entry was withdrawn (assertion %); '
          're-assert only as supersedes_id = %', governing, governing;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER toc_disposition_assertion_withdrawn_guard
BEFORE INSERT ON toc_disposition_assertion
FOR EACH ROW EXECUTE FUNCTION check_toc_disposition_not_withdrawn();

-- Same columns, same order, same 0046 identity; a key whose latest assertion is
-- withdrawn yields no row (no fallback to the row that one superseded).
CREATE OR REPLACE VIEW v_toc_disposition_assertion_latest AS
SELECT l.*
  FROM (SELECT DISTINCT ON
               (source_observation_id,expression_ordinal,source_block_id,printed_label) a.*
          FROM toc_disposition_assertion a
         ORDER BY source_observation_id,expression_ordinal,source_block_id,printed_label,
                  reviewed_at DESC,id DESC) l
 WHERE NOT EXISTS (SELECT 1 FROM toc_disposition_withdrawal w
                    WHERE w.assertion_id = l.id);

COMMENT ON TABLE toc_disposition_withdrawal IS
  'Append-only: a recorded toc_disposition_assertion that no longer applies, on '
  'a cited owner decision. The assertion stays on record; '
  'v_toc_disposition_assertion_latest drops its entry. Refused for a superseded '
  'assertion or an observation with a released instrument. Migration 0061.';
COMMENT ON VIEW v_toc_disposition_assertion_latest IS
  'Standing disposition per printed contents entry (observation, expression, '
  'source block, printed label): the latest assertion, unless that assertion is '
  'withdrawn (0061), in which case the entry has none.';

COMMIT;
