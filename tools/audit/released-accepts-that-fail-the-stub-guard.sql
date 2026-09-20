-- Recorded accept_non_citable decisions in RELEASED instruments that the stub guard would refuse today.
--
-- tools/adjudicate_s7_from_source.py refuses accept_non_citable when the demoted unit carries 500+
-- characters and the kept unit less than half of that: 'the shape that produced 359 citations resolving
-- to less than half their provision'. Earlier bulk paths recorded accepts without that guard -- the
-- 26 commencement inversions superseded on 17 Sep were all of this shape (demoted Definitions with
-- 400 to 4,232 characters against a kept one-line extent sentence of 33 to 351). This lists every
-- remaining released accept that fails the guard, with the demoted unit's opening so each can be read.
-- Assert the rule, report the number.

\pset pager off

CREATE TEMP TABLE acc AS
SELECT a.candidate_id, a.decided_by, c.instrument_id, c.document_id, c.printed_label,
       c.candidate_provision_id AS dem_id, c.canonical_provision_id AS kept_id,
       c.source_block_id, c.source_page, c.canonical_source_page
FROM v_structural_adjudication_latest a
JOIN v_active_structural_candidate c ON c.id = a.candidate_id
JOIN v_release_instrument ri ON ri.id = c.instrument_id
WHERE a.resolution = 'accept_non_citable';

CREATE TEMP TABLE sizes AS
SELECT acc.candidate_id,
       (SELECT coalesce(sum(pb.chars), 0) FROM provision p JOIN provision x ON x.path <@ p.path AND x.is_active
          AND x.instrument_id = p.instrument_id JOIN provision_block pb ON pb.provision_id = x.id WHERE p.id = acc.dem_id) AS dem_chars,
       (SELECT coalesce(sum(pb.chars), 0) FROM provision p JOIN provision x ON x.path <@ p.path AND x.is_active
          AND x.instrument_id = p.instrument_id JOIN provision_block pb ON pb.provision_id = x.id WHERE p.id = acc.kept_id) AS kept_chars
FROM acc;

\echo '-- 1. released accepts the stub guard would refuse'
SELECT count(*) AS decisions, count(DISTINCT acc.instrument_id) AS instruments
FROM acc JOIN sizes s USING (candidate_id)
WHERE s.dem_chars >= 500 AND s.kept_chars < s.dem_chars * 0.5;

\echo '-- 2. every one'
SELECT i.short_title, acc.printed_label, acc.source_page, s.dem_chars, s.kept_chars, acc.decided_by,
       left(regexp_replace(dt.text, '\s+', ' ', 'g'), 70) AS demoted_opens,
       left(regexp_replace(coalesce(kv.text, ''), '\s+', ' ', 'g'), 50) AS kept_text,
       acc.candidate_id
FROM acc JOIN sizes s USING (candidate_id)
JOIN instrument i ON i.id = acc.instrument_id
JOIN text_block dt ON dt.id = acc.source_block_id
JOIN v_provision kv ON kv.provision_id = acc.kept_id
WHERE s.dem_chars >= 500 AND s.kept_chars < s.dem_chars * 0.5
ORDER BY s.dem_chars DESC;
