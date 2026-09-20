-- RELEASED sections whose number is held by a fragment while the real section was accepted as a demotion.
--
-- Confirmed by hand on 17 Sep in three released instruments:
--   * Pakistan Nuclear Regulatory Authority Ordinance, 2001 -- s_2 is '2. It extends to the whole of
--     Pakistan.' (section 1's sub-section); the real '2. Definitions.____ In this Ordinance...' with its
--     17 definitions was accepted as a demotion and now sits at cl_2.
--   * Torture and Custodial Death (Prevention and Punishment) Act, 2022 -- the same shape.
--   * Sindh Mental Health Act, 2013 -- s_3 is ' (u) "psychiatrist" means...' from page 7; the real
--     '3. In this Act, unless there is anything repugnant...' with its definitions is cl_3.
-- The recorded rationales verified that the printed LABEL stayed reachable ('this demotion removes a
-- duplicate rather than a citation'), which is true and beside the point: the label now resolves to the
-- wrong text. A citation rendered from these records (INV-1) names the right number and quotes the wrong
-- provision.
--
-- Shape tested here, deliberately narrow so the rows are worth reading one by one:
--   * the decision is accept_non_citable and the instrument is released;
--   * the DEMOTED unit's first block opens with its own label as a section opener ('2. Definitions', '3. In');
--   * the KEPT unit's own text does not open that way -- it opens with a bracketed sub-part '(2)', '(u)',
--     or a commencement / extent sentence, i.e. it is a fragment of another section;
--   * the demoted subtree carries more text than the kept one.
-- Assert the rule, report the number.

\pset pager off

CREATE TEMP TABLE released_inversion AS
WITH acc AS (
  SELECT a.candidate_id, a.decided_by, c.instrument_id, c.document_id, c.printed_label,
         c.candidate_provision_id AS dem_id, c.canonical_provision_id AS kept_id,
         c.source_block_id, c.source_page, dt.text AS dem_block, kv.text AS kept_text
  FROM v_structural_adjudication_latest a
  JOIN v_active_structural_candidate c ON c.id = a.candidate_id
  JOIN v_release_instrument ri ON ri.id = c.instrument_id
  JOIN text_block dt ON dt.id = c.source_block_id
  JOIN v_provision kv ON kv.provision_id = c.canonical_provision_id
  WHERE a.resolution = 'accept_non_citable'
    AND c.printed_label ~ '^[0-9]{1,4}[A-Z]?$'
    AND dt.text ~ ('^\s*' || c.printed_label || '\.\s*[A-Z]')
    AND coalesce(kv.text, '') ~* '^\s*(\([a-z0-9]{1,4}\)|it extends|it shall come into force|this act may be called|these rules may be called)'
)
SELECT acc.*,
       (SELECT coalesce(sum(length(coalesce(v.text, ''))), 0) FROM provision p JOIN provision x ON x.path <@ p.path AND x.is_active
          JOIN v_provision v ON v.provision_id = x.id WHERE p.id = acc.dem_id) AS dem_chars,
       (SELECT coalesce(sum(length(coalesce(v.text, ''))), 0) FROM provision p JOIN provision x ON x.path <@ p.path AND x.is_active
          JOIN v_provision v ON v.provision_id = x.id WHERE p.id = acc.kept_id) AS kept_chars
FROM acc;

DELETE FROM released_inversion WHERE dem_chars <= kept_chars;

\echo '-- 1. how many released sections hold a fragment while the real section is demoted'
SELECT count(*) AS decisions, count(DISTINCT instrument_id) AS instruments FROM released_inversion;

\echo '-- 2. every one'
SELECT i.short_title, r.printed_label, r.source_page, r.dem_chars, r.kept_chars,
       left(regexp_replace(r.dem_block, '\s+', ' ', 'g'), 70) AS demoted_opens,
       left(regexp_replace(r.kept_text, '\s+', ' ', 'g'), 60) AS kept_text,
       r.decided_by, r.candidate_id
FROM released_inversion r JOIN instrument i ON i.id = r.instrument_id
ORDER BY r.dem_chars DESC;
