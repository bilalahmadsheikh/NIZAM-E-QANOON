-- DRAFT by agent K6 (18 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-4612-superseded.sh. Pattern: declare-truncated-sources.sql
-- (documents 33 -> 4634 and 127 -> 3573: superseded_by_complete_copy, the complete copy already in the corpus).
--
-- Document 4612, observation 4743 (https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-19-000003.pdf), catalogued
-- 'THE SINDH CENSARSHIP OF FILM RULES, 2014': the Sindh Government Gazette of Thursday 27 July 2017 (No. 30), seventeen pages,
-- gazette pp703-720, carrying the Culture Department's notification making THE SINDH CENSORSHIP OF FILM RULES, 2014.
-- It is a PARTIAL copy: gazette page 706 is not in the file (PDF p3 is gazette 705, PDF p4 is gazette 707), so rule 2(n)-(p)
-- and rules 3-9 are not printed; pp1-2 are the issue's cover and S&GAD service notifications; several passages are faded.
--
-- The complete Rules are ALREADY IN THE CORPUS AND RELEASED: document 1922 (observations 4528, 9571, 9577; the Sindh Code
-- copy https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-15-000266.pdf, 29 pages), instrument e0595d43 (283
-- provisions). Identity by READING both (agent K6, 18 Oct 2026), not by title: wherever 4612 is legible it prints 1922's
-- text -- rule 1(1) 'These rules may be called the Sindh Censorship of Film Rules, 2014.'; rule 2's definitions (a)-(m) word
-- for word, including '(b) ... under rule 10', '(j) "Member"', the printed '"Penal in relation to a Centre" means a Panel of
-- Members'; rule 10 (10(4) 'the appeal under section 7', 'Sale of Publicity Material'); 12(1) 'under clause (a) of sub-rule
-- (2) of rule 10 is pre-[excised]'; 18 'deposit with the Board a certified copy ...'; 19(a)-(l); rule 36 with its printed
-- repeated sub-rules (2)-(4); rule 37 (Repeal of the Censorship of Films Rules, 1980); Schedule II (TABLE OF FEES, see
-- rule 10 (2) (d)) with its 'Revised Rate' column and rows 01-12. (Compared provision by provision: rules 1-2, 10, 12, 18,
-- 19, 36, 37 and Schedule II; the rest of 4612 was read on its renders and agrees in structure: rules 11-37, Forms A-J.) The SHA-256s differ (a4205d24... the
-- Gazette scan, 0a0acf0c... the Code copy), as a Gazette scan and a Code derivative must; the reading settles identity.
--
-- Owner: decision-review-2026-10-18-4612.json, document 4612, q1 'superseded-by-1922' ("Mark it a copy of 1922
-- (Recommended)"); card claude/agK6/card-4612.md. Nothing new is released and nothing is reconstructed; 4612's blocks and
-- tree stay in the database. tools/apply_source_incompleteness.py then sets 4612's active instrument duplicate_of 1922's.
--
-- No refetch: the complete copy is held (as for document 127 -> 3573, "no new acquisition was needed").
-- Idempotent: a second run inserts nothing once a record stands for 4743.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM document WHERE id = 4612 AND is_active) THEN
        RAISE EXCEPTION 'document 4612 is not active (was it promoted? the record must name the active revision)';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM instrument i JOIN v_release_instrument r ON r.id = i.id
                    WHERE i.document_id = 1922 AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION 'document 1922 has no released canonical instrument: refusing to supersede 4612 by nothing';
    END IF;
END $$;

INSERT INTO source_incompleteness
    (source_observation_id, document_id, resolution, complete_document_id,
     body_stops_at, promised_top, observed,
     attempts_considered, first_attempt_at, last_attempt_at, observed_error,
     evidence, asserted_by)
SELECT 4743, 4612, 'superseded_by_complete_copy', 1922,
       'gazette page 706 is missing between PDF p3 (gazette 705, ending at rule 2(m)) and PDF p4 (gazette 707, opening at '
       'rule 10(1))',
       'rule 2(n)-(p) and rules 3-9 (gazette page 706); the complete Rules, rules 1-37 and Schedules I-II, are held in '
       'document 1922',
       'Seventeen pages read on the review-pack renders and the owner''s notes (ocr-review-doc-4612.json, 17/17 accepted). '
       'p1-2 (gazette 703-704): the Gazette cover, CONTENTS and six S&GAD service notifications (other gazette content). '
       'p3 (705): CULTURE DEPARTMENT, the notification and rules 1-2(m). p4-17 (707-720): rules 10-37, Schedule I (Forms '
       'A-J), Schedule II. Gazette 706 is not printed; rule 12(2), 18, 19(a) and parts of 10(1) are faded.',
       1,
       coalesce(o.fetched_at, o.ingested_at), coalesce(o.fetched_at, o.ingested_at),
       'no refetch: the complete copy of these Rules is already in the corpus (document 1922, the Sindh Code copy, '
       'released); the landed Gazette file itself lacks gazette page 706',
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'review_method', 'both documents read: 4612 on its review-pack renders and the owner''s page notes; 1922 from its '
                          'released provisions (instrument e0595d43); identity from the Rules'' title and rule 1(1), the '
                          'definitions (a)-(m) word for word, rules 10, 12, 18, 19 where 4612 is legible, the repeated '
                          '36(2)-(4), rule 37 and Schedule II''s columns and rows, compared provision by provision',
         'attempt_ids', '[]'::jsonb,
         'note', 'the complete copy was already in the corpus under another observation on the same portal; no new '
                 'acquisition was needed',
         'complete_document_id', 1922,
         'complete_instrument', 'e0595d43-d5f7-47d1-b86a-de3d5e9d5834',
         'complete_observation_ids', jsonb_build_array(4528, 9571, 9577),
         'complete_url', 'https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-15-000266.pdf',
         'truncated_sha256', (SELECT sha256 FROM document WHERE id = 4612),
         'complete_sha256', (SELECT sha256 FROM document WHERE id = 1922),
         'sha256_note', 'a Gazette scan and a Code copy differ byte-wise; the reading settles identity',
         'render_artifact', jsonb_build_array(
           '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4612/images/page-003.png',
           '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4612/images/page-004.png'),
         'render_sha256', jsonb_build_array(
           'b3e403c175dab206b1f4b15583ff4f7eb6ac365201057b4d5a1caf36005613ba',
           '0b9687142489de31fc79ad4c8614f03ddd27f5e5f25caeb44f558d0a69e1ad2e'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'gazette page 706: rule 2(n)-(p) and rules 3-9',
                                                         'between', 'rule 2(m) (PDF p3) and rule 10(1) (PDF p4)')),
         'owner_decision', jsonb_build_object(
           'source', '.artifacts/decision-review/exports/decision-review-2026-10-18-4612.json',
           'document_id', 4612, 'question_id', 'q1', 'choice', 'superseded-by-1922',
           'card', '.artifacts/release-work-2026-09-24/claude/agK6/card-4612.md'),
         'recovery_path', 'already held: the Rules are released from document 1922; nothing further is expected'),
       'claude.source-incompleteness-review/1'
  FROM source_observation o
 WHERE o.id = 4743
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4743);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4743 AND resolution = 'superseded_by_complete_copy'
                      AND document_id = 4612 AND complete_document_id = 1922) THEN
        RAISE EXCEPTION 'no superseded_by_complete_copy record 4612 -> 1922 for observation 4743';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, document_id, resolution, complete_document_id, attempts_considered
  FROM v_source_incompleteness_latest WHERE source_observation_id = 4743;
