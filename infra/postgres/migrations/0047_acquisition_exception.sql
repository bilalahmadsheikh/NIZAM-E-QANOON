-- A catalogued item the portal no longer serves is a fact about the source,
-- not a pending task.  Forty remain after repeated dated attempts: the federal
-- portal names its files by content hash (administrator<md5>.pdf) and rotates
-- them, so the cached URL 404s even where the Act is still published; two
-- provincial items were catalogued with no English PDF at all.
--
-- acquisition_attempt already records WHAT happened on each fetch.  What it
-- cannot record is the DECISION that no further fetch is expected to succeed,
-- and why.  Without that, an unresolved count cannot distinguish work nobody
-- has done from work that has been done and cannot succeed -- and the honest
-- corpus figure (4,717 of 4,757 landed) reads as an open gap forever.
--
-- Nothing here forecloses recovery.  An exception names the observation, cites
-- the attempts that justify it, and is superseded rather than edited; if
-- catalogue re-discovery later yields a working URL, the ordinary recovery
-- worker lands the file and the exception is superseded by that fact.
--
-- Governing contract: docs/02-corpus-and-ingestion.html section 2.

BEGIN;

CREATE TABLE acquisition_exception (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_observation_id bigint NOT NULL REFERENCES source_observation(id)
                              ON DELETE RESTRICT,
    -- Why the item cannot be acquired, as distinct from how the fetch failed.
    reason                text NOT NULL CHECK (reason IN (
                              'url_rotated_by_portal',
                              'withdrawn_from_portal',
                              'no_english_pdf_published',
                              'no_pdf_url_catalogued',
                              'served_content_is_not_a_pdf')),
    -- The attempts that justify the decision, and what they returned.
    attempts_considered   integer NOT NULL CHECK (attempts_considered >= 1),
    first_attempt_at      timestamptz NOT NULL,
    last_attempt_at       timestamptz NOT NULL,
    observed_error        text NOT NULL CHECK (btrim(observed_error) <> ''),
    evidence              jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    asserted_by           text NOT NULL CHECK (btrim(asserted_by) <> ''),
    asserted_at           timestamptz NOT NULL DEFAULT now(),
    supersedes_id         bigint REFERENCES acquisition_exception(id)
                              ON DELETE RESTRICT,

    CHECK (last_attempt_at >= first_attempt_at),
    -- An exception must say who reviewed it and how, exactly as the OCR and
    -- contents-disposition assertions do.
    CHECK (evidence ? 'reviewer_type'),
    CHECK (evidence ? 'attempt_ids')
);

CREATE INDEX acquisition_exception_observation
    ON acquisition_exception(source_observation_id, asserted_at DESC, id DESC);

-- An exception is meaningless for an item that did land, and a landed recovery
-- must retire it rather than sit alongside it.
CREATE FUNCTION check_acquisition_exception() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    current_outcome text;
    recovered integer;
BEGIN
    SELECT o.outcome::text INTO current_outcome
      FROM source_observation o WHERE o.id = NEW.source_observation_id;
    IF current_outcome = 'landed' THEN
        RAISE EXCEPTION
            'observation % landed; an acquisition exception cannot apply to it',
            NEW.source_observation_id;
    END IF;

    SELECT count(*) INTO recovered
      FROM acquisition_attempt a
     WHERE a.source_observation_id = NEW.source_observation_id
       AND a.outcome = 'recovered';
    IF recovered > 0 THEN
        RAISE EXCEPTION
            'observation % already has a recovered attempt', NEW.source_observation_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER acquisition_exception_guard
    BEFORE INSERT ON acquisition_exception
    FOR EACH ROW EXECUTE FUNCTION check_acquisition_exception();

-- The current decision for each observation: latest wins, superseded rows stay.
CREATE VIEW v_acquisition_exception_latest AS
SELECT DISTINCT ON (e.source_observation_id) e.*
  FROM acquisition_exception e
 ORDER BY e.source_observation_id, e.asserted_at DESC, e.id DESC;

-- What is still open: catalogued, not landed, not recovered, not explained.
CREATE VIEW v_acquisition_unresolved AS
SELECT o.id AS source_observation_id, o.source_id, o.canonical_url,
       o.error_code, o.http_status,
       o.source_metadata ->> 'title' AS title,
       (SELECT count(*) FROM acquisition_attempt a
         WHERE a.source_observation_id = o.id) AS attempts
  FROM source_observation o
 WHERE o.outcome <> 'landed'
   AND NOT EXISTS (SELECT 1 FROM acquisition_attempt a
                    WHERE a.source_observation_id = o.id
                      AND a.outcome = 'recovered')
   AND NOT EXISTS (SELECT 1 FROM v_acquisition_exception_latest e
                    WHERE e.source_observation_id = o.id);

COMMIT;
