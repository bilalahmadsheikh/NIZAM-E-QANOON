-- 0003  extraction_attempt, and the views development actually works from
--
-- Two things this fixes.
--
-- First, failures. Doc 02 §3.1 records missing links and parse errors as
-- first-class observations, and §8 insists "Nothing reaches retrieval because a
-- script finished." Until now a rejected extraction printed to stderr and was
-- gone. The ~150-document OCR backlog that §4 predicts has to be a query, not
-- something someone remembers from a scrollback.
--
-- Second, findability. Segmentation is developed against real statutes, and a
-- developer looking for the Penal Code should not have to know its SHA-256.
-- The title, year and instrument hints live in source_observation's metadata;
-- the views join them so a document can be found by name.

BEGIN;

CREATE TYPE extraction_outcome AS ENUM ('extracted', 'rejected', 'error');

CREATE TABLE extraction_attempt (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sha256       char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    extractor    text     NOT NULL,
    lane         extraction_lane,
    outcome      extraction_outcome NOT NULL,
    -- Kept on SET NULL rather than CASCADE: the record that an extraction
    -- happened outlives the document it produced, which is what makes a
    -- re-extraction visible rather than silent.
    document_id  bigint REFERENCES document(id) ON DELETE SET NULL,
    reason       text,
    detail       jsonb NOT NULL DEFAULT '{}'::jsonb,
    duration_ms  integer,
    attempted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX extraction_attempt_sha    ON extraction_attempt (sha256, attempted_at DESC);
CREATE INDEX extraction_attempt_failed ON extraction_attempt (outcome, attempted_at DESC)
    WHERE outcome <> 'extracted';

COMMENT ON TABLE extraction_attempt IS
    'Every extraction try, successful or not. Doc 02 §8 -- the OCR backlog is a query on this.';

-- ---------------------------------------------------------------- v_document
-- A document with the human-readable identity the portal gave it. One row per
-- document; the observation chosen is the one carrying a title, preferring the
-- earliest fetch so the name is stable as re-scrapes accumulate.
CREATE VIEW v_document AS
SELECT d.id                                   AS document_id,
       d.sha256,
       b.source_id,
       o.source_metadata ->> 'title'          AS title,
       coalesce(o.source_metadata ->> 'year',
                o.source_metadata ->> 'year_or_dept')  AS year,
       coalesce(o.source_metadata ->> 'type',
                o.source_metadata ->> 'doc_type')      AS doc_type,
       o.canonical_url,
       o.source_metadata ->> 'archive_path'   AS archive_path,
       d.language,
       d.page_count,
       d.char_count,
       d.printable_ratio,
       d.empty_pages,
       d.lane,
       d.extractor,
       d.extracted_at,
       b.byte_length
  FROM document d
  JOIN blob b ON b.sha256 = d.sha256
  LEFT JOIN LATERAL (
       SELECT so.*
         FROM source_observation so
        WHERE so.sha256 = d.sha256
        ORDER BY (so.source_metadata ->> 'title') IS NULL, so.fetched_at
        LIMIT 1
  ) o ON true;

COMMENT ON VIEW v_document IS
    'Extracted documents by their published title. The join developers actually need.';

-- ------------------------------------------------------------ v_extract_queue
-- Landed bytes with no successful extraction. This is the work list: what to
-- extract next, and -- once E2 has had its turn -- exactly which documents need
-- the OCR lane that doc 02 §4 routes to E3/E4.
CREATE VIEW v_extract_queue AS
SELECT DISTINCT ON (o.sha256)
       o.sha256,
       o.source_id,
       o.object_key,
       o.byte_length,
       o.source_metadata ->> 'title' AS title,
       a.outcome                     AS last_outcome,
       a.reason                      AS last_reason,
       a.attempted_at                AS last_attempt
  FROM source_observation o
  LEFT JOIN document d ON d.sha256 = o.sha256
  LEFT JOIN LATERAL (
       SELECT ea.* FROM extraction_attempt ea
        WHERE ea.sha256 = o.sha256
        ORDER BY ea.attempted_at DESC LIMIT 1
  ) a ON true
 WHERE o.outcome = 'landed'
   AND o.sha256 IS NOT NULL
   AND d.id IS NULL
 ORDER BY o.sha256, (o.source_metadata ->> 'title') IS NULL, o.byte_length;

COMMENT ON VIEW v_extract_queue IS
    'Blobs with no document yet, and why the last attempt failed. The OCR backlog lives here.';

-- ------------------------------------------------------------- v_corpus_health
-- One row per source: how much of it is actually usable. This is the number to
-- watch while the corpus is being built.
CREATE VIEW v_corpus_health AS
SELECT b.source_id,
       count(*)                                     AS documents,
       sum(d.page_count)                            AS pages,
       sum(d.char_count)                            AS characters,
       round(avg(d.printable_ratio), 4)             AS avg_printable,
       count(*) FILTER (WHERE d.empty_pages > 0)    AS docs_with_blank_pages,
       min(d.page_count)                            AS min_pages,
       max(d.page_count)                            AS max_pages
  FROM document d
  JOIN blob b ON b.sha256 = d.sha256
 GROUP BY b.source_id;

COMMIT;
