-- 0119  Judgments: sources, extractions, judgment, opinion, paragraph, lineage, case types and the link tables
--       (DECISION-LOG D-117, D-118, D-119, D-123; docs/PRECEDENT-MODEL.md §2-§4).
--
-- Judgments keep a ladder of their own beside the statute ladder:
--   judgment_source -> judgment_document -> judgment_block -> judgment -> judgment_opinion -> judgment_paragraph
-- The statute tables (source_observation, blob, document, text_block) are not shared. Audits C1-C9 assert that
-- every landed observation's every block belongs to a provision of a law, which a judgment never is (D-123).
--
-- Evidence is append-only, as for statutes. A re-parse retires the earlier judgment revision (is_active,
-- retired_at) and appends a new one; nothing is updated in place except that retirement.
--
-- judgment and judgment_paragraph are partitioned by decided_on (docs/03 §7): a catch-all before 2010, then one
-- partition per year to 2027, created here ahead of time and never on demand. A decision date outside them fails the
-- insert loudly. A judgment with no printed decision date never reaches these tables (gate J1): its document is
-- recorded 'held' with the reason.

BEGIN;

-- --------------------------------------------------------------------------------------------- bytes and readings

CREATE TABLE judgment_source (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id    text NOT NULL,                       -- 'pk-scp-judgments'
    court_code   text NOT NULL REFERENCES court (code),
    archive      text NOT NULL,                       -- the archive file as received
    member       text NOT NULL,                       -- its path inside the archive
    source_url   text,                                -- the court portal URL, where the archive's manifest gives one
    url_status   text,                                -- the manifest's status for that URL
    sha256       char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_length  bigint NOT NULL CHECK (byte_length > 0),
    object_key   text NOT NULL,                       -- raw/judgments/<source_id>/<sha256>, never overwritten
    observed_at  timestamptz NOT NULL,                -- the archive member's own timestamp
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (archive, member, sha256)
);
CREATE INDEX ix_judgment_source_sha ON judgment_source (sha256);

-- One reading of one file's bytes. Every file read gets a row whatever came of it, so nothing is silently lost (C7).
CREATE TABLE judgment_document (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sha256                char(64) NOT NULL,
    court_code            text NOT NULL REFERENCES court (code),
    extractor             text NOT NULL,
    parser                text NOT NULL,                -- 'nizam.judgment/1'
    lane                  text NOT NULL CHECK (lane IN ('E2', 'E4')),
    language              text NOT NULL CHECK (language IN ('en', 'ur', 'mixed')),
    page_count            integer NOT NULL CHECK (page_count > 0),
    char_count            integer NOT NULL CHECK (char_count >= 0),
    outcome               text NOT NULL CHECK (outcome IN ('parsed', 'held', 'needs_ocr', 'reporter_reprint',
                                                           'duplicate', 'not_a_judgment')),
    hold_reason           text,
    duplicate_of_document bigint REFERENCES judgment_document (id),
    body_sha256           char(64),                     -- of the folded body text, for J6
    detail                jsonb NOT NULL DEFAULT '{}',
    is_active             boolean NOT NULL DEFAULT true,
    retired_at            timestamptz,
    supersedes_id         bigint REFERENCES judgment_document (id),
    read_at               timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_judgment_document_reason CHECK ((outcome = 'parsed') = (hold_reason IS NULL)),
    CONSTRAINT ck_judgment_document_duplicate CHECK ((outcome = 'duplicate') = (duplicate_of_document IS NOT NULL)),
    CONSTRAINT ck_judgment_document_active CHECK (is_active = (retired_at IS NULL))
);
CREATE UNIQUE INDEX ux_judgment_document_active ON judgment_document (sha256) WHERE is_active;

CREATE TABLE judgment_block (
    document_id   bigint NOT NULL REFERENCES judgment_document (id),
    reading_order integer NOT NULL CHECK (reading_order >= 0),
    page_no       integer NOT NULL CHECK (page_no >= 1),
    x0 real, y0 real, x1 real, y1 real,
    text          text NOT NULL,
    PRIMARY KEY (document_id, reading_order)
);

-- ------------------------------------------------------------------------------------------------- case types

