--
-- Drafted by agent CQ (10 Oct 2026, prepare mode); the lead renames it without -DRAFT before running it.
-- Pattern: tools/evidence/declare-source-incompleteness-510.sql / -1247.sql / -1822.sql.
--
-- Document 2205, THE SIND PUBLIC CONVEYANCES ACT, 1920 (Sind Act No. VII of 1920): the landed copy stops inside
-- section 20(3); sections 21-38 are not printed. Section 39 is repealed, as its contents row prints ('Repealed.]'),
-- and stands as a repealed stub from the contents disposition recorded on 24 Sep (assertion 212, kept).
--
-- Observation 3341, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-18-000095.pdf,
-- SHA-256 d2981d6cde41f757c289255369f3457d95633855b9f77d5acdce51ae3d4e9f23, eight pages.
--
-- A record already stands: source_incompleteness 3 (asserted 2026-09-21 by claude.source-incompleteness-review/1,
-- 'no_complete_copy_acquired', five network_error attempts 139-143: the portal did not answer). This file SUPERSEDES
-- it (supersedes_id 3) so that the standing record carries what has happened since: the owner's decision and a dated
-- refetch that reached the portal. Nothing in record 3 is wrong; it is kept.
--
-- Owner decision: decision-review-2026-10-10-i.json, document 2205, q1, choice "release-with-gap" (reviewer Bilal
-- Ahmad, page images reviewed): "Release the available sections 1-20 as source-verified text, marking section 20(3)
-- as truncated. Record sections 21-39 as missing from the supplied copy under source incompleteness (migration
-- 0054). Preserve their contents entries without generating corresponding legislative text. The absence of these
-- provisions must not be interpreted as repeal or omission from the Act itself. The missing portions may be
-- incorporated when a complete authoritative source becomes available."
-- Owner answer of 10 Oct 2026 (given to the lead; logged in CLAUDE-CLAIMS.md): section 39 stays a REPEALED stub, as
-- the contents prints it ('39. Repealed.]'); toc_disposition_assertion 212 is kept and not withdrawn. Only sections
-- 21-38 are recorded as missing from this copy.
--
-- Read from the renders on 2026-10-10 (agent CQ): p1 (a6f6275f...) and p2 (d2e15bc4...) are the contents: rows
-- 1-20 with 16A, then (p2) '21. Book of fares to be issued.', the caption 'Offences and punishments.', rows 22-29,
-- 'Procedure.', rows 30-33, 'Miscellaneous.', rows 34-38 and '39. Repealed.] Schedule. [Repealed.]'. pp3-8 print the
-- title, '[17th June, 1920]', long title, preamble and sections 1-20 in a bordered table. p8 (c0cd4bf2...) prints
-- 16A, 17, the cross-heading 'Fares and stands', 18, 19 and 20(1)-(3); the table closes after '(3) Every such driver
-- shall on demand produce such list for the information of any hirer of, or passenger travelling in, the conveyance'
-- -- no full stop -- and only footnotes 1-5 follow. There is no page 9. Section 1(2) itself names 'sections 36 and
-- 38', which this copy does not print.
--
-- "Marking section 20(3) as truncated": there is no per-provision truncation column in the schema; the mark is this
-- record's body_stops_at (and evidence.truncated_provision), which L6 reads with v_toc_gap_source_incomplete. s.20(3)
-- is released with exactly the printed words (no stop supplied, nothing completed).
--
-- A dry run of tools/record_source_refetch.py --observation 3341 on 2026-10-10 returned HTTP 200, application/pdf,
-- 200157 bytes, SHA-256 d2981d6c... = the held blob ('unchanged_copy'); it recorded nothing (prepare mode).
--
-- ORDER:
--   1. python tools/record_source_refetch.py --observation 3341 --apply
--      (a dated refetch of the official URL; 'unchanged_copy' if the portal serves the same bytes). If it reports a
--      DIFFERENT valid PDF it records nothing: land and read that copy first -- this file then refuses to run.
--   2. pin + replay (claude/agCQ/pin-2205.json, patch-2205.json). Disposition 212 is kept: the replay materialises
--      s.39 as a repealed stub linked to contents row 39.
--   3. this file. It refuses unless step 1's attempt (after record 3's last attempt) exists.
--   4. tools/adjudicate_toc_from_source.py with claude/agCQ/toc-2205-DRAFT.json (rows 21-38), naming the id this file
--      prints as source_incompleteness_id and the toc_entry_ids re-read after the replay.
--
-- Idempotent: once the new record governs observation 3341 a second run inserts nothing.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 3341 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 3341 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by,
    supersedes_id
)
SELECT 3341, 2205, 'no_complete_copy_acquired', NULL,
       'Page 8 of 8 ends inside section 20(3), "... for the information of any hirer of, or passenger travelling in, '
       'the conveyance", with no full stop; only footnotes 1-5 follow and there is no further page. Section 20(3) is '
       'released as printed and marked as cut off by this copy.',
       'Contents rows 21-38 (page 2), from "21. Book of fares to be issued." to "38. Powers may be exercised from time '
       'to time.". Row 39 "Repealed.] Schedule. [Repealed.]" is not part of the gap: the contents prints s.39 as '
       'repealed, and it stands as a repealed stub (owner, 10 Oct).',
       'All eight rendered pages read. The contents (pp1-2) list sections 1-20 with 16A and, on p2, sections 21-39 under '
       'the captions "Offences and punishments.", "Procedure." and "Miscellaneous.". The body (pp3-8) prints the title '
       '"Sind Act No.VII of 1920 [THE SIND PUBLIC CONVEYANCES ACT, 1920.]", "[17th June, 1920]", the long title, the '
       'preamble and sections 1-20 in a bordered table; p8 prints 16A, 17, the cross-heading "Fares and stands", 18, 19 '
       'and 20(1)-(3), and the table closes after "(3) Every such driver shall on demand produce such list for the '
       'information of any hirer of, or passenger travelling in, the conveyance" with no full stop. Only footnotes 1-5 '
       'follow. Sections 21-38 are printed nowhere, and nothing in the contents or the body marks them repealed or '
       'omitted; s.1(2) itself names sections 36 and 38. Their absence is a gap in this copy, not a repeal or omission '
       'from the Act (owner q1). Section 39, printed in the contents as "Repealed.]", is a repealed stub, not part of '
       'the gap (owner, 10 Oct).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_or(outcome = 'unchanged_copy')
            THEN 'The portal did not answer on 2026-09-21 (five network errors); a dated refetch of the official URL '
                 'on ' || to_char(max(attempted_at) FILTER (WHERE outcome = 'unchanged_copy'), 'YYYY-MM-DD')
                 || ' returned the same eight-page PDF (SHA-256 d2981d6c...); no copy printing sections 21-38 was '
                 'obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing sections 21-38 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'd2981d6cde41f757c289255369f3457d95633855b9f77d5acdce51ae3d4e9f23',
         'supersedes_reason', 'record 3 (2026-09-21) stands unchanged in substance; this record adds the owner '
                              'decision, the refetch that reached the portal and the contents rows the gap covers',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc2205-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2205-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2205-p8.png'),
         'render_sha256', jsonb_build_array(
           'a6f6275fb6b6bb19090b8a495da00c38429a892c34db2b7477e196ff2e4de510',
           'd2e15bc41b61b36f67a347f916c8b56c13f1a8bf4181daeaff5ba921c96da325',
           'c0cd4bf298362f4b970a2aa9d21acdf8e1728a542fcd07fb1faaaef52d305f87'),
         'truncated_provision', jsonb_build_object(
           'section', '20', 'subsection', '3', 'page', 8, 'source_block_id', 169403,
           'printed_end', 'Every such driver shall on demand produce such list for the information of any hirer of, '
                          'or passenger travelling in, the conveyance',
           'note', 'no full stop; the copy ends here. Released with exactly the printed words.'),
         'missing_contents_rows', jsonb_build_array(
           jsonb_build_object('printed_label', '21', 'printed_heading', 'Book of fares to be issued.', 'contents_page', 2, 'contents_source_block_id', 169311),
           jsonb_build_object('printed_label', '22', 'printed_heading', 'Keeping public conveyance without licence.', 'contents_page', 2, 'contents_source_block_id', 169312),
           jsonb_build_object('printed_label', '23', 'printed_heading', 'Failure to cause public conveyance to ply when so required by the police.', 'contents_page', 2, 'contents_source_block_id', 169313),
           jsonb_build_object('printed_label', '24', 'printed_heading', 'Licensee of public conveyance permitting unlicensed driver to use the same or permitting the same to be drawn by unlicensed horse.', 'contents_page', 2, 'contents_source_block_id', 169313),
           jsonb_build_object('printed_label', '25', 'printed_heading', 'Failure to produce public conveyance or horse for inspection.', 'contents_page', 2, 'contents_source_block_id', 169313),
           jsonb_build_object('printed_label', '26', 'printed_heading', 'Offences by drivers of public conveyances.', 'contents_page', 2, 'contents_source_block_id', 169314),
           jsonb_build_object('printed_label', '27', 'printed_heading', 'Failure to return licence or to notify address.', 'contents_page', 2, 'contents_source_block_id', 169315),
           jsonb_build_object('printed_label', '28', 'printed_heading', 'Injury to public conveyance.', 'contents_page', 2, 'contents_source_block_id', 169316),
           jsonb_build_object('printed_label', '29', 'printed_heading', 'Compensation payable by driver causing damage.', 'contents_page', 2, 'contents_source_block_id', 169317),
           jsonb_build_object('printed_label', '30', 'printed_heading', 'Arrest by police.', 'contents_page', 2, 'contents_source_block_id', 169318),
           jsonb_build_object('printed_label', '31', 'printed_heading', 'Procedure in case of dispute.', 'contents_page', 2, 'contents_source_block_id', 169319),
           jsonb_build_object('printed_label', '32', 'printed_heading', 'Licensee may be required to produce driver: penalty.', 'contents_page', 2, 'contents_source_block_id', 169320),
           jsonb_build_object('printed_label', '33', 'printed_heading', 'Refusal to pay fare.', 'contents_page', 2, 'contents_source_block_id', 169321),
           jsonb_build_object('printed_label', '34', 'printed_heading', 'Disposal of property: penalty.', 'contents_page', 2, 'contents_source_block_id', 169322),
           jsonb_build_object('printed_label', '35', 'printed_heading', 'Rules.', 'contents_page', 2, 'contents_source_block_id', 169323),
           jsonb_build_object('printed_label', '36', 'printed_heading', 'Extention of Act.', 'contents_page', 2, 'contents_source_block_id', 169324),
           jsonb_build_object('printed_label', '37', 'printed_heading', 'Power to apply or adapt certain provisions to vehicles not used for the purpose of plying for hire.', 'contents_page', 2, 'contents_source_block_id', 169325),
           jsonb_build_object('printed_label', '38', 'printed_heading', 'Powers may be exercised from time to time.', 'contents_page', 2, 'contents_source_block_id', 169325)),
         'repealed_not_missing', jsonb_build_object(
           'printed_label', '39', 'printed_heading', 'Repealed.]', 'contents_page', 2, 'contents_source_block_id', 169326,
           'toc_disposition_assertion_id', 212,
           'note', 'the contents prints "39. Repealed.]" and "Schedule. [Repealed.]"; s.39 stands as a repealed stub from '
                   'assertion 212 (owner answer 10 Oct 2026, logged in CLAUDE-CLAIMS.md); it is not part of this gap'),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-10-i.json',
           'document_id', 2205, 'question_id', 'q1',
           'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record; sections 21-38 '
                         'are shown as not available in this copy -- never as repealed or omitted, never fabricated.',
         'recovery_path', 'retry sindhlaws.gov.pk or find a Sind Government Gazette / Sindh Code copy of Sind Act VII of '
                          '1920 printing sections 21-38, then recover_acquisition.py --alternate-for 3341 --url <that '
                          'copy>; incorporating it needs no new owner decision (owner q1: "may be incorporated when a '
                          'complete authoritative source becomes available")'),
       'claude.source-incompleteness-review/1',
       3
  FROM acquisition_attempt
 WHERE source_observation_id = 3341
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND bool_or(attempted_at > (SELECT last_attempt_at FROM source_incompleteness WHERE id = 3))
   AND (SELECT id FROM v_source_incompleteness_latest WHERE source_observation_id = 3341) = 3;

DO $$
BEGIN
    IF (SELECT id FROM v_source_incompleteness_latest WHERE source_observation_id = 3341) = 3 THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 3341 after record 3: run '
                        'tools/record_source_refetch.py --observation 3341 --apply first';
    END IF;
END $$;

COMMIT;

-- The id to name as source_incompleteness_id in the contents readings.
SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error, supersedes_id
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 3341;
