-- 0129  A sexual-offence judgment is also marked by the words of its body (DECISION-LOG D-131).
--
-- Measured 24 Nov 2026: 240 released judgments speak of rape, zina-bil-jabr, sodomy or the prosecutrix in their body;
-- only 122 cite PPC s.354A/376/376A/377/377B in a form that resolves (the rest cite the Zina Ordinance of 1979, cite
-- unresolved, or name the offence without the section). Withholding a name in a judgment that mentions the offence in
-- passing costs only the name; showing a victim's name is the harm s.376A(1) forbids. 'minor' is not used this way:
-- the word is too common ('minor discrepancies').

BEGIN;
ALTER TABLE sensitive_category_rule DROP CONSTRAINT sensitive_category_rule_kind_check;
ALTER TABLE sensitive_category_rule ADD CONSTRAINT sensitive_category_rule_kind_check
    CHECK (kind IN ('law_cited', 'header_words', 'body_words'));
INSERT INTO sensitive_category_rule (category, kind, pattern, labels, note, recorded_by) VALUES
 ('sexual_offence', 'body_words',
  '\m(rape[ds]?|raping|zina[- ]bil[- ]jabr|sodomy|sodomi[sz]ed|unnatural offence|prosecutrix)\M', NULL,
  'the offence named in the body', 'migration 0129');
COMMIT;
