-- The sharp form of accepted-demotions-with-operative-text.sql:
-- operative text beneath an ACCEPTED demoted node that exists NOWHERE ELSE citable in the instrument.
--
-- A demoted node can legitimately hold operative text when it is a duplicate -- the same Act printed
-- twice, a contents region that copied the body -- because the kept twin is still citable. What must
-- never happen is that the ONLY copy of a provision sits under a node that accept_non_citable retyped as a
-- clause of the wrong parent -- a citation rendered from that record would name the wrong provision. So for every operative-looking descendant we ask whether a released (citable) provision
-- of the same instrument, outside the demoted subtree, carries the same opening text (compared on the
-- first 60 letters and digits, case- and punctuation-blind).
--
-- Remaining false positives to expect: text the kept twin carries with different OCR damage, and
-- quoted amendment text whose operative home is the amending clause. Read before re-opening.
-- Assert the rule, report the number.

\pset pager off

CREATE TEMP TABLE acc_desc AS
SELECT a.candidate_id, c.instrument_id, c.document_id, c.printed_label, c.source_page,
       x.id AS descendant_id, x.label AS descendant_label, vx.text AS dtext,
       left(regexp_replace(lower(vx.text), '[^a-z0-9]', '', 'g'), 60) AS fp
FROM v_structural_adjudication_latest a
JOIN v_active_structural_candidate c ON c.id = a.candidate_id
JOIN provision p ON p.id = c.candidate_provision_id
JOIN provision x ON x.path <@ p.path AND x.id <> p.id AND x.is_active
JOIN v_provision vx ON vx.provision_id = x.id
WHERE a.resolution = 'accept_non_citable'
  AND vx.text ~* '\y(shall|means|may not|is hereby|are hereby)\y'
  AND length(regexp_replace(lower(vx.text), '[^a-z0-9]', '', 'g')) >= 30;

CREATE INDEX ON acc_desc (instrument_id, fp);

CREATE TEMP TABLE released_fp AS
SELECT r.instrument_id, r.id AS provision_id,
       left(regexp_replace(lower(v.text), '[^a-z0-9]', '', 'g'), 60) AS fp
FROM v_release_provision r
JOIN v_provision v ON v.provision_id = r.id
WHERE r.instrument_id IN (SELECT DISTINCT instrument_id FROM acc_desc)
  AND length(regexp_replace(lower(coalesce(v.text, '')), '[^a-z0-9]', '', 'g')) >= 30;

CREATE INDEX ON released_fp (instrument_id, fp);

CREATE TEMP TABLE unique_hidden AS
SELECT d.*
FROM acc_desc d
WHERE NOT EXISTS (
  SELECT 1 FROM released_fp r
  WHERE r.instrument_id = d.instrument_id AND r.fp = d.fp AND r.provision_id <> d.descendant_id
);

\echo '-- 1. operative descendants with no citable twin'
SELECT count(*) AS provisions, count(DISTINCT candidate_id) AS decisions, count(DISTINCT instrument_id) AS instruments
FROM unique_hidden;

\echo '-- 2. by decision, most first'
SELECT i.short_title, u.document_id, u.printed_label, u.source_page, count(*) AS hidden,
       u.candidate_id, min(left(regexp_replace(u.dtext, '\s+', ' ', 'g'), 90)) AS sample
FROM unique_hidden u JOIN instrument i ON i.id = u.instrument_id
GROUP BY i.short_title, u.document_id, u.printed_label, u.source_page, u.candidate_id
ORDER BY hidden DESC, i.short_title;
