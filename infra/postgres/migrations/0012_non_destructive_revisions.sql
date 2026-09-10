-- 0012  non-destructive extraction and segmentation revisions
--
-- Corpus evidence is append-only.  Re-running an extractor or segmenter must
-- never erase the pages, blocks, tree, or block assignments produced by an
-- earlier run.  An official observation is also not a duplicate merely because
-- it points at byte-identical content: each observation remains a separately
-- segmentable expression until legal identity resolution is reviewed.
--
-- Document 02 sections 3, 7 and 8: observations, bytes, expressions and legal
-- identity are different rungs; failures and earlier attempts remain evidence.
-- Document 03 section 6: promotion is transactional and active data is a view
-- over retained revisions, not the result of DELETE-and-rebuild.

-- PostgreSQL requires a newly-added enum label to commit before it is used.
ALTER TYPE lifecycle_state ADD VALUE IF NOT EXISTS 'unknown' BEFORE 'in_force';

BEGIN;

-- ---------------------------------------------------------------- extraction
-- Keep every extracted expression.  Exactly one revision of the same bytes,
-- language and publication role is active; older revisions retain all pages
-- and text blocks and point forward through supersedes_document_id.
ALTER TABLE document
    DROP CONSTRAINT IF EXISTS document_sha256_language_publication_role_extractor_key;

ALTER TABLE document
    ADD COLUMN is_active boolean NOT NULL DEFAULT true,
    ADD COLUMN supersedes_document_id bigint REFERENCES document(id) ON DELETE RESTRICT,
    ADD COLUMN retired_at timestamptz,
    ADD COLUMN verification_state text NOT NULL DEFAULT 'unverified'
        CHECK (verification_state IN ('unverified','passed','review','rejected'));

CREATE UNIQUE INDEX uq_document_active_expression
    ON document (sha256, language, publication_role) WHERE is_active;
CREATE INDEX document_revision_chain ON document (supersedes_document_id)
    WHERE supersedes_document_id IS NOT NULL;

-- ------------------------------------------------------------- legal revision
-- An instrument is one portal observation interpreted as a legal expression.
-- Byte-identical observations are deliberately not collapsed.  Re-segmenting
-- one observation retires only its previous materialisation.
ALTER TABLE instrument
    ADD COLUMN source_observation_id bigint REFERENCES source_observation(id) ON DELETE RESTRICT,
    ADD COLUMN is_active boolean NOT NULL DEFAULT true,
    ADD COLUMN supersedes_instrument_id uuid REFERENCES instrument(id) ON DELETE RESTRICT,
    ADD COLUMN retired_at timestamptz,
    ADD COLUMN verification_state text NOT NULL DEFAULT 'unverified'
        CHECK (verification_state IN ('unverified','passed','review','rejected'));

-- Choose the observation that best explains each existing materialisation.
-- Jurisdiction match is decisive; exact portal title is the second vote.  No
-- observation is deleted and every other observation remains available for its
-- own expression on the next segmentation pass.
WITH ranked AS (
    SELECT i.id AS instrument_id,o.id,o.canonical_url,
           row_number() OVER (
             PARTITION BY i.id
             ORDER BY
               (CASE o.source_id
                  WHEN 'pk-federal' THEN 'fed'
                  WHEN 'pk-punjab' THEN 'punjab'
                  WHEN 'pk-sindh' THEN 'sindh'
                  WHEN 'pk-kp' THEN 'kp'
                  WHEN 'pk-balochistan' THEN 'balochistan'
                  ELSE '' END = i.jurisdiction::text) DESC,
               (o.source_metadata->>'title'=i.short_title) DESC,
               o.fetched_at DESC NULLS LAST,o.id) AS rn
      FROM instrument i JOIN source_observation o
        ON o.sha256=i.source_sha256 AND o.outcome='landed'
), pick AS (SELECT * FROM ranked WHERE rn=1)
UPDATE instrument i
   SET source_observation_id=pick.id,
       source_url=coalesce(i.source_url,pick.canonical_url)
  FROM pick WHERE i.id=pick.instrument_id AND i.source_observation_id IS NULL;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM instrument WHERE source_observation_id IS NULL) THEN
    RAISE EXCEPTION 'cannot prove a source observation for every existing instrument';
  END IF;
END $$;

ALTER TABLE instrument ALTER COLUMN source_observation_id SET NOT NULL;
DROP INDEX IF EXISTS uq_instrument_document;
CREATE UNIQUE INDEX uq_instrument_active_observation
    ON instrument (source_observation_id) WHERE is_active;
CREATE INDEX instrument_revision_chain ON instrument (supersedes_instrument_id)
    WHERE supersedes_instrument_id IS NOT NULL;

