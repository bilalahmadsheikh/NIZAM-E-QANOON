-- 0118  Courts are data; whether a decision binds is a dated rule read from the Constitution's own text
--       (DECISION-LOG D-116, docs/PRECEDENT-MODEL.md §1).
--
-- docs/03 §1.1's `court` enum had no Federal Constitutional Court, no AJK or GB courts and no dates, and docs/04 §6.1
-- called it stale. Art. 189 was substituted on 13 Nov 2025 (Constitution (Twenty-seventh Amendment) Act 2025 s.34), so
-- whether a Supreme Court decision binds now depends on the date asked about.
--
-- Every row here rests on words in a released law. It cites them by a key that survives a replay of that law
-- (source observation, expression ordinal, the unit's printed label), plus the exact words (`source_quote`), never by
-- a provision or version id: those change when the law is re-segmented. `law_unit_quote_found()` checks that the
-- words are still printed in a released version of the unit. This migration refuses to seed a row whose words are
-- not found, and audit A24 asserts the same rule on every run.
--
-- Only binding rules are stored. "Persuasive" is a doctrine, not a record. Where no rule is recorded for a court on
-- a date, the resolver (nizam/storage/authority.py) answers NotRecorded, never a guess. That covers:
--   * the AJK and GB courts, whose constitutional texts are not held;
--   * the bench rules (a larger bench binds a smaller one), which are case law and are seeded from the judgment
--     paragraph that lays them down (basis 'case_law', added with the judgment tables);
--   * 2017-01-07 .. 2025-11-13 for the Supreme Court rule, and 2017-01-07 .. 2026-06-19 for Arts. 201 and 203GG.
--     The Constitution is dated only for 2016 (obs 2810) and from 19 Jun 2026 (obs 507), and the 23rd and 24th
--     Amendment Acts (2017) are not held, so continuity cannot be shown from amendment records.

BEGIN;

CREATE TYPE court_class AS ENUM ('constitutional_apex', 'apex', 'shariat', 'high_court', 'subordinate',
                                 'tribunal', 'special');

-- Are these words printed in a released version of the unit (or anywhere in its subtree)?
-- Whitespace is folded; nothing else.
CREATE FUNCTION law_unit_quote_found(p_observation bigint, p_ordinal integer, p_unit text, p_quote text)
RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS (
        SELECT 1
          FROM v_release_instrument r
          JOIN provision a ON a.instrument_id = r.id AND a.is_active AND a.label = p_unit
                          AND a.kind IN ('section', 'article', 'preamble')
          JOIN provision c ON c.instrument_id = r.id AND c.is_active AND c.path <@ a.path
          JOIN provision_version v ON v.provision_id = c.id
         WHERE r.source_observation_id = p_observation AND r.expression_ordinal = p_ordinal
           AND position(regexp_replace(p_quote, '\s+', ' ', 'g')
                        IN regexp_replace(v.text_normalised, '\s+', ' ', 'g')) > 0)
$$;

-- Rows are append-only. A mistaken row is withdrawn (withdrawn_at, once, with a reason), never edited or deleted.
CREATE FUNCTION court_record_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION '%: rows are append-only; withdraw instead (withdrawn_at, withdrawn_reason)', TG_TABLE_NAME;
    END IF;
    IF OLD.withdrawn_at IS NOT NULL
       OR NEW.withdrawn_at IS NULL OR NEW.withdrawn_reason IS NULL
       -- a stored generated column is not yet computed in a BEFORE trigger's NEW, so it is left out of the comparison
       OR (to_jsonb(NEW) - 'withdrawn_at' - 'withdrawn_reason' - 'deciding_key')
          <> (to_jsonb(OLD) - 'withdrawn_at' - 'withdrawn_reason' - 'deciding_key')
    THEN
        RAISE EXCEPTION '%: the only permitted change is a one-time withdrawal with a reason', TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END $$;

CREATE TABLE court (
    code                      text PRIMARY KEY CHECK (code ~ '^[A-Z][A-Z0-9-]{1,15}$'),
    name                      text NOT NULL,
    court_class               court_class NOT NULL,
    territory                 jurisdiction NOT NULL,       -- 'fed': the whole federation
    source_observation_id     bigint NOT NULL REFERENCES source_observation (id),
    source_expression_ordinal integer NOT NULL,
    source_unit               text NOT NULL,
    source_quote              text NOT NULL CHECK (length(source_quote) BETWEEN 12 AND 2000),
    recorded_by               text NOT NULL,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    withdrawn_at              timestamptz,
    withdrawn_reason          text
);

-- Each printed form of a court's name. Constitution names are seeded here; headers seen in landed judgments are added
-- with method 'observed' and the document they were read from.
CREATE TABLE court_alias (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    court_code       text NOT NULL REFERENCES court (code),
    alias_printed    text NOT NULL,
    alias_key        text NOT NULL CHECK (alias_key = lower(regexp_replace(alias_key, '\s+', ' ', 'g'))),
    method           text NOT NULL CHECK (method IN ('statute_text', 'observed')),
    evidence         jsonb NOT NULL DEFAULT '{}',
    recorded_by      text NOT NULL,
    recorded_at      timestamptz NOT NULL DEFAULT now(),
    withdrawn_at     timestamptz,
    withdrawn_reason text
);
CREATE UNIQUE INDEX ux_court_alias_key ON court_alias (alias_key) WHERE withdrawn_at IS NULL;

-- Art. 203: "Each High Court shall supervise and control all courts subordinate to it." A subordinate court is
-- subordinate to the High Court of its territory.
CREATE TABLE court_superintendence (
    high_court                text NOT NULL REFERENCES court (code),
    territory                 jurisdiction NOT NULL,
    source_observation_id     bigint NOT NULL REFERENCES source_observation (id),
    source_expression_ordinal integer NOT NULL,
    source_unit               text NOT NULL,
    source_quote              text NOT NULL,
    recorded_by               text NOT NULL,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    withdrawn_at              timestamptz,
    withdrawn_reason          text
);
CREATE UNIQUE INDEX ux_court_superintendence ON court_superintendence (territory) WHERE withdrawn_at IS NULL;

-- What a court may hear, each kind resting on its article (docs/06 forum finder; a judgment's jurisdiction invoked).
CREATE TABLE court_jurisdiction (
    id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    court_code                text REFERENCES court (code),
    court_class               court_class,
    kind                      text NOT NULL CHECK (kind IN ('original', 'appellate', 'constitutional_writ', 'revisional',
                                                            'review', 'shariat', 'advisory', 'transfer')),
    validity                  daterange NOT NULL CHECK (NOT isempty(validity)),
    source_observation_id     bigint NOT NULL REFERENCES source_observation (id),
    source_expression_ordinal integer NOT NULL,
    source_unit               text NOT NULL,
    source_quote              text NOT NULL,
    recorded_by               text NOT NULL,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    withdrawn_at              timestamptz,
    withdrawn_reason          text,
    CONSTRAINT ck_court_jurisdiction_one_holder CHECK (num_nonnulls(court_code, court_class) = 1)
);

CREATE TABLE authority_rule (
    id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    deciding_court            text REFERENCES court (code),
    deciding_class            text CHECK (deciding_class IN ('constitutional_apex', 'apex', 'shariat', 'high_court')),
    -- whom it binds
    receiving                 text NOT NULL CHECK (receiving IN ('all_other_courts', 'courts_subordinate_to_deciding',
                                                                 'high_courts_and_their_subordinate_courts',
                                                                 'same_court_smaller_bench')),
    except_court              text REFERENCES court (code),
    effect                    text NOT NULL DEFAULT 'binding' CHECK (effect = 'binding'),
    -- "to the extent that it decides a question of law or is based upon or enunciates a principle of law"
    scope                     text NOT NULL DEFAULT 'question_of_law' CHECK (scope = 'question_of_law'),
    subject                   text NOT NULL DEFAULT 'all' CHECK (subject IN ('all', 'shariat_chapter_3A')),
    subject_to                text[] NOT NULL DEFAULT '{}',        -- as printed: 'Article 189', 'Articles 203D and 203F'
    validity                  daterange NOT NULL CHECK (NOT isempty(validity)),
    basis                     text NOT NULL CHECK (basis IN ('dated_text', 'commencement',
                                                             'continuity_from_amendment_records', 'case_law')),
    source_observation_id     bigint REFERENCES source_observation (id),
    source_expression_ordinal integer,
    source_unit               text,
    source_quote              text,
    source_paragraph_id       uuid,                                -- a judgment paragraph; FK with the judgment tables
    recorded_by               text NOT NULL,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    withdrawn_at              timestamptz,
    withdrawn_reason          text,
    deciding_key              text GENERATED ALWAYS AS (coalesce(deciding_court, 'class:' || deciding_class)) STORED,
    CONSTRAINT ck_authority_one_decider CHECK (num_nonnulls(deciding_court, deciding_class) = 1),
    CONSTRAINT ck_authority_one_source CHECK (
        (source_paragraph_id IS NULL AND source_observation_id IS NOT NULL AND source_expression_ordinal IS NOT NULL
         AND source_unit IS NOT NULL AND source_quote IS NOT NULL)
     OR (source_paragraph_id IS NOT NULL AND source_observation_id IS NULL AND source_expression_ordinal IS NULL
         AND source_unit IS NULL AND source_quote IS NULL)),
    CONSTRAINT ck_authority_case_law CHECK ((basis = 'case_law') = (source_paragraph_id IS NOT NULL)),
    CONSTRAINT ck_authority_bench_rule CHECK ((receiving = 'same_court_smaller_bench') <= (basis = 'case_law')),
    -- the INV-5 pattern: one rule per decider, receiver and subject at any date
    CONSTRAINT authority_rule_no_overlap EXCLUDE USING gist (
        deciding_key WITH =, receiving WITH =, subject WITH =, validity WITH &&) WHERE (withdrawn_at IS NULL)
);

CREATE TRIGGER court_append_only BEFORE UPDATE OR DELETE ON court
    FOR EACH ROW EXECUTE FUNCTION court_record_append_only();
CREATE TRIGGER court_alias_append_only BEFORE UPDATE OR DELETE ON court_alias
    FOR EACH ROW EXECUTE FUNCTION court_record_append_only();
CREATE TRIGGER court_superintendence_append_only BEFORE UPDATE OR DELETE ON court_superintendence
    FOR EACH ROW EXECUTE FUNCTION court_record_append_only();
CREATE TRIGGER court_jurisdiction_append_only BEFORE UPDATE OR DELETE ON court_jurisdiction
    FOR EACH ROW EXECUTE FUNCTION court_record_append_only();
CREATE TRIGGER authority_rule_append_only BEFORE UPDATE OR DELETE ON authority_rule
    FOR EACH ROW EXECUTE FUNCTION court_record_append_only();

-- Every standing row whose words are (or are not) printed in a released version of its unit. A24 reads this.
CREATE VIEW v_court_record_source AS
SELECT 'court' AS record, code AS key, source_observation_id, source_expression_ordinal, source_unit, source_quote,
       law_unit_quote_found(source_observation_id, source_expression_ordinal, source_unit, source_quote) AS found
  FROM court WHERE withdrawn_at IS NULL
UNION ALL
SELECT 'superintendence', high_court || ':' || territory, source_observation_id, source_expression_ordinal,
       source_unit, source_quote,
       law_unit_quote_found(source_observation_id, source_expression_ordinal, source_unit, source_quote)
  FROM court_superintendence WHERE withdrawn_at IS NULL
UNION ALL
SELECT 'jurisdiction', coalesce(court_code, court_class::text) || ':' || kind, source_observation_id,
       source_expression_ordinal, source_unit, source_quote,
       law_unit_quote_found(source_observation_id, source_expression_ordinal, source_unit, source_quote)
  FROM court_jurisdiction WHERE withdrawn_at IS NULL
UNION ALL
SELECT 'authority', id::text, source_observation_id, source_expression_ordinal, source_unit, source_quote,
       law_unit_quote_found(source_observation_id, source_expression_ordinal, source_unit, source_quote)
  FROM authority_rule WHERE withdrawn_at IS NULL AND source_paragraph_id IS NULL;

-- ---------------------------------------------------------------------------------------------------------------
-- Seeds. Observation 507 = the Constitution as served (dated from 19 Jun 2026); 2810/0 = the Constitution copy dated
-- [2016-06-08, 2017-01-07); 15198/0 = the Constitution (Twenty-seventh Amendment) Act 2025 (commenced 2025-11-13).
-- ---------------------------------------------------------------------------------------------------------------

INSERT INTO court (code, name, court_class, territory, source_observation_id, source_expression_ordinal,
                   source_unit, source_quote, recorded_by) VALUES
 ('FCC', 'Federal Constitutional Court of Pakistan', 'constitutional_apex', 'fed', 507, 0, '175',
  'a Federal Constitutional Court of Pakistan, hereinafter referred to as the Federal Constitutional Court',
  'migration 0118'),
 ('SC',  'Supreme Court of Pakistan', 'apex', 'fed', 507, 0, '175',
  'a Supreme Court of Pakistan', 'migration 0118'),
 ('FSC', 'Federal Shariat Court', 'shariat', 'fed', 507, 0, '203C',
  'There shall be constituted for the purposes of this Chapter a Court to be called the Federal Shariat Court.',
  'migration 0118'),
 ('LHC', 'Lahore High Court', 'high_court', 'punjab', 507, 0, '198',
  'The Lahore High Court shall have a Bench each at Bahawalpur, Multan and Rawalpindi', 'migration 0118'),
 ('SHC', 'High Court of Sindh', 'high_court', 'sindh', 507, 0, '198',
  'the High Court of Sindh shall have a Bench at Sukkur', 'migration 0118'),
 ('PHC', 'Peshawar High Court', 'high_court', 'kp', 507, 0, '198',
  'the Peshawar High Court shall have a Bench each at Abbottabad', 'migration 0118'),
 ('BHC', 'High Court of Balochistan', 'high_court', 'balochistan', 507, 0, '198',
  'the High Court of Balochistan shall have a Bench at Sibi', 'migration 0118'),
 ('IHC', 'Islamabad High Court', 'high_court', 'ict', 507, 0, '198',
  'The High Court for Islamabad Capital Territory shall have its principal seat at Islamabad.', 'migration 0118');

INSERT INTO court_alias (court_code, alias_printed, alias_key, method, evidence, recorded_by)
SELECT code, name, lower(name), 'statute_text',
       jsonb_build_object('source_observation_id', source_observation_id, 'unit', source_unit), 'migration 0118'
  FROM court;
INSERT INTO court_alias (court_code, alias_printed, alias_key, method, evidence, recorded_by) VALUES
 ('IHC', 'High Court for Islamabad Capital Territory', 'high court for islamabad capital territory', 'statute_text',
  '{"source_observation_id": 507, "unit": "198"}', 'migration 0118');

INSERT INTO court_superintendence (high_court, territory, source_observation_id, source_expression_ordinal,
                                   source_unit, source_quote, recorded_by)
SELECT code, territory, 507, 0, '203', 'Each High Court shall supervise and control all courts subordinate to it.',
       'migration 0118'
  FROM court WHERE court_class = 'high_court';

INSERT INTO court_jurisdiction (court_code, court_class, kind, validity, source_observation_id,
                                source_expression_ordinal, source_unit, source_quote, recorded_by) VALUES
 ('FCC', NULL, 'original', '[2025-11-13,)', 507, 0, '175E',
  'The Federal Constitutional Court shall, to the exclusion of every other court, have original jurisdiction in any '
  'dispute between any two or more Governments.', 'migration 0118'),
 ('FCC', NULL, 'appellate', '[2025-11-13,)', 507, 0, '175F',
  'The Federal Constitutional Court shall have jurisdiction to hear and determine appeals from judgments, decrees, '
  'final orders or sentences of a High Court', 'migration 0118'),
 ('FCC', NULL, 'review', '[2025-11-13,)', 507, 0, '175G',
  'The Federal Constitutional Court shall have the power, subject to the provisions of any Act of Majlis-e-Shoora '
  '(Parliament) and any rules made by the Federal Constitutional Court, to review any judgment pronounced or any '
  'order made by it.', 'migration 0118'),
 ('SC', NULL, 'appellate', '[2026-06-19,)', 507, 0, '185',
  'the Supreme Court shall have jurisdiction to hear and determine appeals from judgments, decrees, final orders or '
  'sentences of a High Court.', 'migration 0118'),
 (NULL, 'high_court', 'constitutional_writ', '[2026-06-19,)', 507, 0, '199',
  'Subject to the Constitution, a High Court may, if it is satisfied that no other adequate remedy is provided by law',
  'migration 0118'),
 ('FSC', NULL, 'shariat', '[2026-06-19,)', 507, 0, '203D',
  'examine and decide the question whether or not any law or provision of law is repugnant to the Injunctions of '
  'Islam', 'migration 0118');

INSERT INTO authority_rule (deciding_court, deciding_class, receiving, except_court, subject, subject_to, validity,
                            basis, source_observation_id, source_expression_ordinal, source_unit, source_quote,
                            recorded_by) VALUES
 -- Art. 189 before the 27th Amendment, as the 2016 copy prints it
 ('SC', NULL, 'all_other_courts', NULL, 'all', '{}', '[2016-06-08,2017-01-07)', 'dated_text', 2810, 0, '189',
  'Any decision of the Supreme Court shall, to the extent that it decides a question of law or is based upon or '
  'enunciates a principle of law, be binding on all other courts in Pakistan.', 'migration 0118'),
 -- Art. 189 as substituted by the 27th Amendment Act s.34, from its commencement
 ('FCC', NULL, 'all_other_courts', NULL, 'all', '{}', '[2025-11-13,)', 'commencement', 15198, 0, '34',
  'Any decision of the Federal Constitutional Court shall, to the extent that it decides a question of law or is '
  'based upon or enunciates a principle of law, be binding on all other courts in Pakistan including the Supreme '
  'Court.', 'migration 0118'),
 ('SC', NULL, 'all_other_courts', 'FCC', 'all', '{}', '[2025-11-13,)', 'commencement', 15198, 0, '34',
  'Any decision of the Supreme Court shall, to the extent that it decides a question of law or is based upon or '
  'enunciates a principle of law, be binding on all other courts in Pakistan except the Federal Constitutional '
  'Court.', 'migration 0118'),
 -- Art. 201, both dated texts
 (NULL, 'high_court', 'courts_subordinate_to_deciding', NULL, 'all', '{"Article 189"}', '[2016-06-08,2017-01-07)',
  'dated_text', 2810, 0, '201',
  'Subject to Article 189, any decision of a High Court shall, to the extent that it decides a question of law or is '
  'based upon or enunciates a principle of law, be binding on all courts subordinate to it.', 'migration 0118'),
 (NULL, 'high_court', 'courts_subordinate_to_deciding', NULL, 'all', '{"Article 189"}', '[2026-06-19,)',
  'dated_text', 507, 0, '201',
  'Subject to Article 189, any decision of a High Court shall, to the extent that it decides a question of law or is '
  'based upon or enunciates a principle of law, be binding on all courts subordinate to it.', 'migration 0118'),
 -- Art. 203GG, both dated texts
 ('FSC', NULL, 'high_courts_and_their_subordinate_courts', NULL, 'shariat_chapter_3A', '{"Articles 203D and 203F"}',
  '[2016-06-08,2017-01-07)', 'dated_text', 2810, 0, '203GG',
  'Subject to Articles 203D and 203F, any decision of the Court in the exercise of its jurisdiction under this '
  'Chapter shall be binding on a High Court and on all courts subordinate to a High Court.', 'migration 0118'),
 ('FSC', NULL, 'high_courts_and_their_subordinate_courts', NULL, 'shariat_chapter_3A', '{"Articles 203D and 203F"}',
  '[2026-06-19,)', 'dated_text', 507, 0, '203GG',
  'Subject to Articles 203D and 203F, any decision of the Court in the exercise of its jurisdiction under this '
  'Chapter shall be binding on a High Court and on all courts subordinate to a High Court.', 'migration 0118');

-- Refuse the migration if any seeded row's words are not printed where it says they are.
DO $$
DECLARE missing text;
BEGIN
    SELECT string_agg(record || ' ' || key || ' (obs ' || source_observation_id || ', unit ' || source_unit || ')', '; ')
      INTO missing FROM v_court_record_source s WHERE NOT s.found;
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION '0118: seed words not found in a released version: %', missing;
    END IF;
END $$;

COMMIT;
