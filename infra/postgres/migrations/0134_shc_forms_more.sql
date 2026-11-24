-- 0134  Sindh: more printed forms, read in the headers a second 1-in-25 dry run still held at J3 (DECISION-LOG D-138).
--
-- 'Cr. Misc. Appl. No S- 36 of 2016', 'Cr. Bail App. No S – 328 of 2021', '1st Criminal Bail Application No S-697',
-- 'Spl. Crl. A.T.J.A. No 19 of 2017', 'Spl. Cr. A.T.A. No 111 of 2019', 'Spl. Cr. Jail ATA No 20 of 2019', 'Spl. CRA No
-- 70 of 2018', 'J.M. No 37/2015', 'J. Misc. No 34 of 2020', 'I.A. No 46 of 2015', 'I. Appeal No 114 of 2016', 'I.T.A.
-- No 176 of 1998', 'I.T.C No 140 of 2005', 'Execution No 68 of 2016', 'Civil Reference No 02 of 2018', 'Special Customs
-- Appeal No 149 of 2002', 'Cr. Appeals No 188, 193 ... of', 'Criminal Acq. Appeal No 591 of 2022', 'Cr. Revision
-- Appln. No D-19 of 2024', 'M.A. No 18 of 2021'. 'M.A.' becomes a form now that an order sheet's 'For orders on M.A.
-- No ...' is no longer read as a case decided (nizam.corpus.judgment_case._NOT_DECIDED_HERE, D-138).

BEGIN;
UPDATE case_type SET printed_forms = printed_forms || '{"cr misc appl","crl misc appl","cr misc app","crl misc app",'
  '"cr misc applications","criminal misc appln","criminal misc appl","criminal misc applications"}'
 WHERE code = 'SHC:CRLMA';
UPDATE case_type SET printed_forms = printed_forms || '{"cr bail app","crl bail app","cr bail a","cr bail applns",'
  '"criminal bail","criminal bail appln","1st criminal bail","1st criminal bail application","1st cr bail appln",'
  '"1st crl bail appln","ist crl bail appln","ist cr bail appln","ist criminal bail application","b a"}'
 WHERE code = 'SHC:CRLBA';
UPDATE case_type SET printed_forms = printed_forms || '{"spl crl a t j a","spl cr a t j a","spl cr jail ata",'
  '"spl crl jail ata","spl cr a t jail appeal","spl crl anti terrorism jail appeal","spl cr anti terrorism jail appeal"}'
 WHERE code = 'SHC:SPLATJA';
UPDATE case_type SET printed_forms = printed_forms || '{"spl cr a t a","spl crl a t a","spl ata appeal","spl cr ata",'
  '"spl crl ata"}' WHERE code = 'SHC:SPLATA';
UPDATE case_type SET printed_forms = printed_forms || '{"spl crl jail appeal","spl cr jail appeal","spl criminal appeal",'
  '"spl crl acquittal appeal"}' WHERE code = 'SHC:SPLCRLA';
UPDATE case_type SET printed_forms = printed_forms || '{"i a","i appeal"}' WHERE code = 'SHC:FA';
UPDATE case_type SET printed_forms = printed_forms || '{"cr appeals","crl appeals"}' WHERE code = 'SHC:CRLA';
UPDATE case_type SET printed_forms = printed_forms || '{"criminal acq appeal"}' WHERE code = 'SHC:CRLACQA';
UPDATE case_type SET printed_forms = printed_forms || '{"cr revision appln","cr revision appl","cr revision",'
  '"criminal rev application","cr revision application"}' WHERE code = 'SHC:CRLRA';
UPDATE case_type SET printed_forms = printed_forms || '{"m a"}' WHERE code = 'SHC:MA';
UPDATE case_type SET printed_forms = printed_forms || '{"judicial companies miscellaneous"}' WHERE code = 'SHC:JCM';
UPDATE case_type SET printed_forms = printed_forms || '{"special sales tax reference appln"}' WHERE code = 'SHC:STRA';
INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 ('SHC:SPLCRA', 'SHC', 'Special Criminal Reference Application (as printed: Spl. CRA)', 'reference', 'criminal',
  '{"spl cra","special cra"}', 'migration 0134'),
 ('SHC:JM',     'SHC', 'Judicial Miscellaneous', 'misc_application', 'civil',
  '{"judicial miscellaneous","j m","j misc"}', 'migration 0134'),
 ('SHC:ITA',    'SHC', 'Income Tax Appeal', 'appeal', 'civil', '{"income tax appeal","i t a","ita"}', 'migration 0134'),
 ('SHC:ITC',    'SHC', 'Income Tax Case (as printed: I.T.C)', 'other', 'civil', '{"i t c","itc"}', 'migration 0134'),
 ('SHC:EXEC',   'SHC', 'Execution', 'other', 'civil', '{"execution","execution application"}', 'migration 0134'),
 ('SHC:CIVREF', 'SHC', 'Civil Reference', 'reference', 'civil', '{"civil reference"}', 'migration 0134'),
 ('SHC:SCA',    'SHC', 'Special Customs Appeal', 'appeal', 'civil', '{"special customs appeal","spl customs appeal"}',
  'migration 0134');
COMMIT;