-- A canonical path is stable inside an expression revision.  It is allowed to
-- recur in an older retained revision of the same observation.
ALTER TABLE provision DROP CONSTRAINT IF EXISTS uq_provision_path;
ALTER TABLE provision ADD CONSTRAINT uq_provision_instrument_path
    UNIQUE (instrument_id, path);

-- ------------------------------------------------------- assignment revisions
-- provision_block used block_id as its primary key, forcing a re-segmentation
-- to delete the previous assignment.  Group assignments into immutable sets.
CREATE TABLE block_assignment_set (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id           bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    source_observation_id bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    instrument_id         uuid REFERENCES instrument(id) ON DELETE RESTRICT,
    segmenter             text NOT NULL DEFAULT 'legacy-before-0012',
    is_active             boolean NOT NULL DEFAULT true,
    supersedes_set_id     uuid REFERENCES block_assignment_set(id) ON DELETE RESTRICT,
    retired_at            timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),
    CHECK ((instrument_id IS NULL) OR is_active OR retired_at IS NOT NULL)
);

CREATE UNIQUE INDEX uq_assignment_active_observation
    ON block_assignment_set (source_observation_id) WHERE is_active;
CREATE INDEX assignment_document ON block_assignment_set (document_id, created_at DESC);

INSERT INTO block_assignment_set
       (document_id, source_observation_id, instrument_id, segmenter)
SELECT d.id,
       coalesce(i.source_observation_id, pick.id),
       i.id,
       'legacy-before-0012'
  FROM document d
  LEFT JOIN instrument i ON i.document_id = d.id AND i.is_active
  LEFT JOIN LATERAL (
       SELECT o.id FROM source_observation o
        WHERE o.sha256=d.sha256 AND o.outcome='landed'
        ORDER BY o.fetched_at DESC NULLS LAST, o.id LIMIT 1
  ) pick ON true
 WHERE EXISTS (SELECT 1 FROM provision_block pb WHERE pb.document_id=d.id);

ALTER TABLE provision_block ADD COLUMN assignment_set_id uuid;
UPDATE provision_block pb
   SET assignment_set_id = s.id
  FROM block_assignment_set s
 WHERE s.document_id=pb.document_id;

-- The broad UPDATE above is safe for the existing one-instrument-per-document
-- state.  Refuse migration rather than guess if that invariant is not true.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM provision_block WHERE assignment_set_id IS NULL) THEN
    RAISE EXCEPTION 'could not place every legacy block assignment in a revision set';
  END IF;
END $$;

ALTER TABLE provision_block ALTER COLUMN assignment_set_id SET NOT NULL;
ALTER TABLE provision_block DROP CONSTRAINT provision_block_pkey;
ALTER TABLE provision_block ADD PRIMARY KEY (assignment_set_id, block_id);
ALTER TABLE provision_block ADD CONSTRAINT provision_block_assignment_set_fkey
    FOREIGN KEY (assignment_set_id) REFERENCES block_assignment_set(id) ON DELETE RESTRICT;

-- A run identifies the official observation it processed, not only shared bytes.
ALTER TABLE segmentation_run
    ADD COLUMN source_observation_id bigint REFERENCES source_observation(id) ON DELETE RESTRICT;
UPDATE segmentation_run r SET source_observation_id=i.source_observation_id
  FROM instrument i WHERE r.instrument_id=i.id AND r.source_observation_id IS NULL;
UPDATE segmentation_run r SET source_observation_id=pick.id
  FROM document d
  CROSS JOIN LATERAL (
      SELECT o.id FROM source_observation o
       WHERE o.sha256=d.sha256 AND o.outcome='landed'
       ORDER BY o.fetched_at DESC NULLS LAST, o.id LIMIT 1
  ) pick
 WHERE r.document_id=d.id AND r.source_observation_id IS NULL;
ALTER TABLE segmentation_run ALTER COLUMN source_observation_id SET NOT NULL;
CREATE INDEX segmentation_run_observation
    ON segmentation_run (source_observation_id, run_at DESC);

-- --------------------------------------------------------------- provenance
CREATE TABLE instrument_source (
    instrument_id        uuid NOT NULL REFERENCES instrument(id) ON DELETE RESTRICT,
    source_observation_id bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    role                 text NOT NULL DEFAULT 'primary'
                         CHECK (role IN ('primary','supporting','conflicting')),
    PRIMARY KEY (instrument_id, source_observation_id)
);
INSERT INTO instrument_source (instrument_id, source_observation_id, role)
SELECT id, source_observation_id, 'primary' FROM instrument;

