-- 0123  One record per case: the case a judgment decides, the cases it decides together, and how the judgments of
--       one case relate -- a judgment giving the reasons for a short order, and a second copy of one decision
--       (DECISION-LOG D-125; docs/PRECEDENT-MODEL.md §3.3 as built).
--
-- judgment stays one row per file read (D-118, §3.3 as built): a short order and its detailed reasons are two
-- judgments, each with its own date. What joins them is the case. These tables are derived, rebuilt from the
-- released judgments by one named builder (nizam.judgment_cases/1), as the link tables are (D-108, D-119); A28
-- asserts they are exactly the release.
--
-- A case is keyed by the case as printed: '<court>/<type>/<number>/<year>' ('SC/CA/1507/2024'). The key is built
-- from printed words, never from a row id, so a rebuild never changes it and a stored reference to a case never
-- breaks (the INV-4 rule, read for cases).

BEGIN;

CREATE TABLE judicial_case (
    case_key        text PRIMARY KEY,
    court_code      text NOT NULL REFERENCES court (code),
    case_type_code  text NOT NULL REFERENCES case_type (code),
    case_number     text NOT NULL CHECK (case_number ~ '^[1-9][0-9]{0,5}(-[A-Z])?$'),   -- no leading zero
    case_year       smallint NOT NULL CHECK (case_year BETWEEN 1947 AND 2100),
    builder         text NOT NULL,
    UNIQUE (court_code, case_type_code, case_number, case_year),
    CONSTRAINT ck_case_key CHECK (case_key = court_code || '/' || split_part(case_type_code, ':', 2) || '/'
                                             || case_number || '/' || case_year),
    CONSTRAINT ck_case_type_court CHECK (split_part(case_type_code, ':', 1) = court_code)
);

-- Which cases a judgment decides: its lead case (the first printed), and the cases of the same type and year
-- printed beside it ('Civil Appeals No. 1507 and 1508 of 2024').
CREATE TABLE judgment_case (
    judgment_id  uuid NOT NULL,
    decided_on   date NOT NULL,
    case_key     text NOT NULL REFERENCES judicial_case (case_key),
    role         text NOT NULL CHECK (role IN ('lead', 'joined')),
    builder      text NOT NULL,
    PRIMARY KEY (judgment_id, decided_on, case_key),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on)
);
CREATE UNIQUE INDEX ux_judgment_case_lead ON judgment_case (judgment_id, decided_on) WHERE role = 'lead';
CREATE INDEX ix_judgment_case_key ON judgment_case (case_key);

-- One row per released judgment the builder read, whatever came of it, so a judgment never silently has no case
-- (C7). 'no_number_read': the case line prints no number ('No. Nil'); 'no_year_read': no year closes the number.
-- header_differs: the header parser's case number or year (judgment.case_number, case_year) is not what this
-- grammar reads; the case line is the record, and the difference is reported (A28).
CREATE TABLE judgment_case_state (
    judgment_id     uuid NOT NULL,
    decided_on      date NOT NULL,
    builder         text NOT NULL,
    outcome         text NOT NULL CHECK (outcome IN ('grouped', 'no_number_read', 'no_year_read')),
    case_line_read  text NOT NULL,
    header_differs  boolean NOT NULL DEFAULT false,
    built_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (judgment_id, decided_on),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on)
);

-- How a judgment relates to another judgment of its case.
--   reasons_for: the judgment says it gives the reasons for the court's short order ('The above are the reasons for
--     our short order dated 22.4.2024'). short_order_on is the date printed for that order (date_basis: printed;
--     even_date, the judgment's own date; paragraph, a date printed for the short order earlier in the paragraph;
--     not_printed). The short order is other_judgment when this case holds exactly one judgment decided that day.
--   copy_of: a second file of one decision (bodies at COPY_MIN word 5-gram overlap, same case, same date when
--     both are dated). other_judgment is the copy kept; a copy is not shown beside it.
CREATE TABLE judgment_relation (
    judgment_id        uuid NOT NULL,
    decided_on         date NOT NULL,
    relation           text NOT NULL CHECK (relation IN ('reasons_for', 'copy_of')),
    case_key           text NOT NULL REFERENCES judicial_case (case_key),
    other_judgment_id  uuid,
    other_decided_on   date,
    short_order_on     date,
    date_basis         text CHECK (date_basis IN ('printed', 'even_date', 'paragraph', 'not_printed')),
    printed            text NOT NULL,
    score              real CHECK (score BETWEEN 0 AND 1),
    builder            text NOT NULL,
    PRIMARY KEY (judgment_id, decided_on, relation),
    FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on),
    FOREIGN KEY (other_judgment_id, other_decided_on) REFERENCES judgment (id, decided_on),
    CONSTRAINT ck_relation_other CHECK ((other_judgment_id IS NULL) = (other_decided_on IS NULL)
                                        AND other_judgment_id IS DISTINCT FROM judgment_id),
    CONSTRAINT ck_relation_copy CHECK (relation <> 'copy_of'
                                       OR (other_judgment_id IS NOT NULL AND score IS NOT NULL
                                           AND short_order_on IS NULL AND date_basis IS NULL)),
    CONSTRAINT ck_relation_reasons CHECK (relation <> 'reasons_for'
                                          OR (date_basis IS NOT NULL AND score IS NULL
                                              AND (short_order_on IS NULL) = (date_basis = 'not_printed')
                                              AND (other_judgment_id IS NULL OR other_decided_on = short_order_on)))
);
CREATE INDEX ix_judgment_relation_other ON judgment_relation (other_judgment_id) WHERE other_judgment_id IS NOT NULL;

-- A case citation resolves to the case (D-125): 'Civil Appeal No. 984 of 2018' is resolved when the case is held,
-- however many judgments it has. dst_judgment_id is set only when the case holds one decision (copies aside).
ALTER TABLE judgment_case_reference ADD COLUMN dst_case_key text;
ALTER TABLE judgment_case_reference DROP CONSTRAINT judgment_case_reference_resolution_check;
ALTER TABLE judgment_case_reference ADD CONSTRAINT judgment_case_reference_resolution_check
    CHECK (resolution IN ('resolved', 'not_held', 'ambiguous', 'own_case'));
ALTER TABLE judgment_case_reference DROP CONSTRAINT ck_jcr_resolved;
-- 'resolved' names a judgment or a case; 'own_case' is the judgment citing a case it decides; a /1 row
-- ('ambiguous', several judgments matched) keeps its meaning until the linker is rebuilt
ALTER TABLE judgment_case_reference ADD CONSTRAINT ck_jcr_resolved
    CHECK (CASE resolution
             WHEN 'resolved' THEN dst_judgment_id IS NOT NULL OR dst_case_key IS NOT NULL
             WHEN 'own_case' THEN dst_case_key IS NOT NULL AND dst_judgment_id IS NULL
             ELSE dst_judgment_id IS NULL AND dst_case_key IS NULL END);
CREATE INDEX ix_jcr_case ON judgment_case_reference (dst_case_key) WHERE dst_case_key IS NOT NULL;

-- The decisions shown: released judgments that are not a second copy of another (D-125). Readers list judgments
-- from here; v_release_judgment still holds every released reading (A25).
CREATE VIEW v_shown_judgment AS
SELECT j.* FROM v_release_judgment j
 WHERE NOT EXISTS (SELECT 1 FROM judgment_relation r
                    WHERE r.judgment_id = j.id AND r.decided_on = j.decided_on AND r.relation = 'copy_of');

COMMIT;
