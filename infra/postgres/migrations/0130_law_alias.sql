-- 0130  Reviewed law aliases: a law's printed name that its recorded title does not carry (DECISION-LOG D-134).
--
-- Judgments cite laws by practitioner abbreviations ('NAB Ordinance', 'ITO, 2001', 'PEEDA Act'), older names
-- ('NWFP Pre-emption Act') and other spellings ('Qanoon-e-Shahadat'), which the title search cannot join. An alias is
-- added only from evidence a person read (PRECEDENT-MODEL §4.1): a row of the review sheet with the decision
-- 'alias', the law it names (by source document, stable across replays), and the judgment paragraphs read. The
-- citation resolver (nizam.storage.citations, shared by L3 and the judgment linker) reads the active rows. A row is
-- never edited or deleted: it is withdrawn with a reason, and a corrected row added. A30 audits the table.

BEGIN;
CREATE TABLE law_alias (
    id               bigserial PRIMARY KEY,
    alias_key        text NOT NULL CHECK (alias_key <> '' AND alias_key = lower(alias_key)),
    printed_forms    text[] NOT NULL CHECK (cardinality(printed_forms) > 0),
    document_id      bigint NOT NULL,                   -- the law named: its source document
    title_words      text NOT NULL,                     -- its recorded title, as the resolver searches it
    jurisdiction     text NOT NULL,
    basis            text NOT NULL CHECK (basis IN ('abbreviation', 'spelling', 'former_name', 'short_name')),
    evidence         jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'array' AND jsonb_array_length(evidence) > 0),
    citations_seen   integer NOT NULL,                  -- at review, reported
    judgments_seen   integer NOT NULL,
    review_sheet     text NOT NULL,
    reviewed_by      text NOT NULL,
    reviewed_on      date NOT NULL,
    note             text,
    recorded_at      timestamptz NOT NULL DEFAULT now(),
    withdrawn_at     timestamptz,
    withdrawn_reason text,
    CHECK ((withdrawn_at IS NULL) = (withdrawn_reason IS NULL))
);
-- one law per printed name: an alias that could mean two laws is not an alias
CREATE UNIQUE INDEX ux_law_alias_active ON law_alias (alias_key) WHERE withdrawn_at IS NULL;
COMMENT ON TABLE law_alias IS 'Reviewed printed names of laws that their titles do not carry (D-134); read by '
                               'nizam.storage.citations.resolve; withdrawn, never deleted';
COMMIT;
