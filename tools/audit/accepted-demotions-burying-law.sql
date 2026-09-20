-- Accepted demotions that bury law -- anywhere in the demoted unit.
--
-- This supersedes two narrower checks, both of which missed real cases:
--
--   * the 17 Sep check read only the demoted node's DESCENDANTS. It misses a
--     node with no children that holds several blocks of its own (document
--     4497's candidate 344983a9 -- the block it owns carries rule 6's proviso).
--   * the 18 Sep check read only the node's OWN blocks past the first. It
--     misses law that sits in the children (Income Tax Ordinance s.133).
--
-- Ask both questions at once. `accept_non_citable` retypes the demoted
-- "section" to a clause under the same parent and keeps its whole subtree, so
-- nothing is deleted -- but every character of law inside that subtree is then
-- addressed under a node no citation can name.
--
-- POPULATION (corrected 18 Sep, after 10 of 23 readings were refused as "0
-- active candidates match"). The population must be the one `./nz s7-source`
-- can actually write against: `v_active_structural_candidate`, whose instrument
-- EXPRESSION is live. Keying off a live candidate_provision instead counts
-- rows on retired expressions that no decision can reach -- 2,107 that way
-- against 2,066 this way. The difference is not only arithmetic: the Income Tax
-- Ordinance's six accepts on labels 133 and 236Y are all on retired
-- expressions, while the live candidates for those labels carried NO
-- adjudication at all. So the live tree's section 133 is wrong not because a
-- decision went the wrong way but because none was ever made and the
-- segmenter's default left a footnote holding the number. An audit of decisions
-- cannot see that; see `released-phantom-sections.sql` for the shape that can.
--
-- Section 133, "Reference to High Court", is the case worth knowing: the
-- citable section is a footnote beginning "1Section 133 substituted by the
-- Finance Act, 2005. The original section 133 read as follows:", quoting the
-- pre-2005 procedure, while the law as amended sits demoted with 39 children.
-- A citation to section 133 renders repealed procedure as current law --
-- INV-4 and INV-5 failing together.
--
-- THE OPENER FLAG IS A FLAG, NOT A FILTER. Corpus-wide it separates well: 35%
-- of rows carry no opener, matching the 36% false-positive rate measured by
-- reading 83 rows against source. On a single document it can be useless. The
-- Sales Tax Act (document 4447) prints section 33's penalties as a numbered
-- TABLE, and the serial cell of each row -- "5.", "7." -- looks exactly like a
-- provision opener to a raw-block regex, so every row there reports true. Never
-- read a `t` as proof that a row is a real defect; read the page.
--
-- Assert the rule, report the number.

\pset pager off

\echo '-- 1. accepts that can be acted on, and how many bury operative text'
WITH accepted AS (
  SELECT c.id, c.document_id, c.printed_label, c.candidate_provision_id, p.path
  FROM v_structural_adjudication_latest a
  JOIN v_active_structural_candidate c ON c.id = a.candidate_id
  JOIN provision p ON p.id = c.candidate_provision_id AND p.is_active
  WHERE a.resolution = 'accept_non_citable'),
-- TWO COLUMNS, NOT ONE (18 Sep 2026). These are different questions and were
-- being conflated. `operative_chars` counts every block in the demoted subtree
-- INCLUDING the node's own opening block; `behind_opener` excludes it.
--
-- Both are needed. For document 4489's section 133 the opening block IS the
-- buried law -- the live "Reference to High Court" text as amended -- so
-- excluding it would hide the worst case in the corpus. But for a food-colour
-- specification sheet the opening block is a table row reading "3. Water
-- insoluble matter, per cent by mass, Max. 0.2", and it matches only because
-- the sheet's requirement line says "shall conform"; nothing sits behind it.
-- Counting those inflates the total on exactly the numbered-table documents
-- where the opener flag already fails -- 4460, 4447, 3247, 3525.
--
-- Read `behind_opener` as "law sits behind an opener that should never have
-- been a unit" and `operative_chars` as "law is addressed under a non-citable
-- node". Neither alone is the queue.
first_block AS (
  SELECT ac.id, tb.id AS block_id
  FROM accepted ac
  JOIN LATERAL (
    SELECT tb2.id
    FROM provision_block pb2
    JOIN block_assignment_set b2
      ON b2.id = pb2.assignment_set_id AND b2.is_active
    JOIN text_block tb2 ON tb2.id = pb2.block_id
    WHERE pb2.provision_id = ac.candidate_provision_id
    ORDER BY tb2.page_no, tb2.reading_order
    LIMIT 1) tb ON true),
buried AS (
  SELECT ac.id,
         sum(length(v.text)) FILTER (
           WHERE v.text ~* '\y(shall|means|may not|is hereby|are hereby)\y')
           AS operative_chars,
         (SELECT coalesce(sum(length(tb.text)), 0)
            FROM v_provision v2
            JOIN provision_block pb ON pb.provision_id = v2.provision_id
            JOIN block_assignment_set bas
              ON bas.id = pb.assignment_set_id AND bas.is_active
            JOIN text_block tb ON tb.id = pb.block_id
           WHERE v2.path <@ ac.path AND v2.document_id = ac.document_id
             AND tb.text ~* '\y(shall|means|may not|is hereby|are hereby)\y'
             AND tb.id <> (SELECT block_id FROM first_block f WHERE f.id = ac.id)
         ) AS behind_opener
  FROM accepted ac
  JOIN v_provision v
    ON v.path <@ ac.path AND v.document_id = ac.document_id
  GROUP BY ac.id, ac.path, ac.document_id, ac.candidate_provision_id),
-- The reader's discriminator, measured rather than assumed. Of 83 rows read
-- against source, 30 were false positives: the buried text was a penalty cell,
-- a specification row, or law quoted inside a footnote, and no block of the
-- node began with a provision opener, while every superseded row had one.
--
-- It must be asked of the RAW BLOCK text. `v_provision.text` has the label
-- stripped by the segmenter, so a provision's text never begins "48. Heading"
-- and the same test against it returns zero for every row -- which is what it
-- did on the first attempt, and is a measurement of the view's shape, not of
-- the corpus.
opener AS (
  SELECT ac.id,
         bool_or(tb.text ~ '^\s*\[?\d{1,4}[A-Z-]*\.\s') AS has_provision_opener
  FROM accepted ac
  JOIN v_provision v ON v.path <@ ac.path AND v.document_id = ac.document_id
  JOIN provision_block pb ON pb.provision_id = v.provision_id
  JOIN block_assignment_set bas ON bas.id = pb.assignment_set_id AND bas.is_active
  JOIN text_block tb ON tb.id = pb.block_id
  GROUP BY ac.id)
SELECT (SELECT count(*) FROM accepted) AS accepts_actionable,
       count(*) FILTER (WHERE b.operative_chars > 0) AS bury_something,
       count(*) FILTER (WHERE b.behind_opener > 0) AS bury_BEHIND_the_opener,
       count(*) FILTER (WHERE b.operative_chars > 0 AND o.has_provision_opener)
         AS also_open_a_provision,
       sum(b.operative_chars) AS operative_chars_total,
       sum(b.behind_opener)   AS operative_chars_behind_opener
FROM buried b JOIN opener o ON o.id = b.id;

\echo '-- 2. the queue, worst first, flagged by whether a provision opener is buried'
WITH accepted AS (
  SELECT c.id, c.document_id, c.printed_label, p.path
  FROM v_structural_adjudication_latest a
  JOIN v_active_structural_candidate c ON c.id = a.candidate_id
  JOIN provision p ON p.id = c.candidate_provision_id AND p.is_active
  WHERE a.resolution = 'accept_non_citable')
SELECT ac.id, ac.document_id, ac.printed_label,
       sum(length(v.text)) FILTER (
         WHERE v.text ~* '\y(shall|means|may not|is hereby|are hereby)\y')
         AS operative_chars,
       bool_or(EXISTS (SELECT 1 FROM provision_block pb
                        JOIN block_assignment_set bas
                          ON bas.id = pb.assignment_set_id AND bas.is_active
                        JOIN text_block tb ON tb.id = pb.block_id
                       WHERE pb.provision_id = v.provision_id
                         AND tb.text ~ '^\s*\[?\d{1,4}[A-Z-]*\.\s')) AS opens_a_provision,
       max(left(regexp_replace(v.text, '\s+', ' ', 'g'), 90)) FILTER (
         WHERE v.text ~* '\y(shall|means|may not|is hereby|are hereby)\y')
         AS sample
FROM accepted ac
JOIN v_provision v ON v.path <@ ac.path AND v.document_id = ac.document_id
GROUP BY ac.id, ac.document_id, ac.printed_label
HAVING sum(length(v.text)) FILTER (
         WHERE v.text ~* '\y(shall|means|may not|is hereby|are hereby)\y') > 800
ORDER BY operative_chars DESC
LIMIT 40;
