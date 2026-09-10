-- 0001  source_observation -- Document 02 §3.1
--
-- The acquisition record: what an official portal exposed, when, and what bytes
-- came back. This is the first real table in the corpus database and the one the
-- landing tool already populates from the scrapers' manifests.
--
-- §3 is emphatic that this is not the same thing as legal identity: "The URL is
-- an observation key, not document identity: official portals change filenames
-- and links. Byte identity is the SHA-256 hash; legal identity is resolved later
-- from jurisdiction, instrument type, number and year." So there is no instrument
-- or provision reference here, and there must not be one until doc 03 §2 lands.
--
-- Failures are rows too, with a null sha256 and an outcome that is not 'landed'.
-- §3.1: "Record missing links and parse errors as first-class observations. A
-- disappearing official file triggers review; it does not delete the published
-- corpus."

BEGIN;

CREATE TYPE observation_outcome AS ENUM ('landed', 'failed', 'missing', 'skipped', 'unknown');

CREATE TABLE source_observation (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    source_id       text        NOT NULL,          -- pk-federal, pk-punjab, ...
    canonical_url   text,                          -- the PDF URL the portal served
    referring_url   text,                          -- the listing page it was found on
    discovered_at   timestamptz,
    fetched_at      timestamptz,

    http_status     integer,
    etag            text,
    last_modified   text,
    media_type      text,
    byte_length     bigint      CHECK (byte_length IS NULL OR byte_length >= 0),

    -- Byte identity. 64 lowercase hex characters, or null when nothing was
    -- retrieved. Constrained rather than trusted: a truncated hash silently
    -- breaks deduplication and blob lookup.
    sha256          char(64)    CHECK (sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'),

    object_key      text,                          -- raw/{source_id}/{sha256}
    scraper_version text,                          -- script name @ content hash
    source_metadata jsonb       NOT NULL DEFAULT '{}'::jsonb,

    outcome         observation_outcome NOT NULL,
    error_code      text,

    ingested_at     timestamptz NOT NULL DEFAULT now(),

    -- A landed observation must carry the bytes it claims to have landed.
    CONSTRAINT landed_has_bytes CHECK (
        outcome <> 'landed' OR (sha256 IS NOT NULL AND object_key IS NOT NULL)
    )
);

COMMENT ON TABLE  source_observation IS
    'Doc 02 §3.1. What a portal exposed at a point in time. Observation key, not legal identity.';
COMMENT ON COLUMN source_observation.sha256 IS
    'Byte identity. Deduplicates byte-identical files without losing separate official observations.';
COMMENT ON COLUMN source_observation.object_key IS
    'raw/{source_id}/{sha256} in the blob store. Never overwritten (§3.1).';

-- One row per (source, url, fetch). Re-running the landing tool must not create
-- duplicates, and NULLS NOT DISTINCT makes that hold for the manually-added
-- files that have no manifest row and therefore no URL.
CREATE UNIQUE INDEX source_observation_identity
    ON source_observation (source_id, canonical_url, fetched_at, sha256)
    NULLS NOT DISTINCT;

-- Blob lookup: "which observations produced these bytes?"
CREATE INDEX source_observation_sha256  ON source_observation (sha256)
    WHERE sha256 IS NOT NULL;

-- The review queue: everything that did not land.
CREATE INDEX source_observation_failed  ON source_observation (source_id, outcome)
    WHERE outcome <> 'landed';

CREATE INDEX source_observation_metadata ON source_observation USING gin (source_metadata);

COMMIT;
