-- 0145  How a judgment treats a case it cites (DECISION-LOG D-160; docs/PRECEDENT-MODEL.md §2.1, §2 review rules).
--
-- case_treatment is DERIVED: rebuilt from the resolved case citations of released judgments
-- (judgment_case_reference, resolution 'resolved') by one builder (nizam.workers.case_treatments), reading the
-- court's own words in the citation's sentence (nizam.storage.treatment). Every row is a machine candidate.
-- case_treatment_review is EVIDENCE, append-only: a reviewer's decision on one reading, keyed by the evidence's
-- words, the case treated and the treatment (treatment.review_key), so it outlives every rebuild. The builder sets
-- each row's review_status from the latest review of its key. A negative treatment (overruled, per_incuriam,
-- disapproved) is shown only when lawyer_verified (§2; docs/06 §5.1).

BEGIN;

CREATE TABLE IF NOT EXISTS case_treatment (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  judgment_id      uuid NOT NULL,                 -- the treating judgment
  decided_on       date NOT NULL,
  paragraph_id     uuid NOT NULL,
  cite_start       integer NOT NULL,              -- the citation, as judgment_case_reference holds it
  cite_end         integer NOT NULL,
  sentence_start   integer NOT NULL,              -- the evidence: the sentence holding the citation
  sentence_end     integer NOT NULL,
  dst_case_key     text NOT NULL,                 -- the case treated
  dst_judgment_id  uuid,                          -- its one decision, when the case has one
  treatment        text NOT NULL CHECK (treatment IN ('applied', 'followed', 'approved', 'explained',
                                                      'distinguished', 'overruled', 'per_incuriam', 'disapproved')),
  method           text NOT NULL DEFAULT 'grammar' CHECK (method IN ('grammar', 'model', 'human')),
  review_key       char(64) NOT NULL,
  review_status    text NOT NULL DEFAULT 'machine_candidate'
                       CHECK (review_status IN ('machine_candidate', 'lawyer_verified', 'contested', 'rejected')),
  builder          text NOT NULL,
  CONSTRAINT ck_case_treatment_spans CHECK (sentence_start <= cite_start AND cite_end <= sentence_end),
  FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on)
);
CREATE INDEX IF NOT EXISTS ix_case_treatment_dst ON case_treatment (dst_case_key);
CREATE INDEX IF NOT EXISTS ix_case_treatment_judgment ON case_treatment (judgment_id);

CREATE TABLE IF NOT EXISTS case_treatment_review (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  review_key   char(64) NOT NULL,
  decision     text NOT NULL CHECK (decision IN ('lawyer_verified', 'contested', 'rejected')),
  reviewer     text NOT NULL,
  note         text,
  reviewed_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_case_treatment_review_key ON case_treatment_review (review_key, reviewed_at DESC);

CREATE OR REPLACE FUNCTION case_treatment_review_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'case_treatment_review is evidence: append a new review, never change or remove one';
END $$;
DROP TRIGGER IF EXISTS tr_case_treatment_review_append_only ON case_treatment_review;
CREATE TRIGGER tr_case_treatment_review_append_only BEFORE UPDATE OR DELETE ON case_treatment_review
  FOR EACH ROW EXECUTE FUNCTION case_treatment_review_append_only();

COMMENT ON TABLE case_treatment IS
  'A judgment''s treatment of a case it cites (D-160): derived by nizam.workers.case_treatments from the court''s '
  'own words in the citation''s sentence; machine candidates; negative ones shown only when lawyer_verified. A35.';
COMMENT ON TABLE case_treatment_review IS
  'Reviews of case treatments (D-160), append-only evidence keyed by treatment.review_key; the latest wins.';

COMMIT;
