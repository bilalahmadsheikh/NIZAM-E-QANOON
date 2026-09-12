-- Why each unreleased instrument is unreleased, and what would release it.
--
-- v_release_instrument excludes an expression while it has ANY pending contents
-- gap or ANY pending S7 unit. This script classifies every one of those units by
-- the repair it needs, then reports how many instruments each repair would free.
-- An instrument releases only when EVERY unit blocking it is covered, so the
-- yield of a repair is not the number of units it closes.
--
-- Reads only. Creates temp tables; nothing survives the session.
--
--   ./nz psql < tools/audit/blocked-release-worklist.sql
--
-- Contents-gap classes follow tools/triage_toc_gaps.py (a/b/c/d/e). S7 verdicts
-- replicate tools/s7_triage.py's rules in SQL so both queues can be joined per
-- instrument -- the tool classifies in Python and cannot be joined against.
--
-- The class-e work is the part that is not in either tool: a gap whose label and
-- heading are both absent from the TREE is not thereby absent from the SOURCE.
-- C5 = 0 guarantees every character of the PDF is in a text_block, so the raw
-- blocks can be searched directly. Doing that (excluding the contents list's own
-- blocks) splits the class in two, and most of it turns out to be law the corpus
-- holds but cannot cite.

\pset format aligned
SET work_mem='256MB';
-- ── contents-gap classes ────────────────────────────────────────────────────
CREATE TEMP TABLE _prov AS
 SELECT p.instrument_id, p.kind::text AS kind,
        regexp_replace(lower(p.label),'[^a-z0-9]','','g') AS lk,
        regexp_replace(lower(coalesce(p.heading,'')),'[^a-z0-9]','','g') AS hk
   FROM provision p JOIN instrument i ON i.id=p.instrument_id
                                     AND i.is_active AND i.duplicate_of IS NULL
  WHERE p.is_active;
CREATE INDEX ON _prov (instrument_id, lk);
CREATE INDEX ON _prov (instrument_id, hk);
ANALYZE _prov;
CREATE TEMP TABLE _gapc AS
SELECT g.instrument_id, g.toc_entry_id,
  CASE WHEN m.sec>0 THEN 'a' WHEN g.hk<>'' AND m.byhead=1 THEN 'b'
       WHEN g.hk<>'' AND m.byhead>1 THEN 'c'
       WHEN m.anylbl>0 THEN 'd' ELSE 'e' END AS klass
FROM (SELECT toc_entry_id, instrument_id,
             regexp_replace(lower(printed_label),'[^a-z0-9]','','g') AS lk,
             regexp_replace(lower(coalesce(printed_heading,'')),'[^a-z0-9]','','g') AS hk
        FROM v_toc_gap_pending) g
LEFT JOIN LATERAL (
  SELECT count(*) FILTER (WHERE p.lk=g.lk AND p.kind IN ('section','article')) AS sec,
         count(*) FILTER (WHERE p.lk=g.lk) AS anylbl,
         count(*) FILTER (WHERE g.hk<>'' AND p.hk=g.hk) AS byhead
    FROM _prov p WHERE p.instrument_id=g.instrument_id
                   AND (p.lk=g.lk OR (g.hk<>'' AND p.hk=g.hk))) m ON true;
-- ── S7 verdict classes (s7_triage rules, in SQL) ────────────────────────────
CREATE TEMP TABLE _s7c AS
SELECT v.instrument_id, v.id, CASE
  WHEN coalesce((v.evidence->>'group_size')::int,0) >= 10 THEN 'compendium'
  WHEN btrim(k.text) ~ '[*]{3,}' THEN 'inverted'
  WHEN btrim(k.text) ~ '^\s*\d+[A-Za-z-]*\.\s*[^.]{0,60}\.?\s*$'
       AND length(btrim(d.text)) >= greatest(3*length(btrim(k.text)),120) THEN 'inverted'
  WHEN length(btrim(d.text)) >= 3*length(btrim(k.text))
       AND length(btrim(d.text)) >= 120 THEN 'inverted'
  WHEN length(btrim(k.text)) >= 3*length(btrim(d.text))
       AND length(btrim(k.text)) >= 120 THEN 'probably-correct'
  WHEN coalesce(v.evidence->>'parent_kind','') NOT IN ('','instrument') THEN 'nesting'
  ELSE 'unclear' END AS verdict
  FROM v_structural_adjudication_pending v
  JOIN text_block k ON k.id=v.canonical_source_block_id
  JOIN text_block d ON d.id=v.source_block_id;
