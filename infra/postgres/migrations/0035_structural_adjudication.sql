-- Item-level, source-anchored adjudication for repeated sibling labels (S7).
--
-- The segmenter must prevent two sibling citable units from sharing a label,
-- but its former evidence was only an aggregate count in segmentation_run.
-- That could not tell a reviewer what changed or whether the second occurrence
-- was a table row, form field, missed container, or appended instrument.  Keep
-- each proposal on the immutable instrument revision and record decisions as
-- append-only events.  Source text and prior trees are never updated or erased.

-- PostgreSQL requires new enum values to commit before a transaction uses
-- them. These are printed auxiliary containers, not synonyms for a Schedule.
ALTER TYPE provision_kind ADD VALUE IF NOT EXISTS 'form';
ALTER TYPE provision_kind ADD VALUE IF NOT EXISTS 'appendix';
ALTER TYPE provision_kind ADD VALUE IF NOT EXISTS 'annexure';
ALTER TYPE provision_kind ADD VALUE IF NOT EXISTS 'order';

BEGIN;

CREATE TABLE segmentation_structural_candidate (
    id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id              uuid NOT NULL REFERENCES instrument(id) ON DELETE RESTRICT,
    source_observation_id      bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    document_id                bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    candidate_provision_id     uuid NOT NULL REFERENCES provision(id) ON DELETE RESTRICT,
    canonical_provision_id     uuid NOT NULL REFERENCES provision(id) ON DELETE RESTRICT,
    parent_provision_id        uuid REFERENCES provision(id) ON DELETE RESTRICT,
    decision_kind              text NOT NULL CHECK (decision_kind='repeated_sibling_label'),
    original_kind              provision_kind NOT NULL,
    printed_label              text NOT NULL,
    source_block_id            bigint NOT NULL REFERENCES text_block(id) ON DELETE RESTRICT,
    source_page                integer NOT NULL CHECK (source_page>0),
    canonical_source_block_id  bigint NOT NULL REFERENCES text_block(id) ON DELETE RESTRICT,
    canonical_source_page      integer NOT NULL CHECK (canonical_source_page>0),
    proposed_resolution        text NOT NULL CHECK (proposed_resolution IN
                                  ('retype_non_citable','restore_citable',
                                   'reparent','split_instrument')),
    segmenter                  text NOT NULL,
    evidence                   jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    created_at                 timestamptz NOT NULL DEFAULT now(),
    UNIQUE (instrument_id,candidate_provision_id,decision_kind),
    CHECK (candidate_provision_id<>canonical_provision_id)
);

CREATE INDEX structural_candidate_observation
    ON segmentation_structural_candidate(source_observation_id,created_at DESC);
CREATE INDEX structural_candidate_instrument
    ON segmentation_structural_candidate(instrument_id);

CREATE TABLE segmentation_structural_adjudication (
    id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id               uuid NOT NULL REFERENCES segmentation_structural_candidate(id)
                                   ON DELETE RESTRICT,
    resolution                 text NOT NULL CHECK (resolution IN
                                  ('accept_non_citable','restore_citable',
                                   'reparent','split_instrument','reject_candidate')),
    review_basis               text NOT NULL CHECK (review_basis IN
                                  ('machine_evidenced','source_verified','human_verified')),
    method                     text NOT NULL,
    rationale                  text NOT NULL,
    evidence                   jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    supersedes_adjudication_id uuid REFERENCES segmentation_structural_adjudication(id)
                                   ON DELETE RESTRICT,
    decided_by                 text NOT NULL,
    decided_at                 timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX structural_adjudication_head
    ON segmentation_structural_adjudication(candidate_id)
    WHERE supersedes_adjudication_id IS NULL;

CREATE VIEW v_active_structural_candidate AS
SELECT c.*
  FROM segmentation_structural_candidate c
  JOIN instrument i ON i.id=c.instrument_id AND i.is_active;

CREATE VIEW v_structural_adjudication_latest AS
SELECT DISTINCT ON (a.candidate_id) a.*
  FROM segmentation_structural_adjudication a
 ORDER BY a.candidate_id,a.decided_at DESC,a.id DESC;

CREATE VIEW v_structural_adjudication_pending AS
SELECT c.*
  FROM v_active_structural_candidate c
  LEFT JOIN v_structural_adjudication_latest a ON a.candidate_id=c.id
 WHERE a.id IS NULL;

-- Application-facing legal views fail closed.  Extraction release views remain
-- useful for review, while citable reads see only quality-passed documents with
-- no unresolved structural proposal.
CREATE VIEW v_release_instrument AS
SELECT i.*
  FROM instrument i
  JOIN v_document_quality_status q ON q.document_id=i.document_id
 WHERE i.is_active
   AND q.overall_outcome='passed'
   AND NOT EXISTS (
       SELECT 1 FROM v_structural_adjudication_pending p
        WHERE p.instrument_id=i.id);

CREATE VIEW v_release_provision AS
SELECT p.*
  FROM provision p
  JOIN v_release_instrument i ON i.id=p.instrument_id
 WHERE p.is_active;

CREATE VIEW v_release_provision_version AS
SELECT v.*
  FROM provision_version v
  JOIN v_release_provision p ON p.id=v.provision_id;

COMMENT ON TABLE segmentation_structural_candidate IS
  'Immutable parser proposal for an S7 collision, anchored to both source blocks and one tree revision.';
COMMENT ON TABLE segmentation_structural_adjudication IS
  'Append-only decision event; machine evidence is named separately from source/human verification.';
COMMENT ON VIEW v_release_instrument IS
  'Fail-closed legal-expression boundary: extraction quality passed and no structural decision pending.';

COMMIT;
