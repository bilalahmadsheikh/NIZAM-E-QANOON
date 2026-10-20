-- Lead, 20 Oct 2026. Migration 0065: document 4641 (observation 4130, Sindh Code PUB-16-000550, catalogued 'SINDH
-- AGRICULTURAL INCOME TAX (AMENDMENT) ORDINANCE, 1997') is an UNOFFICIAL TRANSLATION of document 1522.
-- Applied by .artifacts/release-work-2026-09-24/claude/lead-4641-non-authoritative.sh, which passes -v export_sha=<sha256
-- of the owner's export>.
--
-- 4641 is the OCR revision of 3842 (same PDF, sha 42f17058...). It prints the Ordinance in Urdu with English headings;
-- its closing note says the translation is for public information and cannot be used in a court. Its body matches
-- 1522, 'SINDH ORDINANCE NO. XVI of 1997' [20 December 1997], section by section, including s.3(3) 'net income from 1
-- July 1998', s.4's substitution of section 6-A, and the preamble (lead, 17 Oct). Its title page prints 'SINDH ORDINANCE
-- NO.X OF 1997', and its contents item 4 'Amendment of section 73 of Act II of 1899'; the Sindh Judicial Academy statute
-- index (sja.gos.pk, WebHelp_Pro/S.htm, read 20 Oct 2026) lists the 1997 amendment of this title only as Ord. XVI (PLD
-- 1998 Sindh 38), so the title and contents are misprints in the translation. Renders: claude/renders/doc3842-p1.png,
-- doc3842-p2.png.
--
-- Owner: decision-review-2026-10-20-4641-4642.json, 4641 q1 'keep-1522' ("do each recommended by u").

\set ON_ERROR_STOP on
BEGIN;

INSERT INTO source_non_authoritative_copy
    (source_observation_id, document_id, kind, authoritative_document_id, observed,
     owner_decision, evidence, recorded_by)
SELECT 4130, 4641, 'unofficial_translation', 1522,
       'An Urdu translation (English headings) of the Sindh Agricultural Income Tax (Amendment) Ordinance, 1997. Its '
       'closing note: for public information, cannot be used in a court. Body = document 1522 (Ordinance XVI of 1997, '
       '20 December 1997) section by section. Title page misprints "SINDH ORDINANCE NO.X OF 1997" and contents item 4 '
       '"Amendment of section 73 of Act II of 1899" (1522 s.4 substitutes section 6-A); the SJA statute index lists '
       'this amendment only as XVI.',
       jsonb_build_object('export', '.artifacts/decision-review/exports/decision-review-2026-10-20-4641-4642.json',
                          'document_id', 4641, 'question_id', 'q1', 'choice', 'keep-1522'),
       jsonb_build_object(
         'copy_sha256', (SELECT sha256 FROM document WHERE id = 4641),
         'authoritative_sha256', (SELECT sha256 FROM document WHERE id = 1522),
         'finding', 'unofficial_translation',
         'reviewer_type', 'assistant',
         'basis', 'the translation''s own closing note (not for use in court); 4641 read against 1522 section by '
                  'section (lead, 17 Oct 2026); Sindh Judicial Academy statute index S.htm lists only Ord. XVI of 1997',
         'renders', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc3842-p1.png',
                                      '.artifacts/release-work-2026-09-24/claude/renders/doc3842-p2.png'),
         'index_url', 'https://sja.gos.pk/assets/library/WebHelp_Pro/S.htm',
         'export_sha256', :'export_sha'),
       'claude.non-authoritative-review/1'
 WHERE NOT EXISTS (SELECT 1 FROM source_non_authoritative_copy WHERE source_observation_id = 4130);

COMMIT;

SELECT id, document_id, kind, authoritative_document_id FROM source_non_authoritative_copy
 WHERE source_observation_id = 4130;
