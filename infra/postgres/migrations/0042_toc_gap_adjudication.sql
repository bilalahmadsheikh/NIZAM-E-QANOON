-- Append-only adjudication for a printed contents entry whose section was not
-- resolved in the body.  Governing contract: docs/02 §5 and §8 (the contents
-- list is source evidence, never operative text; no missing section is
-- fabricated merely to close a metric).

BEGIN;

CREATE TABLE toc_gap_adjudication (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id  uuid NOT NULL REFERENCES instrument(id) ON DELETE RESTRICT,
    document_id    bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    printed_label  text NOT NULL CHECK (btrim(printed_label) <> ''),
    resolution     text NOT NULL CHECK (resolution IN
                       ('absent_in_source','found_elsewhere','parser_defect',
                        'other_instrument')),
    source_page    integer NOT NULL CHECK (source_page > 0),
    evidence       jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    rationale      text NOT NULL CHECK (btrim(rationale) <> ''),
    decided_by     text NOT NULL CHECK (btrim(decided_by) <> ''),
    decided_at     timestamptz NOT NULL DEFAULT now(),
    supersedes_id  uuid REFERENCES toc_gap_adjudication(id) ON DELETE RESTRICT,

    -- A claim that the official source omits a promised section is a human
    -- page-reading result, not a parser inference.  Store both facts so a
    -- future bulk tool cannot silently manufacture these decisions.
    CHECK (resolution <> 'absent_in_source' OR
           (evidence @> '{"human_page_review":true}'::jsonb
            AND evidence ? 'render_artifact')),
    CHECK (resolution <> 'parser_defect' OR evidence ? 'defect_class'),
    CHECK (resolution <> 'found_elsewhere' OR evidence ? 'found_provision_id'),
    CHECK (resolution <> 'other_instrument' OR evidence ? 'other_instrument_id')
);

CREATE INDEX toc_gap_adjudication_key
    ON toc_gap_adjudication(instrument_id,printed_label,decided_at DESC,id DESC);
CREATE INDEX toc_gap_adjudication_document
    ON toc_gap_adjudication(document_id,decided_at DESC);

CREATE FUNCTION check_toc_gap_adjudication() RETURNS trigger
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
    IF NOT EXISTS (
        SELECT 1 FROM instrument_toc_entry e
         WHERE e.instrument_id=NEW.instrument_id
           AND e.provision_id IS NULL
           AND e.printed_label=NEW.printed_label
    ) THEN
        RAISE EXCEPTION 'label % is not an unresolved printed TOC entry for instrument %',
                        NEW.printed_label,NEW.instrument_id;
    END IF;

    IF NEW.supersedes_id IS NOT NULL THEN
        SELECT * INTO previous FROM toc_gap_adjudication
         WHERE id=NEW.supersedes_id;
        IF NOT FOUND OR previous.instrument_id<>NEW.instrument_id
           OR previous.document_id<>NEW.document_id
           OR previous.printed_label<>NEW.printed_label THEN
            RAISE EXCEPTION 'superseded TOC adjudication is for a different gap';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER toc_gap_adjudication_guard
BEFORE INSERT ON toc_gap_adjudication
FOR EACH ROW EXECUTE FUNCTION check_toc_gap_adjudication();

CREATE VIEW v_toc_gap_adjudication_latest AS
SELECT DISTINCT ON (a.instrument_id,a.printed_label) a.*
  FROM toc_gap_adjudication a
 ORDER BY a.instrument_id,a.printed_label,a.decided_at DESC,a.id DESC;

-- Row-level queue: unlike aggregated v_toc_gap, this preserves each printed
-- entry's exact source block/page. A parser_defect decision classifies work but
-- does not close it; only a corrected replay that resolves the entry removes
-- that row. The other three resolutions explain why no provision_id is proper.
CREATE VIEW v_toc_gap_pending AS
SELECT e.id AS toc_entry_id,e.instrument_id,i.document_id,i.short_title,
       i.jurisdiction,e.ordinal,e.printed_label,e.printed_heading,
       e.entry_kind,e.source_block_id,e.source_page,
       a.id AS adjudication_id,a.resolution,a.source_page AS reviewed_page,
       a.evidence AS adjudication_evidence,a.rationale,a.decided_by,a.decided_at
  FROM instrument_toc_entry e
  JOIN instrument i ON i.id=e.instrument_id
                   AND i.is_active AND i.duplicate_of IS NULL
  LEFT JOIN v_toc_gap_adjudication_latest a
    ON a.instrument_id=e.instrument_id AND a.printed_label=e.printed_label
 WHERE e.provision_id IS NULL
   AND (a.id IS NULL OR a.resolution='parser_defect');

-- Rebuild the application boundary with the adjudicated row-level TOC gate.
-- This is not a relaxation: parser defects remain pending; source-absence and
-- cross-expression decisions require source evidence constrained above.
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

COMMENT ON TABLE toc_gap_adjudication IS
  'Append-only, page-evidenced decision for an unresolved printed contents label; docs/02 §5 and §8.';
COMMENT ON VIEW v_toc_gap_pending IS
  'Canonical row-level printed-contents gaps not finally source-adjudicated; parser defects remain pending until replay.';
COMMENT ON VIEW v_release_instrument IS
  'Fail-closed quality, identity, S7, adjudicated printed-contents and multi-expression-boundary publication boundary.';

COMMIT;
