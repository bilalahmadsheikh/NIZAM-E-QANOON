-- DRAFT by agent K6 (18 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-ocr-4538.sh with psql variables, because the document is the
-- OCR-promoted revision of 4538 whose id and block ids exist only after the promotion:
--   ./nz psql -v ON_ERROR_STOP=1 -v doc=<promoted id> -v blk1=<E1's first span block> -v blk2=<E2's first span block> < this file
-- Source-verified boundary evidence for the reviewed split of that revision
-- (tools/evidence/multi-instrument-plans/doc-<promoted id>.json, written from claude/agK6/work/agK6-mkplan_4538.py).
--
-- The photographed compilation (observation 4234, 'CIVIL DEFNECE RULES, 1951', twelve pages, printed pp128-138 of a
-- 'STATUTORY RULES AND ORDERS' volume) prints THE CIVIL DEFENCE (SPECIAL POWERS) RULES, 1951 from p1 to rule 22(4) on
-- p12, closed by the compiler's reference '[See Gaz. of P., 1951, Ext., pp. 571-582]'; then, on p12, two notifications
-- under section 9 of the Civil Defence (Special Powers) Ordinance, 1951, each under its own printed caption and closed
-- by its own Gazette reference:
--   E1 'Delegation of Powers to the Provincial Governments' -- No. 5/1/50-C.D.I., dated the 26th July, 1951
--      ('[See Gaz. of P., 1951, Ext., p. 582]');
--   E2 'Delegation of Powers to Director-General of Railways to make Rules' -- No. 5/1/51-C.D., dated the 29th
--      September, 1951 ('[See Gaz. of P., 1951, Ext., p. 665]').
-- Owner: decision-review-2026-10-18-4538.json, document 4538, q2 'split' (each notification its own instrument, related
-- to the Rules); export m q1 'printed-only' (handwriting set aside, printed text released unamended). The Rules open
-- the document at its first block, so they need no boundary row; each notification's span starts at its printed
-- caption and is anchored here.
--
-- Guards: the document must be the active promoted revision of 4538 with an active single-tree instrument (the first
-- segmentation); each anchor must be a page-12 block whose text is exactly its printed caption, and the next block in
-- reading order must open with the notification's printed number and date (the span start checked against the printed
-- heading, render page-012.png). Idempotent.

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE k6_args ON COMMIT DROP AS SELECT :doc::bigint AS doc, :blk1::bigint AS blk1, :blk2::bigint AS blk2;

CREATE TEMP TABLE k6_anchor ON COMMIT DROP AS
SELECT v.ordinal, v.blk, v.caption, v.number_prefix, v.title, v.number, v.fact
  FROM k6_args a, LATERAL (VALUES
    (1, a.blk1, 'Delegation of Powers to the Provincial Governments',
        'No. 5/1/50-C.D.I., dated the 26th July, 1951.',
        'Delegation of Powers to the Provincial Governments (No. 5/1/50-C.D.I., dated 26 July 1951)',
        'No. 5/1/50-C.D.I.',
        'p12 prints the caption ''Delegation of Powers to the Provincial Governments'' and below it ''No. 5/1/50-C.D.I., dated the 26th July, 1951.--In exercise of the powers conferred by section 9 of the Civil Defence (Special Powers) Ordinance, 1951 (VI of 1951), the Central Government is pleased to direct that all powers or duties which under the provisions of the said Ordinance or rules made thereunder are conferred or imposed upon the Central Government shall be exercised or discharged by the Provincial Governments.'', closed by ''[See Gaz. of P., 1951, Ext., p. 582]'''),
    (2, a.blk2, 'Delegation of Powers to Director-General of Railways to make Rules',
        'No. 5/1/51-C.D., dated the 29th September, 1951.',
        'Delegation of Powers to Director-General of Railways to make Rules (No. 5/1/51-C.D., dated 29 September 1951)',
        'No. 5/1/51-C.D.',
        'p12 prints the caption ''Delegation of Powers to Director-General of Railways to make Rules'' and below it ''No. 5/1/51-C.D., dated the 29th September, 1951.--In exercise of the powers conferred by section 9 of the Civil Defence (Special Powers) Ordinance, 1951 (VI of 1951), the Central Government is pleased to authorize the Director-General of Railways to make rules under the provisions of the said Ordinance for Railway Air Raid Precautions Services on the Railways.'', closed by ''[See Gaz. of P., 1951, Ext., p. 665]''')
  ) AS v(ordinal, blk, caption, number_prefix, title, number, fact);