ANALYZE _gapc; ANALYZE _s7c;
-- ── one row per blocked instrument ──────────────────────────────────────────
CREATE TEMP TABLE _blocked AS
SELECT i.id AS instrument_id, i.document_id,
  coalesce(g.a,0) AS ga, coalesce(g.b,0) AS gb, coalesce(g.c,0) AS gc,
  coalesce(g.d,0) AS gd, coalesce(g.e,0) AS ge, coalesce(g.n,0) AS gaps,
  coalesce(s.inv,0) AS s_inv, coalesce(s.comp,0) AS s_comp,
  coalesce(s.nest,0) AS s_nest, coalesce(s.unc,0) AS s_unc,
  coalesce(s.ok,0) AS s_ok, coalesce(s.n,0) AS s7
FROM instrument i
LEFT JOIN (SELECT instrument_id, count(*) n,
             count(*) FILTER (WHERE klass='a') a, count(*) FILTER (WHERE klass='b') b,
             count(*) FILTER (WHERE klass='c') c, count(*) FILTER (WHERE klass='d') d,
             count(*) FILTER (WHERE klass='e') e FROM _gapc GROUP BY 1) g ON g.instrument_id=i.id
LEFT JOIN (SELECT instrument_id, count(*) n,
             count(*) FILTER (WHERE verdict='inverted') inv,
             count(*) FILTER (WHERE verdict='compendium') comp,
             count(*) FILTER (WHERE verdict='nesting') nest,
             count(*) FILTER (WHERE verdict='unclear') unc,
             count(*) FILTER (WHERE verdict='probably-correct') ok
             FROM _s7c GROUP BY 1) s ON s.instrument_id=i.id
WHERE i.is_active AND i.duplicate_of IS NULL
  AND (g.n > 0 OR s.n > 0);
ANALYZE _blocked;
SELECT count(*) AS blocked_instruments, sum(gaps) AS toc_units, sum(s7) AS s7_units FROM _blocked;

\echo ''
\echo '=== RELEASE YIELD — instruments freed when a repair set is applied ==='
\echo '(an instrument releases only when EVERY unit blocking it is covered)'
SELECT step, instruments, units FROM (
 SELECT 1 AS ord, 'R6  adjudicate probably-correct S7 (decision only)' AS step,
        count(*) AS instruments, sum(s_ok) AS units FROM _blocked
   WHERE gaps=0 AND s7=s_ok AND s_ok>0
 UNION ALL
 SELECT 2, 'R1  relink class-a gaps (exact-tree overlay, no replay)',
        count(*), sum(ga) FROM _blocked WHERE s7=0 AND gaps=ga AND ga>0
 UNION ALL
 SELECT 3, 'R2  + found_elsewhere class-b gaps',
        count(*), sum(ga+gb) FROM _blocked WHERE s7=0 AND gaps=ga+gb AND gb>0
 UNION ALL
 SELECT 4, 'R5  reparent nesting S7',
        count(*), sum(s_nest) FROM _blocked WHERE gaps=0 AND s7=s_nest AND s_nest>0
 UNION ALL
 SELECT 5, 'R4  S10 split compendium S7',
        count(*), sum(s_comp) FROM _blocked WHERE gaps=0 AND s7=s_comp AND s_comp>0
 UNION ALL
 SELECT 6, 'R3  parser repair: class-d gaps + inverted S7 (restores law)',
        count(*), sum(gd+s_inv) FROM _blocked
   WHERE gaps=gd AND s7=s_inv AND gd+s_inv>0
 UNION ALL
 SELECT 7, '--- CUMULATIVE: every mechanisable repair (R1-R6) ---',
        count(*), sum(gaps+s7) FROM _blocked
   WHERE gc=0 AND ge=0 AND s_unc=0
 UNION ALL
 SELECT 8, 'R7  needs a person: class c/e gaps or unclear S7',
        count(*), sum(gc+ge+s_unc) FROM _blocked WHERE gc+ge+s_unc>0
) x ORDER BY ord;

