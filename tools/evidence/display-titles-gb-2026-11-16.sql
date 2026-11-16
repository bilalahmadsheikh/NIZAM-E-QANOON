-- Display titles for the 27 Gilgit-Baltistan laws landed 16 Nov 2026 (recrawl-2026-11-16/1, archived captures of
-- gba.gov.pk). Their catalogue titles are the portal's FILE NAMES ('gb envirment protection act 2016', 'gb tomporary
-- resisence act 2016', 'gbla finance act 2010'). Each name below is the law's own short-title clause, read from its
-- s.1 (quoted), with OCR spacing joined ('G ilg it- Balt ist an' -> 'Gilgit-Baltistan', 'Gilgit- Baltistan') and a
-- printed citation ('Act, No. III of 2017') rendered as the year. Nothing is added that the clause does not print.
-- Two clauses disagree with the catalogue beyond spelling and are recorded as printed:
--   11379 prints 'These rules may be called the Gilgit-Baltistan Legislative Assembly Finance Committee Rules-2010'
--         (catalogued 'gbla finance act 2010'; the instrument kind stays as segmented and is reported, not changed);
--   11382 prints 'Environmental Protection Act, 2014' (catalogued 2016, the file's upload year).
-- Append-only; a later reading supersedes by a newer row.

BEGIN;

WITH d(doc, name, quote) AS (VALUES
  (11356, 'The Gilgit-Baltistan Rented Premises Act, 2010', 'This Act may be called the Gilgit- Baltistan Rented premises Act. No. VI of 2010.'),
  (11357, 'The Gilgit-Baltistan Anti-Corruption Establishment Act, 2017', 'This Act may be called the Gilgit-Baltistan Anti-Corruption Establishment Act, No. III of 2017.'),
  (11358, 'The Gilgit-Baltistan Legislative Assembly Secretariat Recruitment Terms and Condition Act, 2010', 'This Act may be called the Gilgit Baltistan Legislative Assembly Secretariat Recruitment terms and condition Act, 2010.'),
  (11359, 'The Gilgit-Baltistan Child Marriages Restraint Act, 2015', 'This Act may be called the Gilgit-Baltistan Child Marriages Restraint Act, No. I of 2015.'),
  (11360, 'The Gilgit-Baltistan Technical Education & Vocational Training Act, 2018', 'This Act may be called Gilgit-Baltistan Technical Education & Vocational Training Act – 2018.'),
  (11361, 'The Gilgit-Baltistan Legislative Assembly Speaker (Salaries, Allowances and Privileges) Act, 2010', 'This Act shall be called the Gilgit-Baltistan Legislative Assembly Speaker (Salaries, Allowances and Privileges) Act No. II of 2010.'),
  (11362, 'The Gilgit-Baltistan Parliamentary Secretaries (Salary, Allowances and Privileges) Act, 2010', 'This Act may be called the Gilgit-Baltistan Parliamentary Secretaries (Salary, Allowances and Privileges) Act, 2010.'),
  (11363, 'The Gilgit-Baltistan Legislative Assembly Deputy Speaker (Salaries, Allowances and Privileges) Act, 2010', 'This Act shall be called the Gilgit-Baltistan Legislative Assembly Deputy Speaker (Salaries, Allowances and Privileges) Act No. III of 2010.'),
  (11364, 'The Gilgit-Baltistan Prohibition of Interest on Private Loans Act, 2017', 'This Act may be called the Gilgit Baltistan Prohibition of Interest on Private Loans Act, No. IV of 2017.'),
  (11365, 'The Gilgit-Baltistan Legislative Assembly Members (Salaries, Allowances and Privileges) (Amendment) Act, 2018', 'This Act may be called the Gilgit Baltistan Legislative Assembly Members (Salaries, Allowances and Privileges) (Amendment) Act, 2018.'),
  (11366, 'The Gilgit-Baltistan Prohibition of Expressing Matters on Walls Act, 2016', 'This Act may be called the Gilgit-Baltistan Prohibition of Expressing Matters on Walls Act, 2016.'),
  (11367, 'The Gilgit-Baltistan Medical College (Governing Body) Act, 2016', 'This Act may be called the Gilgit-Baltistan Medical College (Governing Body) Act, 2016.'),
  (11368, 'The Gilgit-Baltistan Charities Act, 2018', 'This Act may be cited as the Gilgit-Baltistan Charities Act 2018.'),
  (11369, 'The Gilgit-Baltistan Sound Systems (Regulation) Act, 2017', 'This Act may be called the Gilgit-Baltistan Sound Systems (Regulation) Act No. I of 2017.'),
  (11370, 'The Gilgit-Baltistan Excise Act, 2018', 'This Act may be called the Gilgit- Baltistan Excise Act, 2018;'),
  (11371, 'The Gilgit-Baltistan Government Servants Benevolent Fund & Group Insurance Act, 2018', 'This Act may be called the Gilgit-Baltistan Government Servants Benevolent Fund & Group Insurance Act, 2018.'),
  (11372, 'The Protection against Harassment of Women at the Workplace Act, 2013', 'This Act may be called the Protection against Harassment of women at the Workplace Act No. I of 2013. It extends to the whole of Gilgit-Baltistan.'),
  (11373, 'The Gilgit-Baltistan Prohibition of Corporal Punishment Act, 2015', 'This Act may be called the Gilgit-Baltistan Prohibition of Corporal Punishment Act, 2015.'),
  (11374, 'The Gilgit-Baltistan Information of Temporary Residents Act, 2016', 'This Act may be cited as the Gilgit-Baltistan Information of Temporary Residents Act 2016.'),
  (11375, 'The Gilgit-Baltistan Security of Vulnerable Establishments Act, 2016', 'This Act may be called the Gilgit-Baltistan Security of Vulnerable Establishments Act 2016.'),
  (11376, 'The Gilgit-Baltistan Health Department (Regularization of Services of Doctors) Act, 2018', 'This act may be called the Gilgit-Baltistan Health Department (Regularization of Services of Doctors) Act, 2018'),
  (11377, 'The Gilgit-Baltistan Pre-emption Act, 2010', 'This Act may be called the Gilgit-Baltistan Pre-emption Act, 2010,'),
  (11378, 'The Gilgit-Baltistan Police Welfare Fund Act, 2018', 'This act may be called The Gilgit- Baltistan Police Welfare Fund Act, No. I of 2018.'),
  (11379, 'The Gilgit-Baltistan Legislative Assembly Finance Committee Rules, 2010', 'These rules may be called the Gilgit –Baltistan Legislative Assembly Finance Committee Rules-2010.'),
  (11380, 'The Gilgit-Baltistan Disaster Management Act, 2017', 'This Act may be called the Gilgit-Baltistan Disaster Management Act, No. II of 2017.'),
  (11381, 'The IDD Control Act Gilgit Baltistan, 2011', 'This Act may be called the IDD Control Act Gilgit Baltistan, 2011.'),
  (11382, 'The Gilgit-Baltistan Environmental Protection Act, 2014', 'This Act may be called the G ilg it- Balt ist an Environmental Protection Act, 2014.')
)
INSERT INTO instrument_metadata_assertion
       (source_observation_id, expression_ordinal, field, value, assertion, basis, method, evidence, recorded_by)
SELECT i.source_observation_id, i.expression_ordinal, 'display_title', d.name, 'asserted', 'reviewed_corrected_name',
       'nizam.display_title_from_printed_text/1',
       jsonb_build_object('reviewer_type', 'claude', 'page_read', true, 'review_evidence', d.quote,
                          'corrected_from', i.short_title, 'reviewed_file',
                          'tools/evidence/display-titles-gb-2026-11-16.sql'),
       'claude'
  FROM d JOIN v_release_instrument i ON i.document_id = d.doc
 WHERE NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                    WHERE c.instrument_id = i.id AND c.field = 'display_title');

COMMIT;
