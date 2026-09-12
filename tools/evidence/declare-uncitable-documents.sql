-- Three active documents carry no instrument. All three were segmented and
-- REJECTED, which is the quality gate working, but a rejection with no recorded
-- reason is indistinguishable from a silent failure -- so `./nz lint` reports
-- them, correctly, as text nothing can cite.
--
-- Read against the source, each rejection is right and the reason is different:
--
--   2044, 2046   the document's entire text is "THIS LAW HAS BEEN REPEALED" --
--                28 characters. The portal serves a placeholder where the law
--                used to be. There is no operative text to segment, and no
--                parser change will produce one.
--
--   3479         21 pages whose blocks read "NAME OF THE DEPARTMENT",
--                "FUNCTIONAL UNIT", "APPOINTING AUTHORITY", "NAME OF THE POST"
--                -- a cadre-schedule table. It has columns, not sections. C4 and
--                C5 confirm every character is stored and reachable; what it
--                lacks is citable structure, because the source has none.
--
-- Recording this turns three open findings into three declared facts. It deletes
-- nothing: the text stays exactly where it is, and a future decision to give
-- schedules their own citable form (docs/03b, "schedules as tables") can still
-- act on it.

BEGIN;

INSERT INTO extraction_assertion (sha256, page_no, kind, evidence, detail, asserted_by)
SELECT d.sha256, 1, 'source_content_confirmed',
       'The source page carries the single line "THIS LAW HAS BEEN REPEALED" and '
       'nothing else -- 28 characters for the whole document. The portal serves a '
       'placeholder in place of the repealed law, so there is no operative text to '
       'segment. Segmentation rejected it as wholly unstructured, which is correct.',
       jsonb_build_object(
           'document_id', d.id,
           'purpose',     'no-operative-text',
           'char_count',  d.char_count,
           'review',      'direct-text',
           'segmentation_outcome', 'rejected'),
       'claude.source-review/1'
  FROM document d
 WHERE d.id IN (2044, 2046) AND d.is_active
   AND NOT EXISTS (SELECT 1 FROM extraction_assertion a
                    WHERE a.sha256 = d.sha256 AND a.page_no = 1
                      AND a.detail->>'purpose' = 'no-operative-text');

INSERT INTO extraction_assertion (sha256, page_no, kind, evidence, detail, asserted_by)
SELECT d.sha256, 1, 'source_content_confirmed',
       'The document is a cadre-schedule table: its blocks are column headings '
       '("NAME OF THE DEPARTMENT", "FUNCTIONAL UNIT", "APPOINTING AUTHORITY", '
       '"NAME OF THE POST") across 21 pages. It contains no numbered provisions, '
       'so segmentation rejected it as unstructured. Every character remains '
       'stored and reachable (C4, C5); what the source lacks is citable structure.',
       jsonb_build_object(
           'document_id', d.id,
           'purpose',     'table-document-no-provisions',
           'pages',       d.page_count,
           'char_count',  d.char_count,
           'review',      'direct-text',
           'segmentation_outcome', 'rejected'),
       'claude.source-review/1'
  FROM document d
 WHERE d.id = 3479 AND d.is_active
   AND NOT EXISTS (SELECT 1 FROM extraction_assertion a
                    WHERE a.sha256 = d.sha256 AND a.page_no = 1
                      AND a.detail->>'purpose' = 'table-document-no-provisions');

COMMIT;
