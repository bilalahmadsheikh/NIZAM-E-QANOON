-- Read-only shortlist for bounded, source-backed correction. Never infer a
-- non-citable verdict from a duplicate printed number.
BEGIN READ ONLY;
WITH blockers AS (
  SELECT i.id AS instrument_id, i.document_id,
         (SELECT count(*) FROM v_structural_adjudication_pending s
           WHERE s.instrument_id=i.id) AS s7_count,
         (SELECT count(*) FROM v_toc_gap_pending t
           WHERE t.instrument_id=i.id) AS toc_count
  FROM instrument i
  WHERE i.is_active AND i.duplicate_of IS NULL
), candidates AS (
  SELECT b.document_id, c.id AS case_id, c.instrument_id,
         c.printed_label, c.source_page, c.source_block_id,
         c.canonical_source_block_id,
         a.resolution, a.review_basis,
         left(a.rationale, 280) AS rationale_excerpt,
         a.evidence ? 'structural_overrides' AS has_durable_override
  FROM blockers b
  JOIN v_structural_adjudication_pending c ON c.instrument_id=b.instrument_id
  JOIN v_structural_adjudication_latest a ON a.candidate_id=c.id
  WHERE b.s7_count=1 AND b.toc_count=0
    AND a.resolution='reparent' AND a.review_basis='source_verified'
)
SELECT * FROM candidates ORDER BY document_id LIMIT 12;
COMMIT;
