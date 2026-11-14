-- Citation abbreviations: an amendment footnote that names its amending law by an editorial abbreviation
-- ('Subs. by F.A.O., 1975, Art. 2 and Table, for "Central Government"') resolves to that law when, and only when, a
-- reviewed row here says what the abbreviation stands for.
--
-- WHY. Measured 14 Nov 2026: 300 recorded footnotes in 99 documents cite 'F.A.O., 1975' and resolve to nothing --
-- v_amendment_reference_current (0072-0074) resolves a citation by its NAME (title key + year) or, when bare, by its
-- NUMBER, and an abbreviation is neither. The consolidated texts print no key to their abbreviations, and none was
-- found on the official portals (legal-source-scout, 14 Nov 2026); the only evidence that counts is the corpus's own
-- print, so each row carries it.
--
-- WHAT A ROW SAYS. Printed abbreviation + year -> the instrument title it stands for, in one jurisdiction, with the
-- pattern that recognises it at the start of a cited text. The view resolves through a row only when the citation
-- carries no parsed title, is not a bare 'Act N of YYYY' citation, and exactly ONE active canonical instrument of that
-- jurisdiction and year has the expanded title -- otherwise it stays unresolved, never guessed (the 0072 rule).
--
-- NOT RECORDED (14 Nov 2026), and why -- each needs its own evidence before a row:
--   'A.O., 1937', 'A.O., 1961', 'A.O., 1964' -- the Orders these denote are not held, so there is nothing to resolve to;
--   'A.O., 1949' (50 footnotes)               -- read only on a secondary (non-official) page; no footnote in the corpus
--                                               glosses it or prints the same amendment in full;
--   'Baln. A.O. of 1975' (23)                 -- the Balochistan Laws (Adaptation) Order, 1975 is not held.
--
-- Append-only, latest row per (abbreviation, cited_year, jurisdiction) wins; withdraw with assertion 'withdrawn'.
-- REVERSAL: restore the 0074 view, then drop v_citation_abbreviation_current, the triggers, function and table.
-- Governing contract: docs/03b §1.1 (amends); docs/03 §9; migration 0072's resolution rule.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE citation_abbreviation (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    abbreviation  text NOT NULL CHECK (btrim(abbreviation) <> ''),          -- as printed: 'F.A.O.'
    cited_year    smallint NOT NULL CHECK (cited_year BETWEEN 1800 AND 2100),
    jurisdiction  text NOT NULL CHECK (jurisdiction IN ('fed','punjab','sindh','kp','balochistan','ict','ajk','gb')),
    pattern       text NOT NULL CHECK (left(pattern, 1) = '^' AND strpos(pattern, cited_year::text) > 0),
    expands_to    text NOT NULL CHECK (btrim(expands_to) <> ''),            -- the title, as printed in full
    assertion     text NOT NULL CHECK (assertion IN ('recorded', 'withdrawn')),
    evidence      jsonb NOT NULL CHECK (coalesce(jsonb_typeof(evidence) = 'object'
                                                AND btrim(evidence->>'reviewer_type') <> ''
                                                AND jsonb_typeof(evidence->'printed') = 'array', false)),
    recorded_by   text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at   timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION check_citation_abbreviation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'citation_abbreviation is append-only';
    END IF;
    PERFORM '' ~* NEW.pattern;                              -- an invalid regular expression is refused here
    RETURN NEW;
END $$;

CREATE TRIGGER citation_abbreviation_guard
BEFORE INSERT OR UPDATE OR DELETE ON citation_abbreviation
FOR EACH ROW EXECUTE FUNCTION check_citation_abbreviation();

CREATE TRIGGER citation_abbreviation_no_truncate
BEFORE TRUNCATE ON citation_abbreviation
FOR EACH STATEMENT EXECUTE FUNCTION check_citation_abbreviation();

CREATE VIEW v_citation_abbreviation_current AS
SELECT * FROM (
    SELECT DISTINCT ON (abbreviation, cited_year, jurisdiction) *
      FROM citation_abbreviation
     ORDER BY abbreviation, cited_year, jurisdiction, recorded_at DESC, id DESC) a
 WHERE assertion = 'recorded';

INSERT INTO citation_abbreviation (abbreviation, cited_year, jurisdiction, pattern, expands_to, assertion, evidence,
                                   recorded_by)
VALUES ('F.A.O.', 1975, 'fed', '^\s*(the\s+)?f\.?\s*a\.?\s*o\.?\s*,?\s*(of\s+)?1975\M',
        'Federal Adaptation of Laws Order', 'recorded',
        jsonb_build_object(
          'reviewer_type', 'assistant',
          'printed', jsonb_build_array(
             jsonb_build_object('document_id', 4501, 'page', 263,
                                'text', 'Subs. by F.A.O., 1975 (P.O. No. 4 of 1975),Art. 2 and Table, for "Central Government"',
                                'reading', 'the abbreviation glossed by the number P.O. No. 4 of 1975 in the same footnote'),
             jsonb_build_object('document_id', 4501, 'page', 41,
                                'text', 'Subs. by the Federal Adaptation of Laws Order, 1975 (P. O. No. 4 of 1975), Art. 2 '
                                        'and Table, for "Central Government"',
                                'reading', 'the same substitution, same instrument, printed in full')),
          'corroboration', '627 pairs of footnotes (14 Nov 2026) print the same substitution "Art. 2 and Table, for '
                           '"Central Government"" abbreviated in one footnote and in full in another; the corpus holds '
                           'one Federal Adaptation of Laws Order, 1975 (order 4 of 1975, fed)',
          'measured', '300 recorded footnotes in 99 documents cite F.A.O., 1975 (14 Nov 2026)'),
        'claude');

