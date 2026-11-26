-- 0146  Provisions a court strikes down or declares repugnant (DECISION-LOG D-161; docs/PRECEDENT-MODEL.md §4.3,
--       §2.2; docs/03b `invalidated_by`). Serving changes only through a lawyer's verified review.
--
--  * judicial_invalidation_candidate: DERIVED, rebuilt by nizam.workers.invalidation_candidates from the court's own
--    words ("is hereby declared repugnant to the Injunctions of Islam", "struck down", "ultra vires", "void") in a
--    sentence that holds a resolved statute citation (judgment_statute_reference). Machine candidates only.
--  * judicial_invalidation_review: EVIDENCE, append-only. A reviewer's decision on one candidate, keyed like the
--    treatment reviews (the sentence's words, the provision, the reading), with what the review establishes: the
--    provision, its extent ('whole' unit, or 'words' -- part of its text only), and the day it takes effect
--    (the decision's own day, or the day it names: Art. 203D(2)(b); an FSC decision waits while an appeal lies or is
--    pending, the 203D(2) proviso -- the reviewer's reading, never inferred here).
--  * mv_provision_invalidation: the serving snapshot of the LATEST review per key when it is lawyer_verified with
--    extent 'whole'. operative_provision stops serving such a unit, and everything under it, from its effective day,
--    as it does a repealed unit (0102). A 'words' extent does not remove the unit: the text still serves and the
--    status says what was read down (reader, not view). Until a review is verified, nothing served changes.
--  invalidation_coverage stays 'not_tracked': only the judgments held are read, and only verified rows serve.

BEGIN;

CREATE TABLE IF NOT EXISTS judicial_invalidation_candidate (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  judgment_id     uuid NOT NULL,
  decided_on      date NOT NULL,
  paragraph_id    uuid NOT NULL,
  sentence_start  integer NOT NULL,
  sentence_end    integer NOT NULL,
  provision_id    uuid NOT NULL,
  instrument_id   uuid NOT NULL,
  reading         text NOT NULL CHECK (reading IN ('declared_repugnant', 'struck_down')),
  review_key      char(64) NOT NULL,
  review_status   text NOT NULL DEFAULT 'machine_candidate'
                      CHECK (review_status IN ('machine_candidate', 'lawyer_verified', 'contested', 'rejected')),
  builder         text NOT NULL,
  FOREIGN KEY (judgment_id, decided_on) REFERENCES judgment (id, decided_on)
);
CREATE INDEX IF NOT EXISTS ix_invalidation_candidate_provision ON judicial_invalidation_candidate (provision_id);

CREATE TABLE IF NOT EXISTS judicial_invalidation_review (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  review_key    char(64) NOT NULL,
  decision      text NOT NULL CHECK (decision IN ('lawyer_verified', 'contested', 'rejected')),
  provision_id  uuid,                     -- as verified (it may correct the candidate's)
  extent        text CHECK (extent IN ('whole', 'words')),
  extent_note   text,                     -- the words read down, as printed, for 'words'
  effective_on  date,
  appeal_state  text CHECK (appeal_state IN ('none', 'time_running', 'pending', 'decided')),
  reviewer      text NOT NULL,
  note          text,
  reviewed_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_invalidation_review_verified CHECK (
    decision <> 'lawyer_verified' OR (provision_id IS NOT NULL AND extent IS NOT NULL AND effective_on IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_invalidation_review_key ON judicial_invalidation_review (review_key, reviewed_at DESC);

CREATE OR REPLACE FUNCTION judicial_invalidation_review_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'judicial_invalidation_review is evidence: append a new review, never change or remove one';
END $$;
DROP TRIGGER IF EXISTS tr_invalidation_review_append_only ON judicial_invalidation_review;
CREATE TRIGGER tr_invalidation_review_append_only BEFORE UPDATE OR DELETE ON judicial_invalidation_review
  FOR EACH ROW EXECUTE FUNCTION judicial_invalidation_review_append_only();

-- the latest review of each key; verified, whole-unit ones serve
CREATE OR REPLACE VIEW v_judicial_invalidation_verified AS
SELECT DISTINCT ON (r.review_key) r.review_key, r.decision, r.provision_id, r.extent, r.extent_note, r.effective_on,
       r.appeal_state, r.reviewer, r.reviewed_at
  FROM judicial_invalidation_review r
 ORDER BY r.review_key, r.reviewed_at DESC, r.id DESC;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_provision_invalidation AS
SELECT p.instrument_id, p.id AS provision_id, p.path, min(v.effective_on) AS effective_on
  FROM v_judicial_invalidation_verified v
  JOIN provision p ON p.id = v.provision_id
 WHERE v.decision = 'lawyer_verified' AND v.extent = 'whole'
 GROUP BY 1, 2, 3;
CREATE UNIQUE INDEX IF NOT EXISTS mv_provision_invalidation_pk ON mv_provision_invalidation (provision_id);
CREATE INDEX IF NOT EXISTS mv_provision_invalidation_instrument ON mv_provision_invalidation (instrument_id);

COMMENT ON MATERIALIZED VIEW mv_provision_invalidation IS
  'Serving snapshot (D-161): units a lawyer-verified review says a court struck down or declared repugnant, whole, '
  'with the day it takes effect. operative_provision stops serving them from that day. Refreshed by '
  'tools/refresh_serving.py; audit A36.';

CREATE OR REPLACE VIEW operative_provision AS
WITH base AS (
SELECT p.id                                   AS provision_id,
       p.instrument_id,
       p.parent_id,
       p.path,
       p.kind::text                           AS provision_kind,
       p.label,
       p.heading,
       p.marginal_note,
       p.ordinal,
       p.first_page,
       CASE WHEN m.text_language IN ('ur', 'sd') THEN NULL ELSE v.text_en END                         AS text_en,
       CASE WHEN m.text_language IN ('ur', 'sd') THEN coalesce(v.text_ur, v.text_en) ELSE v.text_ur END AS text_ur,
       m.text_language,
       v.id                                   AS version_id,
       v.validity,
       v.operation::text                      AS operation,
       m.jurisdiction,
       m.instrument_kind,
       m.instrument_title,
       m.instrument_number,
       m.instrument_year,
       CASE WHEN m.law_repealed_on IS NOT NULL THEN 'repealed' ELSE m.status END AS instrument_status,
       m.enacted_on,
       m.commenced_on,
       m.law_repealed_on                      AS repealed_on,
       m.repealed_by_id,
       m.superseded_by_instrument_id,
       m.source_url,
       m.document_id,
       CASE WHEN m.commenced_on IS NOT NULL THEN 'established' ELSE 'not_tracked' END AS commencement_coverage,
       'not_tracked'::text                    AS invalidation_coverage,
       m.extent_basis                         AS extent_coverage,
       nzq_as_of()                            AS as_of,
       m.currency,
       m.currency_reason,
       m.territory_exits,
       kf.text_known_from,
       kf.basis                               AS text_known_from_basis,
       ((m.law_repealed_on IS NOT NULL AND m.law_repealed_on <= nzq_as_of())
        OR (m.currency IN ('not_current', 'historical') AND m.not_current_from IS NOT NULL
            AND m.not_current_from <= nzq_as_of()))                                   AS law_gone,
       m.historical_validity, m.territory_reach
  FROM mv_instrument_serving m
  JOIN provision p ON p.instrument_id = m.instrument_id AND p.is_active
  LEFT JOIN mv_provision_text_known_from kf ON kf.provision_id = p.id
  JOIN provision_version v ON v.provision_id = p.id
                          AND (v.validity @> nzq_as_of()
                               OR (upper_inf(v.validity) AND kf.text_known_from IS NOT NULL
                                   AND nzq_as_of() >= kf.text_known_from AND nzq_as_of() < lower(v.validity)))
 WHERE (m.historical_validity IS NULL OR m.historical_validity @> nzq_as_of())
   AND (m.enacted_on IS NULL OR m.enacted_on <= nzq_as_of())
   AND (m.instrument_year IS NULL OR m.instrument_year <= extract(year FROM nzq_as_of()))
   AND (m.commenced_on IS NULL OR m.commenced_on <= nzq_as_of())
   AND (nzq_territory() IS NULL OR nzq_territory() = ANY (m.territory_reach))
   AND NOT coalesce(nzq_territory() IS NOT NULL AND m.territory_exits ? nzq_territory()
                    AND (m.territory_exits ->> nzq_territory())::date <= nzq_as_of(), false)
   -- 0102: a repealed unit and everything under it, from the repeal, everywhere or in its territory
   AND NOT EXISTS (SELECT 1 FROM mv_provision_repeal r
                    WHERE r.instrument_id = p.instrument_id AND p.path <@ r.path
                      AND r.effective_from <= nzq_as_of()
                      AND (r.territory_key = '*' OR r.territory_key = nzq_territory()))
   -- 0146: a unit a lawyer-verified review says a court struck down or declared repugnant, whole, from that day
   AND NOT EXISTS (SELECT 1 FROM mv_provision_invalidation ji
                    WHERE ji.instrument_id = p.instrument_id AND p.path <@ ji.path
                      AND ji.effective_on <= nzq_as_of())
)
SELECT b.provision_id, b.instrument_id, b.parent_id, b.path, b.provision_kind, b.label, b.heading, b.marginal_note,
       b.ordinal, b.first_page, b.text_en, b.text_ur, b.text_language, b.version_id, b.validity, b.operation,
       b.jurisdiction, b.instrument_kind, b.instrument_title, b.instrument_number, b.instrument_year,
       b.instrument_status, b.enacted_on, b.commenced_on, b.repealed_on, b.repealed_by_id,
       b.superseded_by_instrument_id, b.source_url, b.document_id, b.commencement_coverage, b.invalidation_coverage,
       b.extent_coverage, b.as_of, b.currency, b.currency_reason, b.territory_exits, b.text_known_from,
       b.text_known_from_basis,
       b.law_gone AS survives_repeal
  FROM base b
 WHERE NOT b.law_gone
    -- 0103: a unit its law's repeal expressly excepts stays served
    OR EXISTS (SELECT 1 FROM mv_provision_survival s
                WHERE s.instrument_id = b.instrument_id
                  AND (b.path = s.path OR (s.subtree AND b.path <@ s.path)));

COMMIT;
