-- Recorded accept_non_citable S7 decisions whose demoted node has operative text beneath it.
--
-- accept_non_citable is the only S7 decision that releases an instrument as written. Mechanically it
-- retypes the demoted 'section' as a CLAUSE under the same parent and keeps its whole subtree -- nothing
-- is deleted, but whatever that node swallowed stays addressed beneath it. The stub guard only compares character counts.
-- On 17 Sep, cataloguing found accepted collisions where a footnote, a fee cell, a tariff code, a
-- form field or a list row had opened a node that swallowed the operative text printed after it --
-- definitions, sub-rules, amending instructions (documents 3901, 4397, 4467, 4502, 4591, 4077). This
-- asks the same question of the decisions already recorded in the database, including those that
-- released instruments.
--
-- The text test is a heuristic ("shall", "means", "may not", "is hereby", "are hereby" in a
-- descendant's own text). It will flag honest cases too -- a demoted duplicate whose kept twin
-- carries the same text, a quoted amendment -- so read each row before re-opening a decision.
-- Assert the rule, report the number.

\pset pager off

CREATE TEMP TABLE accepted_with_operative_text AS
WITH acc AS (
  SELECT a.candidate_id, c.document_id, c.instrument_id, c.printed_label, c.candidate_provision_id,
         c.canonical_provision_id, c.source_block_id, c.source_page, a.decided_by
  FROM v_structural_adjudication_latest a
  JOIN v_active_structural_candidate c ON c.id = a.candidate_id
  WHERE a.resolution = 'accept_non_citable'
)
SELECT acc.*,
       count(x.id) AS descendants,
       count(x.id) FILTER (WHERE vx.text ~* '\y(shall|means|may not|is hereby|are hereby)\y') AS operative_like,
       min(left(regexp_replace(vx.text, '\s+', ' ', 'g'), 100))
         FILTER (WHERE vx.text ~* '\y(shall|means|may not|is hereby|are hereby)\y') AS sample
FROM acc
JOIN provision p ON p.id = acc.candidate_provision_id
LEFT JOIN provision x ON x.path <@ p.path AND x.id <> p.id AND x.is_active
LEFT JOIN v_provision vx ON vx.provision_id = x.id
GROUP BY acc.candidate_id, acc.document_id, acc.instrument_id, acc.printed_label, acc.candidate_provision_id,
         acc.canonical_provision_id, acc.source_block_id, acc.source_page, acc.decided_by
HAVING count(x.id) FILTER (WHERE vx.text ~* '\y(shall|means|may not|is hereby|are hereby)\y') > 0;

\echo '-- 1. how many, and how many sit in RELEASED instruments'
SELECT count(*) AS decisions,
       count(DISTINCT instrument_id) AS instruments,
       count(*) FILTER (WHERE instrument_id IN (SELECT instrument_id FROM v_release_instrument)) AS in_released,
       count(DISTINCT instrument_id) FILTER (WHERE instrument_id IN (SELECT instrument_id FROM v_release_instrument)) AS released_instruments
FROM accepted_with_operative_text;

\echo '-- 2. every one, for reading'
SELECT i.short_title, w.document_id, w.printed_label, w.source_page, w.descendants, w.operative_like,
       (w.instrument_id IN (SELECT instrument_id FROM v_release_instrument)) AS released,
       w.decided_by, w.candidate_id, w.sample
FROM accepted_with_operative_text w
JOIN instrument i ON i.id = w.instrument_id
ORDER BY released DESC, w.operative_like DESC, i.short_title;
