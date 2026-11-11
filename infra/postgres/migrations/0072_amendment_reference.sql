-- Amendment references: which law amended which provision, as the consolidated text's own footnotes print it.
--
-- WHY. docs/03b §1.1 names `amends` ("instrument closes one version and opens another; selects the right text for
-- as_of; surfaces the amendment chain"). Every released version carries operation 'original' and amended_by_id NULL:
-- nothing links a provision to the law that changed it. The consolidated texts already say it -- the segmenter sets
-- their footnotes aside as role 'footnote' blocks: '1Subs. by the Law Reforms Ordinance, 1972 (XII of 1972), s. 2',
-- '2Ins. by Act IV of 2017, s. 4 (w.e.f. 3-10-2017)'.
--
-- WHAT A ROW SAYS. One footnote entry of one expression, verbatim, with what it was parsed into: the operation(s),
-- the amending law as cited (title, kind, number, year, section) and a printed 'with effect from' date if any. The
-- amended PROVISION is named by the body block that carries the same footnote marker on the same page
-- ('1[(3) The ...]'); when no single block carries it, target_block_id is NULL and only the instrument is known.
-- Like 0054/0062/0065/0066/0067/0070 the record is about SOURCES (observation, expression ordinal, block ids), so a
-- replay does not orphan it.
--
-- AS BUILT, against docs/03b: this records the `amends` relation, not version history. The corpus holds the current
-- consolidated wording only; the wording before each amendment is not in it, so no version is closed or opened and
-- provision_version is not touched. v_amendment_reference_current resolves the amended instrument and provision,
-- and the amending instrument only where exactly ONE released instrument matches the citation (number/kind/year in
-- the same or federal jurisdiction, else folded title and year). A citation to a law the corpus does not hold, or
-- matching two, stays unresolved -- never guessed.
--
-- Withdrawal is a later row with assertion 'withdrawn' for the same key (append-only, latest wins).
-- REVERSAL (irreversible once a row exists, docs/03 §9): with the table empty, drop the view, triggers, function and
-- table. Governing contract: docs/03b §1.1 (amends); docs/03 §9; docs/SCHEMA.md.

BEGIN;

SET LOCAL lock_timeout = '10s';

CREATE TABLE amendment_reference (
    id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_observation_id  bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    expression_ordinal     smallint NOT NULL CHECK (expression_ordinal >= 0),
    footnote_block_id      bigint NOT NULL CHECK (footnote_block_id > 0),
    entry_ordinal          smallint NOT NULL CHECK (entry_ordinal >= 0),     -- position of the entry in its block
    source_page            integer NOT NULL CHECK (source_page > 0),
    marker                 text,                                             -- '1', '2', ... as printed
    footnote_text          text NOT NULL CHECK (btrim(footnote_text) <> ''),
    operations             text[] NOT NULL CHECK (cardinality(operations) > 0
                                   AND operations <@ ARRAY['substituted','inserted','added','omitted','renumbered',
                                                           'repealed','amended']::text[]),
    cited_text             text NOT NULL CHECK (btrim(cited_text) <> ''),
    cited_title            text,
    cited_kind             text CHECK (cited_kind IS NULL OR cited_kind IN ('act','ordinance','order','regulation')),
    cited_number           text,
    cited_year             smallint CHECK (cited_year IS NULL OR cited_year BETWEEN 1800 AND 2100),
    cited_section          text,
    effective_from         date,
    target_block_id        bigint CHECK (target_block_id IS NULL OR target_block_id > 0),
    assertion              text NOT NULL CHECK (assertion IN ('recorded', 'withdrawn')),
    method                 text NOT NULL CHECK (btrim(method) <> ''),
    evidence               jsonb NOT NULL CHECK (coalesce(jsonb_typeof(evidence) = 'object'
                                                      AND btrim(evidence->>'reviewer_type') <> '', false)),
    recorded_by            text NOT NULL CHECK (btrim(recorded_by) <> ''),
    recorded_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX amendment_reference_key
    ON amendment_reference (source_observation_id, expression_ordinal, footnote_block_id, entry_ordinal,
                            recorded_at DESC, id DESC);

CREATE FUNCTION check_amendment_reference() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'amendment_reference is append-only';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM source_observation WHERE id = NEW.source_observation_id AND outcome = 'landed') THEN
        RAISE EXCEPTION 'observation % has not landed', NEW.source_observation_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM text_block t JOIN document d ON d.id = t.document_id
                     JOIN source_observation o ON o.sha256 = d.sha256
                    WHERE t.id = NEW.footnote_block_id AND o.id = NEW.source_observation_id
                      AND t.page_no = NEW.source_page) THEN
        RAISE EXCEPTION 'footnote block % is not on page % of observation %',
                        NEW.footnote_block_id, NEW.source_page, NEW.source_observation_id;
    END IF;
    IF NEW.target_block_id IS NOT NULL AND NOT EXISTS (
           SELECT 1 FROM text_block t JOIN document d ON d.id = t.document_id
             JOIN source_observation o ON o.sha256 = d.sha256
            WHERE t.id = NEW.target_block_id AND o.id = NEW.source_observation_id
              AND t.page_no = NEW.source_page) THEN
        RAISE EXCEPTION 'target block % is not on page % of observation %',
                        NEW.target_block_id, NEW.source_page, NEW.source_observation_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER amendment_reference_guard
