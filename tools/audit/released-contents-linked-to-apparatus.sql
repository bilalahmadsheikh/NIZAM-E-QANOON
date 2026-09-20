-- A contents entry can be "linked" and still point at editorial apparatus.
--
--     docker compose -f infra/compose.yaml exec -T postgres \
--       psql -U nizam -d nizam_clean < tools/audit/released-contents-linked-to-apparatus.sql
--
-- WHY THIS EXISTS. The release gate asks whether every printed contents entry
-- resolves to a provision. It does not ask what the provision IS. Document 3867,
-- the Punjab Excise Act 1914, passes that question with 88 of its 96 entries
-- linked -- while entry 1, "Short title, extent and commencement.", resolves to a
-- provision whose whole text is `Subs, for the words "excisable article" by A. O.,
-- 1937.` The Act's footnote apparatus became its structure: the citation fragment
-- "Part I-A, pages 132-133" inside a footnote opened 23 root PART nodes, and the
-- footnote markers opened sections. An instrument in that state can be released
-- and will then serve editorial notes under real section numbers, which is an
-- INV-1 failure (the identifier is right, the provision behind it is not law).
--
-- WHAT THIS MEASURES. Released instruments whose contents entry reads like a real
-- contents row but whose linked provision's own text OPENS with the segmenter's
-- own provenance vocabulary. Three deliberate narrowings, each of which cost
-- something to learn:
--
--   1. The test is anchored at the START of the provision's text, not "contains".
--      A `contains` test over the same vocabulary flags 4,613 entries in 1,691
--      released instruments -- almost the whole release -- because an ordinary
--      section may quote a Gazette or an amending Act. Anchoring is what makes
--      this a criterion rather than a smell.
--   2. The vocabulary allows an OPTIONAL leading marker digit, because
--      `v_provision.text` has the label stripped by the segmenter. Asking a
--      "begins with an opener" question of the view returns false for every row.
--   3. A bare disposition opener (`Omitted by ...`, `Rep. by ...`) is EXCLUDED.
--      An omitted section's own printed body IS that sentence, so such a record is
--      correct. Only editorial provenance counts: Subs./Ins./Added/Ibid/See now/
--      "For Statement of Objects and Reasons"/"The words ... rep. by"/Pakistan Code.
--
-- The vocabulary mirrors nizam/corpus/segment.py::_FOOTNOTE. Keep them together:
-- if the segmenter learns a new provenance form, this audit must learn it too.
--
-- MEASURED 18 Sep 2026 on nizam_clean: 88 entries in 21 released instruments
-- (59 distinct instrument+label pairs), plus 44 entries in 5 instruments where the
-- CONTENTS ROW ITSELF is a footnote line -- reported separately below, because
-- there the link is junk pointing at junk and the repair is the contents boundary,
-- not the link. Seven of the 88 were read against the rendered source page
-- (documents 2534, 4242, 1918, 3905, 2231, 2877, 1181): seven of seven were real.

\pset pager off
\pset border 2

CREATE TEMP VIEW audit_apparatus_re AS
SELECT '^\s*(?:\d{1,3}\s*[.:-]?\s*)?('
    || 'Subs\.|Subs,|Substituted\s+(?:for|by|vide)'
    || '|Ins\.|Inserted\s+(?:by|vide)|Added\s+(?:by|vide)'
    || '|Ibid\b|See\s+now\b'
    || '|For\s+(?:the\s+)?Statement\s+of\s+Objects'
    || '|This\s+(?:Act|Ordinance|section)\s+(?:has\s+been\s+extended'
    ||   '|was\s+(?:assented|published|originally|previously)|previously)'
    || '|Pakistan\s+Code\b'
    || '|The\s+(?:original\s+)?(?:words?|brackets|provisions?|figures?|letters?|commas?)\b'
    ||   '[^\n]{0,200}\b(?:rep\.|omitted\s+by|substituted|subs\.|ins\.)'
    || '|Certain\s+words\b[^\n]{0,200}\bomitted\s+by'
    || '|S\.?\s*\d{1,4}\s*[-–]?\s*[A-Z]?\s*,?\s*'
    ||   '(?:ins\.|inserted|subs\.|substituted|omitted|deleted)\b'
    || '|Proviso\s+omitted\b'
    || '|For\s+rules\s+see\b|See\s+[Nn]otification\b'
    || ')' AS re;