-- The printed name of a case type, per court, as observed in that court's judgments.
CREATE TABLE case_type (
    code          text PRIMARY KEY,                     -- 'SC:CP'
    court_code    text NOT NULL REFERENCES court (code),
    name          text NOT NULL,                        -- 'Civil Petition'
    kind          text NOT NULL CHECK (kind IN ('leave_petition', 'appeal', 'jail_petition', 'original_petition',
                                                'suo_motu', 'human_rights_case', 'review', 'misc_application',
                                                'intra_court_appeal', 'reference', 'shariat_appeal', 'contempt',
                                                'bail', 'writ', 'revision', 'suit', 'other')),
    area          text NOT NULL CHECK (area IN ('civil', 'criminal', 'constitutional', 'shariat', 'mixed')),
    printed_forms text[] NOT NULL,                      -- lowercase, punctuation folded to single spaces
    recorded_by   text NOT NULL,
    recorded_at   timestamptz NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------------------------- the judgment

CREATE TABLE judgment (
    id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    decided_on           date NOT NULL,
    document_id          bigint NOT NULL REFERENCES judgment_document (id),
    court_code           text NOT NULL REFERENCES court (code),
    seat                 text,
    decided_on_basis     text NOT NULL CHECK (decided_on_basis IN ('announced', 'signed_at', 'date_of_decision',
                                                                   'date_of_order')),
    decided_on_printed   text NOT NULL,                 -- the words the date was read from
    hearing_on           date,
    jurisdiction_printed text,                          -- '(Appellate Jurisdiction)'
    case_no_printed      text NOT NULL,
    case_type_code       text REFERENCES case_type (code),
    case_number          text,
    case_year            smallint CHECK (case_year BETWEEN 1947 AND 2100),
    bench_printed        text[] NOT NULL DEFAULT '{}',  -- judges as printed under PRESENT
    bench_size           smallint CHECK (bench_size > 0),
    reported_flag        boolean,                       -- 'Approved for reporting' / 'Not approved for reporting'
    disposition          text CHECK (disposition IN ('allowed', 'dismissed', 'partly_allowed', 'remanded',
                                                     'disposed', 'leave_granted', 'leave_refused', 'adjourned')),
    disposition_printed  text,
    neutral_citation     text,                          -- only when the judgment prints one
    parties_raw          text,                          -- internal: never a search key, never displayed (D-122)
    parties_display      text,                          -- NULL until the sensitive-category rules exist (D-122)
    publish_scope        text NOT NULL DEFAULT 'judgments' CHECK (publish_scope = 'judgments'),
    parser               text NOT NULL,
    is_active            boolean NOT NULL DEFAULT true,
    retired_at           timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, decided_on),
    CONSTRAINT ck_judgment_active CHECK (is_active = (retired_at IS NULL)),
    CONSTRAINT ck_judgment_hearing CHECK (hearing_on IS NULL OR hearing_on <= decided_on)
) PARTITION BY RANGE (decided_on);

CREATE TABLE judgment_opinion (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    judgment_id      uuid NOT NULL,
    decided_on       date NOT NULL,
    ordinal          smallint NOT NULL CHECK (ordinal >= 0),
    -- only judgment_of_court, majority, order_of_court, short_order and detailed_reasons can carry a holding;
    -- 'unclassified' is an opinion found beside another and not yet read for its kind
    kind             text NOT NULL CHECK (kind IN ('judgment_of_court', 'order_of_court', 'majority', 'concurring',
                                                   'dissenting', 'short_order', 'detailed_reasons', 'separate_note',
                                                   'unclassified')),
    heading_printed  text,                              -- 'JUDGMENT', 'ORDER', 'SHORT ORDER', 'DISSENTING NOTE'
    author_printed   text,                              -- 'Qazi Muhammad Amin Ahmed, J.'
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on),
    UNIQUE (judgment_id, ordinal)
);

CREATE TABLE judgment_paragraph (
    id           uuid NOT NULL DEFAULT gen_random_uuid(),
    decided_on   date NOT NULL,
    judgment_id  uuid NOT NULL,
    opinion_id   uuid REFERENCES judgment_opinion (id),
    ordinal      integer NOT NULL CHECK (ordinal >= 0),  -- internal order; never shown or cited
    -- header: court, bench, case, parties, counsel; body: the court's text; footnote: a page footnote;
    -- closing: signatures, place and date; furniture: running heads and page numbers
    kind         text NOT NULL CHECK (kind IN ('header', 'body', 'footnote', 'closing', 'furniture')),
    printed_no   text,                                  -- the number the judgment prints, else NULL (INV-1)
    role         text CHECK (role IN ('facts', 'arguments', 'reasoning', 'holding', 'order')),
    page_first   integer NOT NULL,
    page_last    integer NOT NULL,
    first_block  integer NOT NULL,                      -- judgment_block.reading_order
    last_block   integer NOT NULL,
    text         text NOT NULL,
    PRIMARY KEY (id, decided_on),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on),
    CONSTRAINT ck_paragraph_pages CHECK (page_first <= page_last AND first_block <= last_block),
    CONSTRAINT ck_paragraph_body_opinion CHECK ((kind = 'body') = (opinion_id IS NOT NULL))
) PARTITION BY RANGE (decided_on);

