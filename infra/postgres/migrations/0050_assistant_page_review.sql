-- Admit an assistant's page reading as its own basis for `absent_in_source`.
--
-- Migration 0042 requires that resolution to carry `human_page_review: true`
-- and a `render_artifact`, and says why in its own text:
--
--     A claim that the official source omits a promised section is a human
--     page-reading result, not a parser inference.  Store both facts so a
--     future bulk tool cannot silently manufacture these decisions.
--
-- That rule has done its job and is kept. What it could not distinguish is two
-- different things it had collapsed into one flag: WHO LOOKED, and WHETHER THE
-- READING IS EVIDENCED. An assistant can genuinely read a rendered page --
-- document 169 was settled that way, by reading page 1 and page 3 and finding
-- that its contents prints rows 4 and 5 identically and the Act ends at section
-- 5 -- and the danger the rule guards against is not who did the reading but a
-- decision made with no page behind it at all.
--
-- So `assistant_page_review` is admitted ALONGSIDE the human flag, never as a
-- substitute for it, and it must carry strictly more evidence than the human
-- path does:
--
--   * `render_artifact`   the rendered page(s) the reading was made from,
--   * `render_sha256`     their content hashes, so the decision names exactly
--                         the image that was read and a later reviewer can
--                         verify the page has not changed underneath it,
--   * `observed`          what the page shows, in words, so the reading can be
--                         disagreed with rather than merely trusted.
--
-- The two bases stay distinguishable for ever: `human_page_review` remains
-- true only where a person read the page, and every query, gate and audit can
-- tell the difference and decide for itself which to honour.
--
-- Authorised by the project owner, 13 September 2026: "do the machine
-- verification as much as possible and accept them on those basis and with
-- every detail of each in md and pic show me each if i want to unaccept
-- something i will tell u". Each decision is therefore append-only and
-- supersedable, and is rendered for review before it is relied on.

BEGIN;

ALTER TABLE toc_gap_adjudication
    DROP CONSTRAINT toc_gap_adjudication_check;

ALTER TABLE toc_gap_adjudication
    ADD CONSTRAINT toc_gap_adjudication_check CHECK (
        resolution <> 'absent_in_source'
        OR (evidence @> '{"human_page_review":true}'::jsonb
            AND evidence ? 'render_artifact')
        OR (evidence @> '{"assistant_page_review":true}'::jsonb
            AND evidence ? 'render_artifact'
            AND evidence ? 'render_sha256'
            AND evidence ? 'observed')
    );

COMMENT ON CONSTRAINT toc_gap_adjudication_check ON toc_gap_adjudication IS
  'absent_in_source needs a page reading: either a human one with its render, '
  'or an assistant one that additionally names the render hashes it read and '
  'states in words what the page shows. The two bases are never merged.';

-- Which reviews rest on whose reading, at a glance. The release gate does not
-- consult this; it exists so a person can audit the assistant path and
-- supersede any row in it.
CREATE OR REPLACE VIEW v_toc_gap_review_basis AS
SELECT a.id,
       a.instrument_id,
       a.document_id,
       a.toc_entry_id,
       a.printed_label,
       a.resolution,
       CASE
           WHEN a.evidence @> '{"human_page_review":true}'::jsonb
               THEN 'human_page_review'
           WHEN a.evidence @> '{"assistant_page_review":true}'::jsonb
               THEN 'assistant_page_review'
           ELSE 'no_page_reading'
       END AS review_basis,
       a.evidence->'render_artifact' AS render_artifact,
       a.evidence->'render_sha256'   AS render_sha256,
       a.evidence->>'observed'       AS observed,
       a.rationale,
       a.decided_by,
       a.decided_at
  FROM toc_gap_adjudication a
 WHERE NOT EXISTS (SELECT 1 FROM toc_gap_adjudication l
                    WHERE l.supersedes_id = a.id);

COMMENT ON VIEW v_toc_gap_review_basis IS
  'Every standing contents-gap decision with the basis of its page reading. '
  'Use it to audit the assistant-reviewed rows and supersede any that a '
  'source reading disagrees with.';

COMMIT;
