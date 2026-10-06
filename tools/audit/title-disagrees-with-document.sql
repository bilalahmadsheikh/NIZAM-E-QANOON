-- Is a released instrument actually the Act its title claims?
--
-- WHY THIS EXISTS. Document 4587 is released as "SINDH PUBLIC CONVEYANCES
-- (AMENDMENT) ACT, 1996". Its own first page prints
--
--     THE ALTAF HUSSAIN UNIVERSITY AT KARACHI ACT, 2014.
--     SINDH ACT NO. I OF 2015.
--
-- The catalogued URL served a different statute and nothing noticed, because
-- the title is carried from the CATALOGUE while the text comes from the PDF and
-- no criterion compares them. Someone citing the Public Conveyances Act is
-- handed a university charter -- a false identity published as law, which is
-- worse than a missing one: a gap is visible, this is not.
--
-- C1 cannot catch it ("every acquired file becomes a blob" never asks what is
-- IN the file), C9 cannot ("a partial copy is never published" -- this copy is
-- complete, just of another Act), and A1/A2 cannot (character recall against an
-- independent extractor is perfect; we extracted the wrong document faithfully).
--
-- THE TEST, and why the obvious one fails. The first version asked what
-- FRACTION of a title's words appear in the document. On the one case known to
-- be wrong it scored 67% -- indistinguishable from healthy -- because "sindh"
-- occurs in 42 blocks of the Altaf Hussain University Act and "public" in 3.
-- Averaging over title words lets common words vouch for a statute they do not
-- identify.
--
-- So ask about the RAREST word instead. Rank each title's words by how many
-- documents in the corpus contain them, take the least common, and ask whether
-- THAT word appears in this expression. "Conveyance" appears in 0 blocks of
-- document 4587; "sindh" and "public" are worthless as identity. A title whose
-- most distinctive word is absent from its own text is the signature of a
-- mis-served file.
--
-- It is a REPORTING query, not a gate, and deliberately so: a low overlap can
-- also mean a faithful document whose title the catalogue rendered differently
-- (an English title over an Urdu gazette, an Act known by two names). Every row
-- needs a page read before it is called a defect. Assert the rule; report the
-- number.
--
--     ./nz psql < tools/audit/title-disagrees-with-document.sql

\pset format aligned
\set ON_ERROR_STOP on
SET work_mem='256MB';

-- Words that carry no identity: they appear in almost every statute's title.
CREATE TEMP TABLE stop_word(w text PRIMARY KEY);
INSERT INTO stop_word(w) VALUES
  ('the'),('of'),('and'),('for'),('to'),('in'),('on'),('at'),('by'),('act'),
  ('acts'),('ordinance'),('ordinances'),('rules'),('rule'),('regulations'),
  ('regulation'),('order'),('orders'),('amendment'),('amending'),('bill'),
  ('notification'),('schedule'),('province'),('provincial'),('government'),
  ('pakistan'),('doc'),('pdf'),('no'),('nos');

