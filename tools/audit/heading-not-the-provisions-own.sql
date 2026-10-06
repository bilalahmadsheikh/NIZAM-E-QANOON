-- A11 -- provisions whose heading is not the name their own printed block gives them.
--
-- WIRED, 21 September 2026, gated at threshold 0. The value is read from the census recorded by
-- `tools/census_heading_mislabel.py` into `heading_mislabel_census` (migration 0053), never
-- recomputed here -- this file's SQL shadow is for INSPECTION ONLY and over-reports 4.7x, for the
-- reason set out under "THE A11 FRAGMENT" below. The "WHY NOT YET" section at the foot is kept as
-- the record of what had to be true first, with what actually happened noted against each point.
--
-- A11 is RED as it stands: 5 provisions in 3 documents (4043 x3, 4139, 1683), down from 101 in 30.
-- `.patch_schedule_row_name.py` is the measured repair for all five and is handed over, not
-- applied. See "WHERE IT STANDS" at the foot.
--
-- WHAT IT CATCHES.  A citation that resolves to the right text under the WRONG NAME. Nothing flags
-- it today. The contents-gap queue cannot see it by construction: a contents list running at an
-- offset to the body still finds a same-numbered provision for every entry, so it produces no
-- unmatched entry and no gap. A5 passes, A10 passes, and the gap queue is empty for several of the
-- worst affected documents.
--
-- Doc 4499 (Industrial Relations Act, 2008) is the case. Page 30 prints
--
--     37. Penalty for obstructing inspector.  Whoever willfully obstructs ...
--     38. Penalty for contravening section 34 or section 35, etc.
--
-- while the printed contents on page 2 lists those two at 36 and 37, because the contents omits a
-- section the body enacts. Pairing on the number alone gave section 37 the name of 38, and 38 the
-- name of "WORKS COUNCIL", for twenty-two consecutive sections. Doc 3508 repeats it for twenty, doc
-- 3387 for ten, doc 4406 for six, doc 3677 for seven.
--
-- THE RULE.  Where a provision's own first block opens "<its label>. <Name>.--" and the tree
-- carries a materially different name, the tree asserts something the source contradicts.
--
-- FOUR GUARDS, each written because the number was wrong without it:
--
--   1. a name is not operative text.  Without this the Canal and Drainage Act's "3. In this Act
--      unless there be something repugnant in the subject or context,--" reads as a name
--      contradicting the genuine marginal note "Interpretation clause.", and every marginal-note
--      statute in the corpus joins the list.
--   2. a name does not open with a preposition.  Every Sindh and Punjab Finance Act prints its
--      amending sections as "2. In the Stamp Act, 1899, in its application to Sindh, ..." with the
--      real heading in the margin.  This guard alone removed 27.
--   3. a name is not editorial apparatus.  Doc 1382's section 2 prints "Clause (d) omitted by
--      Khyber Pakhtunkhwa Ordinance ..." where the marginal note is "Definitions." -- a footnote at
--      the head of a provision, which is A10's defect, counted there.
--   4. one name written two ways is one name.  The CrPC's contents prints "Issues of process" where
--      its body prints "Issus of process", and "Special Judicial Magistrates" against the body's
--      "Special Judicial 2[* * *] Magistrate".  Doc 2511 prints "Welfare Fund" against a carried
--      "Punjab Employees Welfare Fund" -- truncated at the FRONT, which prefix comparison misses.
--      Doc 2582 abbreviates "Agriculture Pesticide Technical Advisory Committee" to "APTA".  The
--      Court Fees Act prints "costs" where the contents prints "cost".
--
-- The count fell 6,682 -> 1,514 -> 140 -> 113 -> 102 -> 101 as those guards were added. Each fall
-- was a class of honest drafting being removed, not a defect being hidden.
--
-- THE AUTHORITATIVE COUNT is `./nz mislabelled-headings` (tools/census_heading_mislabel.py): 101 in
-- 30 documents. It applies all four guards, including per-token fuzzy matching and initialism
-- detection, neither of which is expressible in a criteria.sql scalar subquery.
--
-- THIS FILE IS ONLY ITS SQL SHADOW -- guards 1-3 plus prefix containment. MEASURED, it reports 472
-- in 221 documents: 4.7x the true count, and dominated by exactly the instruments where a wrong
-- number would be most alarming -- CrPC 44, Customs Act 14, PAF Act 13, Army Act 11, Constitution
-- 11, PPC 11. Every one of those is guard 4's population: one name spelt two ways. So the SQL form
-- below is for INSPECTION ONLY and must not be used as A11's value. See "WHY NOT YET" point 3.

\pset pager off

