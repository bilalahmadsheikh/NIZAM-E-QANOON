-- The attempt ledger could not record the most informative result there is.
--
-- `acquisition_attempt.outcome` was written for a queue of items that had NOT
-- landed: 'recovered' when the fetch produced a usable PDF, and
-- 'http_error' / 'network_error' / 'invalid_pdf' when it did not.
--
-- Refetching a LANDED but incomplete source (see 0054) produces a fourth
-- result that none of those describes. On 21 Sep 2026 the Balochistan Code's
-- copy of the Witness Protection Act, 2016 was requested again at its
-- catalogued URL. It answered HTTP 200 with a valid 23,599-byte PDF whose
-- SHA-256 is d19d65a9a1db4920532fd5bb9efa5dbee5d82e8551bfec3aa3bffc26333d1100
-- -- byte-for-byte the seven-page file already held, which stops inside
-- section 2 of twenty-nine.
--
-- Recording that as 'recovered' would be false twice over: nothing was
-- recovered, and the value is what the recovery worker's queue uses to decide
-- an item needs no further work. Recording it as 'invalid_pdf' would be false
-- too -- the PDF is valid, it is simply short. Leaving it unrecorded would
-- lose the single best piece of evidence an incompleteness declaration can
-- carry: that the portal was asked again, on a named date, and still serves
-- the partial copy.
--
-- So the vocabulary gains the value that says exactly that, and nothing else
-- changes. No existing row is touched; 'unchanged_copy' is not 'recovered', so
-- the recovery queue still considers such an item outstanding, which is
-- correct -- a complete copy has still not been obtained.

BEGIN;

ALTER TABLE acquisition_attempt
    DROP CONSTRAINT acquisition_attempt_outcome_check;

ALTER TABLE acquisition_attempt
    ADD CONSTRAINT acquisition_attempt_outcome_check CHECK (outcome IN (
        -- The fetch produced a usable PDF that the corpus did not hold.
        'recovered',
        -- The fetch produced, byte for byte, the copy already held.
        'unchanged_copy',
        -- The server answered, and not with the document.
        'http_error',
        -- The server could not be reached at all.
        'network_error',
        -- Bytes arrived and are not a readable PDF.
        'invalid_pdf'));

COMMENT ON COLUMN acquisition_attempt.outcome IS
    'What the fetch returned. ''unchanged_copy'' means the portal served the '
    'identical bytes already held -- evidence that a known-incomplete source '
    'cannot be improved by refetching it, never that the item is resolved.';

COMMIT;