WITH released AS (
    SELECT r.id, r.document_id, r.short_title,
           r.source_start_block_id, r.source_end_block_id
      FROM v_release_instrument r
     WHERE coalesce(btrim(r.short_title),'') <> ''
),
-- The words of the EXPRESSION's own opening, not the document's.
--
-- A first attempt read `page_no <= 3` of the document and reported 15
-- zero-overlap rows, every one of them document 4497 -- ESTACODE, a compendium
-- whose expressions are separate rules beginning hundreds of pages in. Its
-- first three pages are a cover sheet, so "Civil Servants (Appeal) Rules, 1977"
-- shared no word with them and read as a mis-served file. That was the query's
-- blind spot, not a defect in the corpus.
--
-- An instrument records where it starts and ends in the block stream, so use
-- that: the opening of the expression itself, which is where a statute prints
-- its own name. Documents that record no span fall back to their first pages.
opening AS (
    SELECT rel.id AS instrument_id,
           lower(string_agg(b.text, ' ' ORDER BY b.reading_order)) AS head
      FROM released rel
      JOIN text_block b ON b.document_id = rel.document_id
     WHERE (rel.source_start_block_id IS NULL AND b.page_no <= 3)
        OR (rel.source_start_block_id IS NOT NULL
            AND b.id >= rel.source_start_block_id
            AND b.id <= coalesce(rel.source_end_block_id, rel.source_start_block_id + 400)
            AND b.id < rel.source_start_block_id + 400)
     GROUP BY rel.id
),
title_word AS (
    SELECT rel.id, rel.document_id, rel.short_title, w.word
      FROM released rel
      CROSS JOIN LATERAL regexp_split_to_table(lower(rel.short_title), '[^a-z]+') AS w(word)
     WHERE length(w.word) >= 4
       AND NOT EXISTS (SELECT 1 FROM stop_word s WHERE s.w = w.word)
),
-- How many RELEASED instruments carry each word in their title. A word in one
-- title is an identifier; a word in six hundred is vocabulary.
word_frequency AS (
    SELECT word, count(DISTINCT id) AS titles_using
      FROM title_word GROUP BY word
),
ranked AS (
    SELECT tw.id, tw.document_id, tw.short_title, tw.word, wf.titles_using,
           row_number() OVER (PARTITION BY tw.id ORDER BY wf.titles_using, tw.word) AS rarity_rank
      FROM title_word tw
      JOIN word_frequency wf ON wf.word = tw.word
),
scored AS (
    SELECT r.id, r.document_id, r.short_title,
           r.word         AS rarest_word,
           r.titles_using AS titles_sharing_that_word,
           (o.head LIKE '%'||r.word||'%') AS rarest_word_present,
           (SELECT count(*) FROM title_word t2 WHERE t2.id = r.id)               AS distinctive_words,
           (SELECT count(*) FROM title_word t2
             WHERE t2.id = r.id AND o.head LIKE '%'||t2.word||'%')               AS words_found
      FROM ranked r
      JOIN opening o ON o.instrument_id = r.id
     WHERE r.rarity_rank = 1
)
SELECT document_id,
       left(short_title, 50) AS released_as,
       rarest_word,
       titles_sharing_that_word AS shared_by,
       rarest_word_present      AS present,
       distinctive_words AS words_in_title,
       words_found       AS found_in_document,
       round(100.0 * words_found / nullif(distinctive_words,0)) AS pct
  INTO TEMP title_check
  FROM scored
 WHERE distinctive_words >= 2;

\echo ''
\echo '-- THE SIGNAL: a released instrument whose title''s rarest word is absent from its own text'
SELECT count(*) AS rarest_word_missing FROM title_check WHERE NOT present;

\echo ''
\echo '-- SPLIT BY WHETHER ANOTHER ACT USES THE WORD -- this is the discriminator'
\echo '-- shared_by = 1: the word occurs in no other title, so it is almost always'
\echo '--   a misspelling IN THE CATALOGUE (genral, eeucation, emplyees, lndemnity).'
\echo '--   The document is the right Act; its stored name is spelt wrong.'
\echo '-- shared_by >= 2: other Acts use this word correctly and THIS text lacks it.'
\echo '--   That is the mis-served-file shape. Document 4587 sits here, on'
\echo '--   "conveyances", and a page read confirms it is the Altaf Hussain'
\echo '--   University Act published as the Sindh Public Conveyances Act.'
SELECT CASE WHEN shared_by = 1 THEN 'likely a catalogue misspelling'
            ELSE 'CHECK: other Acts use this word; this text does not' END AS band,
       count(*) AS instruments
  FROM title_check WHERE NOT present GROUP BY 1 ORDER BY 1 DESC;

\echo ''
\echo '-- the mis-served candidates, for reading (most-shared word first)'
SELECT document_id, released_as, rarest_word, shared_by, pct
  FROM title_check WHERE NOT present AND shared_by >= 2
 ORDER BY shared_by DESC, document_id LIMIT 40;

\echo ''
\echo '-- for contrast: the averaged measure, which MISSES the known case at 67%'
SELECT CASE WHEN pct = 0 THEN '0%'
            WHEN pct < 34 THEN '1-33%'
            WHEN pct < 67 THEN '34-66%'
            WHEN pct < 100 THEN '67-99%'
            ELSE '100%' END AS averaged_overlap,
       count(*) AS instruments,
       count(*) FILTER (WHERE NOT present) AS of_which_rarest_word_missing
  FROM title_check GROUP BY 1 ORDER BY min(pct);