CREATE TEMP VIEW audit_apparatus_link AS
SELECT t.id                                   AS entry_id,
       t.instrument_id,
       p.document_id,
       t.printed_label,
       t.printed_heading,
       t.match_method,
       p.provision_id,
       p.label                                AS target_label,
       p.first_page                           AS target_page,
       p.text                                 AS target_text,
       (coalesce(t.printed_heading,'') ~* a.re) AS entry_is_apparatus_too
  FROM instrument_toc_entry t
  JOIN v_release_instrument ri ON ri.id = t.instrument_id
  JOIN v_provision p          ON p.provision_id = t.provision_id
 CROSS JOIN audit_apparatus_re a
 WHERE t.provision_id IS NOT NULL
   AND coalesce(p.text,'') <> ''
   AND p.text ~* a.re;

\echo '──── the criterion measure: a real contents row resolving to apparatus'
SELECT count(*)                                        AS entries,
       count(DISTINCT instrument_id)                   AS instruments,
       count(DISTINCT instrument_id::text||'|'||coalesce(printed_label,'')) AS distinct_labels
  FROM audit_apparatus_link
 WHERE NOT entry_is_apparatus_too;

\echo '──── reported separately: the contents row is itself a footnote line'
SELECT count(*) AS entries, count(DISTINCT instrument_id) AS instruments
  FROM audit_apparatus_link
 WHERE entry_is_apparatus_too;

\echo '──── by instrument'
SELECT l.document_id, left(coalesce(ri.short_title,''),52) AS short_title,
       count(*) AS entries,
       count(DISTINCT coalesce(l.printed_label,'')) AS labels
  FROM audit_apparatus_link l
  JOIN v_release_instrument ri ON ri.id = l.instrument_id
 WHERE NOT l.entry_is_apparatus_too
 GROUP BY 1,2 ORDER BY 3 DESC, 1;

\echo '──── every row, for a reader'
SELECT l.document_id, l.printed_label AS entry,
       left(regexp_replace(coalesce(l.printed_heading,''),'\s+',' ','g'),38) AS entry_heading,
       l.target_label, l.target_page,
       left(regexp_replace(l.target_text,'\s+',' ','g'),90) AS target_text
  FROM audit_apparatus_link l
 WHERE NOT l.entry_is_apparatus_too
 ORDER BY l.document_id, l.printed_label;

\echo '──── corroboration through the SOURCE BLOCK rather than the stripped view text'
-- Of the 88, 53 have an active source block and 34 of those blocks also OPEN with
-- the vocabulary; the other 19 carry the footnote run mid-block, after body text,
-- which is the document 2231 shape. 35 hits have no active block at all -- their
-- text reached the provision by another route, which is worth its own look.
WITH firstblk AS (
  SELECT l.entry_id, tb.text AS block_text,
         row_number() OVER (PARTITION BY l.entry_id ORDER BY tb.reading_order) AS rn
    FROM audit_apparatus_link l
    JOIN provision_block pb        ON pb.provision_id = l.provision_id
    JOIN block_assignment_set bas  ON bas.id = pb.assignment_set_id AND bas.is_active
    JOIN text_block tb             ON tb.id = pb.block_id
   WHERE NOT l.entry_is_apparatus_too)
SELECT count(*) FILTER (WHERE block_text ~* (SELECT re FROM audit_apparatus_re))
         AS first_block_confirms,
       count(*) AS hits_with_an_active_block
  FROM firstblk WHERE rn = 1;

-- ---------------------------------------------------------------------------
-- PROPOSED GATE CRITERION, in the form tools/audit/criteria.sql uses.
--
-- Add to the `m` CTE (alongside toc_pending and toc_bad_source), reading through
-- the audit_* views already defined there so it counts active revisions only:
--
--     (SELECT count(*)
--        FROM instrument_toc_entry t
--        JOIN v_release_instrument ri ON ri.id = t.instrument_id
--        JOIN v_provision p ON p.provision_id = t.provision_id
--       WHERE t.provision_id IS NOT NULL
--         AND coalesce(p.text,'') <> ''
--         AND p.text ~* <the apparatus regex above>
--         AND coalesce(t.printed_heading,'') !~* <the same regex>
--     )                                                     AS toc_links_apparatus,
--
-- and the row itself:
--
--     UNION ALL SELECT 'A10','contents entries resolve to law, not apparatus',
--            toc_links_apparatus::text,'0',
--            CASE WHEN toc_links_apparatus=0 THEN 'PASS' ELSE 'FAIL' END FROM m
--
-- It adds a criterion and weakens none: A5 still asserts contents agreement and
-- reports the pending queue, A9 still asserts exact source anchors. A10 asserts
-- the question neither of them asks -- that a link points at law.
--
-- Note what adding it costs today: 21 released instruments would move to FAIL, so
-- the release set shrinks by 21 until they are re-segmented. That is the honest
-- state; they are currently answering "section 1" with a footnote.
--
-- Threshold 0 is right rather than a ratio: one released instrument serving an
-- editorial note under a section number is an INV-1 breach, and the number is
-- small enough to drive to zero.
-- ---------------------------------------------------------------------------