DO $$
DECLARE y integer;
BEGIN
    EXECUTE 'CREATE TABLE judgment_p_pre2010 PARTITION OF judgment FOR VALUES FROM (MINVALUE) TO (''2010-01-01'')';
    EXECUTE 'CREATE TABLE judgment_paragraph_p_pre2010 PARTITION OF judgment_paragraph '
            'FOR VALUES FROM (MINVALUE) TO (''2010-01-01'')';
    FOR y IN 2010..2027 LOOP
        EXECUTE format('CREATE TABLE judgment_p%s PARTITION OF judgment FOR VALUES FROM (%L) TO (%L)',
                       y, make_date(y, 1, 1), make_date(y + 1, 1, 1));
        EXECUTE format('CREATE TABLE judgment_paragraph_p%s PARTITION OF judgment_paragraph '
                       'FOR VALUES FROM (%L) TO (%L)', y, make_date(y, 1, 1), make_date(y + 1, 1, 1));
    END LOOP;
END $$;

CREATE UNIQUE INDEX ux_judgment_active_document ON judgment (document_id, decided_on) WHERE is_active;
CREATE INDEX ix_judgment_court_case ON judgment (court_code, case_type_code, case_number, case_year);
CREATE INDEX ix_judgment_paragraph_judgment ON judgment_paragraph (judgment_id, ordinal);

-- ------------------------------------------------------------------------------------------ history and links

-- The same case up the hierarchy (D-117: appeal outcomes are lineage, not treatment).
CREATE TABLE judgment_lineage (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    upper_judgment_id    uuid NOT NULL,
    upper_decided_on     date NOT NULL,
    relation             text NOT NULL CHECK (relation IN ('appeal', 'leave_petition', 'revision', 'review',
                                                           'intra_court_appeal', 'remand', 'reasons_for')),
    lower_court_code     text REFERENCES court (code),  -- NULL when the printed court is not in the registry
    lower_court_printed  text NOT NULL,
    lower_case_printed   text,
    lower_decided_on     date,
    lower_judgment_id    uuid,                          -- set when the lower judgment is held
    outcome              text CHECK (outcome IN ('affirmed', 'reversed', 'modified', 'set_aside', 'remanded',
                                                 'leave_refused', 'dismissed', 'withdrawn')),
    source_paragraph_id  uuid NOT NULL,
    method               text NOT NULL CHECK (method IN ('grammar', 'model', 'human')),
    review_status        text NOT NULL DEFAULT 'machine_candidate'
                             CHECK (review_status IN ('machine_candidate', 'lawyer_verified', 'contested', 'rejected')),
    parser               text NOT NULL,
    FOREIGN KEY (upper_judgment_id, upper_decided_on) REFERENCES judgment (id, decided_on)
);

-- Judgment -> provision (D-119). Derived: rebuilt from the active judgments by one named linker, like
-- provision_reference (D-108). The version is the one in force on the decision date in the court's territory.
CREATE TABLE judgment_statute_reference (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    paragraph_id       uuid NOT NULL,
    decided_on         date NOT NULL,
    judgment_id        uuid NOT NULL,
    char_start         integer NOT NULL,
    char_end           integer NOT NULL,
    raw                text NOT NULL,                   -- as printed
    label              text NOT NULL,
    subs               text[] NOT NULL DEFAULT '{}',
    law_printed        text,
    alias              text,
    dst_instrument_id  uuid,
    dst_provision_id   uuid,
    dst_version_id     uuid,
    version_basis      text CHECK (version_basis IN ('dated', 'not_dated')),
    resolution         text NOT NULL CHECK (resolution IN ('resolved', 'ambiguous', 'law_not_held', 'unit_not_found',
                                                           'no_law_named')),
    alternates         uuid[] NOT NULL DEFAULT '{}',
    role               text NOT NULL CHECK (role IN ('charge', 'quoted', 'challenged', 'interpreted', 'cited')),
    linker             text NOT NULL,
    FOREIGN KEY (paragraph_id, decided_on) REFERENCES judgment_paragraph (id, decided_on),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on),
    CONSTRAINT ck_jsr_span CHECK (0 <= char_start AND char_start < char_end),
    CONSTRAINT ck_jsr_resolved CHECK ((resolution = 'resolved') = (dst_provision_id IS NOT NULL))
);
CREATE INDEX ix_jsr_provision ON judgment_statute_reference (dst_provision_id) WHERE dst_provision_id IS NOT NULL;
CREATE INDEX ix_jsr_instrument ON judgment_statute_reference (dst_instrument_id) WHERE dst_instrument_id IS NOT NULL;
CREATE INDEX ix_jsr_judgment ON judgment_statute_reference (judgment_id);