\echo ''
\echo '=== THE RESIDUE: what a person must actually read ==='
SELECT 'instruments needing any human reading' AS metric, count(*)::text AS value FROM _blocked WHERE gc+ge+s_unc>0
UNION ALL SELECT '  blocked by exactly one such unit', count(*)::text FROM _blocked WHERE gc+ge+s_unc=1 AND gaps+s7=1
UNION ALL SELECT '  distinct documents behind them', count(DISTINCT document_id)::text FROM _blocked WHERE gc+ge+s_unc>0
UNION ALL SELECT '  contents-gap pages to render (distinct doc+page)',
   (SELECT count(*)::text FROM (SELECT DISTINCT g.document_id,g.source_page FROM v_toc_gap_pending g
      JOIN _gapc c ON c.toc_entry_id=g.toc_entry_id AND c.klass IN ('c','e')) y)
UNION ALL SELECT '  unclear S7 units to read', (SELECT count(*)::text FROM _s7c WHERE verdict='unclear');

\echo ''
\echo '=== CAN THE class-e RESIDUE BE SHRUNK? Does the promised heading appear in the RAW TEXT? ==='
\echo '(C5=0 guarantees every character of the PDF is in a block, so absence here is real absence)'
CREATE TEMP TABLE _etest AS
SELECT g.toc_entry_id, g.document_id, g.instrument_id, g.printed_label, g.printed_heading,
       regexp_replace(lower(coalesce(g.printed_heading,'')),'[^a-z0-9]','','g') AS hk
  FROM v_toc_gap_pending g
  JOIN _gapc c ON c.toc_entry_id=g.toc_entry_id AND c.klass='e'
 WHERE length(regexp_replace(lower(coalesce(g.printed_heading,'')),'[^a-z0-9]','','g')) >= 12;
ANALYZE _etest;
SELECT count(*) AS class_e_with_a_usable_heading,
       count(*) FILTER (WHERE hit) AS heading_text_IS_in_the_document,
       count(*) FILTER (WHERE NOT hit) AS heading_text_is_NOT_in_the_document
  FROM (
   SELECT e.toc_entry_id,
          EXISTS (SELECT 1 FROM text_block b
                   WHERE b.document_id=e.document_id
                     AND regexp_replace(lower(b.text),'[^a-z0-9]','','g') LIKE '%'||e.hk||'%') AS hit
     FROM _etest e) x;

\echo ''
\echo '=== corrected: search only blocks OUTSIDE the contents list itself ==='
CREATE TEMP TABLE _tocblocks AS
 SELECT DISTINCT e.source_block_id AS block_id FROM instrument_toc_entry e
  WHERE e.source_block_id IS NOT NULL;
CREATE INDEX ON _tocblocks(block_id);
ANALYZE _tocblocks;
SELECT count(*) AS class_e_tested,
       count(*) FILTER (WHERE hit) AS heading_printed_in_body_too,
       count(*) FILTER (WHERE NOT hit) AS heading_appears_only_in_the_contents
  FROM (
   SELECT e.toc_entry_id,
          EXISTS (SELECT 1 FROM text_block b
                   WHERE b.document_id=e.document_id
                     AND NOT EXISTS (SELECT 1 FROM _tocblocks t WHERE t.block_id=b.id)
                     AND b.page_no <> (SELECT source_page FROM v_toc_gap_pending v
                                        WHERE v.toc_entry_id=e.toc_entry_id)
                     AND regexp_replace(lower(b.text),'[^a-z0-9]','','g') LIKE '%'||e.hk||'%') AS hit
     FROM _etest e) x;

