-- 0132  The High Court of Sindh and the High Court of Balochistan: their case types as their own headers print them
--       (DECISION-LOG D-138; docs/PRECEDENT-MODEL.md §3.6; the 0124/0126 practice).
--
-- Sindh, observed 24 Nov 2026 by tools/observe_case_forms.py over 1 in 8 files of sindh_high_court_judgements.zip
-- (7,029 files with a manifest case number; in 5,346 the number was found printed in the file's own header, and the
-- words before it are the form; evidence: E:/nizam-data/acquire/work/shc-case-forms.json). The manifest's own type
-- names (Const. P., Cr. Bail, I.T.R.A ...) are the portal's, not the court's print, and are recorded only where a
-- header prints them too. A register letter before the number ('C.P. No. D-2606', 'S-1043', 'Suit No. B-12') is part
-- of the number, read by the case-line grammar, not a case type. 'M.A.' is not a form: order sheets list applications
-- ('For orders on M.A. No. 1056/2023'); the Miscellaneous Appeal is recorded by its spelled-out names only.
--
-- Balochistan, observed in the 31 files of balochistan_high_court_judgements.zip that are the court's own judgments
-- (the rest are law-report reprints, not landed, D-120). Its name is recorded (0118: 'High Court of Balochistan').

BEGIN;
INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 ('SHC:CP',       'SHC', 'Constitution Petition', 'writ', 'constitutional',
  '{"constitution petition","constitution petitions","constitutional petition","constitutional petitions",'
  '"const petition","const petitions","const pett","const p","c p","cp","c ps","cps"}', 'migration 0132'),
 ('SHC:CRLBA',    'SHC', 'Criminal Bail Application', 'bail', 'criminal',
  '{"criminal bail application","criminal bail applications","cr bail application","cr bail applications",'
  '"crl bail application","crl bail applications","cr bail appl","cr bail appln","crl bail appl","crl bail appln",'
  '"criminal bail appl","cr b a","crl b a","bail application"}', 'migration 0132'),
 ('SHC:SPLCRLBA', 'SHC', 'Special Criminal Bail Application', 'bail', 'criminal',
  '{"special criminal bail application","spl cr bail application","spl criminal bail application",'
  '"spl crl bail application"}', 'migration 0132'),
 ('SHC:CRLMA',    'SHC', 'Criminal Miscellaneous Application', 'misc_application', 'criminal',
  '{"criminal miscellaneous application","criminal misc application","criminal misc applications",'
  '"cr misc application","crl misc application","cr misc appln","crl misc appln","crl misc a","cr misc a"}',
  'migration 0132'),
 ('SHC:SCRA',     'SHC', 'Special Customs Reference Application', 'reference', 'civil',
  '{"special customs reference application","special custom reference application","scra","s c r a","scr a"}',
  'migration 0132'),
 ('SHC:ITRA',     'SHC', 'Income Tax Reference Application', 'reference', 'civil',
  '{"income tax reference application","itra","i t r a","itr a"}', 'migration 0132'),
 ('SHC:ITR',      'SHC', 'Income Tax Reference', 'reference', 'civil',
  '{"income tax reference","itr","i t r"}', 'migration 0132'),
 ('SHC:STRA',     'SHC', 'Special Sales Tax Reference Application', 'reference', 'civil',
  '{"special sales tax reference application","special str a","spl str a","special str","spl str","sstra",'
  '"special stra","special s t r a"}', 'migration 0132'),
 ('SHC:HCA',      'SHC', 'High Court Appeal', 'intra_court_appeal', 'civil',
  '{"high court appeal","high court appeals","h c a","hca"}', 'migration 0132'),
 ('SHC:SPLHCA',   'SHC', 'Special High Court Appeal', 'intra_court_appeal', 'civil',
  '{"special high court appeal","special h c a","spl h c a"}', 'migration 0132'),
 ('SHC:SUIT',     'SHC', 'Suit', 'suit', 'civil', '{"suit","suits"}', 'migration 0132'),
 ('SHC:ADMSUIT',  'SHC', 'Admiralty Suit', 'suit', 'civil', '{"admiralty suit","adm suit"}', 'migration 0132'),
 ('SHC:RA',       'SHC', 'Revision Application (Civil Revision)', 'revision', 'civil',
  '{"civil revision application","civil revision applications","civil rev application","civil revision appl",'
  '"civil revision appln","revision application","civil revision","r a"}', 'migration 0132'),
 ('SHC:CRLRA',    'SHC', 'Criminal Revision Application', 'revision', 'criminal',
  '{"criminal revision application","criminal revision applications","crl revision application",'
  '"crl rev application","cr revision application","cr rev application","criminal revision","crl revision"}',
  'migration 0132'),
 ('SHC:FA',       'SHC', 'First Appeal', 'appeal', 'civil',
  '{"first appeal","first appeals","ist appeal","1st appeal","ist civil appeal","first civil appeal"}',
  'migration 0132'),
 ('SHC:SA',       'SHC', 'Second Appeal', 'appeal', 'civil',
  '{"second appeal","second appeals","iind appeal","ii appeal","2nd appeal"}', 'migration 0132'),
 ('SHC:MA',       'SHC', 'Miscellaneous Appeal', 'appeal', 'civil',
  '{"civil miscellaneous appeal","civil misc appeal","misc appeal","miscellaneous appeal"}', 'migration 0132'),
 ('SHC:FRA',      'SHC', 'First Rent Appeal', 'appeal', 'civil', '{"first rent appeal","f r a","fra"}', 'migration 0132'),
 ('SHC:CRLA',     'SHC', 'Criminal Appeal', 'appeal', 'criminal',
  '{"criminal appeal","criminal appeals","cr appeal","crl appeal"}', 'migration 0132'),
 ('SHC:CRLJA',    'SHC', 'Criminal Jail Appeal', 'appeal', 'criminal',
  '{"criminal jail appeal","criminal jail appeals","cr jail appeal","crl jail appeal"}', 'migration 0132'),
 ('SHC:CRLACQA',  'SHC', 'Criminal Acquittal Appeal', 'appeal', 'criminal',
  '{"criminal acquittal appeal","criminal acquittal appeals","cr acquittal appeal","crl acquittal appeal"}',
  'migration 0132'),
 ('SHC:SPLCRLA',  'SHC', 'Special Criminal Appeal', 'appeal', 'criminal',
  '{"special criminal appeal","special cr appeal","spl cr appeal","spl crl appeal"}', 'migration 0132'),
 ('SHC:SPLATA',   'SHC', 'Special Criminal Anti-Terrorism Appeal', 'appeal', 'criminal',
  '{"special criminal anti terrorism appeal","spl cr anti terrorism appeal","spl crl anti terrorism appeal",'
  '"special cr a t appeal","spl cr a t appeal"}', 'migration 0132'),
 ('SHC:SPLATJA',  'SHC', 'Special Criminal Anti-Terrorism Jail Appeal', 'appeal', 'criminal',
  '{"special criminal anti terrorism jail appeal","criminal anti terrorism jail appeal",'
  '"crl anti terrorism jail appeal","spl anti terrorism jail appeal","spl anti terr jail appeal",'
  '"criminal a t j appeal","crl a t j a"}', 'migration 0132'),
 ('SHC:CRLACCA',  'SHC', 'Criminal Accountability Appeal', 'appeal', 'criminal',
  '{"criminal accountability appeal","criminal accountability appeals","cr accountability appeal",'
  '"cr acctt appeal"}', 'migration 0132'),
 ('SHC:CRLTA',    'SHC', 'Criminal Transfer Application', 'misc_application', 'criminal',
  '{"criminal transfer application","crl transfer application","cr transfer application","cr tr application",'
  '"cr trf appl","cr transfer appl","cr transfer appln"}', 'migration 0132'),
 ('SHC:CTA',      'SHC', 'Civil Transfer Application', 'misc_application', 'civil',
  '{"civil transfer application","civil family transfer application","c t a"}', 'migration 0132'),
 ('SHC:CONF',     'SHC', 'Confirmation Case', 'reference', 'criminal',
  '{"confirmation case","criminal confirmation case"}', 'migration 0132'),
 ('SHC:SMA',      'SHC', 'Succession Miscellaneous Application', 'misc_application', 'civil',
  '{"s m a","sma"}', 'migration 0132'),
 ('SHC:JCM',      'SHC', 'Judicial Companies Miscellaneous', 'misc_application', 'civil',
  '{"j c m","jcm","j c misc"}', 'migration 0132'),
 ('SHC:ELECA',    'SHC', 'Election Appeal', 'appeal', 'constitutional', '{"election appeal"}', 'migration 0132'),
 ('SHC:EP',       'SHC', 'Election Petition', 'original_petition', 'constitutional',
  '{"election petition"}', 'migration 0132'),
 ('BHC:CP',       'BHC', 'Constitution Petition', 'writ', 'constitutional',
  '{"constitution petition","constitution petitions","constitutional petition","constitutional petitions",'
  '"const petition","c p","cp","c ps","cps"}', 'migration 0132'),
 ('BHC:CRP',      'BHC', 'Civil Revision Petition', 'revision', 'civil',
  '{"civil revision petition","civil revision"}', 'migration 0132'),
 ('BHC:CRLREV',   'BHC', 'Criminal Revision', 'revision', 'criminal',
  '{"criminal revision","crl revision"}', 'migration 0132'),
 ('BHC:CQP',      'BHC', 'Criminal Quashment Petition', 'misc_application', 'criminal',
  '{"criminal quashment petition","criminal quashment"}', 'migration 0132'),
 ('BHC:CRLTA',    'BHC', 'Criminal Transfer Application', 'misc_application', 'criminal',
  '{"criminal transfer application"}', 'migration 0132'),
 ('BHC:RFA',      'BHC', 'Regular First Appeal', 'appeal', 'civil', '{"regular first appeal","r f a","rfa"}',
  'migration 0132'),
 ('BHC:CMA',      'BHC', 'Civil Miscellaneous Appeal', 'appeal', 'civil', '{"civil misc appeal","civil miscellaneous appeal"}',
  'migration 0132'),
 ('BHC:CRLA',     'BHC', 'Criminal Appeal', 'appeal', 'criminal', '{"criminal appeal","crl appeal"}', 'migration 0132'),
 ('BHC:CRLJA',    'BHC', 'Criminal Jail Appeal', 'appeal', 'criminal', '{"criminal jail appeal"}', 'migration 0132'),
 ('BHC:ADMSUIT',  'BHC', 'Admiralty Suit', 'suit', 'civil', '{"admiralty suit"}', 'migration 0132');
COMMIT;
