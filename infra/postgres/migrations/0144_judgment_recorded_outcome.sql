-- 0144  What a court above did with a judgment, as the court below's own records state it (DECISION-LOG D-159).
--
-- The Islamabad High Court's judgment listing (mis.ihc.gov.pk, D-156) records, for some of its judgments, what the
-- Supreme Court later did with them: O_SC_STATUS ('Upheld', 'Set Aside', 'Remanded Back') and O_SC_DDATE. That is
-- an official record, kept here as the court's own words with its source, beside the appeal chains read from the
-- upper judgments' text (0143). It is a second source of a judgment's later history, never merged into the first:
-- a reader sees which says what. Derived: rebuilt from the landed archive's listing by nizam.workers.recorded_outcomes.

BEGIN;

CREATE TABLE IF NOT EXISTS judgment_recorded_outcome (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  judgment_id       uuid NOT NULL,
  decided_on        date NOT NULL,
  source_id         text NOT NULL,                  -- the landed source whose listing records it
  listing_ref       text NOT NULL,                  -- the record's own id in that listing (O_ID)
  upper_court_code  text NOT NULL REFERENCES court (code),
  outcome           text NOT NULL CHECK (outcome IN ('affirmed', 'set_aside', 'remanded')),
  outcome_printed   text NOT NULL,                  -- as the listing prints it
  upper_decided_on  date,
  upper_file_url    text,                           -- the upper court's judgment as the listing links it
  builder           text NOT NULL,
  UNIQUE (judgment_id, source_id, listing_ref),
  FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on)
);

COMMENT ON TABLE judgment_recorded_outcome IS
  'A judgment''s later history as the court below records it in its own listing (D-159): the court above, its '
  'outcome as printed and its date. Read beside judgment_lineage_link, labelled by source; audit A34.';

COMMIT;
