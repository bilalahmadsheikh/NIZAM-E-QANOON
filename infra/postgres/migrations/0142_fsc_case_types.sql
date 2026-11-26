-- 0142  The Federal Shariat Court: its case types as its own headers and lists print them (DECISION-LOG D-157;
--       docs/PRECEDENT-MODEL.md §3.6; the 0124/0126/0132/0140 practice). The court is recorded (0118, Art. 203C), and
--       Art. 203GG's rule (authority_rule 6, 7) binds the High Courts and the courts subordinate to them.
--
-- Observed 26 Nov 2026 over the 538 files of fsc_judgments.zip (the court's own site: its Shariat petition table, its
-- criminal and suo motu lists, its landmark page). On page 1 of 247 files a case line was found: the type's words
-- before 'No.', then a number with its seat letter (I, K, L, P, Q: Islamabad, Karachi, Lahore, Peshawar, Quetta) and
-- the year; evidence: E:/nizam-data/acquire/work/fsc-case-forms.json. The lists' own names ('Sh.P.', 'Jail Criminal
-- Appeal', 'Shariat suo moto') are the court's record and are recorded with the header forms.

BEGIN;
INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 ('FSC:SHP',    'FSC', 'Shariat Petition', 'original_petition', 'shariat',
  '{"shariat petition","shariat petitions","sh p","shp"}', 'migration 0142'),
 ('FSC:SSM',    'FSC', 'Shariat Suo Moto', 'suo_motu', 'shariat',
  '{"shariat suo moto","shariat suo motu","suo moto"}', 'migration 0142'),
 ('FSC:CRLA',   'FSC', 'Criminal Appeal', 'appeal', 'criminal',
  '{"criminal appeal","criminal appeals","cr appeal","crl appeal","cr a"}', 'migration 0142'),
 ('FSC:JCRLA',  'FSC', 'Jail Criminal Appeal', 'appeal', 'criminal',
  '{"jail criminal appeal","jail criminal appeals","jail cr appeal","jail crl appeal","j cr a"}', 'migration 0142'),
 ('FSC:CRLREV', 'FSC', 'Criminal Revision', 'revision', 'criminal',
  '{"criminal revision","criminal revision petition","crl revision"}', 'migration 0142'),
 ('FSC:MR',     'FSC', 'Criminal Murder Reference', 'reference', 'criminal',
  '{"criminal murder reference","criminal murder ref","murder reference"}', 'migration 0142');
COMMIT;