\echo ''
\echo '=== evidence sample: the promised section, printed in the body, not in the tree ==='
\pset format unaligned
\pset fieldsep ' | '
SELECT e.document_id, e.printed_label, left(e.printed_heading,42) AS promised,
       b.page_no, left(regexp_replace(b.text,'\s+',' ','g'),84) AS body_block_found
  FROM _etest e
  JOIN LATERAL (
    SELECT b.page_no, b.text FROM text_block b
     WHERE b.document_id=e.document_id
       AND NOT EXISTS (SELECT 1 FROM _tocblocks t WHERE t.block_id=b.id)
       AND b.page_no <> (SELECT source_page FROM v_toc_gap_pending v WHERE v.toc_entry_id=e.toc_entry_id)
       AND regexp_replace(lower(b.text),'[^a-z0-9]','','g') LIKE '%'||e.hk||'%'
     ORDER BY b.page_no LIMIT 1) b ON true
 ORDER BY e.document_id LIMIT 10;

\pset format aligned
\pset format aligned
CREATE TEMP TABLE _cols AS
 SELECT b.document_id,
        percentile_disc(0.10) WITHIN GROUP (ORDER BY b.x0) AS x_left,
        percentile_disc(0.50) WITHIN GROUP (ORDER BY b.x0) AS x_body
   FROM text_block b
  WHERE b.document_id IN (SELECT DISTINCT document_id FROM _etest)
  GROUP BY b.document_id;
ANALYZE _cols;
\pset format aligned
CREATE TEMP TABLE _found AS
SELECT e.toc_entry_id, e.document_id, e.printed_label, b.id AS block_id,
       b.page_no, b.x0, b.x1, c.x_left, c.x_body,
       position(btrim(e.printed_label)||'.' in b.text) > 0 AS block_carries_the_number,
       b.text AS btext
  FROM _etest e
  JOIN _cols c ON c.document_id=e.document_id
  JOIN LATERAL (
    SELECT b.id,b.page_no,b.x0,b.x1,b.text FROM text_block b
     WHERE b.document_id=e.document_id
       AND NOT EXISTS (SELECT 1 FROM _tocblocks t WHERE t.block_id=b.id)
       AND b.page_no <> (SELECT source_page FROM v_toc_gap_pending v WHERE v.toc_entry_id=e.toc_entry_id)
       AND regexp_replace(lower(b.text),'[^a-z0-9]','','g') LIKE '%'||e.hk||'%'
     ORDER BY b.page_no LIMIT 1) b ON true;
ANALYZE _found;
SELECT count(*) AS promised_heading_found_in_body,
       count(*) FILTER (WHERE x_body-x_left >= 60) AS in_a_two_column_document,
       count(*) FILTER (WHERE x_body-x_left >= 60 AND x1 < x_body-4) AS printed_in_the_MARGIN_column,
       count(*) FILTER (WHERE block_carries_the_number) AS block_also_carries_the_number,
       count(*) FILTER (WHERE NOT block_carries_the_number) AS heading_printed_with_NO_number,
       count(DISTINCT document_id) AS documents
  FROM _found;
