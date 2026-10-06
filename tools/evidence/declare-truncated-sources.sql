-- Three landed files that are partial copies of their statutes, and what was
-- done about each. Found by reading pages on 20-21 Sep 2026.
--
-- Every attempt below was actually made from this machine on 21 Sep 2026 and
-- its result is recorded verbatim -- the HTTP status, the bytes, the SHA-256
-- where one came back, the connection error where none did. Nothing here is
-- inferred from the catalogue.
--
-- This deletes nothing. The truncated documents, their text blocks and their
-- provision trees all remain, because everything in the PDF stays in the
-- database. What the supersessions change is which instrument the release
-- publishes as the Act, so that a reader asking for section 6 of the Raisani
-- Hospital Act gets section 6 instead of a gap.
--
-- Governing contract: docs/02-corpus-and-ingestion.html section 2;
-- schema: infra/postgres/migrations/0054, 0055.

BEGIN;

-- ---------------------------------------------------------------------------
-- The attempts.
-- ---------------------------------------------------------------------------

-- Document 127, observation 1342. The Balochistan Code still serves the same
-- seven-page file at its catalogued URL: HTTP 200, a valid PDF, and a SHA-256
-- identical to the blob already held. Refetching this source cannot help.
INSERT INTO acquisition_attempt
    (source_observation_id, requested_url, final_url, http_status, media_type,
     byte_length, response_sha256, outcome, error, attempted_at)
VALUES
    (1342,
     'http://balochistancode.gob.pk/lawdir/f371e560-8ae9-4e60-a19c-fc7adde65ef5.pdf',
     'http://balochistancode.gob.pk/lawdir/f371e560-8ae9-4e60-a19c-fc7adde65ef5.pdf',
     200, 'application/pdf', 23599,
     'd19d65a9a1db4920532fd5bb9efa5dbee5d82e8551bfec3aa3bffc26333d1100',
     'unchanged_copy',
     'portal serves the identical seven-page copy; body still stops inside '
     'section 2 of the twenty-nine its contents lists',
     timestamptz '2026-09-21 08:11:00+00');

-- Document 2205, observation 3341. sindhlaws.gov.pk resolves to 103.205.178.1
-- and refuses the connection on both 443 and 80. Five attempts, plus an
-- independent check over a different network path, all failed the same way.
INSERT INTO acquisition_attempt
    (source_observation_id, requested_url, http_status, outcome, error,
     attempted_at)
SELECT 3341,
       'https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-18-000095.pdf',
       NULL, 'network_error',
       'Failed to connect to sindhlaws.gov.pk port 443: Couldn''t connect to '
       'server (103.205.178.1; no route to host on 443 and 80)',
       at
  FROM (VALUES (timestamptz '2026-09-21 08:19:23+00'),
               (timestamptz '2026-09-21 08:19:31+00'),
               (timestamptz '2026-09-21 08:19:37+00'),
               (timestamptz '2026-09-21 08:19:44+00'),
               (timestamptz '2026-09-21 08:19:51+00')) AS t(at);

-- ---------------------------------------------------------------------------
-- The declarations.
-- ---------------------------------------------------------------------------

-- Document 33 -> document 4634. The nine-page Balochistan Gazette copy landed
-- on 12 Sep 2026 as observation 9573 and holds sections 1 to 19 complete.
--
-- Identity was established by READING BOTH, not by title: this corpus has
-- titles that match across genuinely different instruments. The SHA-256s
-- differ (7f9bd7b1... against d3242860...), which is expected and proves
-- nothing either way -- one is a Code-portal derivative, the other a Gazette
-- scan. What matches is the content: Act No. III of 2012 in both; passed by
-- the Provincial Assembly of Balochistan on 20 June 2012 in both; assented to
-- by the Governor on 26 June 2012 in both; Balochistan Gazette (Extraordinary)
-- No. 80 of 28 June 2012 in both; the preamble word for word; and sections 1
-- to 5 word for word, up to the exact clause where document 33 stops.
INSERT INTO source_incompleteness
    (source_observation_id, document_id, resolution, complete_document_id,
     body_stops_at, promised_top, observed,
     attempts_considered, first_attempt_at, last_attempt_at, observed_error,
     evidence, asserted_by)
