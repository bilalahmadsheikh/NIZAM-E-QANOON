-- 0128  Names withheld in sensitive judgments: the categories, their recorded basis, the rules that mark a judgment,
--       and the derived display (DECISION-LOG D-131; docs/PRECEDENT-MODEL.md §6.3, D-122).
--
-- D-122: parties_raw is internal; the parties shown are redacted for sensitive categories (sexual offences, minors,
-- family, medical). Each category names its basis from the corpus where one exists, or is marked product policy; no
-- basis is asserted from memory. The quotes below were read in the served laws on 24 Nov 2026, and are cited the way
-- the court records are (0118): observation, expression ordinal, unit label and the exact words, never a row id.
-- A29 asserts that the words are still printed in the served unit.
--
-- judgment_sensitivity and judgment_display are derived, rebuilt whole from the release by one builder
-- (nizam.judgment_privacy/1). judgment.parties_display (0119) is not used: the judgment row is append-only evidence.

BEGIN;

CREATE TABLE sensitive_category (
    code        text PRIMARY KEY CHECK (code IN ('sexual_offence', 'minor', 'family', 'medical')),
    name        text NOT NULL,
    -- statute: the law forbids publishing the identity, and its exception does not reach this product;
    -- follows_statute: the law protects the identity but exempts published judgments, and the product follows its
    -- purpose; product_policy: no provision found in the corpus
    basis_kind  text NOT NULL CHECK (basis_kind IN ('statute', 'follows_statute', 'product_policy')),
    basis_note  text NOT NULL,
    recorded_by text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sensitive_category_source (
    id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category                  text NOT NULL REFERENCES sensitive_category (code),
    role                      text NOT NULL CHECK (role IN ('protects', 'exempts')),
    source_observation_id     bigint NOT NULL REFERENCES source_observation (id),
    source_expression_ordinal integer NOT NULL,
    source_unit               text NOT NULL,
    source_quote              text NOT NULL,
    recorded_by               text NOT NULL,
    recorded_at               timestamptz NOT NULL DEFAULT now()
);

-- What marks a judgment: a resolved citation of a law (by its recorded title) and, where given, of these labels;
-- or words printed in its header.
CREATE TABLE sensitive_category_rule (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category    text NOT NULL REFERENCES sensitive_category (code),
    kind        text NOT NULL CHECK (kind IN ('law_cited', 'header_words')),
    pattern     text NOT NULL,                       -- a case-insensitive regex over the law's title, or the header
    labels      text[],                              -- law_cited: the units that count; NULL = any unit of the law
    note        text,
    recorded_by text NOT NULL,
    CONSTRAINT ck_rule_labels CHECK (kind = 'law_cited' OR labels IS NULL)
);

CREATE TABLE judgment_sensitivity (
    judgment_id uuid NOT NULL,
    decided_on  date NOT NULL,
    category    text NOT NULL REFERENCES sensitive_category (code),
    rule_id     bigint NOT NULL REFERENCES sensitive_category_rule (id),
    evidence    text NOT NULL,                       -- the citation or the header words that matched, as printed
    builder     text NOT NULL,
    PRIMARY KEY (judgment_id, decided_on, category),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on)
);

-- names_withheld is internal: readers use it to redact text and to refuse a search that names a withheld person,
-- and never return it.
CREATE TABLE judgment_display (
    judgment_id     uuid NOT NULL,
    decided_on      date NOT NULL,
    parties_display text,                            -- 'A v. B' as printed, with withheld names replaced
    redacted        boolean NOT NULL,
    names_withheld  text[] NOT NULL DEFAULT '{}',
    builder         text NOT NULL,
    PRIMARY KEY (judgment_id, decided_on),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on),
    CONSTRAINT ck_display_withheld CHECK (redacted OR cardinality(names_withheld) = 0)
);

INSERT INTO sensitive_category (code, name, basis_kind, basis_note, recorded_by) VALUES
 ('sexual_offence', 'Sexual offence', 'statute',
  'Pakistan Penal Code s.376A(1) makes printing or publishing anything that may make known the identity of the victim '
  'of an offence under ss. 354A, 376, 376A, 377 or 377B an offence; its Explanation exempts judgments printed in law '
  'journals, which this product is not. The Anti-Rape (Investigation and Trial) Act 2021 s.26(1) forbids disclosing '
  'the identity of a victim or the victim''s family in respect of its scheduled offences.', 'migration 0128'),
 ('minor', 'Minor', 'follows_statute',
  'Juvenile Justice System Act 2018 s.13(1) makes publishing anything that may make known the identity of a juvenile '
  'an offence; its Explanation says that publishing a judgment of a High Court or the Supreme Court is not an offence '
  'under the section. Names of minors are withheld anyway, following the section''s purpose.', 'migration 0128'),
 ('family', 'Family', 'product_policy',
  'No provision restricting the publication of names in family cases was found in the corpus (searched 24 Nov 2026). '
  'Names are withheld as product policy: family disputes expose private lives (D-122).', 'migration 0128'),
 ('medical', 'Medical', 'product_policy',
  'No provision restricting the publication of names in judgments about health was found in the corpus (the Sindh '
  'HIV and AIDS Act protects the identity of a child tested for HIV, which is narrower). Names are withheld as '
  'product policy (D-122).', 'migration 0128');