-- Judgment -> judgment: a printed case citation (reporter reference or case number), resolved when held.
CREATE TABLE judgment_case_reference (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    paragraph_id       uuid NOT NULL,
    decided_on         date NOT NULL,
    judgment_id        uuid NOT NULL,
    char_start         integer NOT NULL,
    char_end           integer NOT NULL,
    raw                text NOT NULL,
    reporter_series    text,                            -- 'PLD', 'SCMR' (an identifier, never reporter prose)
    reporter_year      smallint,
    reporter_court     text,
    reporter_page      integer,
    case_printed       text,
    dst_judgment_id    uuid,
    resolution         text NOT NULL CHECK (resolution IN ('resolved', 'not_held', 'ambiguous')),
    linker             text NOT NULL,
    FOREIGN KEY (paragraph_id, decided_on) REFERENCES judgment_paragraph (id, decided_on),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on),
    CONSTRAINT ck_jcr_span CHECK (0 <= char_start AND char_start < char_end),
    CONSTRAINT ck_jcr_resolved CHECK ((resolution = 'resolved') = (dst_judgment_id IS NOT NULL))
);
CREATE INDEX ix_jcr_dst ON judgment_case_reference (dst_judgment_id) WHERE dst_judgment_id IS NOT NULL;
CREATE INDEX ix_jcr_reporter ON judgment_case_reference (reporter_series, reporter_year, reporter_page);

CREATE TABLE judgment_link_state (
    judgment_id uuid NOT NULL,
    decided_on  date NOT NULL,
    linker      text NOT NULL,
    linked_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (judgment_id, decided_on),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on)
);

-- ---------------------------------------------------------------------------------------------- release views

CREATE VIEW v_release_judgment AS
SELECT j.* FROM judgment j JOIN judgment_document d ON d.id = j.document_id
 WHERE j.is_active AND d.is_active AND d.outcome = 'parsed';

CREATE VIEW v_release_judgment_paragraph AS
SELECT p.* FROM judgment_paragraph p JOIN v_release_judgment j ON j.id = p.judgment_id AND j.decided_on = p.decided_on;

-- What is held, per court and year of decision, and what is not (D-122). Shown with every precedent answer.
CREATE VIEW v_judgment_coverage AS
SELECT d.court_code,
       extract(year FROM j.decided_on)::int AS year,
       count(*) FILTER (WHERE j.id IS NOT NULL)            AS judgments_released,
       min(j.decided_on) AS first_decided, max(j.decided_on) AS last_decided
  FROM judgment_document d
  LEFT JOIN judgment j ON j.document_id = d.id AND j.is_active
 WHERE d.is_active AND d.outcome = 'parsed'
 GROUP BY 1, 2;

CREATE VIEW v_judgment_document_outcome AS
SELECT court_code, outcome, coalesce(split_part(hold_reason, ':', 1), '') AS reason, count(*) AS documents
  FROM judgment_document WHERE is_active GROUP BY 1, 2, 3;

-- Release views read only: rows are written by the judgment worker in one transaction per document.
CREATE FUNCTION judgment_evidence_no_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '%: judgment evidence is append-only; retire the revision instead', TG_TABLE_NAME;
END $$;
CREATE TRIGGER judgment_source_no_delete BEFORE DELETE ON judgment_source
    FOR EACH ROW EXECUTE FUNCTION judgment_evidence_no_delete();
CREATE TRIGGER judgment_document_no_delete BEFORE DELETE ON judgment_document
    FOR EACH ROW EXECUTE FUNCTION judgment_evidence_no_delete();

-- ----------------------------------------------------------------------------------------- SC case types (seen)