VALUES (
    1358, 33, 'superseded_by_complete_copy', 4634,
    'section 5, mid-clause',
    'section 16 of its own printed contents; the Gazette copy prints 19',
    'Three pages. Page 1 is the contents, page 2 the enacting formula, page 3 '
    'the body. The last block reads "Administration of 5. The administration '
    'and management of the affairs of the" and the file ends there, with no '
    'terminal stop, no Schedule and no imprint. Sections 6 to 19 were never '
    'printed in this copy.',
    2,
    timestamptz '2026-09-12 19:34:05+00',
    timestamptz '2026-09-21 08:11:00+00',
    'the Balochistan Code publishes this Act only as the three-page extract; '
    'the complete text exists in the Gazette and was acquired separately',
    jsonb_build_object(
        'reviewer_type', 'assistant',
        'review_method', 'every page of both documents read block by block '
                         'from text_block; identity established from Act '
                         'number, assembly and assent dates, gazette number '
                         'and date, and word-for-word agreement of the '
                         'preamble and sections 1-5',
        'attempt_ids', '[]'::jsonb,
        'alternate_observation_id', 9573,
        'alternate_url', 'https://health.balochistan.gov.pk/wp-content/uploads/2025/03/2012.pdf',
        'truncated_sha256', (SELECT sha256 FROM document WHERE id = 33),
        'complete_sha256', (SELECT sha256 FROM document WHERE id = 4634),
        'sha256_note', 'the two files differ, as a Code derivative and a '
                       'Gazette scan must; SHA equality would have proved '
                       'sameness, inequality proves nothing and the reading '
                       'settles it',
        'complete_copy_pages', 9,
        'complete_copy_sections', '1-19',
        'gazette_number_in_both', 'No. 80, 28 June 2012',
        'recovery_path', 'already recovered; nothing further is expected'),
    'claude.source-incompleteness-review/1');

-- Document 127 -> document 3573. The complete twenty-eight-page copy was
-- ALREADY IN THE CORPUS and nobody had noticed: observation 1302, a different
-- lawdir GUID on the same Balochistan Code portal, catalogued under the fuller
-- title "The Balochistan Witness Protection Act, 2016". It holds sections 1 to
-- 29 and the Schedule to item 18.
--
-- Identity by reading: "(Balochistan Act IV of 2016)" and "[5th April, 2016]"
-- in both; the preamble word for word; section 1(1) to (3) word for word;
-- section 2's definitions word for word INCLUDING the printer's duplicated
-- "(c)" and "(d)" labels, which both copies reproduce identically. One
-- discrepancy is recorded rather than smoothed over: document 127's footnote
-- cites Balochistan Gazette (Extraordinary) No. 426 and document 3573's cites
-- No. 42, both dated 5 April 2016. One of the two misprints the number; the
-- rest of the evidence is unambiguous.
INSERT INTO source_incompleteness
    (source_observation_id, document_id, resolution, complete_document_id,
     body_stops_at, promised_top, observed,
     attempts_considered, first_attempt_at, last_attempt_at, observed_error,
     evidence, asserted_by)