\pset format aligned
\echo '=== the 396 with NO number: is there operative text right after the heading? ==='
CREATE TEMP TABLE _after AS
SELECT f.toc_entry_id, f.document_id, f.printed_label, f.block_id, f.page_no,
       length(btrim(f.btext)) AS heading_block_len,
       (SELECT sum(length(btrim(n.text))) FROM text_block n
         WHERE n.document_id=f.document_id
           AND n.reading_order > (SELECT reading_order FROM text_block WHERE id=f.block_id)
           AND n.reading_order <= (SELECT reading_order FROM text_block WHERE id=f.block_id) + 2
       ) AS next_two_blocks_chars,
       (SELECT count(*) FROM provision_block pb
          JOIN block_assignment_set s ON s.id=pb.assignment_set_id AND s.is_active
         WHERE pb.block_id=f.block_id AND pb.provision_id IS NOT NULL) AS heading_block_owned
  FROM _found f WHERE NOT f.block_carries_the_number;
ANALYZE _after;
SELECT count(*) AS no_number_cases,
       count(*) FILTER (WHERE next_two_blocks_chars >= 120) AS substantive_text_follows,
       count(*) FILTER (WHERE next_two_blocks_chars < 120) AS little_or_nothing_follows,
       count(*) FILTER (WHERE heading_block_owned > 0) AS heading_block_already_in_a_provision,
       count(*) FILTER (WHERE heading_block_owned = 0) AS heading_block_orphaned,
       count(DISTINCT document_id) AS documents
  FROM _after;
\echo ''
\echo '=== sample: heading present, no number, substantive text following ==='
\pset format unaligned
\pset fieldsep ' | '
SELECT a.document_id, a.printed_label, a.page_no, a.heading_block_len AS hlen,
       a.next_two_blocks_chars AS follows, a.heading_block_owned AS owned,
       left(regexp_replace((SELECT text FROM text_block WHERE id=a.block_id),'\s+',' ','g'),60) AS heading_block
  FROM _after a WHERE a.next_two_blocks_chars >= 120 ORDER BY a.document_id LIMIT 10;
\pset format aligned
\echo '=== FINAL: release yield of the layout-aware parser repair ==='
-- gaps the repair would close: class a (relink), class b, class d (demoted),
-- and class e whose promised heading is printed in the body with text after it.
CREATE TEMP TABLE _closable AS
 SELECT toc_entry_id FROM _gapc WHERE klass IN ('a','b','d')
 UNION
 SELECT a.toc_entry_id FROM _after a WHERE a.next_two_blocks_chars >= 120
 UNION
 SELECT f.toc_entry_id FROM _found f WHERE f.block_carries_the_number;
ANALYZE _closable;
CREATE TEMP TABLE _resid AS
SELECT b.instrument_id, b.document_id, b.gaps, b.s7,
       (SELECT count(*) FROM _gapc c WHERE c.instrument_id=b.instrument_id
          AND NOT EXISTS (SELECT 1 FROM _closable z WHERE z.toc_entry_id=c.toc_entry_id)) AS gaps_left,
       b.s_unc AS s7_left_unclear, b.s_comp, b.s_nest, b.s_ok, b.s_inv
  FROM _blocked b;
ANALYZE _resid;
SELECT 'blocked instruments now' AS bucket, count(*)::text AS instruments FROM _resid
UNION ALL SELECT 'released by layout-aware repair + relink + S7 mechanisable',
   count(*)::text FROM _resid WHERE gaps_left=0 AND s7_left_unclear=0
UNION ALL SELECT '   ... still blocked, needing a person',
   count(*)::text FROM _resid WHERE gaps_left>0 OR s7_left_unclear>0
UNION ALL SELECT '   ... of those, blocked by ONE unit only',
   count(*)::text FROM _resid WHERE gaps_left+s7_left_unclear=1 AND gaps+s7=1
UNION ALL SELECT 'contents gaps still needing a page after the repair',
   (SELECT count(*)::text FROM _gapc c WHERE NOT EXISTS (SELECT 1 FROM _closable z WHERE z.toc_entry_id=c.toc_entry_id))
UNION ALL SELECT 'distinct documents behind those gaps',
   (SELECT count(DISTINCT g.document_id)::text FROM v_toc_gap_pending g
      WHERE NOT EXISTS (SELECT 1 FROM _closable z WHERE z.toc_entry_id=g.toc_entry_id));
