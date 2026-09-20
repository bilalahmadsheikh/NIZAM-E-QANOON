-- A recorded census of provisions whose heading is not the name the source
-- prints for them, and a watermark that says which corpus it was measured on.
--
-- THE DEFECT CLASS.  A citation that resolves to the RIGHT TEXT under the WRONG
-- NAME.  Doc 4499 (Industrial Relations Act, 2008) prints on p.30
--
--     37. Penalty for obstructing inspector.  Whoever willfully obstructs ...
--
-- while its printed contents lists that name at 36, because the list omits a
-- section the body enacts.  Pairing on the number alone gave section 37 the
-- name of 38 for twenty-two consecutive sections.  Nothing in the audit sees
-- it: an offset contents list still finds a same-numbered provision for every
-- entry, so it produces no unmatched entry and no gap.  A5 passes, A9 passes,
-- A10 passes, and the gap queue is empty for the worst affected documents.
-- `tools/audit/heading-not-the-provisions-own.sql` documents the class and the
-- four false-positive guards that four successive rounds of review added to it.
--
-- WHY THE NUMBER IS STORED RATHER THAN COMPUTED.  Guard 4 -- "one name written
-- two ways is one name" -- needs per-token fuzzy matching and initialism
-- detection.  The Code of Criminal Procedure's contents prints "Issues of
-- process" where its body prints "Issus of process"; doc 2511 prints "Welfare
-- Fund" against a carried "Punjab Employees Welfare Fund", truncated at the
-- FRONT, which prefix comparison misses; doc 2582 abbreviates "Agriculture
-- Pesticide Technical Advisory Committee" to "APTA".  Written as SQL where
-- `criteria.sql` computes its values, with guards 1-3 plus prefix containment
-- and no token comparison, the rule was MEASURED at 472 rows in 221 documents
-- against a true count of 101 -- 4.7x, concentrated in the CrPC (44), the
-- Customs Act (14), the PAF Act (13), the Army Act (11), the Constitution (11)
-- and the PPC (11).  An A11 printing 472 would be a worse artefact than no A11.
-- The detector therefore stays in `tools/census_heading_mislabel.py`, and this
-- is where it records what it found.
--
-- A STORED NUMBER IS A LIE THE MOMENT THE CORPUS MOVES.  That is the whole
-- difficulty, and the reason this migration is more than a table.  A criterion
-- reading a cached census must be able to prove the census describes the corpus
-- it is auditing, and must say "stale" rather than report a stale PASS.
-- `v_heading_mislabel_corpus_state` is that proof, and the census tool and the
-- audit read the SAME definition of it so the two cannot drift.
--
-- THREE WATERMARKS WERE MEASURED on this corpus (20 September 2026, during a
-- full `--all --redo` replay, which is exactly the condition a staleness test
-- has to survive):
--
--   * count of active instruments -- 4,692 rows, 7 ms.  REJECTED, and not on
--     cost.  Re-segmentation is append-only (0012): it retires one instrument
--     and appends its replacement, so the count is unchanged by the very event
--     that invalidates a census.  751 documents had been re-segmented that day
--     and the count had not moved once.  A watermark blind to the commonest
--     corpus change is not a watermark.
--
--   * max(instrument.created_at) / max(retired_at) -- 8 ms.  REJECTED.  It does
--     advance on every re-segmentation, but it is a clock, not an identity: it
--     answers "has anything happened since?" and not "is this census about THIS
--     corpus?"  It cannot see a `duplicate_of` flip by identity resolution
--     (0036), a retirement with no replacement, or a restore that moves the
--     corpus backwards to an earlier state -- after which the census would read
--     fresh while describing a tree that no longer exists.
--
--   * md5 over the census population itself -- 83,184 rows, 212 ms warm.
--     CHOSEN.  It is not a proxy for the thing that matters; it IS the thing
--     that matters, digesting exactly the columns the detector reads.  It
--     changes if a provision enters or leaves the scope (which covers every
--     re-segmentation, retirement and duplicate flip), if a heading changes, if
--     a label changes, or if a provision is re-anchored to a different block.
--     It moves in both directions, so a restore is detected as surely as a run.
--     212 ms is not material next to an audit that already walks the recursive
--     ancestor closure of 517,171 provisions.
--
--     It relies on one property, stated here so a future change cannot break it
--     silently: `text_block` is IMMUTABLE (0012).  The detector parses the
--     printed opener out of `text_block.text`, which is not in the digest --
--     only `first_block`, its id.  That is sufficient only while re-extraction
--     appends a new document revision and forces re-segmentation, which gives
--     the provisions new blocks and new ids.  If text_block ever becomes
--     mutable, this digest must grow a column and this comment must go.
--
-- WHAT IS STORED, AND WHAT IS NOT.  The census header carries no counts.  Every
-- number the criterion reports is derived from `heading_mislabel_finding`, so a
-- header and its findings cannot disagree -- a denormalised `mislabelled`
-- column would be a second place for the truth to live.  A census that found
-- NOTHING is still a row in the header, which is the state A11 is meant to
-- reach; "no findings" and "never measured" must not look alike.
--
-- `provision_id` is recorded WITHOUT a foreign key, deliberately.  A finding is
-- an observation about a corpus state named by `corpus_digest`, not a live
-- pointer.  ON DELETE CASCADE would let the archive-and-prune workflow
-- (tools/prune_retired_instruments.sql) quietly delete evidence of what a past
-- census saw; ON DELETE RESTRICT would make a recorded census block a prune.
-- Neither is right for a measurement record, so it references nothing and the
-- finding survives the tree it describes, exactly as the evidence tables do.
--
-- Governing contract: docs/02-corpus-and-ingestion.html section 8 (the audit
-- criteria), docs/CORPUS-CRITERIA.md (A11).