CREATE TEMP TABLE heading_not_own AS
SELECT i.document_id                                        AS doc,
       left(i.short_title, 46)                              AS title,
       p.id                                                 AS provision_id,
       p.label,
       p.first_page                                         AS page,
       p.heading                                            AS heading_carried,
       btrim((regexp_match(
           regexp_replace(tb.text, '\s+', ' ', 'g'),
           '^[[:space:]]*(?:[0-9]{0,3}[[:space:]]*\[[[:space:]]*)?'
           || regexp_replace(p.label, '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g')
           || '[[:space:]]*[.)][[:space:]]*([A-Z][^.]{6,90}?)[[:space:]]*'
           || '(?:\.[[:space:]]*[-]{1,2}|\.[[:space:]]*__|\.[[:space:]]+)'
       ))[1], ' .-')                                        AS printed_name,
       (EXISTS (SELECT 1 FROM instrument_toc_entry e
                 WHERE e.provision_id = p.id))              AS reachable_by_citation
  FROM provision p
  JOIN instrument i ON i.id = p.instrument_id AND i.is_active AND i.duplicate_of IS NULL
  JOIN text_block tb ON tb.id = p.first_block
 WHERE p.is_active
   AND p.heading IS NOT NULL AND btrim(p.heading) <> ''
   AND p.kind::text IN ('section','article','rule','regulation','paragraph');

DELETE FROM heading_not_own WHERE printed_name IS NULL;

-- guards 1 and 2: a name is not operative text, and does not open with a preposition
DELETE FROM heading_not_own
 WHERE printed_name ~* '\m(shall|may|must|means?|includes?|is|are|was|were|has|have|had|be|been|appl(y|ies|ied)|extends?|comes?|said|this|these|whoever|nothing|no|any|every|where|when|unless|if|subject|notwithstanding|provided|following|hereby|such|there)\M'
    OR printed_name ~* '^(in|of|for|to|on|at|by|from|under|upon|after|before|throughout|where|when|while|if|save|except|with|without|during|against|notwithstanding|subject|provided|according|pursuant|whenever|whereas)\M'
    OR array_length(regexp_split_to_array(btrim(printed_name), '\s+'), 1) NOT BETWEEN 2 AND 14;

-- guard 3: a name is not editorial apparatus
DELETE FROM heading_not_own
 WHERE printed_name ~* '^(clause|sub-?section|sub-?rule|proviso|words?|figures?|letters?|brackets?|commas?|entry|entries|schedule)\M[^\n]{0,80}?\m(omitted|substituted|subs\.|ins\.|inserted|added|deleted|rep\.)\M'
    OR printed_name ~* '^(subs\.|ins\.|added|omitted|substituted|inserted)\M';

-- guard 4, partial: one name differently truncated at the FRONT of the string
DELETE FROM heading_not_own
 WHERE lower(regexp_replace(printed_name, '[^a-zA-Z0-9]', '', 'g'))
         LIKE lower(regexp_replace(heading_carried, '[^a-zA-Z0-9]', '', 'g')) || '%'
    OR lower(regexp_replace(heading_carried, '[^a-zA-Z0-9]', '', 'g'))
         LIKE lower(regexp_replace(printed_name, '[^a-zA-Z0-9]', '', 'g')) || '%'
    OR length(regexp_replace(printed_name, '[^a-zA-Z0-9]', '', 'g')) < 10
    OR length(regexp_replace(heading_carried, '[^a-zA-Z0-9]', '', 'g')) < 10;

\echo '=== SQL shadow: provisions whose heading is not the name their own block prints'
SELECT count(*) AS provisions,
       count(DISTINCT doc) AS documents,
       count(*) FILTER (WHERE reachable_by_citation) AS reachable_by_citation
  FROM heading_not_own;

\echo '=== by document'
SELECT doc, min(title) AS title, count(*) AS n
  FROM heading_not_own GROUP BY doc ORDER BY n DESC, doc LIMIT 30;

\echo '=== the rows themselves'
SELECT doc, label, page,
       left(heading_carried, 44) AS heading_carried,
       left(printed_name, 44)    AS source_prints
  FROM heading_not_own
 ORDER BY doc, page, label LIMIT 80;