DO $$
DECLARE a k6_args%ROWTYPE; r record; caption_ok int; next_text text;
BEGIN
    SELECT * INTO a FROM k6_args;
    IF NOT EXISTS (SELECT 1 FROM document WHERE id = a.doc AND supersedes_document_id = 4538 AND is_active) THEN
        RAISE EXCEPTION 'document % is not the active promoted revision of 4538', a.doc;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM instrument i WHERE i.document_id = a.doc AND i.source_observation_id = 4234
                     AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION 'document % has no active single-tree instrument (run the first segmentation)', a.doc;
    END IF;
    FOR r IN SELECT * FROM k6_anchor ORDER BY ordinal LOOP
        SELECT count(*) INTO caption_ok FROM text_block t
         WHERE t.id = r.blk AND t.document_id = a.doc AND t.page_no = 12 AND btrim(t.text) = r.caption;
        IF caption_ok <> 1 THEN
            RAISE EXCEPTION 'anchor E% (block %) is not the page-12 block printing the caption ''%''', r.ordinal, r.blk, r.caption;
        END IF;
        SELECT n.text INTO next_text FROM text_block t JOIN text_block n
            ON n.document_id = t.document_id AND n.page_no = t.page_no AND n.reading_order > t.reading_order
         WHERE t.id = r.blk ORDER BY n.reading_order LIMIT 1;
        IF next_text IS NULL OR left(next_text, length(r.number_prefix)) <> r.number_prefix THEN
            RAISE EXCEPTION 'the block after anchor E% does not open with ''%'' (%)', r.ordinal, r.number_prefix, left(next_text, 60);
        END IF;
    END LOOP;
END $$;

WITH args AS (SELECT * FROM k6_args),
active_instrument AS (
  SELECT i.id FROM instrument i, args
   WHERE i.document_id = args.doc AND i.source_observation_id = 4234
     AND i.is_active AND i.duplicate_of IS NULL
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id, source_observation_id, document_id, start_block_id, source_page,
    detected_title, detected_kind, detected_year, detected_number, confidence,
    method, evidence
)
SELECT ai.id, 4234, args.doc, k.blk, 12,
       k.title, 'notification', 1951, k.number, 1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'expression_ordinal', k.ordinal,
         'plan', 'tools/evidence/multi-instrument-plans/doc-' || args.doc || '.json',
         'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-18-4538.json',
         'owner_question', jsonb_build_object('document_id', 4538, 'question_id', 'q2', 'choice', 'split'),
         'source_facts', jsonb_build_array(
           'p12 ends the Rules with rule 22(4) ''If any person contravenes any order made in pursuance of this Rule, he shall be punishable with imprisonment for a term which may extend to six months, or with fine, or with both.'' and the compiler''s reference ''[See Gaz. of P., 1951, Ext., pp. 571-582]''',
           k.fact,
           'the foot of p12 prints ''1See foot-note 1, on page 128, supra.'' with a handwritten citation beneath (set aside: owner q1 printed-only)'),
         'reviewed_pages', jsonb_build_array(12),
         'render_artifact', '.artifacts/ocr-review-pack-4538/doc-4538/images/page-012.png',
         'render_sha256', '806d1fa5df447abf3e1fd37244284a856a520bd53128e3ea9741ba299e5ac050')
  FROM active_instrument ai CROSS JOIN args CROSS JOIN k6_anchor k
ON CONFLICT (instrument_id, start_block_id, method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id, resolution, review_basis, method, rationale, evidence, decided_by
)
SELECT c.id, 'confirmed_split', 'source_verified', 'claude.multi-expression-plan/1',
       'Block ' || c.start_block_id || ' (PDF p12, the printed caption ''' || k.caption || ''') begins the Central '
       'Government''s notification ' || k.number || ' of 1951 under section 9 of the Civil Defence (Special Powers) '
       'Ordinance, 1951 -- a separate instrument printed after the Civil Defence (Special Powers) Rules, 1951 and related '
       'to them (owner decision 2026-10-18, 4538 q2 split; precedents 1626, 1839, 4598).',
       jsonb_build_object('reviewer_type', 'assistant', 'source_start_block_id', c.start_block_id,
                          'expression_ordinal', k.ordinal,
                          'plan', 'tools/evidence/multi-instrument-plans/doc-' || c.document_id || '.json',
                          'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-18-4538.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
  JOIN k6_args args ON c.document_id = args.doc
  JOIN k6_anchor k ON c.start_block_id = k.blk
 WHERE c.source_observation_id = 4234
   AND c.method = 'claude.multi-expression-plan/1'
   AND NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication a
                    WHERE a.candidate_id = c.id AND a.resolution = 'confirmed_split');

DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM segmentation_boundary_candidate c
      JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id AND a.resolution = 'confirmed_split'
      JOIN k6_args args ON c.document_id = args.doc
      JOIN k6_anchor k ON c.start_block_id = k.blk;
    IF n <> 2 THEN
        RAISE EXCEPTION 'expected a confirmed_split at both notification captions, found %', n;
    END IF;
END $$;

COMMIT;

SELECT c.id, c.start_block_id, c.source_page, left(c.detected_title, 80) AS title, a.resolution
  FROM segmentation_boundary_candidate c
  JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id
 WHERE c.source_observation_id = 4234 AND c.method = 'claude.multi-expression-plan/1';
