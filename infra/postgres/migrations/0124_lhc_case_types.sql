-- 0124  Lahore High Court: its case types and the printed forms of its name, as observed in its own archive
--       (DECISION-LOG D-128; docs/PRECEDENT-MODEL.md §3.6, §1.1 court_alias).
--
-- Observed 23 Nov 2026 in lahore_HC_judgements.zip (4,557 PDFs; 4,320 with a text layer and no reporter headnote):
-- the case line of 4,299 headers was read, and each form below occurs there. A full name not printed in a header
-- is taken from the archive's own category label (PTR: "P. for Tax Reference (P.T.R.)"; C.O.: "Civil Original
-- (Commercial)"; Crl. Org.: "Criminal Original (Writ)", contempt). Forms are lowercase with punctuation folded to
-- single spaces, as the parser folds a header; the longest form that opens the case line wins. Nothing is added
-- that the archive does not print. The "Diary No." / "D. No." objection numbers are not case types.

BEGIN;

INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 ('LHC:WP',     'LHC', 'Writ Petition', 'writ', 'constitutional',
  '{"writ petition","writ petitions","w p","wp"}', 'migration 0124'),
 ('LHC:CRLA',   'LHC', 'Criminal Appeal', 'appeal', 'criminal',
  '{"criminal appeal","criminal appeals","criminal apeal","crl appeal","crl apeeal","crl app","crl a","cr appeal"}',
  'migration 0124'),
 ('LHC:CR',     'LHC', 'Civil Revision', 'revision', 'civil',
  '{"civil revision","civil rev","c r","cr"}', 'migration 0124'),
 ('LHC:CRLMISC','LHC', 'Criminal Miscellaneous', 'misc_application', 'criminal',
  '{"criminal miscellaneous","criminal misc","crl misc","cr misc"}', 'migration 0124'),
 ('LHC:MR',     'LHC', 'Murder Reference', 'reference', 'criminal',
  '{"murder reference","m r"}', 'migration 0124'),
 ('LHC:CSR',    'LHC', 'Capital Sentence Reference', 'reference', 'criminal',
  '{"capital sentence reference","csr"}', 'migration 0124'),
 ('LHC:CRLREV', 'LHC', 'Criminal Revision', 'revision', 'criminal',
  '{"criminal revision","crl revision","crl rev","cr revision"}', 'migration 0124'),
 ('LHC:RFA',    'LHC', 'Regular First Appeal', 'appeal', 'civil',
  '{"regular first appeal","r f a","rfa"}', 'migration 0124'),
 ('LHC:RSA',    'LHC', 'Regular Second Appeal', 'appeal', 'civil',
  '{"regular second appeal","r s a","rsa"}', 'migration 0124'),
 ('LHC:FAO',    'LHC', 'First Appeal from Order', 'appeal', 'civil',
  '{"first appeal from order","first appeal against order","f a o","fao"}', 'migration 0124'),
 ('LHC:EFA',    'LHC', 'Execution First Appeal', 'appeal', 'civil',
  '{"execution first appeal","e f a","efa"}', 'migration 0124'),
 ('LHC:ICA',    'LHC', 'Intra Court Appeal', 'intra_court_appeal', 'mixed',
  '{"intra court appeal","intra court appeals","i c a","ica"}', 'migration 0124'),
 ('LHC:SA',     'LHC', 'Service Appeal', 'appeal', 'civil',
  '{"service appeal"}', 'migration 0124'),
 ('LHC:PTR',    'LHC', 'Petition for Tax Reference', 'reference', 'civil',
  '{"p t r","ptr"}', 'migration 0124'),
 ('LHC:ITR',    'LHC', 'Income Tax Reference', 'reference', 'civil',
  '{"income tax reference","i t r","itr"}', 'migration 0124'),
 ('LHC:STR',    'LHC', 'Sales Tax Reference', 'reference', 'civil',
  '{"sales tax reference","s t r","str"}', 'migration 0124'),
 ('LHC:TR',     'LHC', 'Tax Reference', 'reference', 'civil',
  '{"tax reference","tax references"}', 'migration 0124'),
 ('LHC:CUSREF', 'LHC', 'Customs Reference', 'reference', 'civil',
  '{"customs reference","custom reference","custom ref application"}', 'migration 0124'),
 ('LHC:CUSA',   'LHC', 'Custom Appeal', 'appeal', 'civil',
  '{"custom appeal","customs appeal"}', 'migration 0124'),
 ('LHC:ELA',    'LHC', 'Election Appeal', 'appeal', 'constitutional',
  '{"election appeal"}', 'migration 0124'),
 ('LHC:ELP',    'LHC', 'Election Petition', 'original_petition', 'constitutional',
  '{"election petition"}', 'migration 0124'),
 ('LHC:CO',     'LHC', 'Civil Original', 'original_petition', 'civil',
  '{"civil original","c o","co"}', 'migration 0124'),
 ('LHC:COS',    'LHC', 'Civil Original Suit', 'suit', 'civil',
  '{"civil original suit","c o s","cos"}', 'migration 0124'),
 ('LHC:CM',     'LHC', 'Civil Miscellaneous', 'misc_application', 'civil',
  '{"c m"}', 'migration 0124'),
 ('LHC:RA',     'LHC', 'Review Application', 'review', 'mixed',
  '{"review application","r a"}', 'migration 0124'),
 ('LHC:RP',     'LHC', 'Review Petition', 'review', 'mixed',
  '{"review petition"}', 'migration 0124'),
 ('LHC:TA',     'LHC', 'Transfer Application', 'misc_application', 'mixed',
  '{"transfer application","t a"}', 'migration 0124'),
 ('LHC:EXA',    'LHC', 'Execution Application', 'misc_application', 'civil',
  '{"execution application","ex a","e a"}', 'migration 0124'),
 ('LHC:INSA',   'LHC', 'Insurance Appeal', 'appeal', 'civil',
  '{"insurance appeal"}', 'migration 0124'),
 ('LHC:CRLORG', 'LHC', 'Criminal Original', 'contempt', 'criminal',
  '{"criminal original","crl org"}', 'migration 0124'),
 ('LHC:PSLA',   'LHC', 'Petition for Special Leave to Appeal', 'leave_petition', 'criminal',
  '{"criminal psla","crl psla","psla"}', 'migration 0124');

-- The court's own name as some headers print it, letter-spaced ('L A H O R E  H I G H  C O U R T') or broken by the
-- text layer ('LAHORE HIGH C OURT'). Observed in the same archive (15 and 2 headers).
INSERT INTO court_alias (court_code, alias_printed, alias_key, method, evidence, recorded_by) VALUES
 ('LHC', 'L A H O R E H I G H C O U R T', 'l a h o r e h i g h c o u r t', 'observed',
  '{"archive": "lahore_HC_judgements.zip", "headers": 15}', 'migration 0124'),
 ('LHC', 'LAHORE HIGH C OURT', 'lahore high c ourt', 'observed',
  '{"archive": "lahore_HC_judgements.zip", "headers": 2}', 'migration 0124');

COMMIT;