-- ---------------------------------------------------------------------------------------------
-- THE A11 FRAGMENT, as criteria.sql now carries it.  In the `m` CTE:
--
--     ,(SELECT mislabelled           FROM v_heading_mislabel_census_current) AS heading_not_own
--     ,(SELECT mislabelled_documents FROM v_heading_mislabel_census_current) AS heading_not_own_docs
--     ,(SELECT variant_spellings     FROM v_heading_mislabel_census_current) AS heading_variants
--     ,(SELECT never_measured        FROM v_heading_mislabel_census_current) AS heading_census_absent
--     ,(SELECT is_stale              FROM v_heading_mislabel_census_current) AS heading_census_stale
--     ,(SELECT to_char(measured_at,'YYYY-MM-DD HH24:MI')
--         FROM v_heading_mislabel_census_current)                            AS heading_census_at
--
-- and in the assembly:
--
--     UNION ALL SELECT 'A11','provision headings are the name the source prints',
--            CASE WHEN heading_census_absent THEN 'no census recorded'
--                 WHEN heading_census_stale THEN
--                      heading_not_own||' in '||heading_not_own_docs||
--                      ' docs, measured '||coalesce(heading_census_at,'?')||
--                      ' against a corpus that has since changed'
--                 ELSE heading_not_own||' in '||heading_not_own_docs||
--                      ' docs; '||heading_variants||' spelling variants' END,
--            '0; census fresh',
--            CASE WHEN heading_census_absent THEN 'FAIL (no census)'
--                 WHEN heading_census_stale  THEN 'FAIL (stale)'
--                 WHEN heading_not_own = 0   THEN 'PASS'
--                 ELSE 'FAIL' END FROM m
--
-- Three states, three answers. A cached measurement can be wrong in two ways before it is wrong
-- about the corpus -- never taken, or taken for a corpus that has since moved -- and only the third
-- state may report a pass. The release check at the foot of criteria.sql was widened from
-- `result='FAIL'` to `result <> 'PASS'` so that both stale answers fail closed; matching only the
-- bare word would have let a stale census through as a silent pass, which is the exact failure a
-- stored number invites.
--
-- Staleness is decided by `v_heading_mislabel_corpus_state`: an md5 over the census population
-- itself -- (id, kind, label, heading, first_block) for every active provision of an active,
-- non-duplicate instrument, of a citable kind, with a heading and a block. 83,184 rows, 212 ms
-- warm. Two cheaper watermarks were measured and REJECTED, and not on cost:
--
--   * the count of active instruments (4,692 rows, 7 ms) cannot see a re-segmentation at all --
--     appending a revision retires one instrument and adds its replacement, so the count is
--     identical. 751 documents were re-segmented in one day without moving it once;
--   * max(instrument.created_at) (8 ms) advances on a run but is a clock, not an identity: blind to
--     a duplicate_of resolution, to a retirement with no replacement, and to a restore that moves
--     the corpus BACKWARDS, after which the census would read fresh while describing a tree that is
--     no longer there.
--
-- The digest is the population, so it moves in both directions.
-- ---------------------------------------------------------------------------------------------
-- WHY NOT YET.
--
-- 1. The detector is not certifiably clean.  Four false-positive classes were found in four
--    successive rounds of review, each after the previous round looked finished.  Of the 101 rows
--    now reported, every one read against the page was genuine (4499, 3508, 3387, 4406, 4234, 1716,
--    4139, 1683), but two -- doc 209 s.5 and doc 4490 s.141 -- could not be confirmed from source in
--    the time available.  I cannot assert zero false positives, and A10 could be gated at 0 only
--    because its 80 were all read.
--
-- 2. It cannot reach 0 today even if clean.  Segmenting the 59 affected documents with the repair in
--    `.patch_offset.py` takes the census from 113 to 2 with no section gained or lost.  The two
--    survivors -- doc 1683 s.4 and doc 4139 r.15 -- are genuine but have a DIFFERENT root cause: a
--    schedule row segmented as a section, wearing the real section's name.  Until the patch lands,
--    is re-segmented, and those two documents are repaired, an A11 at threshold 0 is red for
--    reasons already known and recorded, which is a tripwire, not a test.
--
-- 3. Its value cannot be computed where criteria.sql computes values.  Measured above: the SQL
--    form over-reports 4.7x, and the excess is concentrated in the CrPC, the PPC, the Constitution
--    and the service Acts.  An A11 that printed 472 would be a worse artefact than no A11.
--
-- PROPOSED INSTEAD, until all three are met: adopt A11 in the REPORTED form A5 already uses in this
-- file ("contents agreement (median; pending gaps reported)"), with its value carried by the census
-- tool rather than by criteria.sql, and promote it to threshold 0 when (a) every row it reports has
-- been read against the page, (b) the repair has landed and been re-segmented, and (c) the two
-- schedule-row documents are fixed.
--
--     UNION ALL SELECT 'A11','provision headings are the name the source prints (reported)',
--            heading_not_own::text,'reported; 0 after the heading repair lands','PASS' FROM m
--
-- A threshold other than 0 is the other legitimate answer, and I am NOT proposing one. A non-zero
-- threshold here would have to mean "this many citations may name the wrong provision", and there
-- is no number of those that is correct. The reported form says the same thing without pretending
-- a budget exists.