INSERT INTO sensitive_category_source (category, role, source_observation_id, source_expression_ordinal, source_unit,
                                       source_quote, recorded_by) VALUES
 ('sexual_offence', 'protects', 147, 0, '376A',
  'Whoever prints or publishes name or any matter which may make known identity of victim', 'migration 0128'),
 ('sexual_offence', 'exempts', 147, 0, '376A',
  'Printing or publication of judgment of any High Court, the Federal Shariat Court or the Supreme Court in law '
  'journals does not amount to an offence', 'migration 0128'),
 ('sexual_offence', 'protects', 953, 0, '26',
  'No person shall disclose or reveal the identity of any victim', 'migration 0128'),
 ('minor', 'protects', 930, 0, '13',
  'whoever prints or publishes the name or any matter which may make known identity of a juvenile', 'migration 0128'),
 ('minor', 'exempts', 930, 0, '13',
  'The printing or publication of the judgment of any High Court or the Supreme Court does not amount to an offence '
  'within the meaning of this section.', 'migration 0128');

DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT * FROM sensitive_category_source LOOP
        IF NOT law_unit_quote_found(r.source_observation_id, r.source_expression_ordinal, r.source_unit, r.source_quote)
        THEN RAISE EXCEPTION 'sensitive_category_source %: the words are not printed in obs % unit %', r.id,
                             r.source_observation_id, r.source_unit;
        END IF;
    END LOOP;
END $$;

INSERT INTO sensitive_category_rule (category, kind, pattern, labels, note, recorded_by) VALUES
 ('sexual_offence', 'law_cited', '^Pakistan Penal Code$', '{354A,376,376A,377,377B}',
  'the offences s.376A(1) names', 'migration 0128'),
 ('sexual_offence', 'law_cited', '^Anti-Rape \(Investigation and Trial\)', NULL, 'the Act of s.26(1)', 'migration 0128'),
 ('sexual_offence', 'law_cited', 'Offence of Zina', '{10}',
  'zina-bil-jabr before 2006: the same victims (product policy extension)', 'migration 0128'),
 ('minor', 'law_cited', 'Juvenile Justice System', NULL, NULL, 'migration 0128'),
 ('minor', 'law_cited', 'Guardians and Wards Act', NULL, 'custody and guardianship of minors', 'migration 0128'),
 ('minor', 'law_cited', 'Child Marriage Restraint', NULL, NULL, 'migration 0128'),
 ('minor', 'header_words', '\m(minor|juvenile)\M|\mthrough\s+(his|her|their)\s+(father|mother|guardian|next\s+friend)',
  NULL, 'a party printed as a minor or suing through a guardian', 'migration 0128'),
 ('family', 'law_cited', 'Family Courts? Act', NULL, NULL, 'migration 0128'),
 ('family', 'law_cited', 'Muslim Family Laws', NULL, NULL, 'migration 0128'),
 ('family', 'law_cited', 'Dissolution of Muslim Marriages', NULL, NULL, 'migration 0128'),
 ('family', 'law_cited', 'Guardians and Wards Act', NULL, NULL, 'migration 0128'),
 ('family', 'law_cited', 'Dowry', NULL, NULL, 'migration 0128'),
 ('family', 'header_words', '\mfamily\s+court|\mjudge\s+family\M', NULL, 'a family court below', 'migration 0128'),
 ('medical', 'law_cited', 'Mental Health', NULL, NULL, 'migration 0128'),
 ('medical', 'law_cited', '\mHIV\M|\mAIDS\M', NULL, NULL, 'migration 0128'),
 ('medical', 'law_cited', 'Lunacy', NULL, NULL, 'migration 0128'),
 ('medical', 'header_words', '\munsound\s+mind\M|\mlunatic\M', NULL, 'a party printed as of unsound mind',
  'migration 0128');

COMMIT;
