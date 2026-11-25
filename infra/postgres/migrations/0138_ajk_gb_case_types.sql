-- 0138  The AJK and GB courts' case types and header names, as their own judgments print them (DECISION-LOG D-142;
--       docs/PRECEDENT-MODEL.md §3.6; the 0124/0126/0132/0136 practice).
--
-- Observed 25 Nov 2026 in the text layer of every file of the four archives crawled from the courts' own sites (D-139):
-- ajksc_judgments.zip (958 files, 818 with text), ajkhc_judgments.zip (262, 240), sacgb_judgments.zip (748, 730),
-- gbcc_judgments.zip (154, 29 -- the rest are scans, which wait for OCR). The opening of each file's case line, folded
-- as the parser folds it (E:/nizam-data/acquire/work/ajkgb_heads.py, output ajkgb-heads-all.txt). Only forms seen are
-- recorded; a bare 'petition', 'appeal' or 'review' names no type and is left out. The Supreme Appellate Court's
-- 'under objection' registers are their own numbering series ('CPLA under objection No. 12/2020'), so each is its own
-- type, never merged into the numbered petitions.

BEGIN;
INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 -- Supreme Court of Azad Jammu and Kashmir
 ('AJKSC:CA',      'AJKSC', 'Civil Appeal', 'appeal', 'civil', '{"civil appeal","civil appeals"}', 'migration 0138'),
 ('AJKSC:CPLA',    'AJKSC', 'Civil Petition for Leave to Appeal', 'leave_petition', 'civil',
  '{"civil petition for leave to appeal","civil pla","civil plas","civil p l a"}', 'migration 0138'),
 ('AJKSC:CRLA',    'AJKSC', 'Criminal Appeal', 'appeal', 'criminal',
  '{"criminal appeal","criminal appeals","crim appeal","crim appeals","cri appeal","cr appeal"}', 'migration 0138'),
 ('AJKSC:CRLPLA',  'AJKSC', 'Criminal Petition for Leave to Appeal', 'leave_petition', 'criminal',
  '{"criminal pla","criminal p l a","crim pla"}', 'migration 0138'),
 ('AJKSC:CRP',     'AJKSC', 'Civil Review Petition', 'review', 'civil',
  '{"civil review petition","civil review"}', 'migration 0138'),
 ('AJKSC:CRLRP',   'AJKSC', 'Criminal Review Petition', 'review', 'criminal',
  '{"cri review petition","criminal review"}', 'migration 0138'),
 ('AJKSC:CRLREV',  'AJKSC', 'Criminal Revision', 'revision', 'criminal',
  '{"criminal revision","crim revision","cri revision","cr revision"}', 'migration 0138'),
 ('AJKSC:CM',      'AJKSC', 'Civil Miscellaneous', 'misc_application', 'civil', '{"civil misc"}', 'migration 0138'),
 ('AJKSC:CRLMISC', 'AJKSC', 'Criminal Miscellaneous', 'misc_application', 'criminal',
  '{"criminal misc","cr misc"}', 'migration 0138'),
 ('AJKSC:CRLORG',  'AJKSC', 'Criminal Original', 'contempt', 'criminal',
  '{"criminal original","cri original","cr original","crim orig"}', 'migration 0138'),
 ('AJKSC:FA',      'AJKSC', 'Family Appeal', 'appeal', 'civil', '{"family appeals"}', 'migration 0138'),
 -- High Court of Azad Jammu and Kashmir
 ('AJKHC:WP',      'AJKHC', 'Writ Petition', 'writ', 'constitutional', '{"writ petition","w p"}', 'migration 0138'),
 ('AJKHC:CA',      'AJKHC', 'Civil Appeal', 'appeal', 'civil', '{"civil appeal","civ appeal"}', 'migration 0138'),
 ('AJKHC:CRLA',    'AJKHC', 'Criminal Appeal', 'appeal', 'criminal', '{"criminal appeal","crim appeal"}',
  'migration 0138'),
 ('AJKHC:CRLREV',  'AJKHC', 'Criminal Revision', 'revision', 'criminal',
  '{"criminal revision petition","criminal revision","crim revision petition","crim revision"}', 'migration 0138'),
 ('AJKHC:CR',      'AJKHC', 'Civil Revision', 'revision', 'civil', '{"civil revision"}', 'migration 0138'),
 ('AJKHC:RP',      'AJKHC', 'Revision Petition', 'revision', 'mixed', '{"revision petition"}', 'migration 0138'),
 ('AJKHC:FA',      'AJKHC', 'Family Appeal', 'appeal', 'civil', '{"family appeal"}', 'migration 0138'),
 ('AJKHC:SA',      'AJKHC', 'Service Appeal', 'appeal', 'civil', '{"service appeal"}', 'migration 0138'),
 ('AJKHC:REF',     'AJKHC', 'Reference', 'reference', 'mixed', '{"reference"}', 'migration 0138'),
 ('AJKHC:CRLREF',  'AJKHC', 'Criminal Reference', 'reference', 'criminal', '{"criminal reference"}', 'migration 0138'),
 ('AJKHC:CRLMISC', 'AJKHC', 'Criminal Miscellaneous Petition', 'misc_application', 'criminal',
  '{"crim misc petition"}', 'migration 0138'),
 ('AJKHC:CM',      'AJKHC', 'Civil Miscellaneous', 'misc_application', 'civil', '{"civil miscellaneous"}',
  'migration 0138'),
 ('AJKHC:COP',     'AJKHC', 'Company Petition', 'original_petition', 'civil', '{"company petition"}', 'migration 0138'),
 -- Gilgit-Baltistan Supreme Appellate Court
 ('GBSAC:CPLA',    'GBSAC', 'Civil Petition for Leave to Appeal', 'leave_petition', 'civil',
  '{"civil petition for leave to appeal","cpla","c p l a","c p la","c pl a"}', 'migration 0138'),
 ('GBSAC:CPLAUO',  'GBSAC', 'Civil Petition for Leave to Appeal under objection', 'leave_petition', 'civil',
  '{"cpla under objection"}', 'migration 0138'),
 ('GBSAC:CRPLAUO', 'GBSAC', 'Criminal Petition for Leave to Appeal under objection', 'leave_petition', 'criminal',
  '{"cr pla under objection"}', 'migration 0138'),
 ('GBSAC:UO',      'GBSAC', 'Under Objection', 'other', 'mixed', '{"under objection"}', 'migration 0138'),
 ('GBSAC:CA',      'GBSAC', 'Civil Appeal', 'appeal', 'civil', '{"civil appeal","c appeal"}', 'migration 0138'),
 ('GBSAC:CRLA',    'GBSAC', 'Criminal Appeal', 'appeal', 'criminal', '{"criminal appeal","cr appeal","cr a"}',
  'migration 0138'),
 ('GBSAC:CRPLA',   'GBSAC', 'Criminal Petition for Leave to Appeal', 'leave_petition', 'criminal',
  '{"cr pla","cr p l a"}', 'migration 0138'),
 ('GBSAC:CM',      'GBSAC', 'Civil Miscellaneous', 'misc_application', 'civil',
  '{"c misc application","civil misc","c misc","c m a","cm"}', 'migration 0138'),
 ('GBSAC:CRLMISC', 'GBSAC', 'Criminal Miscellaneous', 'misc_application', 'criminal',
  '{"cr misc application","cr misc"}', 'migration 0138'),
 ('GBSAC:SMC',     'GBSAC', 'Suo Motu Case', 'suo_motu', 'constitutional', '{"smc","s m c"}', 'migration 0138'),
 ('GBSAC:CRP',     'GBSAC', 'Civil Review', 'review', 'civil',
  '{"civil review petition","civil review","c review","c rev"}', 'migration 0138'),
 ('GBSAC:CRLRP',   'GBSAC', 'Criminal Review', 'review', 'criminal', '{"criminal review","cr review"}',
  'migration 0138'),
 ('GBSAC:RP',      'GBSAC', 'Review Petition', 'review', 'mixed', '{"review petition"}', 'migration 0138'),
 ('GBSAC:COP',     'GBSAC', 'Contempt Petition', 'contempt', 'mixed', '{"contempt petition"}', 'migration 0138'),
 ('GBSAC:CRLOP',   'GBSAC', 'Criminal Original Petition', 'original_petition', 'criminal',
  '{"cr original petition"}', 'migration 0138'),
 ('GBSAC:OP',      'GBSAC', 'Original Petition', 'original_petition', 'mixed', '{"original petition"}',
  'migration 0138'),
 ('GBSAC:HRC',     'GBSAC', 'Human Rights Case', 'human_rights_case', 'constitutional', '{"h r c","hrc"}',
  'migration 0138'),
 ('GBSAC:CR',      'GBSAC', 'Civil Revision', 'revision', 'civil', '{"civil revision"}', 'migration 0138'),
 ('GBSAC:JP',      'GBSAC', 'Jail Petition', 'jail_petition', 'criminal', '{"jail petition"}', 'migration 0138'),
 ('GBSAC:AA',      'GBSAC', 'Administrative Appeal', 'appeal', 'mixed', '{"administrative appeal"}',
  'migration 0138'),
 -- Gilgit-Baltistan Chief Court (the 29 files with a text layer)
 ('GBCC:WP',       'GBCC', 'Writ Petition', 'writ', 'constitutional', '{"writ pet","w p","wp"}', 'migration 0138'),
 ('GBCC:CR',       'GBCC', 'Civil Revision', 'revision', 'civil', '{"civil revision","c rev"}', 'migration 0138'),
 ('GBCC:CFA',      'GBCC', 'Civil First Appeal', 'appeal', 'civil', '{"civil first appeal","cfa"}', 'migration 0138'),
 ('GBCC:CSA',      'GBCC', 'Civil Second Appeal', 'appeal', 'civil', '{"csa"}', 'migration 0138'),
 ('GBCC:CRLA',     'GBCC', 'Criminal Appeal', 'appeal', 'criminal', '{"criminal appeal","cr app"}', 'migration 0138'),
 ('GBCC:CRLMISC',  'GBCC', 'Criminal Miscellaneous', 'misc_application', 'criminal', '{"cr misc"}', 'migration 0138');

