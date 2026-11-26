-- 0143  Appeal chains linked to the judgments below (DECISION-LOG D-159; docs/PRECEDENT-MODEL.md §3.5).
--
-- judgment_lineage (0119) is read by the parser from an upper judgment's own words ("against the judgment dated
-- 17.01.2017 passed by the Lahore High Court, Multan Bench in Cr.A. No.652-J of 2016"): the court below, its case
-- as printed, its date, and the outcome. Its lower_judgment_id was left for a later step. This table is that step,
-- DERIVED and rebuilt from the release by one builder (nizam.workers.lineage_links), like the other link tables
-- (D-108, D-119, D-125): a parser-written row is never updated in place.
--
-- resolution:
--   resolved            the case below is held and exactly one of its held decisions is of the date printed
--   case_held           the case below is held, but no single held decision is of that date (none printed, an
--                       undated copy, several decisions): the case key is kept, no judgment is chosen
--   case_not_held       the case key was read; the corpus holds no judgment of it
--   not_read            no case number and year could be read from the printed case line
--   court_not_recorded  the court below is not a recorded court (a tribunal, a district court)
-- basis says how the court below was known: printed (the parser's own reading) or sole_court_below (an apex court
-- of AJK or Gilgit-Baltistan says "the High Court": it has one court below, AJKHC or GBCC).

BEGIN;

CREATE TABLE IF NOT EXISTS judgment_lineage_link (
  lineage_id        bigint PRIMARY KEY REFERENCES judgment_lineage (id) ON DELETE CASCADE,
  upper_judgment_id uuid NOT NULL,
  upper_decided_on  date NOT NULL,
  lower_court_code  text REFERENCES court (code),
  lower_case_key    text,
  lower_judgment_id uuid,
  lower_decided_on  date,
  resolution        text NOT NULL CHECK (resolution IN ('resolved', 'case_held', 'case_not_held', 'not_read',
                                                         'court_not_recorded')),
  basis             text NOT NULL CHECK (basis IN ('printed', 'sole_court_below', 'none')),
  builder           text NOT NULL,
  CONSTRAINT ck_lineage_link_shape CHECK (
    (resolution = 'resolved') = (lower_judgment_id IS NOT NULL)
    AND (resolution IN ('resolved', 'case_held', 'case_not_held')) = (lower_case_key IS NOT NULL)),
  FOREIGN KEY (upper_judgment_id, upper_decided_on) REFERENCES judgment (id, decided_on)
);

CREATE INDEX IF NOT EXISTS ix_lineage_link_lower ON judgment_lineage_link (lower_judgment_id)
  WHERE lower_judgment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_lineage_link_lower_case ON judgment_lineage_link (lower_case_key)
  WHERE lower_case_key IS NOT NULL;

COMMENT ON TABLE judgment_lineage_link IS
  'Appeal chains linked (D-159): each released judgment_lineage row -> the court below, its case key and, where one '
  'held decision of that case is of the printed date, that judgment. Derived: rebuilt from the release by '
  'nizam.workers.lineage_links; audit A34. Read for a judgment''s later history (affirmed, set aside, remanded).';

COMMIT;
