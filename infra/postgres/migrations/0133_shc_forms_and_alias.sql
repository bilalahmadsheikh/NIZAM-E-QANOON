-- 0133  Sindh: printed forms 0132 did not hold, the Special Federal Excise Reference Application, and the court's
--       'Sind' spelling (DECISION-LOG D-138).
--
-- Observed 24 Nov 2026 in the files a 1-in-25 dry run of sindh_high_court_judgements.zip held at J3 ('no case number
-- line matching a recorded case type'): 'Crl.B. Appln No.1860 of 2016', 'Cr. Acq. Appeal No. S- 162 of 2014',
-- 'SPL. HCA. NO. 282 OF 2015', '1st Appeals Nos. 36, 89 ... of 2016', 'SCRAs 311 to 313 of 2020', 'Cr. Rev.
-- Appln.No.D-13 of 2018', 'Constt. Petition No. D- 551 of 2007', 'Special Federal Excise Reference Application No.
-- 159 of 2012'. And a header printing 'HIGH COURT OF SIND, CIRCUIT COURT, LARKANA'. Case types are reference grammar:
-- forms are added, none removed.

BEGIN;
UPDATE case_type SET printed_forms = printed_forms || '{"constt petition","constt petitions","constt p"}'
 WHERE code = 'SHC:CP';
UPDATE case_type SET printed_forms = printed_forms || '{"crl b appln","cr b appln","crl b a appln","cr b a appln"}'
 WHERE code = 'SHC:CRLBA';
UPDATE case_type SET printed_forms = printed_forms || '{"cr acq appeal","crl acq appeal","cr acq a","crl acq a"}'
 WHERE code = 'SHC:CRLACQA';
UPDATE case_type SET printed_forms = printed_forms || '{"spl hca","special hca"}' WHERE code = 'SHC:SPLHCA';
UPDATE case_type SET printed_forms = printed_forms || '{"1st appeals","ist appeals"}' WHERE code = 'SHC:FA';
UPDATE case_type SET printed_forms = printed_forms || '{"scras"}' WHERE code = 'SHC:SCRA';
UPDATE case_type SET printed_forms = printed_forms || '{"cr rev appln","crl rev appln","cr rev application"}'
 WHERE code = 'SHC:CRLRA';
INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 ('SHC:SFERA', 'SHC', 'Special Federal Excise Reference Application', 'reference', 'civil',
  '{"special federal excise reference application","spl federal excise reference application"}', 'migration 0133');
INSERT INTO court_alias (court_code, alias_printed, alias_key, method, evidence, recorded_by) VALUES
 ('SHC', 'HIGH COURT OF SIND', 'high court of sind', 'observed',
  '{"archive": "sindh_high_court_judgements.zip", "example": "shc-296589.pdf"}', 'migration 0133');
COMMIT;