-- the pattern recognises the printed variants and nothing else
DO $$
DECLARE p text := (SELECT pattern FROM citation_abbreviation WHERE abbreviation = 'F.A.O.' AND cited_year = 1975);
BEGIN
    IF NOT ('F.A.O., 1975' ~* p AND 'the F.A.O., 1975' ~* p AND 'F. A. O., 1975' ~* p AND 'F.A.O 1975' ~* p
            AND 'F.A. O., 1975 (P.O. No. 4 of 1975)' ~* p AND 'f.a.o, 1975' ~* p) THEN
        RAISE EXCEPTION 'F.A.O. pattern misses a printed variant';
    END IF;
    IF 'A.O., 1975' ~* p OR 'F.A.O., 1937' ~* p OR 'F.A.O., 19750' ~* p
       OR 'the Federal Adaptation of Laws Order, 1975' ~* p THEN
        RAISE EXCEPTION 'F.A.O. pattern matches what it must not';
    END IF;
END $$;

CREATE OR REPLACE VIEW v_amendment_reference_current AS
WITH latest AS (
    SELECT DISTINCT ON (source_observation_id, expression_ordinal, footnote_block_id, entry_ordinal) *
      FROM amendment_reference
     ORDER BY source_observation_id, expression_ordinal, footnote_block_id, entry_ordinal, recorded_at DESC, id DESC)
SELECT l.*,
       amended.id AS amended_instrument_id,
       target.provision_id AS target_provision_id,
       amending.id AS amending_instrument_id,
       cited_jurisdiction(l.cited_text) AS cited_jurisdiction
  FROM latest l
  JOIN instrument amended ON amended.source_observation_id = l.source_observation_id
                         AND amended.expression_ordinal = l.expression_ordinal
                         AND amended.is_active AND amended.duplicate_of IS NULL
  LEFT JOIN LATERAL (
       SELECT pb.provision_id
         FROM provision_block pb
         JOIN block_assignment_set s ON s.id = pb.assignment_set_id AND s.is_active
         JOIN provision p ON p.id = pb.provision_id AND p.is_active AND p.instrument_id = amended.id
        WHERE pb.block_id = l.target_block_id
        LIMIT 1) target ON l.target_block_id IS NOT NULL
  LEFT JOIN LATERAL (
       -- a bare citation only, never West Pakistan
       SELECT CASE WHEN count(*) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE is_bare_citation(l.cited_text) AND l.cited_text !~* '\mw\.?\s*p\.|west\s+pakistan'
          AND l.cited_number IS NOT NULL AND l.cited_kind IS NOT NULL AND l.cited_year IS NOT NULL
          AND r.is_active AND r.duplicate_of IS NULL
          AND r.number = l.cited_number AND r.kind::text = l.cited_kind AND r.year = l.cited_year
          AND (CASE WHEN cited_jurisdiction(l.cited_text) IS NOT NULL
                    THEN r.jurisdiction::text = cited_jurisdiction(l.cited_text)
                    ELSE r.jurisdiction::text IN (amended.jurisdiction::text, 'fed') END)
          AND r.id <> amended.id) by_number ON true
  LEFT JOIN LATERAL (
       -- a named citation: title key and year
       SELECT CASE WHEN count(DISTINCT r.id) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE NOT is_bare_citation(l.cited_text) AND l.cited_title IS NOT NULL AND l.cited_year IS NOT NULL
          AND r.is_active AND r.duplicate_of IS NULL AND r.year = l.cited_year
          AND (instrument_title_key(r.short_title) = instrument_title_key(l.cited_title)
               OR instrument_title_key(r.display_title) = instrument_title_key(l.cited_title))
          AND (CASE WHEN cited_jurisdiction(l.cited_text) IS NOT NULL
                    THEN r.jurisdiction::text = cited_jurisdiction(l.cited_text)
                    ELSE r.jurisdiction::text IN (amended.jurisdiction::text, 'fed') END)
          AND r.id <> amended.id) by_title ON true
  LEFT JOIN LATERAL (
       -- an abbreviated citation with no parsed title: a reviewed citation_abbreviation row, then title key and year
       SELECT CASE WHEN count(DISTINCT r.id) = 1 THEN min(r.id::text)::uuid END AS id
         FROM v_citation_abbreviation_current a
         JOIN instrument r ON r.year = a.cited_year AND r.jurisdiction::text = a.jurisdiction
                          AND r.is_active AND r.duplicate_of IS NULL
                          AND (instrument_title_key(r.short_title) = instrument_title_key(a.expands_to)
                               OR instrument_title_key(r.display_title) = instrument_title_key(a.expands_to))
        WHERE l.cited_title IS NULL AND NOT is_bare_citation(l.cited_text)
          AND l.cited_text ~* a.pattern
          AND r.id <> amended.id) by_abbreviation ON true
  LEFT JOIN instrument amending ON amending.id = coalesce(by_number.id, by_title.id, by_abbreviation.id)
 WHERE l.assertion = 'recorded';

COMMENT ON TABLE citation_abbreviation IS
  'Append-only: a printed citation abbreviation (F.A.O., 1975) and the instrument title it stands for, with the '
  'corpus print that shows it. Read by v_amendment_reference_current for citations with no parsed title. Migration 0078.';

COMMIT;
