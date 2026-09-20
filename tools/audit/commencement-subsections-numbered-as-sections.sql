-- Section 1's sub-sections printed as '2. It extends to...' and '3. It shall come into force...'.
--
-- Pakistan Code PDFs often print the extent and commencement sub-sections of section 1 with a bare
-- '2.' and '3.' instead of '(2)' and '(3)' (page 3 of the Torture and Custodial Death Act, 2022; page 4
-- of the Pakistan Nuclear Regulatory Authority Ordinance, 2001 -- both read from the render on 17 Sep).
-- The segmenter reads them as sections 2 and 3, they collide with the real sections 2 and 3, and in
-- released instruments some collisions were decided the wrong way round: the fragment keeps the
-- section number and the real section (Definitions, with all its clauses) is demoted to a clause.
-- A citation to 'section 2' then renders 'It extends to the whole of Pakistan.'
--
-- Assert the rule, report the number.

\pset pager off

CREATE TEMP TABLE commencement_fragments AS
SELECT tb.document_id, tb.id AS block_id, tb.page_no,
       (regexp_match(tb.text, '^\s*([23])\.\s*It '))[1] AS printed,
       left(regexp_replace(tb.text, '\s+', ' ', 'g'), 70) AS opens
FROM text_block tb
WHERE tb.text ~* '^\s*2\.\s*It (extends|shall extend)\y'
   OR tb.text ~* '^\s*3\.\s*It (shall come into force|comes into force|shall be deemed to have come into force)\y';

\echo '-- 1. how many documents print the shape'
SELECT count(DISTINCT document_id) AS documents, count(*) AS blocks FROM commencement_fragments;

\echo '-- 2. in those documents, the ACTIVE section labelled 2 or 3: does it hold the fragment?'
CREATE TEMP TABLE fragment_sections AS
SELECT DISTINCT ON (p.id) p.id AS provision_id, p.instrument_id, f.document_id, p.label, p.path::text AS path,
       left(regexp_replace(coalesce(v.text, ''), '\s+', ' ', 'g'), 60) AS section_text,
       (p.instrument_id IN (SELECT id FROM v_release_instrument)) AS released
FROM commencement_fragments f
JOIN v_provision v ON v.document_id = f.document_id AND v.label = f.printed AND v.kind = 'section'
JOIN provision p ON p.id = v.provision_id
WHERE coalesce(v.text, '') ~* '^\s*It (extends|shall extend|shall come into force|comes into force|shall be deemed to have come into force)\y';

SELECT count(*) AS sections_holding_a_fragment,
       count(DISTINCT instrument_id) AS instruments,
       count(*) FILTER (WHERE released) AS in_released,
       count(DISTINCT instrument_id) FILTER (WHERE released) AS released_instruments
FROM fragment_sections;

\echo '-- 3. every released one, with the demoted real section beside it when there is one'
SELECT i.short_title, s.label, s.section_text,
       (SELECT left(regexp_replace(coalesce(vx.text, x.heading, ''), '\s+', ' ', 'g'), 50)
          FROM provision x JOIN v_provision vx ON vx.provision_id = x.id
         WHERE x.instrument_id = s.instrument_id AND x.is_active AND x.kind = 'clause'
           AND x.label = s.label AND nlevel(x.path) = nlevel(s.path::ltree)
         LIMIT 1) AS demoted_real_section,
       s.provision_id
FROM fragment_sections s JOIN instrument i ON i.id = s.instrument_id
WHERE s.released
ORDER BY i.short_title, s.label;
