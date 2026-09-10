-- 0013  every recovery request is evidence
-- Document 02 sections 3.1 and 8: failed links and invalid responses are
-- first-class observations.  Recovery never edits the original observation;
-- it records the attempt and, on valid official PDF bytes, appends a new landed
-- observation.

BEGIN;

CREATE TABLE acquisition_attempt (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_observation_id bigint NOT NULL REFERENCES source_observation(id) ON DELETE RESTRICT,
    requested_url         text NOT NULL,
    final_url             text,
    http_status           integer,
    media_type            text,
    byte_length           bigint CHECK (byte_length IS NULL OR byte_length >= 0),
    response_sha256       char(64) CHECK (response_sha256 IS NULL OR response_sha256 ~ '^[0-9a-f]{64}$'),
    object_key            text,
    outcome               text NOT NULL CHECK
                          (outcome IN ('recovered','http_error','network_error','invalid_pdf')),
    error                 text,
    attempted_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX acquisition_attempt_observation
    ON acquisition_attempt (source_observation_id, attempted_at DESC);
CREATE INDEX acquisition_attempt_queue
    ON acquisition_attempt (outcome, attempted_at DESC) WHERE outcome <> 'recovered';

COMMENT ON TABLE acquisition_attempt IS
    'Append-only HTTP evidence for recovering failed official-source observations.';

COMMIT;
