-- Preserve exact gate equivalence and give repeated printed labels entry-level
-- identity. Migration 0042 exposed that one legacy segmentation_run reported
-- two missing labels (1.1, 1.2) which were not itemized in
-- instrument_toc_entry; changing from run aggregate to row-level evidence
-- otherwise released that instrument without a decision. It also exposed that
-- CPC repeats labels such as 1..29 in separate printed contents regions, so
-- instrument+label alone is not a safe adjudication key.

BEGIN;

DROP VIEW v_release_provision_version;
DROP VIEW v_release_provision;
DROP VIEW v_release_instrument;
DROP VIEW v_toc_gap_pending;
DROP VIEW v_toc_gap_adjudication_latest;

ALTER TABLE toc_gap_adjudication
    ADD COLUMN toc_entry_id bigint REFERENCES instrument_toc_entry(id)
        ON DELETE RESTRICT;

CREATE INDEX toc_gap_adjudication_entry
    ON toc_gap_adjudication(toc_entry_id,decided_at DESC,id DESC)
    WHERE toc_entry_id IS NOT NULL;

CREATE OR REPLACE FUNCTION check_toc_gap_adjudication() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    instrument_document bigint;
    document_pages integer;
    previous toc_gap_adjudication%ROWTYPE;
BEGIN
    SELECT i.document_id INTO instrument_document
      FROM instrument i WHERE i.id=NEW.instrument_id;
    SELECT d.page_count INTO document_pages
      FROM document d WHERE d.id=NEW.document_id;

    IF instrument_document IS DISTINCT FROM NEW.document_id THEN
        RAISE EXCEPTION 'TOC adjudication document does not own instrument %',
                        NEW.instrument_id;
    END IF;
    IF NEW.source_page > document_pages THEN
        RAISE EXCEPTION 'TOC adjudication page % exceeds document % page count %',
                        NEW.source_page,NEW.document_id,document_pages;
    END IF;

    IF NEW.toc_entry_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM instrument_toc_entry e
             WHERE e.id=NEW.toc_entry_id
               AND e.instrument_id=NEW.instrument_id
               AND e.provision_id IS NULL
               AND e.printed_label=NEW.printed_label
        ) THEN
            RAISE EXCEPTION 'TOC entry % is not this unresolved printed label',
                            NEW.toc_entry_id;
        END IF;
    ELSE
        -- Legacy run-only gaps are admitted only when the latest immutable run
        -- names the label and no unresolved entry row exists for it.
        IF NOT EXISTS (
            SELECT 1
              FROM LATERAL (
                SELECT r.detail FROM segmentation_run r
                 WHERE r.instrument_id=NEW.instrument_id
                 ORDER BY r.run_at DESC,r.id DESC LIMIT 1
              ) r,
              LATERAL jsonb_array_elements_text(
                coalesce(r.detail->'missing','[]'::jsonb)) label(value)
             WHERE label.value=NEW.printed_label
        ) THEN
            RAISE EXCEPTION 'label % is neither an unresolved TOC entry nor a latest-run gap',
                            NEW.printed_label;
        END IF;
    END IF;

    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT * INTO previous FROM toc_gap_adjudication
         WHERE id=NEW.supersedes_id;
        IF NOT FOUND OR previous.instrument_id<>NEW.instrument_id
           OR previous.document_id<>NEW.document_id
           OR previous.printed_label<>NEW.printed_label
           OR previous.toc_entry_id IS DISTINCT FROM NEW.toc_entry_id THEN
            RAISE EXCEPTION 'superseded TOC adjudication is for a different gap';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE VIEW v_toc_gap_adjudication_latest AS
SELECT DISTINCT ON (a.instrument_id,a.toc_entry_id,a.printed_label) a.*
  FROM toc_gap_adjudication a
 ORDER BY a.instrument_id,a.toc_entry_id,a.printed_label,a.decided_at DESC,a.id DESC;

CREATE VIEW v_toc_gap_pending AS
WITH latest_run AS (
  SELECT DISTINCT ON (r.instrument_id) r.*
    FROM segmentation_run r
    JOIN instrument i ON i.id=r.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
   ORDER BY r.instrument_id,r.run_at DESC,r.id DESC
), entry_gap AS (
  SELECT e.id AS toc_entry_id,e.instrument_id,i.document_id,i.short_title,
         i.jurisdiction,e.ordinal,e.printed_label,e.printed_heading,
         e.entry_kind,e.source_block_id,e.source_page
    FROM instrument_toc_entry e
    JOIN instrument i ON i.id=e.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
   WHERE e.provision_id IS NULL
), run_only_gap AS (
  SELECT NULL::bigint AS toc_entry_id,i.id AS instrument_id,i.document_id,
         i.short_title,i.jurisdiction,(1000000+missing.ordinality)::integer AS ordinal,
         missing.value AS printed_label,NULL::text AS printed_heading,
         'section'::text AS entry_kind,NULL::bigint AS source_block_id,
         NULL::integer AS source_page
    FROM latest_run r
    JOIN instrument i ON i.id=r.instrument_id
    CROSS JOIN LATERAL jsonb_array_elements_text(
      coalesce(r.detail->'missing','[]'::jsonb)) WITH ORDINALITY missing(value,ordinality)
   WHERE r.toc_found AND coalesce(r.toc_missing,0)>0
     AND NOT EXISTS (
       SELECT 1 FROM entry_gap e
        WHERE e.instrument_id=i.id AND e.printed_label=missing.value)
), gap AS (
  SELECT * FROM entry_gap
  UNION ALL
  SELECT * FROM run_only_gap
)
SELECT g.*,a.id AS adjudication_id,a.resolution,
       a.source_page AS reviewed_page,a.evidence AS adjudication_evidence,
       a.rationale,a.decided_by,a.decided_at
  FROM gap g
  LEFT JOIN v_toc_gap_adjudication_latest a
    ON a.instrument_id=g.instrument_id
   AND a.toc_entry_id IS NOT DISTINCT FROM g.toc_entry_id
   AND a.printed_label=g.printed_label
 WHERE a.id IS NULL OR a.resolution='parser_defect';

CREATE VIEW v_release_instrument AS
SELECT i.*
  FROM instrument i
  JOIN v_document_quality_status q ON q.document_id=i.document_id
  JOIN segmentation_run r ON r.instrument_id=i.id
 WHERE i.is_active
   AND i.duplicate_of IS NULL
   AND q.overall_outcome='passed'
   AND r.outcome='segmented'
   AND NOT EXISTS (
       SELECT 1 FROM v_toc_gap_pending t WHERE t.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_structural_adjudication_pending s
        WHERE s.instrument_id=i.id)
   AND NOT EXISTS (
       SELECT 1 FROM v_boundary_adjudication_pending b
        WHERE b.instrument_id=i.id);

CREATE VIEW v_release_provision AS
SELECT p.* FROM provision p
JOIN v_release_instrument i ON i.id=p.instrument_id
WHERE p.is_active;

CREATE VIEW v_release_provision_version AS
SELECT v.* FROM provision_version v
JOIN v_release_provision p ON p.id=v.provision_id;

COMMENT ON COLUMN toc_gap_adjudication.toc_entry_id IS
  'Exact printed contents entry; NULL only for a legacy latest-run missing label that lacked an entry row.';
COMMENT ON VIEW v_toc_gap_pending IS
  'Canonical entry-level TOC gaps plus legacy run-only gaps; parser defects remain pending until replay.';

COMMIT;
