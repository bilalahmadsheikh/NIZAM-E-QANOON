-- Released sections whose own first block prints a DIFFERENT section number from their label.
--
-- Found while cataloguing withheld documents 3078, 3184 and 3277: where a printed contents and a
-- printed body disagree in numbering, the segmenter can pair contents rows with body sections by
-- position, so a provision is labelled and headed from the contents while holding another section's
-- text. Those three are withheld. This asks whether the same thing reached RELEASED law, where no
-- gate would stop a citation rendered from the record (INV-1) naming the wrong section.
--
-- Noise removed, in order, because each was confirmed by reading samples:
--   * the label appears anywhere in the first block as an opener -- the section opens mid-block;
--   * zero-padded serials ('05.', '08.') -- roster rows.
--
-- REMOVED 18 Sep 2026: `AND printed NOT LIKE ('%' || label)`, which excused a row whenever the
-- block-opening number ended with the label, on the theory that a footnote marker was fused in
-- front ('1273.' for 273). It carried two faults in opposite directions. It is anchored at the
-- BLOCK OPENING but applied to every section, including the many that open mid-block -- and
-- 7,113 blocks are the first_block of more than one active section, so the excuse frequently
-- described a different section than the row being judged. And where it did fire it assumed the
-- longer number was marker+label, when often the longer number is the real one and the LABEL is
-- the truncation ('19.' read as 9, '48.' as 8) -- excusing exactly the rows where a section has
-- silently taken another section's text.
--
-- Measured over the release (63,225 sections): the old excuse and the corrected one are
-- COMPLETELY DISJOINT -- 163 rows excused by the old are flagged by the corrected test, and 27
-- excused by the corrected test were being flagged. So this line was hiding 163 released
-- sections from review while excusing none of the right ones.
--
-- The corrected test is `.artifacts/corrected-fused-marker-filter.sql`: take the opener that
-- belongs to THIS section rather than the block's first line, and excuse only when the label
-- continues the instrument's numbering AND is unique in the instrument. Both tests are needed --
-- a RUN of truncations (5,6,7,8 standing for 45,46,47,48) defeats the first alone. It is not
-- inlined here because it takes over an hour over the release; run it when adjudicating
-- marker-vs-label, and read this listing as the review queue it says it is.
-- What is left still mixes two defects that need a reader to tell apart: a provision whose
-- first_block pointer is wrong (heading right, pointer at the previous section's block) and a
-- provision that is genuinely mis-labelled. Read the listing; do not act on the count.
-- KNOWN UNDER-COUNT. `printed` is read from the first block's OPENING, so a
-- section whose first_block points at its marginal note yields NULL and never
-- enters the listing at all. Document 3386 is the demonstration: its sections
-- 45, 47 and 48 appear, but 46 does not, because block 365984 opens with
-- "Dropping of proceedings." This listing is therefore a floor.
--
-- CLASSIFICATION, added 18 Sep 2026 and measured against source readings.
-- The listing mixes two populations and a reader had to separate them by eye
-- until now. One rule, verified against eleven rows read from the rendered page
-- across six documents, agrees with all eleven:
--
--   * the label is used twice in the instrument, OR another released section
--     already carries the PRINTED number  ->  defect. The label is a truncation
--     and this section has borrowed another's number. (6 of 6 source-read.)
--   * the label is unique, no section carries the printed number, and the
--     printed token ends with the label  ->  a footnote marker fused in front,
--     correct as released. (5 of 5 source-read.)
--
-- The second class is why the old one-line excuse existed; it was a real shape,
-- wrongly tested. Document 2605 prints a superscript 1 flattened onto "4." with
-- footnote "This section has been amended in its application to the Punjab...";
-- document 2362 runs a whole column of them, markers 2 through 8 down one page.
--
-- Do not act on the count -- roughly a third to a half of the rows are the
-- fused-marker class. Act on the classification, and read the defects.
--
-- Assert the rule, report the number.

\pset pager off

CREATE TEMP TABLE label_first_block_disagreement AS
WITH p AS (
  SELECT r.id, r.instrument_id, r.label, r.heading, tb.id AS first_block, tb.page_no, tb.text AS t,
         (regexp_match(tb.text, '^\s*(\d{1,4}[A-Z]?)\.\s'))[1] AS printed
  FROM v_release_provision r
  JOIN text_block tb ON tb.id = r.first_block
  WHERE r.kind = 'section' AND r.label ~ '^\d{1,4}[A-Z]?$'
)
SELECT * FROM p
WHERE printed IS NOT NULL
  AND printed <> label
  AND t !~ ('(^|[^0-9A-Za-z])' || label || '\s*[.\]]')
  AND printed !~ '^0\d';

\echo '-- 1. how many'
SELECT count(*) AS sections, count(DISTINCT instrument_id) AS instruments
FROM label_first_block_disagreement;

\echo '-- 2. classified: defect, or a footnote marker fused in front'
SELECT i.short_title, d.id AS provision_id, d.label, d.printed,
       CASE WHEN (SELECT count(*) FROM v_release_provision x
                   WHERE x.instrument_id = d.instrument_id
                     AND x.kind = 'section' AND x.label = d.label) >= 2
             OR EXISTS (SELECT 1 FROM v_release_provision y
                         WHERE y.instrument_id = d.instrument_id
                           AND y.kind = 'section' AND y.label = d.printed)
            THEN 'defect: label is a truncation'
            WHEN d.printed LIKE ('%' || d.label)
            THEN 'correct: fused marker'
            ELSE 'read it' END                                AS classification,
       left(coalesce(d.heading, ''), 36) AS heading,
       d.first_block, d.page_no, left(regexp_replace(d.t, '\s+', ' ', 'g'), 70) AS first_block_opens
FROM label_first_block_disagreement d
JOIN instrument i ON i.id = d.instrument_id
ORDER BY classification, i.short_title, d.label;

\echo '-- 3. the split'
SELECT CASE WHEN (SELECT count(*) FROM v_release_provision x
                   WHERE x.instrument_id = d.instrument_id
                     AND x.kind = 'section' AND x.label = d.label) >= 2
             OR EXISTS (SELECT 1 FROM v_release_provision y
                         WHERE y.instrument_id = d.instrument_id
                           AND y.kind = 'section' AND y.label = d.printed)
            THEN 'defect: label is a truncation'
            WHEN d.printed LIKE ('%' || d.label)
            THEN 'correct: fused marker'
            ELSE 'read it' END AS classification,
       count(*) AS sections, count(DISTINCT d.instrument_id) AS instruments
FROM label_first_block_disagreement d
GROUP BY 1 ORDER BY 2 DESC;
