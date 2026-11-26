-- 0139  The law-report index: a reporter citation the court itself publishes for its judgment ('2026 SCMR 715',
--       'PLD 2016 SC 1') -> the held judgment and its case (DECISION-LOG D-150; docs/PRECEDENT-MODEL.md §4).
--
-- Judgments cite each other mostly by law-report citation: on 26 Nov 2026, 174,657 case citations were 'not_held',
-- 80,602 of them SCMR and about 38,700 PLD SC. No reporter index was held (D-119). The Supreme Court's own judgment
-- search lists, for 2,838 of its judgments, the citation under which the judgment was reported, and its own
-- citation ('SCP') for 3,815 (D-148). That is the court's record, read as an identifier only: no headnote or other
-- reporter text is ever stored (D-120).
--
-- Derived from the release, as the link tables are (D-108, D-119): a row names a released judgment, the table is
-- rebuilt by one builder (nizam.workers.reporter_index) from the listings and the release, and audit A32 asserts it.
-- The key is the citation as judgment_linking.case_citations reads it, with the court folded ('SC', 'S.C',
-- 'Supreme Court' -> 'SC'): the same grammar on both sides, so a citing judgment and the listing agree by
-- construction.

BEGIN;

CREATE TABLE reporter_citation (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    series        text    NOT NULL,                 -- 'SCMR', 'PLD', 'PLJ', 'PLC(CS)' (case_citations' series)
    year          integer NOT NULL CHECK (year BETWEEN 1947 AND 2100),
    court         text    NOT NULL DEFAULT '',      -- folded court of the citation ('SC'); '' when it prints none
    page          integer NOT NULL CHECK (page > 0),
    printed       text    NOT NULL,                 -- the citation as the court's listing prints it
    judgment_id   uuid    NOT NULL,
    decided_on    date    NOT NULL,
    case_key      text,                             -- the judgment's case (judgment_case), when recorded
    source        text    NOT NULL,                 -- 'scp-search' | 'scp-latest'
    source_ref    text    NOT NULL,                 -- the listed file name
    builder       text    NOT NULL,
    CONSTRAINT uq_reporter_citation UNIQUE (series, year, court, page, judgment_id)
);
CREATE INDEX ix_reporter_citation_key ON reporter_citation (series, year, court, page);
COMMENT ON TABLE reporter_citation IS
    'D-150: a reporter citation the court publishes for its own judgment -> the released judgment. An identifier only '
    '(D-120). Derived from the court listings and the release by nizam.workers.reporter_index; audit A32.';

COMMIT;