VALUES (
    1342, 127, 'superseded_by_complete_copy', 3573,
    'section 2, definition (j), on page 4 of 7',
    'section 29 of its own printed contents',
    'Seven pages. Pages 1-2 are the contents, listing sections 1 to 29. Page 3 '
    'is the enacting formula. Page 4 holds sections 1 and 2 and ends at '
    'definition (j). Page 5 contains nothing but "(See Schedule on Next Page)". '
    'Pages 6-7 print the Schedule, fifteen numbered offences. Sections 3 to 29 '
    'are absent from the file. The segmenter then bound the contents headings '
    'to the Schedule items, so the tree published "section 3: Application of '
    'the Act and overriding effect" whose text is the single word "Murder." -- '
    'a false citation, which is the reason this could not be left in place.',
    1,
    timestamptz '2026-09-21 08:11:00+00',
    timestamptz '2026-09-21 08:11:00+00',
    'HTTP 200, application/pdf, 23599 bytes, SHA-256 identical to the copy '
    'already held: the portal still serves the partial file at this URL',
    jsonb_build_object(
        'reviewer_type', 'assistant',
        'review_method', 'every page of both documents read block by block '
                         'from text_block; identity established from Act '
                         'number, commencement date, and word-for-word '
                         'agreement of the preamble, section 1 and section 2 '
                         'including its duplicated clause labels',
        'attempt_ids', (SELECT coalesce(jsonb_agg(a.id ORDER BY a.id), '[]'::jsonb)
                          FROM acquisition_attempt a
                         WHERE a.source_observation_id = 1342
                           AND a.outcome = 'unchanged_copy'),
        'alternate_observation_id', 1302,
        'alternate_url', 'http://balochistancode.gob.pk/lawdir/cb084d4a-13ab-4f2c-9800-7f4d6eb561cb.pdf',
        'truncated_sha256', (SELECT sha256 FROM document WHERE id = 127),
        'complete_sha256', (SELECT sha256 FROM document WHERE id = 3573),
        'complete_copy_pages', 28,
        'complete_copy_sections', '1-29',
        'gazette_number_discrepancy',
            'document 127 cites Gazette (Extraordinary) No. 426 and document '
            '3573 cites No. 42, both dated 5 April 2016; recorded, not resolved',
        'note', 'the complete copy was already in the corpus under a second '
                'observation on the same portal; no new acquisition was needed',
        'recovery_path', 'none needed; the complete copy is document 3573'),
    'claude.source-incompleteness-review/1');

-- Document 2205. No complete copy exists in the corpus and none could be
-- obtained: the Sindh Code portal refuses connections.
INSERT INTO source_incompleteness
    (source_observation_id, document_id, resolution, complete_document_id,
     body_stops_at, promised_top, observed,
     attempts_considered, first_attempt_at, last_attempt_at, observed_error,
     evidence, asserted_by)
VALUES (
    3341, 2205, 'no_complete_copy_acquired', NULL,
    'section 20(3), mid-clause, on page 8 of 8',
    'section 39 of its own printed contents',
    'Eight pages. Pages 1-2 are the contents, listing sections 1 to 39 through '
    'the headings "Offences and punishments" and beyond. The body runs from '
    'section 1 to section 20 and the last prose on the last page reads "Every '
    'such driver shall on demand produce such list for the information of any '
    'hirer of, or passenger travelling in, the conveyance", with no terminal '
    'stop. Only the page''s footnote apparatus follows it. Sections 21 to 39 '
    'were never printed in this copy.',
    5,
    timestamptz '2026-09-21 08:19:23+00',
    timestamptz '2026-09-21 08:19:51+00',
    'Failed to connect to sindhlaws.gov.pk port 443: Couldn''t connect to '
    'server (103.205.178.1); port 80 gives no route to host; an independent '
    'fetch over a different network path returned ECONNREFUSED',
    jsonb_build_object(
        'reviewer_type', 'assistant',
        'review_method', 'every page read block by block from text_block; '
                         'the catalogued URL requested five times from this '
                         'machine and once over an independent network path',
        'attempt_ids', (SELECT coalesce(jsonb_agg(a.id ORDER BY a.id), '[]'::jsonb)
                          FROM acquisition_attempt a
                         WHERE a.source_observation_id = 3341
                           AND a.attempted_at >= timestamptz '2026-09-21 00:00:00+00'),
        'truncated_sha256', (SELECT sha256 FROM document WHERE id = 2205),
        'corpus_searched_for_alternate', true,
        'corpus_search_result',
            'the only other Sindh observations naming this Act are its '
            'amendments: observation 3340 (Amendment Act, 1996) and '
            'observation 4269 (Amendment Ordinance, 1984). Neither reproduces '
            'the principal Act. Observation 3340 is separately defective: the '
            'file it landed, document 4587, is the Altaf Hussain University at '
            'Karachi Act, 2014, not a Public Conveyances amendment at all.',
        'independent_corroboration',
            'the fresh parse produced a parser_defect reading on 19 of the 39 '
            'contents entries -- the 19-of-39 shape of a truncated copy, not '
            'of a parser fault',
        'recovery_path', 'retry sindhlaws.gov.pk when the portal answers '
                         'again, then recover_acquisition.py --alternate-for '
                         '3341 --url <the Sindh Code or Gazette copy>'),
    'claude.source-incompleteness-review/1');

COMMIT;
