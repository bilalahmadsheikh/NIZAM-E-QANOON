-- 0126  Peshawar High Court: its case types as observed in its own archive (DECISION-LOG D-130;
--       docs/PRECEDENT-MODEL.md §3.6).
--
-- Observed 23 Nov 2026 in judgments_peshawar_high_court.zip, folder judgments_peshawar_high_court/ (the bundle also
-- carries the SC archive and law files, which are not this court's). Each form below occurs in the case lines of its
-- headers; forms are lowercase with punctuation folded to single spaces, the longest that opens the case line wins.
-- A full name the headers never print is not invented: 'F.A.B.' (banking appeals: UBL, HBFC, Askari Bank) is
-- recorded under its printed name; 'COC' is contempt ('Cr.Misc (COC) ... in Cr.R'). The court's name needs no alias:
-- 'Peshawar High Court' is recorded (0118).

BEGIN;

INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 ('PHC:WP',     'PHC', 'Writ Petition', 'writ', 'constitutional',
  '{"writ petition","writ petitions","write petition","w p","wp"}', 'migration 0126'),
 ('PHC:CR',     'PHC', 'Civil Revision', 'revision', 'civil',
  '{"civil revision","civil revisions","civil revision petition","c r","cr"}', 'migration 0126'),
 ('PHC:CRLA',   'PHC', 'Criminal Appeal', 'appeal', 'criminal',
  '{"criminal appeal","criminal appeals","crl appeal","cr appeal","cr a"}', 'migration 0126'),
 ('PHC:JCRLA',  'PHC', 'Jail Criminal Appeal', 'appeal', 'criminal',
  '{"jail criminal appeal","jail crl appeal","j cr appeal","j cr a"}', 'migration 0126'),
 ('PHC:EHCRLA', 'PHC', 'Ehtesab Criminal Appeal', 'appeal', 'criminal',
  '{"ehtesab criminal appeal","eh crl appeal","eh cr a","e cr a"}', 'migration 0126'),
 ('PHC:ACCA',   'PHC', 'Accountability Appeal', 'appeal', 'criminal',
  '{"accountability appeal"}', 'migration 0126'),
 ('PHC:BA',     'PHC', 'Criminal Miscellaneous (Bail Application)', 'bail', 'criminal',
  '{"criminal miscellaneous bail application","criminal miscellaneous bail petition","criminal miscellaneous ba",'
  '"criminal bail petition","bail application","bail petition","cr misc ba","cr misc b a","cr m ba","cr m b a",'
  '"cr mba","cr m bail","cr mb","cr m b","ba","b a"}', 'migration 0126'),
 ('PHC:BCA',    'PHC', 'Criminal Miscellaneous (Bail Cancellation Application)', 'bail', 'criminal',
  '{"criminal miscellaneous bail cancellation application","cr misc bca","cr m bca","bca"}', 'migration 0126'),
 ('PHC:QP',     'PHC', 'Quashment Petition', 'misc_application', 'criminal',
  '{"criminal miscellaneous quashment petition","criminal miscellaneous quashment","criminal miscellaneous q",'
  '"criminal quashment petition","quashment petition","quashment petitions","cr misc q p","cr misc qp","cr misc q",'
  '"cr m q p","cr m qp","cr m q","cr mq","q p","qp"}', 'migration 0126'),
 ('PHC:COC',    'PHC', 'Contempt of Court (as printed: COC)', 'contempt', 'mixed',
  '{"coc","cr misc coc"}', 'migration 0126'),
 ('PHC:CRLMISC','PHC', 'Criminal Miscellaneous', 'misc_application', 'criminal',
  '{"criminal miscellaneous","cr misc","cr m"}', 'migration 0126'),
 ('PHC:CRLREV', 'PHC', 'Criminal Revision', 'revision', 'criminal',
  '{"criminal revision","criminal revision petition","cr r"}', 'migration 0126'),
 ('PHC:RFA',    'PHC', 'Regular First Appeal', 'appeal', 'civil',
  '{"regular first appeal","regular first appeals","r f a","r f as","rfa"}', 'migration 0126'),
 ('PHC:RSA',    'PHC', 'Regular Second Appeal', 'appeal', 'civil',
  '{"regular second appeal","r s a","rsa"}', 'migration 0126'),
 ('PHC:FAO',    'PHC', 'First Appeal from Order', 'appeal', 'civil',
  '{"first appeal from order","f a o","fao"}', 'migration 0126'),
 ('PHC:SAO',    'PHC', 'Second Appeal from Order', 'appeal', 'civil',
  '{"second appeal from order","s a o","s a os","sao"}', 'migration 0126'),
 ('PHC:FAB',    'PHC', 'F.A.B. (banking appeal, as printed)', 'appeal', 'civil',
  '{"f a b","fab"}', 'migration 0126'),
 ('PHC:RP',     'PHC', 'Review Petition', 'review', 'mixed',
  '{"review petition"}', 'migration 0126'),
 ('PHC:CM',     'PHC', 'Civil Miscellaneous', 'misc_application', 'civil',
  '{"civil miscellaneous","c m","cm"}', 'migration 0126'),
 ('PHC:CUSREF', 'PHC', 'Customs Reference', 'reference', 'civil',
  '{"customs reference application","customs reference","custom reference","custom ref"}', 'migration 0126'),
 ('PHC:TR',     'PHC', 'Tax Reference', 'reference', 'civil',
  '{"tax reference","t r"}', 'migration 0126'),
 ('PHC:ITR',    'PHC', 'Income Tax Reference Application', 'reference', 'civil',
  '{"income tax reference application","income tax reference"}', 'migration 0126'),
 ('PHC:STR',    'PHC', 'Sales Tax Reference', 'reference', 'civil',
  '{"sales tax reference"}', 'migration 0126'),
 ('PHC:SA',     'PHC', 'Service Appeal', 'appeal', 'civil',
  '{"service tribunal appeal","service appeal"}', 'migration 0126'),
 ('PHC:ELA',    'PHC', 'Election Appeal', 'appeal', 'constitutional',
  '{"election appeal"}', 'migration 0126');

COMMIT;
