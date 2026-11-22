-- 0122: a judgment that prints no usable decision date is released marked undated (D-124).
--
-- Gate J1 held 327 Supreme Court judgments: 296 print no decision date (no 'Announced ... on', no place and date, no
-- 'Date of decision'), and 31 print dates that contradict each other (two signed dates, or a hearing after the date
-- read). The owner ruled on 23 Nov 2026 that they are released marked undated. A date is still never guessed from
-- the hearing, the upload or a folder name (D-118).
--
-- decided_on stays the partition key and the research-date filter, so it cannot be NULL. For an undated judgment it
-- holds the latest day the judgment can have been decided: the day the court's archive was first observed holding
-- the file (judgment_source.observed_at). A research date before it therefore never returns the judgment, which is
-- the conservative reading of INV-5 for case law. That day is never shown as the decision date:
-- v_release_judgment.decision_date is NULL for an undated judgment, and readers render from decision_date.
--
-- decided_not_before is the earliest day it can have been decided, from what the judgment itself prints: the
-- printed date of hearing, else 1 January of the case year. It is NULL when neither is printed or the hearing date is
-- the one in conflict.

ALTER TABLE judgment ADD COLUMN undated_reason text;
ALTER TABLE judgment ADD COLUMN decided_not_before date;
ALTER TABLE judgment ADD COLUMN decided_not_before_basis text
    CHECK (decided_not_before_basis IN ('hearing', 'case_year'));

ALTER TABLE judgment ALTER COLUMN decided_on_printed DROP NOT NULL;
ALTER TABLE judgment DROP CONSTRAINT judgment_decided_on_basis_check;
ALTER TABLE judgment ADD CONSTRAINT judgment_decided_on_basis_check
    CHECK (decided_on_basis IN ('announced', 'signed_at', 'date_of_decision', 'date_of_order', 'undated'));
ALTER TABLE judgment ADD CONSTRAINT ck_judgment_undated CHECK (
    (decided_on_basis = 'undated') = (undated_reason IS NOT NULL)
    AND (decided_on_basis = 'undated') = (decided_on_printed IS NULL));
ALTER TABLE judgment ADD CONSTRAINT ck_judgment_not_before CHECK (
    (decided_not_before IS NULL) = (decided_not_before_basis IS NULL)
    AND (decided_not_before IS NULL OR (decided_on_basis = 'undated' AND decided_not_before <= decided_on)));

-- j.* now ends with the three new columns; decision_date is appended after them.
CREATE OR REPLACE VIEW v_release_judgment AS
SELECT j.*, CASE WHEN j.decided_on_basis = 'undated' THEN NULL ELSE j.decided_on END AS decision_date
  FROM judgment j JOIN judgment_document d ON d.id = j.document_id
 WHERE j.is_active AND d.is_active AND d.outcome = 'parsed';

-- Coverage by year of decision counts dated judgments only; undated ones are one row with year NULL.
DROP VIEW v_judgment_coverage;
CREATE VIEW v_judgment_coverage AS
SELECT d.court_code,
       CASE WHEN j.decided_on_basis = 'undated' THEN NULL ELSE extract(year FROM j.decided_on)::int END AS year,
       count(*) FILTER (WHERE j.id IS NOT NULL)            AS judgments_released,
       min(j.decided_on) FILTER (WHERE j.decided_on_basis <> 'undated') AS first_decided,
       max(j.decided_on) FILTER (WHERE j.decided_on_basis <> 'undated') AS last_decided
  FROM judgment_document d
  LEFT JOIN judgment j ON j.document_id = d.id AND j.is_active
 WHERE d.is_active AND d.outcome = 'parsed'
 GROUP BY 1, 2;