-- The courts' names as their own headers print them, folded ('AZAD JAMMU & KASHMIR' folds to 'azad jammu kashmir')
INSERT INTO court_alias (court_code, alias_printed, alias_key, method, evidence, recorded_by) VALUES
 ('AJKSC', 'SUPREME COURT OF AZAD JAMMU & KASHMIR', 'supreme court of azad jammu kashmir', 'observed',
  '{"archive": "ajksc_judgments.zip", "files": 73, "observed": "2026-11-25"}', 'migration 0138'),
 ('AJKHC', 'HIGH COURT OF AZAD JAMMU & KASHMIR', 'high court of azad jammu kashmir', 'observed',
  '{"archive": "ajkhc_judgments.zip", "files": 118, "observed": "2026-11-25"}', 'migration 0138'),
 ('AJKHC', 'HIGH COURT AZAD JAMMU AND KASHMIR', 'high court azad jammu and kashmir', 'observed',
  '{"archive": "ajkhc_judgments.zip", "files": 6, "observed": "2026-11-25"}', 'migration 0138'),
 ('GBSAC', 'SUPREME APPELLATE COURT GILGIT-BALTISTAN', 'supreme appellate court gilgit baltistan', 'observed',
  '{"archive": "sacgb_judgments.zip", "files": 650, "observed": "2026-11-25"}', 'migration 0138');
COMMIT;
