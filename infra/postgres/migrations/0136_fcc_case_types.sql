-- 0136  The Federal Constitutional Court's case types, as its own headers print them (DECISION-LOG D-139;
--       docs/PRECEDENT-MODEL.md §3.6; the 0124/0126/0132 practice).
--
-- Observed 25 Nov 2026 in all 140 files of fcc_judgments.zip (crawled from fccp.gov.pk's public API the same day): the
-- opening of each file's case line (E:/nizam-data/acquire/work/fcc_heads.py). The court decides cases transferred from
-- the Supreme Court under the 27th Amendment, which keep the Supreme Court's numbers and forms ('C.P.L.A. No. 1807-L of
-- 2018', 'C.A. No. 567 of 2011', 'C.R.P.', 'C.M.A.', 'Suo Moto Case', 'Crl. Org. Petition', 'Crl.R.P.'), and its own
-- ('F.C.P.L.A. No. 642 of 2026', 'F.C.R.P. No. 21 of 2026'). A transferred case is keyed under this court, the court
-- that decided it (D-125: the case as printed, by its deciding court); its earlier Supreme Court record is not joined.
-- Only forms seen are recorded. The court's name is recorded (0118: 'Federal Constitutional Court of Pakistan').

BEGIN;
INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 ('FCC:CP',     'FCC', 'Civil Petition for Leave to Appeal', 'leave_petition', 'civil',
  '{"civil petition for leave to appeal","civil petitions for leave to appeal","civil petition","civil petitions",'
  '"c p l a","c p l as","cpla","cplas","c p","cp"}', 'migration 0136'),
 ('FCC:FCPLA',  'FCC', 'Federal Constitutional Court Petition for Leave to Appeal', 'leave_petition', 'civil',
  '{"f c p l a","f c p l as","fcpla","fcplas"}', 'migration 0136'),
 ('FCC:CA',     'FCC', 'Civil Appeal', 'appeal', 'civil',
  '{"civil appeal","civil appeals","c a","c as","ca","cas"}', 'migration 0136'),
 ('FCC:CRP',    'FCC', 'Civil Review Petition', 'review', 'civil',
  '{"civil review petition","civil review petitions","c r p","crp"}', 'migration 0136'),
 ('FCC:FCRP',   'FCC', 'Federal Constitutional Court Review Petition', 'review', 'civil',
  '{"f c r p","fcrp"}', 'migration 0136'),
 ('FCC:CMA',    'FCC', 'Civil Miscellaneous Application', 'misc_application', 'civil',
  '{"civil miscellaneous application","civil misc application","c m a","cma","c m as"}', 'migration 0136'),
 ('FCC:CMAPP',  'FCC', 'Civil Miscellaneous Appeal', 'appeal', 'civil',
  '{"civil miscellaneous appeal","civil misc appeal","civil miscl appeal","c m appeal"}', 'migration 0136'),
 ('FCC:SMC',    'FCC', 'Suo Motu Case', 'suo_motu', 'constitutional',
  '{"suo motu case","suo moto case","suo motu","suo moto","s m c","smc"}', 'migration 0136'),
 ('FCC:CRLOP',  'FCC', 'Criminal Original Petition', 'contempt', 'criminal',
  '{"criminal original petition","crl org petition","crl o p","crl org p"}', 'migration 0136'),
 ('FCC:CRLRP',  'FCC', 'Criminal Review Petition', 'review', 'criminal',
  '{"criminal review petition","crl r p","crl rp"}', 'migration 0136');
COMMIT;
