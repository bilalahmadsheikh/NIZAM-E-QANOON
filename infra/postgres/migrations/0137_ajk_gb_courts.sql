-- 0137  The AJK and Gilgit-Baltistan courts, and the territories each binding rule's words reach
--       (DECISION-LOG D-141; docs/PRECEDENT-MODEL.md §1).
--
-- 0118 left the AJK and GB courts out because their constitutional texts were not held. Both are now released:
--   * the Azad Jammu and Kashmir Interim Constitution 1974 (observation 15688, D-096, landed and released D-140):
--     Art. 42 constitutes the Supreme Court of AJK, Art. 42-B makes its decisions binding "on all other Courts in
--     Azad Jammu and Kashmir", Art. 43 constitutes the High Court, Art. 44-B binds "all courts subordinate to it";
--   * the Government of Gilgit-Baltistan Order 2018 (observation 15449, D-113): s.75 the Supreme Appellate Court,
--     s.78 binding "on all other Courts in the Gilgit-Baltistan", s.84 the Chief Court, s.88 "all Courts subordinate
--     to it" (printed "Subject to Section 60"; quoted as printed).
--
-- A rule's words name where it reaches, and 0118's resolver ignored that: "all other courts" reached every court in
-- the registry. Seeding AJK and GB courts would have made a Supreme Court of Pakistan decision "binding" on the AJK
-- courts, an AJK Supreme Court decision binding on the Lahore High Court, and Art. 201 ("any decision of a High
-- Court") a rule for the AJK High Court. So each rule now records the territories its words reach (`territories`).
-- 0118's rules print "in Pakistan" (Arts. 189, 201, 203GG): the federation's courts and the territories Art. 1(2)(a)
-- and (b) name -- the four Provinces and the Islamabad Capital Territory. Whether a court of AJK or GB is a "court in
-- Pakistan" under Art. 1(2)(c) is not read into a record: the resolver answers NotRecorded for it, never a guess.
--
-- Neither text prints a superintendence clause ("supervise and control"), so no court_superintendence row is seeded
-- for ajk or gb, and "courts subordinate to it" stays NotRecorded there. Each rule is dated from the day its text is
-- served (the copies' capture dates; text_known_from); earlier days are not recorded.

BEGIN;

-- The column is filled for 0118's rows by its default, which no trigger sees; the default is then dropped, so every
-- later rule names its own reach.
ALTER TABLE authority_rule ADD COLUMN territories jurisdiction[] NOT NULL
    DEFAULT '{fed,punjab,sindh,kp,balochistan,ict}';
ALTER TABLE authority_rule ALTER COLUMN territories DROP DEFAULT;
ALTER TABLE authority_rule ADD CONSTRAINT ck_authority_territories CHECK (cardinality(territories) > 0);
COMMENT ON COLUMN authority_rule.territories IS
    'D-141: the territories the rule''s printed words reach. "in Pakistan": fed and Art. 1(2)(a)-(b) (the four '
    'Provinces and ICT); "in Azad Jammu and Kashmir": ajk; "in the Gilgit-Baltistan": gb. A court outside them is '
    'NotRecorded by the rule, never bound or freed by it.';

INSERT INTO court (code, name, court_class, territory, source_observation_id, source_expression_ordinal,
                   source_unit, source_quote, recorded_by) VALUES
 ('AJKSC', 'Supreme Court of Azad Jammu and Kashmir', 'apex', 'ajk', 15688, 0, '42',
  'There shall be constituted a Supreme Court of Azad Jammu and Kashmir to be the highest Court of appeal.',
  'migration 0137'),
 ('AJKHC', 'High Court of Azad Jammu and Kashmir', 'high_court', 'ajk', 15688, 0, '43',
  'There shall be a High Court for Azad Jammu and Kashmir, hereinafter called the High Court', 'migration 0137'),
 ('GBSAC', 'Gilgit-Baltistan Supreme Appellate Court', 'apex', 'gb', 15449, 0, '75',
  'There shall be constituted a Gilgit-Baltistan Supreme Appellate Court, referred to as the Supreme Appellate Court '
  'to be the highest Court of Appeal.', 'migration 0137'),
 ('GBCC', 'Gilgit-Baltistan Chief Court', 'high_court', 'gb', 15449, 0, '84',
  'There shall be a Gilgit-Baltistan Chief Court, hereinafter called the Chief Court', 'migration 0137');

-- keyed as the parser folds a header (nizam.corpus.judgment.fold: lower case, every other character a space), so
-- 'Gilgit-Baltistan' is 'gilgit baltistan'
INSERT INTO court_alias (court_code, alias_printed, alias_key, method, evidence, recorded_by)
SELECT code, name, btrim(regexp_replace(lower(name), '[^a-z0-9]+', ' ', 'g')), 'statute_text',
       jsonb_build_object('source_observation_id', source_observation_id, 'unit', source_unit), 'migration 0137'
  FROM court WHERE recorded_by = 'migration 0137';
INSERT INTO court_alias (court_code, alias_printed, alias_key, method, evidence, recorded_by) VALUES
 ('AJKHC', 'High Court for Azad Jammu and Kashmir', 'high court for azad jammu and kashmir', 'statute_text',
  '{"source_observation_id": 15688, "unit": "43"}', 'migration 0137');

INSERT INTO authority_rule (deciding_court, deciding_class, receiving, except_court, subject, subject_to, validity,
                            basis, source_observation_id, source_expression_ordinal, source_unit, source_quote,
                            territories, recorded_by) VALUES
 ('AJKSC', NULL, 'all_other_courts', NULL, 'all', '{}', '[2026-05-12,)', 'dated_text', 15688, 0, '42-B',
  'Any decision of the Supreme Court shall, to the extent that it decides a question of law or is based upon or '
  'enunciates a principle of law, be binding on all other Courts in Azad Jammu and Kashmir.', '{ajk}', 'migration 0137'),
 ('AJKHC', NULL, 'courts_subordinate_to_deciding', NULL, 'all', '{"Article 42-B"}', '[2026-05-12,)', 'dated_text',
  15688, 0, '44-B',
  'Subject to Article 42-B, any decision of the High Court shall, to the extent that it decides a question of law or '
  'is based upon or enunciates a principle of law, be binding on all courts subordinate to it.', '{ajk}',
  'migration 0137'),
 ('GBSAC', NULL, 'all_other_courts', NULL, 'all', '{}', '[2026-09-12,)', 'dated_text', 15449, 0, '78',
  'Any decision of the Supreme Appellate Court shall, to the extent that it decides a question of law or is based '
  'upon or enunciates a principle of law, be binding on all other Courts in the Gilgit-Baltistan.', '{gb}',
  'migration 0137'),
 ('GBCC', NULL, 'courts_subordinate_to_deciding', NULL, 'all', '{"Section 60"}', '[2026-09-12,)', 'dated_text',
  15449, 0, '88',
  'Subject to Section 60, any decision of Chief Court shall, to the extent that it decides a question of law or is '
  'based upon or enunciates a principle of law, be binding on all Courts subordinate to it.', '{gb}',
  'migration 0137');

-- Refuse the migration if any row's words are not printed where it says they are (as 0118 does).
DO $$
DECLARE missing text;
BEGIN
    SELECT string_agg(record || ' ' || key || ' (obs ' || source_observation_id || ', unit ' || source_unit || ')', '; ')
      INTO missing FROM v_court_record_source s WHERE NOT s.found;
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION '0137: words not found in a released version: %', missing;
    END IF;
END $$;

COMMIT;