-- Seeded from the Supreme Court archive's own headers and filenames (22 Nov 2026 inventory). Forms are lowercase
-- with punctuation folded to spaces; the parser folds a header the same way and takes the longest form that matches.
INSERT INTO case_type (code, court_code, name, kind, area, printed_forms, recorded_by) VALUES
 ('SC:CP',     'SC', 'Civil Petition', 'leave_petition', 'civil',
  '{"civil petition for leave to appeal","civil petitions for leave to appeal","civil petition","civil petitions","c p l a","cpla","c p","c ps","cp","cps"}', 'migration 0119'),
 ('SC:CA',     'SC', 'Civil Appeal', 'appeal', 'civil',
  '{"civil appeal","civil appeals","c a","c as","ca","cas"}', 'migration 0119'),
 ('SC:CRLP',   'SC', 'Criminal Petition', 'leave_petition', 'criminal',
  '{"criminal petition for leave to appeal","criminal petitions for leave to appeal","criminal petition","criminal petitions","crl p","cr p","crl ps"}', 'migration 0119'),
 ('SC:CRLA',   'SC', 'Criminal Appeal', 'appeal', 'criminal',
  '{"criminal appeal","criminal appeals","crl a","cr a","crl as"}', 'migration 0119'),
 ('SC:JP',     'SC', 'Jail Petition', 'jail_petition', 'criminal',
  '{"jail petition","jail petitions","j p"}', 'migration 0119'),
 ('SC:CONSTP', 'SC', 'Constitution Petition', 'original_petition', 'constitutional',
  '{"constitution petition","constitution petitions","constitutional petition","constitutional petitions","const p","const ps","const petition","constp"}', 'migration 0119'),
 ('SC:CMA',    'SC', 'Civil Miscellaneous Application', 'misc_application', 'civil',
  '{"civil miscellaneous application","civil misc application","civil misc applications","civil miscellaneous applications","c m a","cma","c m as"}', 'migration 0119'),
 ('SC:CRLMA',  'SC', 'Criminal Miscellaneous Application', 'misc_application', 'criminal',
  '{"criminal miscellaneous application","criminal misc application","crl m a","crl misc a","crl misc app"}', 'migration 0119'),
 ('SC:CRP',    'SC', 'Civil Review Petition', 'review', 'civil',
  '{"civil review petition","civil review petitions","c r p","crp"}', 'migration 0119'),
 ('SC:CRLRP',  'SC', 'Criminal Review Petition', 'review', 'criminal',
  '{"criminal review petition","criminal review petitions","crl r p"}', 'migration 0119'),
 ('SC:SMC',    'SC', 'Suo Motu Case', 'suo_motu', 'constitutional',
  '{"suo motu case","suo moto case","suo motu","suo moto","s m c","smc"}', 'migration 0119'),
 ('SC:HRC',    'SC', 'Human Rights Case', 'human_rights_case', 'constitutional',
  '{"human rights case","human right case","h r c","hrc"}', 'migration 0119'),
 ('SC:CRLOP',  'SC', 'Criminal Original Petition', 'contempt', 'criminal',
  '{"criminal original petition","criminal original petitions","crl o p"}', 'migration 0119'),
 ('SC:ICA',    'SC', 'Intra Court Appeal', 'intra_court_appeal', 'mixed',
  '{"intra court appeal","intra court appeals","i c a","ica","crl i c a"}', 'migration 0119'),
 ('SC:REF',    'SC', 'Reference', 'reference', 'constitutional',
  '{"reference","references","ref"}', 'migration 0119'),
 ('SC:CRLSHA', 'SC', 'Criminal Shariat Appeal', 'shariat_appeal', 'shariat',
  '{"criminal shariat appeal","criminal shariat appeals","crl sh a"}', 'migration 0119'),
 ('SC:CSHA',   'SC', 'Civil Shariat Appeal', 'shariat_appeal', 'shariat',
  '{"civil shariat appeal","civil shariat appeals","c sh a"}', 'migration 0119'),
 ('SC:CMAPP',  'SC', 'Civil Miscellaneous Appeal', 'appeal', 'civil',
  '{"civil miscellaneous appeal","civil misc appeal","c m appeal","c m app"}', 'migration 0119'),
 ('SC:CRLMAPP','SC', 'Criminal Miscellaneous Appeal', 'appeal', 'criminal',
  '{"criminal miscellaneous appeal","criminal misc appeal","crl m appeal"}', 'migration 0119');

-- Names under which the SC's headers print the courts below it ("passed by the High Court of Sindh Karachi").
INSERT INTO court_alias (court_code, alias_printed, alias_key, method, evidence, recorded_by) VALUES
 ('SHC', 'Sindh High Court', 'sindh high court', 'observed', '{"archive": "scp_judgments.zip"}', 'migration 0119'),
 ('BHC', 'Balochistan High Court', 'balochistan high court', 'observed', '{"archive": "scp_judgments.zip"}',
  'migration 0119');

COMMIT;