-- Preserve proof that the former in_force value was an ingestion default, then
-- correct the active claim to unknown.  This changes no source text.
CREATE TABLE instrument_status_assertion (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instrument_id         uuid NOT NULL REFERENCES instrument(id) ON DELETE RESTRICT,
    asserted_status       lifecycle_state NOT NULL,
    source_observation_id bigint REFERENCES source_observation(id) ON DELETE RESTRICT,
    method                text NOT NULL,
    review_state          text NOT NULL CHECK (review_state IN ('candidate','accepted','rejected')),
    evidence              jsonb NOT NULL DEFAULT '{}'::jsonb,
    recorded_at           timestamptz NOT NULL DEFAULT now()
);
INSERT INTO instrument_status_assertion
       (instrument_id, asserted_status, source_observation_id, method, review_state, evidence)
SELECT id, status, source_observation_id, 'legacy_schema_default', 'rejected',
       jsonb_build_object('reason','No commencement or status evidence populated before migration 0012')
  FROM instrument WHERE status='in_force' AND commenced_on IS NULL AND repealed_on IS NULL;
UPDATE instrument SET status='unknown'
 WHERE status='in_force' AND commenced_on IS NULL AND repealed_on IS NULL;
ALTER TABLE instrument ALTER COLUMN status SET DEFAULT 'unknown';

-- ---------------------------------------------------------- active-only views
DROP VIEW v_document;
CREATE VIEW v_document AS
SELECT d.id AS document_id, d.sha256, o.source_id,
       o.source_metadata->>'title' AS title,
       coalesce(o.source_metadata->>'year',o.source_metadata->>'year_or_dept') AS year,
       coalesce(o.source_metadata->>'type',o.source_metadata->>'doc_type') AS doc_type,
       o.id AS source_observation_id, o.canonical_url,
       o.source_metadata->>'archive_path' AS archive_path,
       d.language,d.page_count,d.char_count,d.printable_ratio,d.empty_pages,
       d.lane,d.extractor,d.extracted_at,b.byte_length
  FROM document d JOIN blob b ON b.sha256=d.sha256
  LEFT JOIN LATERAL (
       SELECT so.* FROM source_observation so
        WHERE so.sha256=d.sha256 AND so.outcome='landed'
        ORDER BY (so.source_metadata->>'title') IS NULL,so.fetched_at,so.id LIMIT 1
  ) o ON true
 WHERE d.is_active;

CREATE OR REPLACE VIEW v_extract_queue AS
SELECT DISTINCT ON (o.sha256) o.sha256,o.source_id,o.object_key,o.byte_length,
       o.source_metadata->>'title' AS title,a.outcome AS last_outcome,
       a.reason AS last_reason,a.attempted_at AS last_attempt
  FROM source_observation o
  LEFT JOIN document d ON d.sha256=o.sha256 AND d.is_active
  LEFT JOIN LATERAL (
       SELECT ea.* FROM extraction_attempt ea WHERE ea.sha256=o.sha256
        ORDER BY ea.attempted_at DESC LIMIT 1) a ON true
 WHERE o.outcome='landed' AND o.sha256 IS NOT NULL AND d.id IS NULL
 ORDER BY o.sha256,(o.source_metadata->>'title') IS NULL,o.byte_length;

CREATE OR REPLACE VIEW v_corpus_health AS
SELECT b.source_id,count(*) AS documents,sum(d.page_count) AS pages,
       sum(d.char_count) AS characters,round(avg(d.printable_ratio),4) AS avg_printable,
       count(*) FILTER (WHERE d.empty_pages>0) AS docs_with_blank_pages,
       min(d.page_count) AS min_pages,max(d.page_count) AS max_pages
  FROM document d JOIN blob b ON b.sha256=d.sha256
 WHERE d.is_active GROUP BY b.source_id;

CREATE OR REPLACE VIEW v_instrument_duplicates AS
SELECT jurisdiction,kind,number,year,count(*) AS documents,
       array_agg(id ORDER BY created_at) AS instrument_ids,
       array_agg(document_id ORDER BY created_at) AS document_ids,min(short_title) AS a_title
  FROM instrument WHERE number IS NOT NULL AND is_active
 GROUP BY jurisdiction,kind,number,year HAVING count(*)>1;

CREATE OR REPLACE VIEW v_provision AS
SELECT p.id AS provision_id,i.id AS instrument_id,i.jurisdiction,i.kind AS instrument_kind,
       i.short_title,i.year,p.path,nlevel(p.path) AS depth,p.kind,p.label,p.heading,
       p.ordinal,p.first_page,p.last_page,v.text_normalised AS text,v.validity,i.document_id
  FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active
  LEFT JOIN LATERAL (
       SELECT pv.* FROM provision_version pv
        WHERE pv.provision_id=p.id AND upper_inf(pv.validity)
        ORDER BY lower(pv.validity) DESC LIMIT 1) v ON true;

