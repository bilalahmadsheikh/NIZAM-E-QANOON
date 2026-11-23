-- 0127  The Peshawar High Court's name as its own headers type it (DECISION-LOG D-130; PRECEDENT-MODEL §1.1).
--
-- Observed 23 Nov 2026 in judgments_peshawar_high_court.zip: a template prints 'PESHAWAR HIGH OURT' (23 headers),
-- others glue the words ('PESHAWARHIGH COURT', about 26; 'PESHAWAR HIGHCOURT', 2) or space the letters (about 17).
-- These are typed forms, not OCR garble: a garbled text layer ('PESIIAWAR IIIGII COUITT') goes to OCR by gate J9 and
-- is never matched by an alias.

BEGIN;
INSERT INTO court_alias (court_code, alias_printed, alias_key, method, evidence, recorded_by) VALUES
 ('PHC', 'PESHAWAR HIGH OURT', 'peshawar high ourt', 'observed',
  '{"archive": "judgments_peshawar_high_court.zip", "headers": 23}', 'migration 0127'),
 ('PHC', 'PESHAWARHIGH COURT', 'peshawarhigh court', 'observed',
  '{"archive": "judgments_peshawar_high_court.zip", "headers": 26}', 'migration 0127'),
 ('PHC', 'PESHAWAR HIGHCOURT', 'peshawar highcourt', 'observed',
  '{"archive": "judgments_peshawar_high_court.zip", "headers": 2}', 'migration 0127'),
 ('PHC', 'P E S H A W A R H I G H C O U R T', 'p e s h a w a r h i g h c o u r t', 'observed',
  '{"archive": "judgments_peshawar_high_court.zip", "headers": 17}', 'migration 0127');
COMMIT;
