-- A portal PDF is not necessarily one legal instrument.  Compilations,
-- gazettes and consolidated manuals can contain several independently citable
-- Acts, Rules, Orders or Notifications.  Store boundary proposals separately
-- from S7 label proposals and fail closed until each boundary is rejected or
-- a corrected multi-expression materialisation supersedes the candidate tree.

BEGIN;

CREATE TABLE segmentation_boundary_candidate (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id         uuid NOT NULL REFERENCES instrument(id) ON DELETE RESTRICT,
    source_observation_id bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    document_id           bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    start_block_id        bigint NOT NULL REFERENCES text_block(id) ON DELETE RESTRICT,
    source_page           integer NOT NULL CHECK (source_page > 0),
    detected_title        text NOT NULL,
    detected_kind         text,
    detected_year         integer,
    detected_number       text,
    confidence            numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    method                text NOT NULL,
    evidence              jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    created_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (instrument_id,start_block_id,method)
);

CREATE INDEX boundary_candidate_observation
    ON segmentation_boundary_candidate(source_observation_id,source_page);
CREATE INDEX boundary_candidate_instrument
    ON segmentation_boundary_candidate(instrument_id);

CREATE TABLE segmentation_boundary_adjudication (
    id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id               uuid NOT NULL REFERENCES segmentation_boundary_candidate(id)
                                   ON DELETE RESTRICT,
    resolution                 text NOT NULL CHECK (resolution IN
                                  ('confirmed_split','not_boundary',
                                   'embedded_reference','needs_review')),
    review_basis               text NOT NULL CHECK (review_basis IN
                                  ('machine_evidenced','source_verified','human_verified')),
    method                     text NOT NULL,
    rationale                  text NOT NULL,
    evidence                   jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
    supersedes_adjudication_id uuid REFERENCES segmentation_boundary_adjudication(id)
                                   ON DELETE RESTRICT,
    decided_by                 text NOT NULL,
    decided_at                 timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX boundary_adjudication_head
    ON segmentation_boundary_adjudication(candidate_id)
    WHERE supersedes_adjudication_id IS NULL;

CREATE VIEW v_active_boundary_candidate AS
SELECT c.*
  FROM segmentation_boundary_candidate c
  JOIN instrument i ON i.id=c.instrument_id
                   AND i.is_active
                   AND i.duplicate_of IS NULL;

CREATE VIEW v_boundary_adjudication_latest AS
SELECT DISTINCT ON (a.candidate_id) a.*
  FROM segmentation_boundary_adjudication a
 ORDER BY a.candidate_id,a.decided_at DESC,a.id DESC;

-- A confirmed split remains blocking until the candidate's single-instrument
-- tree is superseded.  Only evidence that the signal is not a boundary closes
-- the candidate on the current tree.
CREATE VIEW v_boundary_adjudication_pending AS
SELECT c.*
  FROM v_active_boundary_candidate c
  LEFT JOIN v_boundary_adjudication_latest a ON a.candidate_id=c.id
 WHERE a.id IS NULL OR a.resolution IN ('confirmed_split','needs_review');

DROP VIEW v_release_provision_version;
DROP VIEW v_release_provision;
DROP VIEW v_release_instrument;

CREATE VIEW v_release_instrument AS
SELECT i.*
  FROM instrument i
  JOIN v_document_quality_status q ON q.document_id=i.document_id
  JOIN segmentation_run r ON r.instrument_id=i.id
 WHERE i.is_active
   AND i.duplicate_of IS NULL
   AND q.overall_outcome='passed'
   AND r.outcome='segmented'
   AND (NOT r.toc_found OR coalesce(r.toc_missing,0)=0)
   AND NOT EXISTS (
       SELECT 1 FROM v_structural_adjudication_pending p
        WHERE p.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_boundary_adjudication_pending b
        WHERE b.instrument_id=i.id);

CREATE VIEW v_release_provision AS
SELECT p.*
  FROM provision p
  JOIN v_release_instrument i ON i.id=p.instrument_id
 WHERE p.is_active;

CREATE VIEW v_release_provision_version AS
SELECT v.*
  FROM provision_version v
  JOIN v_release_provision p ON p.id=v.provision_id;

COMMENT ON TABLE segmentation_boundary_candidate IS
  'Immutable, source-block-anchored proposal that one official PDF contains another legal instrument boundary.';
COMMENT ON TABLE segmentation_boundary_adjudication IS
  'Append-only legal/technical review of a proposed multi-instrument boundary.';
COMMENT ON VIEW v_boundary_adjudication_pending IS
  'Active canonical boundary signals not disproved on the current tree; confirmed splits block until materialised.';
COMMENT ON VIEW v_release_instrument IS
  'Fail-closed quality, identity, S7, printed-contents and multi-instrument-boundary publication boundary.';

COMMIT;