BEGIN;

-- Idempotent throughout.  0051 had to be made idempotent after the fact, when a
-- lock contention left the schema ahead of `schema_migration` and the file
-- could not be re-run to record itself -- the one state doc 09a section 7 does
-- not permit.  Every statement below can meet any partial state of its own
-- previous run.

CREATE TABLE IF NOT EXISTS heading_mislabel_census (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    measured_at        timestamptz NOT NULL DEFAULT now(),
    -- Who ran it, and with what.  The detector's own hash is recorded because
    -- a census is only replayable against the code that produced it: changing
    -- a guard in census_heading_mislabel.py changes the number without moving
    -- the corpus by a single row.  The audit cannot check this -- SQL cannot
    -- read a file -- so it is evidence, not a gate.
    measured_by        text NOT NULL CHECK (btrim(measured_by) <> ''),
    detector           text NOT NULL CHECK (btrim(detector) <> ''),
    detector_sha256    char(64) NOT NULL CHECK (detector_sha256 ~ '^[0-9a-f]{64}$'),
    -- The corpus this census describes.  See v_heading_mislabel_corpus_state.
    corpus_digest      char(32) NOT NULL CHECK (corpus_digest ~ '^[0-9a-f]{32}$'),
    scope_provisions   bigint  NOT NULL CHECK (scope_provisions >= 0),
    active_instruments integer NOT NULL CHECK (active_instruments >= 0),
    detail             jsonb   NOT NULL DEFAULT '{}'::jsonb
                           CHECK (jsonb_typeof(detail) = 'object')
);

COMMENT ON TABLE heading_mislabel_census IS
    'One row per run of tools/census_heading_mislabel.py: when it ran, what '
    'ran it, and the digest of the corpus population it read. Carries no '
    'counts; they are derived from heading_mislabel_finding.';

CREATE TABLE IF NOT EXISTS heading_mislabel_finding (
    census_id      bigint NOT NULL REFERENCES heading_mislabel_census(id)
                       ON DELETE CASCADE,
    -- Identity of the unit as the census saw it. No FK: see the note above.
    provision_id   uuid NOT NULL,
    instrument_id  uuid NOT NULL,
    document_id    bigint NOT NULL,
    short_title    text,
    kind           text NOT NULL CHECK (btrim(kind) <> ''),
    label          text NOT NULL CHECK (btrim(label) <> ''),
    first_page     integer,
    -- The disagreement itself, both sides of it, so a reviewer can settle the
    -- row from the record and does not have to re-run the detector to see what
    -- it objected to.
    tree_heading   text NOT NULL CHECK (btrim(tree_heading) <> ''),
    printed_name   text NOT NULL CHECK (btrim(printed_name) <> ''),
    block_excerpt  text,
    -- 'different_name' is the defect A11 gates on: the citation resolves to
    -- mis-labelled text. 'variant_spelling' is the same name set two ways --
    -- reported so the boundary between the two classes stays auditable, never
    -- gated. Guard 4 exists because calling those mis-citations would have put
    -- 62 CrPC sections on the list.
    finding_class  text NOT NULL CHECK (finding_class IN
                       ('different_name', 'variant_spelling')),
    similarity     numeric(4,3) CHECK (similarity IS NULL
                       OR (similarity >= 0 AND similarity <= 1)),
    -- Whether a printed contents entry actually resolves to this provision:
    -- the difference between a name a user can reach by citation and one only
    -- a browse can reach.
    toc_linked     boolean NOT NULL,
    PRIMARY KEY (census_id, provision_id)
);

