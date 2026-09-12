-- 0047 gave the exception vocabulary two values it cannot support from
-- evidence: 'url_rotated_by_portal' and 'withdrawn_from_portal'. A 404 proves
-- that the catalogued URL no longer resolves. Whether the portal rotated the
-- filename, withdrew the document, or reorganised its paths is a different
-- claim, and deciding it needs catalogue re-discovery that has not been run.
-- Recording the stronger reason would put a guess in the evidence table.
--
-- Replace both with what the attempts actually show, and add the one case they
-- distinguish: a server that answers but refuses the request.
--
-- Nothing is dropped: no row was written under the old vocabulary.

BEGIN;

ALTER TABLE acquisition_exception
    DROP CONSTRAINT acquisition_exception_reason_check;

ALTER TABLE acquisition_exception
    ADD CONSTRAINT acquisition_exception_reason_check CHECK (reason IN (
        -- The request completed and the document was not there.
        'catalogued_url_no_longer_resolves',
        -- The server answered and refused the request itself (4xx not 404).
        'portal_rejects_the_request',
        -- The server answered 200 with something that is not a PDF.
        'served_content_is_not_a_pdf',
        -- The catalogue entry exists but the portal publishes no English PDF.
        'no_english_pdf_published',
        -- No PDF URL was ever catalogued for the item.
        'no_pdf_url_catalogued'));

COMMENT ON COLUMN acquisition_exception.reason IS
    'What the dated attempts show, never an inference about the portal''s '
    'intent. A 404 says the catalogued URL no longer resolves; it does not say '
    'the document was withdrawn.';

COMMIT;