BEFORE INSERT OR UPDATE OR DELETE ON amendment_reference
FOR EACH ROW EXECUTE FUNCTION check_amendment_reference();

CREATE TRIGGER amendment_reference_no_truncate
BEFORE TRUNCATE ON amendment_reference
FOR EACH STATEMENT EXECUTE FUNCTION check_amendment_reference();

-- Title key for matching a citation to an instrument: drop a trailing year, lower case, no leading 'the', letters and
-- digits only. 'The Law Reforms Ordinance, 1972' and 'Law Reforms Ordinance' both give 'lawreformsordinance'.
CREATE FUNCTION instrument_title_key(t text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT nullif(regexp_replace(regexp_replace(lower(regexp_replace(coalesce(t, ''), ',?\s*\(?\d{4}\)?\s*\.?\s*$', '')),
                                                '^\s*the\s+', ''), '[^a-z0-9]+', '', 'g'), '')
$$;

CREATE INDEX instrument_title_key_short
    ON instrument (year, instrument_title_key(short_title)) WHERE is_active AND duplicate_of IS NULL;
CREATE INDEX instrument_title_key_display
    ON instrument (year, instrument_title_key(display_title)) WHERE is_active AND duplicate_of IS NULL;

CREATE VIEW v_amendment_reference_current AS
WITH latest AS (
    SELECT DISTINCT ON (source_observation_id, expression_ordinal, footnote_block_id, entry_ordinal) *
      FROM amendment_reference
     ORDER BY source_observation_id, expression_ordinal, footnote_block_id, entry_ordinal, recorded_at DESC, id DESC)
SELECT l.*,
       amended.id AS amended_instrument_id,
       target.provision_id AS target_provision_id,
       amending.id AS amending_instrument_id
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
       -- exactly one active canonical instrument matches by number, kind and year (same or federal jurisdiction) ...
       SELECT CASE WHEN count(*) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE l.cited_number IS NOT NULL AND l.cited_kind IS NOT NULL AND l.cited_year IS NOT NULL
          AND r.is_active AND r.duplicate_of IS NULL
          AND r.number = l.cited_number AND r.kind::text = l.cited_kind AND r.year = l.cited_year
          AND r.jurisdiction::text IN (amended.jurisdiction::text, 'fed')
          AND r.id <> amended.id) by_number ON true
  LEFT JOIN LATERAL (
       -- ... else exactly one by title key and year
       SELECT CASE WHEN count(DISTINCT r.id) = 1 THEN min(r.id::text)::uuid END AS id
         FROM instrument r
        WHERE by_number.id IS NULL AND l.cited_title IS NOT NULL AND l.cited_year IS NOT NULL
          AND r.is_active AND r.duplicate_of IS NULL AND r.year = l.cited_year
          AND (instrument_title_key(r.short_title) = instrument_title_key(l.cited_title)
               OR instrument_title_key(r.display_title) = instrument_title_key(l.cited_title))
          AND r.jurisdiction::text IN (amended.jurisdiction::text, 'fed')
          AND r.id <> amended.id) by_title ON true
  LEFT JOIN instrument amending ON amending.id = coalesce(by_number.id, by_title.id)
 WHERE l.assertion = 'recorded';

COMMENT ON TABLE amendment_reference IS
  'Append-only: one printed amendment footnote entry of one expression (verbatim), parsed into operation(s), the '
  'cited amending law and any w.e.f. date, with the body block carrying the same marker on the page. Resolved by '
  'v_amendment_reference_current. Records the docs/03b amends relation, not version history. Migration 0072.';

COMMIT;