COMMENT ON TABLE heading_mislabel_finding IS
    'One row per provision whose heading is not the name its own printed block '
    'gives it, as of one census. A measurement record, not a live reference: '
    'it outlives the provision tree it describes.';

CREATE INDEX IF NOT EXISTS heading_mislabel_finding_class
    ON heading_mislabel_finding (census_id, finding_class);
CREATE INDEX IF NOT EXISTS heading_mislabel_finding_document
    ON heading_mislabel_finding (document_id);
CREATE INDEX IF NOT EXISTS heading_mislabel_census_measured
    ON heading_mislabel_census (measured_at DESC, id DESC);

-- ---------------------------------------------------------------------------
-- The corpus state, defined ONCE.  The census tool records what this returns;
-- the audit compares against what this returns.  One definition, in git, so the
-- writer and the reader cannot drift apart.
--
-- The population is exactly the detector's: an active provision of an active,
-- non-duplicate instrument, of a citable kind, that carries a heading and is
-- anchored to a block.  `first_block IS NOT NULL` is part of it because the
-- detector joins text_block on it -- a provision with no block is not in the
-- population and must not move the digest.
DROP VIEW IF EXISTS v_heading_mislabel_corpus_state;
CREATE VIEW v_heading_mislabel_corpus_state AS
SELECT md5(string_agg(
           p.id::text || '|' || p.kind::text || '|' || p.label || '|'
           || coalesce(p.heading, '') || '|' || p.first_block::text,
           E'\n' ORDER BY p.id))                                AS corpus_digest,
       count(*)                                                 AS scope_provisions,
       (SELECT count(*) FROM instrument
         WHERE is_active AND duplicate_of IS NULL)              AS active_instruments
  FROM provision p
  JOIN instrument i ON i.id = p.instrument_id
                   AND i.is_active AND i.duplicate_of IS NULL
 WHERE p.is_active
   AND p.first_block IS NOT NULL
   AND p.heading IS NOT NULL AND btrim(p.heading) <> ''
   AND p.kind::text IN ('section','article','rule','regulation','paragraph');

COMMENT ON VIEW v_heading_mislabel_corpus_state IS
    'The heading census population, digested. A census whose corpus_digest '
    'differs from this row is stale and its number describes a corpus that is '
    'no longer there. Measured 212 ms over 83,184 rows.';

-- The standing census, and whether it still describes the corpus.  An empty
-- table yields one row with `measured_at` NULL, so a caller can distinguish
-- "never measured" from "measured, found nothing" without a second query --
-- and cannot mistake either for a pass.
DROP VIEW IF EXISTS v_heading_mislabel_census_current;
CREATE VIEW v_heading_mislabel_census_current AS
SELECT c.id                                                     AS census_id,
       c.measured_at,
       c.measured_by,
       c.detector,
       c.detector_sha256,
       c.corpus_digest,
       c.scope_provisions,
       c.active_instruments,
       s.corpus_digest                                          AS live_digest,
       s.scope_provisions                                       AS live_scope_provisions,
       s.active_instruments                                     AS live_active_instruments,
       (c.id IS NULL)                                           AS never_measured,
       (c.id IS NULL OR c.corpus_digest IS DISTINCT FROM s.corpus_digest)
                                                                AS is_stale,
       (SELECT count(*) FROM heading_mislabel_finding f
         WHERE f.census_id = c.id
           AND f.finding_class = 'different_name')              AS mislabelled,
       (SELECT count(DISTINCT f.document_id) FROM heading_mislabel_finding f
         WHERE f.census_id = c.id
           AND f.finding_class = 'different_name')              AS mislabelled_documents,
       (SELECT count(*) FROM heading_mislabel_finding f
         WHERE f.census_id = c.id
           AND f.finding_class = 'variant_spelling')            AS variant_spellings
  FROM v_heading_mislabel_corpus_state s
  LEFT JOIN LATERAL (
       SELECT * FROM heading_mislabel_census
        ORDER BY measured_at DESC, id DESC LIMIT 1
  ) c ON true;

COMMENT ON VIEW v_heading_mislabel_census_current IS
    'The latest heading census beside the live corpus state. `is_stale` is '
    'true when the census describes a different corpus, and also when there is '
    'no census at all -- both are states in which no number may be reported as '
    'a pass. This is what criterion A11 reads.';

COMMIT;
