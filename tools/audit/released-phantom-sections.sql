-- Released sections that share their first block with ANOTHER released section of the same instrument.
--
-- Found in the released Sindh Livestock Breeding Act: a root-level provision labelled 16 and headed
-- 'Monitoring of genetic merit.' has first_block 145612 -- which is section 1's block, '1. (1) This Act
-- may be called the Sindh Livestock Breeding Act, 2016. (2) It extends to the whole of Sindh. (3) It
-- shall come into force at...' -- and holds two children labelled 2 and 3 that are section 1's own
-- sub-sections. The real section 16 exists separately under Chapter IV. A citation to 'section 16(2)'
-- would render 'It extends to the whole of Sindh'. No release gate looks for this: the phantom's label
-- does not collide with a sibling, and it is not a contents gap.
--
-- Two sections opening on one block is not always wrong -- several short sections can share an
-- extracted block -- so the listing flags the pair where the block does not contain the second
-- section's own label as an opener. Read the rows; do not act on the count. Assert the rule, report
-- the number.

\pset pager off

CREATE TEMP TABLE shared_first_block AS
SELECT a.instrument_id, a.id AS provision_id, a.label, a.heading, a.path::text AS path,
       b.id AS other_id, b.label AS other_label, b.heading AS other_heading,
       a.first_block, tb.page_no, tb.text AS block_text
FROM v_release_provision a
JOIN v_release_provision b
  ON b.instrument_id = a.instrument_id AND b.first_block = a.first_block AND b.id <> a.id
 AND b.kind = 'section'
JOIN text_block tb ON tb.id = a.first_block
WHERE a.kind = 'section'
  AND a.label ~ '^\d{1,4}[A-Z]?$'
  AND tb.text !~ ('(^|[^0-9A-Za-z])' || a.label || '\s*[.\]]');

\echo '-- 1. how many'
SELECT count(DISTINCT provision_id) AS sections, count(DISTINCT instrument_id) AS instruments
FROM shared_first_block;

\echo '-- 2. every one, for reading'
SELECT i.short_title, s.label, left(coalesce(s.heading, ''), 35) AS heading, s.path,
       s.other_label, left(coalesce(s.other_heading, ''), 30) AS other_heading,
       s.first_block, s.page_no, left(regexp_replace(s.block_text, '\s+', ' ', 'g'), 80) AS block_opens
FROM shared_first_block s
JOIN instrument i ON i.id = s.instrument_id
ORDER BY i.short_title, s.path;
