-- The Nawab Shaheed Ghous Bakhsh Raisani Memorial Hospital Act, 2012 is held
-- twice. This records which copy a citation resolves to, and why.
--
-- THE TWO COPIES
--
--   document 33   observation 1358, balochistancode.gob.pk, 3 pages.
--                 A derivative rendering. Its own contents page promises 16
--                 sections; the file stops partway through section 5 and the
--                 Act simply is not in it. The parse reflects that: its 16
--                 "sections" are the CONTENTS LINES, each carrying its heading
--                 as its whole text and no law -- "Short title and
--                 commencement.", "Definitions.", "Establishment of Hospital."
--                 -- and section 16's text even runs on into the next page's
--                 running title. Five real sections exist beneath them.
--
--   document 4634 observation 9573, health.balochistan.gov.pk, 9 pages,
--                 SHA-256 d3242860e7fb2da362b7a89e99ac5741781fcede78250e8b05f
--                 581b883d30098. THE BALOCHISTAN GAZETTE, PUBLISHED BY
--                 AUTHORITY, No. 80, Quetta, Thursday 28 June 2012. It carries
--                 the Provincial Assembly Secretariat notification
--                 No.PAB/Legis: V (03)/2012 recording that Bill No. 3 of 2012
--                 was passed by the Assembly on 20 June 2012, assented to by
--                 the Governor on 26 June 2012, and published as ACT NO. III OF
--                 2012. It runs to section 19 ("Removal of Difficulties") and
--                 closes over the Secretary, Balochistan Provincial Assembly.
--                 19 sections, 88 provisions.
--
-- WHY THE GAZETTE IS CANONICAL
--
--   1. It is the primary instrument of record -- the official gazette
--      "published by authority", carrying the notification, bill number,
--      passage date and assent date. Document 33 is a code-website rendering
--      of it.
--   2. It is complete. Document 33 ends mid-Act; the gazette ends with the
--      Secretary's attestation.
--   3. It holds MORE of the Act than document 33's own contents promises:
--      sections 17, 18 and 19 appear in the gazette and in neither the
--      derivative's body nor its contents list.
--   4. Under INV-4 the provision is the citable unit. Document 33's sections
--      are headings with no provision text under them, so a citation to
--      "section 10 of the Raisani Hospital Act" resolving there returns a
--      title and no law.
--
--   Rendered for review at .review/raisani/doc33-p{1..3}.png and
--   .review/raisani/doc4634-p{1..9}.png.
--
-- WHAT THIS DOES AND DOES NOT DO
--
--   `duplicate_of` links a redundant active expression to the copy the release
--   views should represent. tools/resolve_exact_instrument_duplicates.py uses
--   it only for byte-identical, tree-identical expressions and correctly
--   refuses this pair. This is the other case the field has to carry: two
--   acquisitions of one work that differ in COMPLETENESS. The convention set
--   here, for the next one:
--
--     where two acquisitions of one work differ in completeness, the fuller
--     official source is canonical and the lesser is linked to it; neither
--     observation, blob, document nor provision is deleted.
--
--   Observation 1358, document 33, its blocks and its provisions all remain.
--   The instrument stays active and simply stops being a canonical expression,
--   so `v_release_instrument` -- which requires duplicate_of IS NULL --
--   represents this Act once, through the gazette.

BEGIN;

DO $$
DECLARE
    derivative uuid;
    gazette    uuid;
    gazette_sections integer;
BEGIN
    SELECT id INTO derivative FROM instrument
     WHERE document_id=33 AND is_active AND duplicate_of IS NULL;
    SELECT id INTO gazette FROM instrument
     WHERE document_id=4634 AND is_active AND duplicate_of IS NULL;
    IF derivative IS NULL OR gazette IS NULL THEN
        RAISE EXCEPTION 'expected one canonical expression for each of documents 33 and 4634';
    END IF;

    -- Refuse to demote the derivative to anything less complete than itself.
    SELECT count(*) INTO gazette_sections FROM provision
     WHERE instrument_id=gazette AND is_active AND kind='section';
    IF gazette_sections < 19 THEN
        RAISE EXCEPTION 'gazette expression holds % sections; expected the full 19',
                        gazette_sections;
    END IF;

    UPDATE instrument SET duplicate_of=gazette
     WHERE id=derivative AND is_active AND duplicate_of IS NULL;
END $$;

COMMIT;