CREATE OR REPLACE VIEW v_segmentation_health AS
SELECT i.jurisdiction,count(DISTINCT i.id) AS instruments,count(p.id) AS provisions,
       count(p.id) FILTER (WHERE p.kind='section') AS sections,
       round(avg(r.toc_agreement) FILTER (WHERE r.toc_found),4) AS mean_toc_agreement,
       count(DISTINCT i.id) FILTER (WHERE r.toc_found) AS with_contents
  FROM instrument i LEFT JOIN provision p ON p.instrument_id=i.id
  LEFT JOIN LATERAL (
       SELECT * FROM segmentation_run s WHERE s.instrument_id=i.id
        ORDER BY s.run_at DESC LIMIT 1) r ON true
 WHERE i.is_active GROUP BY i.jurisdiction;

CREATE OR REPLACE VIEW v_toc AS
SELECT e.instrument_id,i.short_title,i.jurisdiction,e.ordinal,e.printed_label,
       e.printed_heading,e.entry_kind,e.provision_id,p.path,p.first_page,
       (e.provision_id IS NOT NULL) AS resolved
  FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id AND i.is_active
  LEFT JOIN provision p ON p.id=e.provision_id;

CREATE OR REPLACE VIEW v_toc_gap AS
SELECT e.instrument_id,i.document_id,i.short_title,i.jurisdiction,count(*) AS gaps,
       (SELECT count(*) FROM instrument_toc_entry a WHERE a.instrument_id=e.instrument_id) AS entries,
       round(100.0*count(*)/(SELECT count(*) FROM instrument_toc_entry a
                              WHERE a.instrument_id=e.instrument_id),1) AS pct_missing,
       array_agg(e.printed_label ORDER BY e.ordinal) AS missing_labels
  FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id AND i.is_active
 WHERE e.provision_id IS NULL
 GROUP BY e.instrument_id,i.document_id,i.short_title,i.jurisdiction;

CREATE OR REPLACE VIEW v_block_accounting AS
SELECT d.id AS document_id,d.char_count AS chars_extracted,count(t.id) AS blocks,
       count(pb.block_id) AS blocks_accounted,count(t.id)-count(pb.block_id) AS blocks_unaccounted,
       coalesce(sum(pb.chars) FILTER (WHERE pb.role='body'),0) AS chars_body,
       coalesce(sum(pb.chars) FILTER (WHERE pb.role<>'body'),0) AS chars_other,
       coalesce(sum(pb.chars) FILTER (WHERE pb.role='unassigned'),0) AS chars_unassigned
  FROM document d JOIN text_block t ON t.document_id=d.id
  LEFT JOIN (provision_block pb JOIN block_assignment_set s
             ON s.id=pb.assignment_set_id AND s.is_active) ON pb.block_id=t.id
 WHERE d.is_active GROUP BY d.id,d.char_count;

CREATE OR REPLACE VIEW v_provision_source AS
SELECT pb.provision_id,count(*) AS blocks,min(t.page_no) AS first_page,
       max(t.page_no) AS last_page,sum(pb.chars) AS chars,
       array_agg(t.id ORDER BY t.reading_order) AS block_ids
  FROM provision_block pb JOIN block_assignment_set s
    ON s.id=pb.assignment_set_id AND s.is_active
  JOIN text_block t ON t.id=pb.block_id
 WHERE pb.provision_id IS NOT NULL GROUP BY pb.provision_id;

CREATE OR REPLACE VIEW v_unstructured_document AS
SELECT d.id AS document_id,d.lane,d.page_count,d.char_count,count(pb.block_id) AS blocks,
       sum(pb.chars) AS chars,r.reason,r.run_at,o.canonical_url AS source_url
  FROM block_assignment_set s JOIN document d ON d.id=s.document_id AND d.is_active
  JOIN source_observation o ON o.id=s.source_observation_id
  JOIN provision_block pb ON pb.assignment_set_id=s.id AND pb.role='unstructured'
  LEFT JOIN LATERAL (
       SELECT reason,run_at FROM segmentation_run x
        WHERE x.source_observation_id=s.source_observation_id
        ORDER BY x.run_at DESC LIMIT 1) r ON true
 WHERE s.is_active
 GROUP BY d.id,d.lane,d.page_count,d.char_count,r.reason,r.run_at,o.canonical_url;

COMMIT;
