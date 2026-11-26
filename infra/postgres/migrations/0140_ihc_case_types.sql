-- 0140  The Islamabad High Court: its case types as its own headers print them (DECISION-LOG D-156;
--       docs/PRECEDENT-MODEL.md §3.6; the 0124/0126/0132 practice). The court itself is recorded (0118, Art. 198),
--       and Art. 201's high-court rule (authority_rule 4, 5) already reaches its subordinate courts in ICT.
--
-- Observed 26 Nov 2026 by tools/observe_case_forms.py over 1 in 3 files of ihc_judgments.zip (the court's own
-- listing, mis.ihc.gov.pk srchDecisionClms; 1,090 files with a listed case number, in 894 the number was found
-- printed in the file's own header after 'ISLAMABAD HIGH COURT, ISLAMABAD / JUDICIAL DEPARTMENT'; evidence:
-- E:/nizam-data/acquire/work/ihc-case-forms.json). The listing's own names ('Writ Petition', 'Regular First Appeal',
-- 'First Appeal Against Order' ...) are the court's record of the case and are recorded with the header forms.
-- A type seen fewer than twice in the headers is recorded only where the listing names it too.

BEGIN;
INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 ('IHC:WP',      'IHC', 'Writ Petition', 'writ', 'constitutional',
  '{"writ petition","writ petitions","w p","wp","w ps"}', 'migration 0140'),
 ('IHC:ICA',     'IHC', 'Intra Court Appeal', 'intra_court_appeal', 'mixed',
  '{"intra court appeal","intra court appeals","i c a","ica"}', 'migration 0140'),
 ('IHC:CR',      'IHC', 'Civil Revision', 'revision', 'civil',
  '{"civil revision","civil revisions","civil revision petition","c r"}', 'migration 0140'),
 ('IHC:RFA',     'IHC', 'Regular First Appeal', 'appeal', 'civil',
  '{"regular first appeal","regular first appeals","r f a","rfa"}', 'migration 0140'),
 ('IHC:RSA',     'IHC', 'Regular Second Appeal', 'appeal', 'civil',
  '{"regular second appeal","r s a","rsa"}', 'migration 0140'),
 ('IHC:FAO',     'IHC', 'First Appeal Against Order', 'appeal', 'civil',
  '{"first appeal against order","first appeal from order","f a o","fao"}', 'migration 0140'),
 ('IHC:EFA',     'IHC', 'Execution First Appeal', 'appeal', 'civil',
  '{"execution first appeal","e f a","efa"}', 'migration 0140'),
 ('IHC:CMA',     'IHC', 'Civil Miscellaneous Appeal', 'appeal', 'civil',
  '{"civil miscellaneous appeal","civil miscellaneous appeals","c m a","cma"}', 'migration 0140'),
 ('IHC:CRLA',    'IHC', 'Criminal Appeal', 'appeal', 'criminal',
  '{"criminal appeal","criminal appeals","crl appeal","crl app"}', 'migration 0140'),
 ('IHC:JA',      'IHC', 'Jail Appeal', 'appeal', 'criminal',
  '{"jail appeal","jail appeals","criminal jail appeal","crl jail appeal"}', 'migration 0140'),
 ('IHC:CRLREV',  'IHC', 'Criminal Revision', 'revision', 'criminal',
  '{"criminal revision","criminal revisions","crl revision","crl rev","criminal revision petition",'
  '"crl revision petition"}', 'migration 0140'),
 ('IHC:CRLMISC', 'IHC', 'Criminal Miscellaneous', 'misc_application', 'criminal',
  '{"criminal miscellaneous","criminal misc","crl misc"}', 'migration 0140'),
 ('IHC:CRLORG',  'IHC', 'Criminal Original', 'contempt', 'criminal',
  '{"criminal original","crl original","crl orig","crl orgl","criminal original case"}', 'migration 0140'),
 ('IHC:MR',      'IHC', 'Murder Reference', 'reference', 'criminal', '{"murder reference"}', 'migration 0140'),
 ('IHC:CUSREF',  'IHC', 'Customs Reference', 'reference', 'civil',
  '{"custom reference","customs reference","custom references","customs references"}', 'migration 0140'),
 ('IHC:ITR',     'IHC', 'Income Tax Reference', 'reference', 'civil',
  '{"income tax reference","i t r","itr"}', 'migration 0140'),
 ('IHC:STR',     'IHC', 'Sales Tax Reference', 'reference', 'civil',
  '{"sales tax reference","s t r"}', 'migration 0140'),
 ('IHC:TR',      'IHC', 'Tax Reference', 'reference', 'civil', '{"tax reference","tax references"}', 'migration 0140'),
 ('IHC:CO',      'IHC', 'Companies Original', 'original_petition', 'civil',
  '{"companies original","company original"}', 'migration 0140'),
 ('IHC:ELA',     'IHC', 'Election Appeal', 'appeal', 'constitutional', '{"election appeal"}', 'migration 0140'),
 ('IHC:PSLA',    'IHC', 'Petition for Special Leave to Appeal', 'leave_petition', 'criminal',
  '{"petition for special leave to appeal","p s l a","psla"}', 'migration 0140');
COMMIT;
